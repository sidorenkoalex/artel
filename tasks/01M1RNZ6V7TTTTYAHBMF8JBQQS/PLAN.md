---
task: 01M1RNZ6V7TTTTYAHBMF8JBQQS
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: регрессия №14 — приёмка гоняет планку на коде кодовой ветки, а не на коде пульта

## Подход

Источник истины приёмочной планки остаётся артефактной веткой (решение
регрессии №12, не пересматривается). Меняется только КУДА планка
материализуется и С КАКИМ `cwd` прогоняется:

- `orchestrator/acceptance.py::materialize_from_branch` вместо
  `tempfile.mkdtemp()` теперь принимает третий параметр `code_dir`
  (рабочий каталог кода задачи) и пишет `code_dir/tasks/<id>/
  acceptance_tests/` НА МЕСТЕ, тем же приёмом overlay/prune, что
  `artifact_branch.materialize_task_dir` уже применяет к `tasks/<id>/`
  целиком: файлы ветки перезаписываются, файл на диске, отсутствующего
  в ветке (устаревшая копия), удаляется. Возвращает `code_dir/tasks/
  <id>` — совместимо с тем, что уже ждёт `acceptance.run`/`acceptance.
  summary`.
- `orchestrator/acceptance.py::run` получил параметр `cwd` (по умолчанию
  `None` → `config.ROOT`, обратная совместимость для вызова вне зоны
  этой задачи — `orchestrator/amend.py`, не трогается). Хвост вывода
  теперь ВСЕГДА начинается строкой `планка: <каталог>, cwd: <cwd>`
  (AC-6) — она же естественно попадает в `detail` отказа, поскольку
  все вызывающие узлы уже кладут `tail` в текст отказа.
- Выбор `code_dir` — тот же узел, что и `runner.role_cwd`: self-target
  → worktree задачи (`workspace.ensure`/`workspace.path`), внешний
  target → `config.PROJECTS/<target>/workspace` (с `mkdir`). Не
  выделено отдельной функцией — используется на 3 точках вызова
  инлайн, идентично `role_cwd`, без побочных эффектов материализации
  ВСЕГО `tasks/<id>/` (та остаётся зоной `runner.role_cwd`, здесь не
  трогается).
- Три точки вызова (требования 3/5, единый узел без дублей):
  1. `orchestrator/fsm.py::_pull_main_or_escalate` — `code_dir` = уже
     вычисленный в функции `wt_path` (тот самый worktree, на котором
     только что прошёл merge). Убран `tempfile`/`shutil.rmtree` —
     материализация теперь на месте, чистить временный каталог не
     нужно.
  2. `orchestrator/fsm_advance.py::review` (ветка `status == "approved"`)
     — для self-target с заведённым worktree на своей ветке `cwd` =
     `workspace.path(task_id)` (было — всегда `config.ROOT`, тоже
     чинится: без этого cwd-резолвящая планка self-target'а осталась
     бы под тем же классом дефекта); для внешнего target `cwd` =
     `config.PROJECTS/<target>/workspace`. Убран `try/finally` с
     `shutil.rmtree`.
  3. `orchestrator/fsm_advance.py::verifying` — тот же выбор `code_dir`
     для передачи в `fsm_autogate._maybe_autogate_acceptance` (внешний
     target); `fsm_autogate.py` вне зоны этой задачи и не трогается.

## Шаги

1. `orchestrator/acceptance.py`: `materialize_from_branch(task_id, branch,
   code_dir)` — материализация на месте с overlay/prune; `run(tdir,
   cwd=None)` — `cwd` прогона, строка `планка: ..., cwd: ...` в начале
   `tail` на обоих исходах (зелёном и красном).
2. `orchestrator/fsm.py::_pull_main_or_escalate` — материализация в
   `wt_path`, прогон с `cwd=wt_path`, убран `tempfile`/`shutil.rmtree`.
3. `orchestrator/fsm_advance.py::review`/`verifying` — материализация в
   `code_dir`/`run_cwd` (worktree self-target либо workspace внешнего
   target), прогон с тем же `cwd`; убран `shutil.rmtree`.
4. Юнит-тесты: обновлены `tests/test_branch_freshness_gate.py` и
   `tests/test_fsm_map_conflict_autoresolve.py` — эти два файла
   (regression №12, НЕ залоченная приёмочная планка) явно утверждали
   старое (temp-каталог) поведение через `assertNotEqual`/
   `assertIn("artel-acceptance-", ...)`; перевёрнуты на `assertEqual`
   каталога и cwd рабочему каталогу кода задачи — иначе они стали бы
   ложно-красными на правильном поведении этой задачи.
5. Локальная приёмочная планка (`tasks/01M1RNZ6V7TTTTYAHBMF8JBQQS/
   acceptance_tests/`, залочена test_author) прогнана целиком —
   зелёная (11/11, включая намеренно-красные AC-6/AC-7, которые
   красные по замыслу теста, не по сбою).
6. Закрытие REVIEW.md итерации 1 (R1-F1, R1-F2):
   - `orchestrator/acceptance.py::materialize_from_branch` — убран `or
     []` на `gitcmd.ls_tree_files(...)`: `None` (git не ответил) и `[]`
     (в ветке легитимно пусто) больше не смешиваются. При `None`
     функция возвращает `tdir`, НЕ трогая диск (тем же приёмом, что
     `artifact_branch.materialize_task_dir`), — прунинг ниже больше не
     стирает уже материализованную планку транзиентным сбоем git на
     повторном вызове.
   - `tests/test_branch_freshness_gate.py::
     test_advance_pulls_main_and_advances_when_acceptance_green` и
     `tests/test_fsm_map_conflict_autoresolve.py::
     test_map_only_conflict_autoresolves_without_escalation` — дописан
     абзац «Ловит мутацию» под добавленные в этой задаче assert'ы по
     `plank_root`/`cwd` (первый файл нёс докстринг про другую мутацию,
     второй не нёс докстринга вовсе).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (материализация в рабочий каталог кода, не tempdir) | 1, 2, 3 |
| 2 (cwd прогона = рабочий каталог кода, не config.ROOT) | 1, 2, 3 |
| 3 (общий вход материализации/прогона для in_dev/merge_gate/review/verifying, без дублей) | 1, 2, 3 |
| 4 (отказ называет каталог и cwd одной строкой) | 1 |

## Влияние на систему

Источник истины `tasks/<id>/acceptance_tests/` НЕ меняется (артефактная
ветка, регрессия №12) — только каталог записи и `cwd` прогона, как и
просит SPEC «Не входит». `acceptance.run`'s сигнатура расширена
обратно-совместимо (`cwd: Path | None = None`) — единственный вызывающий
код вне зоны этой задачи (`orchestrator/amend.py:254`) продолжает
работать без изменений и без затрагивания той же регрессии там (не
предмет этой задачи, зона `amend.py` не объявлена).

Существующие тесты регрессии №12 (`tests/test_artifact_materialization.py`,
`tests/test_fsm_autogate.py`, AC-9) не трогались и остаются зелёными
(прогнаны явно, 8/8). Два ДРУГИХ юнит-теста той же регрессии
(`tests/test_branch_freshness_gate.py`, `tests/test_fsm_map_conflict_
autoresolve.py`) утверждали именно ту деталь реализации (temp-каталог),
которую эта задача чинит — обновлены на новое ожидаемое поведение
(не ослаблены: те же проверки «откуда планка», только с правильным
значением). Полный прогон затронутых модулей — зелёный: `test_acceptance`,
`test_amend`, `test_dry_run`, `test_canary`, `test_branch_freshness_gate`,
`test_fsm_map_conflict_autoresolve`, `test_fsm_autogate`,
`test_artifact_materialization`, `test_fsm_draft_mr_reentry`,
`test_merge_gate_ci_wait`, `test_verifying_ceiling`, `test_zones_gate`,
`test_advance_guard`, `test_review_registry_gate`, `test_capacity_gate`,
`test_multitarget`, `test_multitarget_invariants` — суммарно 245+ тестов,
без падений. `docs/codebase-map.md` перегенерирована тем же коммитом
(изменился только `built_at_sha` — публичные функции/импорты модулей не
переименованы).

Откат — точечный revert трёх файлов (`acceptance.py`, `fsm.py`,
`fsm_advance.py`) плюс двух тестов; лока приёмочной планки задачи это
не касается.

Реестр REVIEW.md итерации 1: R1-F1 (major) и R1-F2 (minor) закрыты
шагом 6 — прогон `test_branch_freshness_gate`,
`test_fsm_map_conflict_autoresolve`, `test_acceptance`,
`test_fsm_autogate`, `test_artifact_materialization` (32/32) и прямой
репро сценария R1-F1 (два вызова `materialize_from_branch`: первый
кладёт реальный файл, второй с `ls_tree_files -> None` больше НЕ стирает
его) подтверждают фикс.

## Риски

`orchestrator/fsm_advance.py::review` для self-target ветки
`workspace.on_task_branch(...) is True` раньше прогоняла `cwd=config.ROOT`
безусловно (тот же класс дефекта, что и регрессия №14, просто не
описанный в её "Контексте" — там названы только `_pull_main_or_escalate`
и внешний target); эта задача заодно чинит и эту точку (`cwd=workspace.
path(task_id)`), раз меняет сигнатуру `run()` и уже здесь стоит. Не
покрыто отдельным AC приёмочной планки этой задачи (SPEC называет только
self-target через `_pull_main_or_escalate` и внешний target через
review/verifying) — риск минимален: смена `cwd` только для планок,
резолвящих `orchestrator/` через неявную вставку `cwd` (не через
`__file__`), а материализация в ЭТОМ пути и до правки, и после неё
кладёт планку по штатной вложенности `tasks/<id>/acceptance_tests/`
worktree, так что `__file__`-путь резолвинга не менялся никогда.

## Подтяжка main (ANSWER-2, hotfix 88b38022)

Пока задача была в разработке, в main вошёл аварийный hotfix
(88b38022, ADR-0013), частично закрывающий ту же регрессию:
`acceptance.run(tdir, code_root=None)` — тот же смысл, что `cwd` этой
задачи, но под именем `code_root`; `fsm._pull_main_or_escalate`
передавал `workspace.path(task_id)` для self-target, без
материализации на месте (планка читалась из временного каталога
регрессии №12, только `cwd` был правильный).

Влита `origin/main` (merge-коммит поверх R1-F1/R1-F2), два конфликта
(`orchestrator/acceptance.py`, `orchestrator/fsm.py`) разрешены в
пользу реализации этой ветки (материализация НА МЕСТЕ в рабочий
каталог кода, без `tempfile`/`shutil.rmtree`) с переименованием
публичного параметра `acceptance.run` с `cwd` на `code_root` — имя
из hotfix, зафиксированное ANSWER-2 как контракт. Переименование
докатано по всем вызывающим узлам одним отдельным коммитом:
`fsm_advance.py::review` (`cwd=run_cwd` → `code_root=run_cwd`) и два
теста (`test_branch_freshness_gate.py`,
`test_fsm_map_conflict_autoresolve.py`: `kwargs.get("cwd")` →
`kwargs.get("code_root")`). `fsm.py::_pull_main_or_escalate` уже
использовал материализацию на месте (шаг 2 этого PLAN) — при
разрешении конфликта её ветка HEAD взята целиком, только имя
параметра приведено к `code_root`.

Прогон после подтяжки: `test_branch_freshness_gate`,
`test_fsm_map_conflict_autoresolve`, `test_acceptance`,
`test_fsm_autogate`, `test_artifact_materialization`, `test_amend`,
`test_dry_run`, `test_multitarget`, `test_multitarget_invariants` —
122/122; `test_zones_gate`, `test_capacity_gate`, `test_advance_guard`,
`test_review_registry_gate`, `test_merge_gate_ci_wait`,
`test_verifying_ceiling`, `test_fsm_draft_mr_reentry`, `test_canary` —
101/101. Локальная приёмочная планка задачи — 11/11 (AC-1..AC-9,
включая намеренно-красные AC-6/AC-7). `docs/codebase-map.md`
перегенерирована мерж-коммитом (только `built_at_sha`). R1-F1
(различение `None`/`[]` у `ls_tree_files`) осталось в силе после
слияния — HEAD-версия `materialize_from_branch` взята без изменений.

## Предложения системе

Нет.
