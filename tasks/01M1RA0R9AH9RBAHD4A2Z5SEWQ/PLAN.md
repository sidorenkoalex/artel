---
task: 01M1RA0R9AH9RBAHD4A2Z5SEWQ
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: Перегенерированная карта после шага роли не ломает подтяжку main

## Подход

`orchestrator/fsm.py::_pull_main_or_escalate` — единственная точка,
обслуживающая все три места вызова подтяжки (`in_dev -> review`,
`acceptance -> merge_gate`, `merge_gate -> done`), поэтому правка идёт
только в ней (и в новой функции `checkpoint.py`, которую она зовёт), без
дублирования логики по точкам вызова.

Перед `git merge`, после того как worktree задачи получен
(`workspace.ensure`):

1. Отбрасываем незакоммиченную `docs/codebase-map.md`: `git checkout --
   docs/codebase-map.md`. Безусловно, до merge — карту всё равно
   перегенерирует и закоммитит сам успешный merge (при конфликте только
   по карте — уже существующий `_auto_resolve_map_conflict`, SPEC T067).
2. Коммитим чекпоинтом прочий незакоммиченный WIP worktree (кроме
   `tasks/<id>/`) — новая функция `checkpoint.commit_pull_checkpoint`,
   переиспользующая ту же обвязку `_commit_worktree_change`, что уже
   несут `commit_timeout_checkpoint`/`commit_abnormal_checkpoint`/
   `commit_pause_now_checkpoint` (SPEC 01M1NBWTSXEJB24PXR417YF1VA). В
   отличие от них — без параметра `role` и без ветки отката для прочих
   ролей: подтяжка main идёт над worktree кодовой ветки задачи, куда
   структурно попадает только код `developer` (SPEC требование 2), и
   `wt` уже разрешён вызывающим кодом для конкретного target'а —
   функции не нужно решать это самой.

Дальше — сам `git merge`. Если он отказывает, различаем ДВЕ причины по
тексту stderr, а не одной веткой, как раньше:

- Текст содержит `"would be overwritten by merge"` (новая константа
  `PULL_OVERWRITE_MARKER`) — это отказ ДО начала слияния из-за
  незакоммиченных файлов, которые очистка выше не устранила (git не
  ответил на одном из своих шагов). Это инцидент очистки, не спор
  версий содержимого (SPEC требование 4): эскалация без формулировки
  «конфликт подтяжки», с alert `kind=incident`. Merge в этой ветке не
  начинался — `git merge --abort` не зовём (нечего абортить).
- Любой другой текст (или `merge is None` — git не ответил на сам
  вызов) — прежняя ветка байт-в-байт: `_conflicting_files` +
  `_auto_resolve_map_conflict` для случая «только карта», иначе
  `git merge --abort` + эскалация с «конфликт подтяжки» (SPEC
  требование 5, AC-7, не ослабляется).

Различение по подстроке текста git — не по возврату кода очистки —
осознанный выбор: и AC-1/AC-4 (карта отброшена успешно), и AC-2/AC-3/
AC-5 (WIP закоммичен успешно) в норме вообще не доходят до этого текста
(`git merge` после чистой очистки просто не отказывает так). Текст
появляется только тогда, когда что-то в самой попытке очистки не
удалось, — ровно то условие, которое требование 4 просит отличать от
содержательного конфликта.

## Шаги

1. `orchestrator/checkpoint.py`: новая публичная функция
   `commit_pull_checkpoint(conn, task_id, wt)`, переиспользующая
   `_commit_worktree_change` с `exclude=f"tasks/{task_id}"`; журналит
   действие «WIP-чекпоинт перед подтяжкой main» и вызывает
   `store.record_fixation` при реальном коммите (та же обвязка, что и у
   существующих трёх чекпоинтов).
2. `orchestrator/fsm.py::_pull_main_or_escalate`: новая константа
   `PULL_OVERWRITE_MARKER`; перед `git merge` — `checkout --
   docs/codebase-map.md` + `checkpoint.commit_pull_checkpoint`; после
   отказа `merge` — классификация по `PULL_OVERWRITE_MARKER` (инцидент
   очистки: эскалация + `alerts.raise_alert(kind="incident")`, без
   «конфликт подтяжки») до существующей ветки конфликта содержимого,
   которая остаётся без изменений.
3. Регенерация `docs/codebase-map.md` (правка `orchestrator/*.py`,
   конвенция `conventions-core.md`).
4. Юнит-тесты `checkpoint.commit_pull_checkpoint` в
   `tests/test_timeout_checkpoint.py` (тот же файл и стиль, что у трёх
   соседних чекпоинтов — пустое дерево, грязное дерево с сообщением/
   sha/журналом, рефиксация, мандат `developer` исключает
   `tasks/<id>/`, отказ git на `add`).
5. AC-8 — правка существующих `tests/test_fsm_map_conflict_
   autoresolve.py` и `tests/test_branch_freshness_gate.py`: их лёгкие
   git-заглушки не знали о новых вызовах `checkout`/`reset`, которые
   требования 1-2 теперь делают перед КАЖДЫМ `git merge` этой функции —
   без правки заглушки либо падали бы `AssertionError` на незнакомом
   вызове, либо (в `test_branch_freshness_gate.py`) посчитали бы
   `checkout`/`reset` за сам `merge_calls`, ломая счётчик `len(...) ==
   1`. Само проверяемое поведение (авторазрешение карты, эскалация
   реального конфликта, число вызовов `merge`/`--abort`) не изменено ни
   одной правкой — только заглушки признают два новых безобидных
   no-op'а.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 1, 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |

## Влияние на систему

- Единственная точка правки (`_pull_main_or_escalate`) обслуживает все
  три вызова подтяжки — правка не дублируется и не может разойтись
  между ними.
- AC-7/требование 5 (настоящий конфликт содержимого продолжает
  эскалировать с «конфликт подтяжки») не тронуты: новая ветка
  классификации проверяется СТРОГО ДО существующей и никогда не входит
  в неё для этого сценария — `_conflicting_files`/`_auto_resolve_map_
  conflict`/`git merge --abort` остаются байт-в-байт.
- Alert `kind=incident` заводится новым путём (`alerts.raise_alert`
  напрямую из `fsm.py`, без промежуточного узла) — дедуп по
  (target=task_id, kind, source, message) уже несёт `alerts.raise_alert`
  сама (не дублируется здесь).
- `checkpoint.commit_pull_checkpoint` — новая публичная функция, не
  правка существующих трёх чекпоинтов: их сигнатуры/поведение (включая
  мандат по роли и откат WIP для не-`developer`) не затронуты.
- Регрессия существующего набора `tests/` — стандартный CI-гейт
  (`.github/workflows/ci.yml`, `unittest discover -s tests`), которого
  требует `merge_gate`; прогнаны локально модули, которые правка
  затрагивает напрямую (`test_timeout_checkpoint`,
  `test_fsm_map_conflict_autoresolve`, `test_branch_freshness_gate`) —
  все зелёные.

## Риски

- Классификация по подстроке текста git (`PULL_OVERWRITE_MARKER`)
  зависит от точной формулировки отказа git при грязном дереве; текст
  этого конкретного сообщения стабилен в git начиная с очень старых
  версий (использован буквально в SPEC «Контекст» и во всех трёх
  локальных приёмочных тестах AC-1/AC-2/AC-6, воспроизводящих реальный
  текст git) — риск невысокий, но не нулевой при экзотических локалях
  git (LC_ALL, нестандартная сборка).

## Эскалация (снята)

Эскалация выше (дефекты `_sandbox.py::advance_from_in_dev` — отсутствие
плашки SPEC/acceptance_tests на диске и устаревшее ожидание
`acceptance.run(tdir)` без `code_root=`) разрешена Оператором ANSWER-2
(вариант а): `amend-tests` добавил `write_acceptance_plank` в
`advance_from_in_dev` и поправил оба `assert_called_once_with` на
`code_root=self.wt_path` (лок планки — 4df2eedd). Диагностика
подтверждена независимым прогоном:

- `python3 -m unittest discover -s tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/
  acceptance_tests -p 'test_*.py'` — 7/7 OK (AC-1..AC-7;
  AC-8 — маркер skip, регрессия набора несёт штатный CI-гейт).
- `python3 -m unittest tests.test_timeout_checkpoint
  tests.test_fsm_map_conflict_autoresolve
  tests.test_branch_freshness_gate` — 47/47 OK (AC-8, повторно на
  текущей голове ветки).

Код требований 1-5 не менялся с коммита 77f3cfc1 — планка была красной
из-за фикстуры теста, не реализации; правка кода этим шагом не
понадобилась.
