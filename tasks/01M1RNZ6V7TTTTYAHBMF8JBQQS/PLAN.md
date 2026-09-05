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

## Предложения системе

Нет.
