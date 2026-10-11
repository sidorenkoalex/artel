---
task: T041
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 2
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Протокол рестарта после таймаута шага: WIP-чекпоинт оркестратора

## Фаза A — план

Итерация 1 отметила один пробел плана: PLAN нигде не рассматривал
внешние target'ы, хотя `commit_timeout_checkpoint` физически обходит
диспетчер `fixation.fix(task_id, target)`. В этой итерации PLAN
дополнен: шаг 1 явно описывает проверку `store.task_target(conn,
task_id) == config.DEFAULT_TARGET` как первое действие функции, таблица
«Покрытие требований» у требования 1 помечена «(только догфуд — см.
«Риски»)», и в «Риски» добавлен блок «Только догфуд» с полным разбором
(почему коммит workspace'а тоже не решил бы AC-1/AC-2 для внешнего
target, ссылка на `fsm._dirty_refuses`/ADR-0003 3д). Пробел закрыт;
остальная оценка Фазы A из итерации 1 (покрытие 7 требований, шаги —
проверяемые единицы, подход не конфликтует с архитектурой) не менялась
и подтверждена повторно на этом diff.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `commit_timeout_checkpoint` (orchestrator/runner.py:396-397) теперь первым действием сверяет `store.task_target(conn, task_id) != config.DEFAULT_TARGET` и делает no-op для внешнего target — ограничение задокументировано в PLAN «Риски» и докстринге функции, не расширяет требование молча. Для догфуда (единственный существующий target, ADR-0003 3д) коммит по-прежнему работает как в итерации 1. |
| 2 | OK | Без изменений с итерации 1: сообщение коммита дословно `f"{task_id}: WIP-чекпоинт после таймаута шага {role}"` (runner.py:404), подтверждено `test_ac1_...`. |
| 3 | OK | Без изменений: `store.journal(conn, task_id, "orchestrator", "WIP-чекпоинт после таймаута шага", detail)` (runner.py:412-413), подтверждено `test_ac1_...`. |
| 4 | OK | Без изменений: вызов только внутри `if timed_out:` (runner.py:567), ветка `if rc != 0:` (runner.py:574) не тронута; `test_ac3_...` проверяет explicit. |
| 5 | OK | `fixation.check_integrity`/`fix`/`read` по-прежнему не изменены во всей ветке (`git diff main...HEAD` не затрагивает `orchestrator/fixation.py`). |
| 6 | OK | Без изменений: ветка `timed_out` в `run_agent_once` по-прежнему возвращает `"timeout"` без ретрая. |
| 7 | OK | Без изменений: все операции — `gitcmd.git("add"/"diff"/"commit")`, `gitcmd.head_sha()`; прямого `subprocess`/`git` в обход модуля нет. |

## Замечания

Пусто — все три пункта вердикта итерации 1 проверены и закрыты
(детали — ниже, для трассируемости).

- Проверка (была: blocker) — `docs/codebase-map.md` перегенерирован
  локально командой `python3 scripts/codebase_map.py` на HEAD `f5928dd`
  и сравнен с закоммитированной версией построчно без учёта строки
  `built_at_sha`: разницы нет — секция `## tests/test_timeout_
  checkpoint.py` и записи «Импортируется» у `orchestrator/fixation.py`,
  `orchestrator/gitcmd.py`, `orchestrator/runner.py`, `orchestrator/
  store.py` присутствуют и совпадают с фактическим деревом. `built_at_
  sha` в закоммитированной карте (`5ad1fc1f...`) — sha родителя коммита
  `f5928dd` (тот, что был HEAD в момент запуска скрипта до коммита) —
  то же соглашение, что и в предыдущих коммитах этой ветки; CI-джоб
  `codebase-map` (`.github/workflows/ci.yml:54-81`) диффит без этой
  строки, так что расхождение не покрасит CI. Локальная регенерация,
  сделанная для проверки, отменена (`git checkout -- docs/codebase-
  map.md`) — REVIEW.md правит только этот файл.
- Проверка (была: major) — `orchestrator/runner.py:396-397` теперь
  содержит `if store.task_target(conn, task_id) != config.DEFAULT_
  TARGET: return ""` до первого `gitcmd.git("add", ...)`; юнит-тест
  `test_non_dogfood_target_skips_checkpoint` (tests/test_timeout_
  checkpoint.py) явно проверяет через `mock.patch.object(gitcmd,
  "git")` + `git_mock.assert_not_called()`, что для `target =
  "another-target"` git вообще не вызывается, коммит не создаётся,
  журнал не пишется. Ограничение «только догфуд» зафиксировано в PLAN
  «Риски» (не только в коде) — расхождение SPEC/PLAN закрыто.
- Проверка (была: minor) — `tests/test_timeout_checkpoint.py` получил
  `test_git_diff_failure_commits_nothing_and_journals_nothing` и
  `test_git_commit_failure_commits_nothing_and_journals_nothing`
  (через общий параметризованный хелпер `_run_with_failing_step`),
  закрывающие класс «отказ git на любом из трёх шагов» целиком, не
  только `git add`, как было в итерации 1.

## Верификация (эта итерация)

- `python3 -m unittest discover -s tests -p "test_*.py"` — 625 тестов,
  3 падения (`test_multitarget.RoleEnvTest::test_env_carries_the_git_
  identity`, `::test_identity_already_in_the_environment_is_not_
  overridden`, `::test_absent_identity_is_journalled_before_the_step`).
  Не относятся к T041 (нет упоминаний `commit_timeout_checkpoint`/
  `record_fixation`/`timeout` в этих тестах): проверено воспроизведением
  той же тестовой группы на `main` в отдельном `git worktree` — падают
  идентично (локальный git-конфиг машины подставляет реальные `user.
  name`/`user.email` вместо ожидаемых тестом значений-проб). Пред-
  существующий дефект окружения, не регрессия этой ветки.
- `python3 -m unittest tests.test_timeout_checkpoint -v` — 7/7 OK.
- `python3 -m unittest discover -s tasks/T041/acceptance_tests -p
  "test_*.py" -v` — 4/4 OK (AC-1..AC-4).
- `git diff --stat main...task/t041-protokol-restarta-posle-taymau` —
  изменённые файлы совпадают с PLAN «Шаги» (runner.py, store.py,
  review.py-комментарии, codebase-map.md, invariants.md, тесты,
  артефакты задачи); ничего вне зоны задачи (`gates.yaml`, `roles.yaml`,
  `.github/`, `templates/`, `skills/` не затронуты).

## Вердикт

`approved`. Оба замечания предыдущей итерации (blocker: устаревшая
карта; major: чекпоинт не таргет-осведомлён) закрыты и подтверждены
прогоном тестов и построчным сравнением карты; minor по тестам отказа
git тоже закрыт, хотя и был необязательным.

## Проверено исполнением
Ретроактивная пометка при миграции корпуса под evidence-контракт (T072, 2026-08-30): это ревью прошло до появления обязательной секции «Проверено исполнением» (SPEC T072, guard.py:review_evidence_errors). Факт исполнения проверок этим ревью, если они проводились, восстановить задним числом нельзя — что реально оценивалось, отражено выше, в разделах «Соответствие SPEC»/«Замечания» этого файла. Секция добавлена постфактум одним коммитом по всему корпусу только для соответствия новому структурному правилу guard.py, содержательно не переписывает исходное ревью.
