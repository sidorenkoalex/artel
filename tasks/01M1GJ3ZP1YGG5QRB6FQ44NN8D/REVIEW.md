---
task: 01M1GJ3ZP1YGG5QRB6FQ44NN8D
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 3
---

# REVIEW: Сухой прогон приёмки — предпросмотр без исполнения

## Фаза A: проверка плана

Таблица «Покрытие требований» в PLAN.md полна (все 6 требований → шаг
1), шаги — проверяемые единицы (шаг 1: модуль + регистрация; шаг 2:
тесты; шаг 3: регенерация карты), подход не конфликтует с конвенциями:
переиспользует установленный приём `orchestrator/fsm.py::
_tests_writing_ac_state` (git-чтение ветки + `guard.scan_ac_content`),
не трогает `scripts/guard.py`, `orchestrator/fsm_advance.py`,
`orchestrator/fsm_autogate.py`, `orchestrator/catalog.py` — как и
требует SPEC «Не входит». План принят без изменений.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) | OK | `orchestrator/dry_run.py::cmd_acceptance_dry_run` зарегистрирована в `orchestrator/artel.py:331` как `"acceptance-dry-run"`, принимает id, печатает файлы/методы/маркеры/трассируемость — проверено прогоном `acceptance_tests/test_ac1_*.py`. |
| 2 (AC-4) | OK | Разбор — только `guard.TEST_METHOD`/`guard.AC_ITEM`/`guard.section_body`/`guard.scan_ac_content`, никакой собственной регулярки на AC-разметку; `test_ac4_reuses_guard_scan.py` (патч `scan_acceptance_tests`/`scan_ac_content` сентинелом) зелёный — подтверждает делегирование, не имитацию. |
| 3 (AC-5) | OK | В `dry_run.py` нет `store.journal`/`store.set_state`/`lease.*`/`subprocess`-вызовов unittest; только `store.db()`/`resolve_task_id`/`get_task` (SELECT) и чтения git. `test_ac5_read_only_no_side_effects.py` (перехват `subprocess.run`, снимки БД до/после) зелёный. |
| 4 (AC-6) | OK | `DRY_RUN_MARKER` — дословная константа, напечатана в начале и в конце вывода; ничего не пишется на диск/БД/журнал (`test_ac6_*` зелёные, включая проверку отсутствия `tasks/<id>/` на диске рабочей копии до/после). |
| 5 (AC-7) | OK | Всё чтение — `gitcmd.branch_exists`/`ls_tree_files`/`show`, диск рабочей копии не читается вовсе (нет `Path.glob`/`os.walk` по `tasks/`). `test_ac7_branch_correct_reading.py` (конфликтующее содержимое на диске под чужим чекаутом) зелёный. |
| 6 (AC-8) | OK | Два разных именованных отказа: `gitcmd.branch_exists` = False → называет ветку; ветка есть, но нет `test_*.py` под `acceptance_tests/` → называет каталог. `test_ac8_*` (включая проверку, что оба сообщения различны) зелёные. |

## Замечания

(нет — 0 blocker/major/minor)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний в этой итерации не заведено — реестр пуст.

## Вердикт
approved — все требования SPEC (1–6, AC-1..AC-9) реализованы и
проверены исполнением; зона задачи соблюдена (`orchestrator/dry_run.py`
+ одна строка регистрации в `orchestrator/artel.py` + регенерация
`docs/codebase-map.md` + артефакты/тесты задачи — `scripts/guard.py`,
`orchestrator/catalog.py`, `orchestrator/fsm_advance.py`,
`orchestrator/fsm_autogate.py` не тронуты); ни один существующий тест,
гейт или инвариант не ослаблен; полный набор тестов зелёный.

## Проверено исполнением
- `python3 -m unittest tests.test_dry_run -v` — 9 тестов, все зелёные
  (unit-тесты `_is_test_file`, отказов по отсутствующей ветке/каталогу,
  read-only, happy path).
- `cd tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/acceptance_tests && python3 -m
  unittest test_ac1_lists_test_files_and_methods
  test_ac2_prints_ac_markers_with_reasons test_ac3_traceability_summary
  test_ac4_reuses_guard_scan test_ac5_read_only_no_side_effects
  test_ac6_dry_run_marker_and_no_persistence
  test_ac7_branch_correct_reading
  test_ac8_named_refusal_missing_branch_or_dir -v` — 12 тестов, все
  зелёные (AC-1..AC-8, реальный git-стенд `RealGitSandbox`). AC-9
  размечен `# AC-9: skip` с обоснованием «регрессия всего `tests/` уже
  исполняется штатным CI-гейтом на каждом коммите» — легальный частый
  случай (ci-covered), не дорогая пометка по существу.
- `python3 -m unittest discover -s tests -p "test_*.py"` — Ran 1233
  tests, OK (AC-9: полный набор зелёный).
- `python3 scripts/codebase_map.py --check` — без вывода/ошибки, карта
  свежая (регенерация шага 3 PLAN подтверждена).
- `python3 -m scripts.guard tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md
  tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/PLAN.md` — «GUARD: ок (2 файлов)».
- Чтение `orchestrator/dry_run.py`, `orchestrator/gitcmd.py`
  (`branch_exists`/`ls_tree_files`/`show`), `scripts/guard.py`
  (`scan_ac_content`/`TEST_METHOD`/`AC_ITEM`/`section_body`),
  `orchestrator/store.py` (`resolve_task_id`/`get_task`/`db` —
  сигнатуры и read-only характер подтверждены чтением исходников) и
  `git diff --stat main...HEAD` (список изменённых файлов ограничен
  зоной задачи) — вручную сверено с заявками PLAN «Подход»/«Влияние на
  систему».

## Предложения системе
(пусто)
