# Записка developer — 01M590GJAF0EDV4NBC4C99MFVH

## Выяснено
- Визит 1. Долгоживущий tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py; узел — `acceptance.full_suite(root, task, command=<профиль>, fresh=True)`, итог по тестам — `FullSuiteRun.tests`.
- Новые поля Profile — `compare=False` (tests/test_01m58fnwbv25ff26e7az9q9912_components.py сравнивает профили).
- test_integrity.py (вне зоны) передаёт two_sided профиль только при pytest-own (R1-F6).

## Итерация 2 (ревью R1-F1…F6)
- R1-F1: `acceptance_suite` — провал checks_local красит только зелёный итог, незелёный сохраняет исход, текст дописан в detail.
- R1-F2: `_report_argv` — pytest-аргументы `pytest-own` только если `is_pytest_command(head)` и не vitest; `acceptance.is_pytest_command` новый, `suite_run._is_pytest` делегирует ему.
- R1-F3: `_install` — flock `deps/<комп>/<сумма>.lock`, повторная проверка отметки под замком (`_install_mark`, `_install_locked`).
- R1-F5: `suite_run.parse(..., reported=)` — строки хода не читаются у профиля с отчётом.
- Дальше: тесты в tests/test_component_report_run.py (R1-F4 + F1/F2/F3/F5), эскалация F6 в PLAN.

## Итерация 3 (возврат с merge_gate: только тесты, код не менялся)
- В tests/test_component_report_gates.py: `ChecksLocalFromRecordTest` (checks_local из targets.yaml без подмены `_task_profile` — в `acceptance_suite` и в теле `_cmd_approve_merge_gate` без приложений), `EmptyInstallTest`.
- У компонента `install` — тип `command` (непустой, targets.py:88); `install: []` допустим только в `test_profile` (`list0`).
- Мутации: with_tools без checks_local / убран `_checks_local_refuse` из тела / `install is None` — все три красные.
- Итог итерации 3: планка 15/15, suite-run №4 зелёный (5995 прошло, 0 упало), карта регенерирована, PLAN п. 11 + шаг 9, status: ready — шаг сдан.

## Не сработало
- В шелле нет `ls`/`cat` в PATH — пользоваться python/Read.

## Где остановился
- Итерация 2: код F1/F2/F3/F5 правлен; сторожа — tests/test_component_report_gates.py (10 тестов, 8 мутаций — все красные); F6 — предложение задачи в PLAN «Предложения системе». Реестр REVIEW размечен fixed. Планка 15/15, затронутые тесты 175 зелёные, карта обновлена, guard ок. suite-run №3 (с приложениями PLAN) — зелёный: 5966 прошло, 0 упало. PLAN status: ready, шаг сдан.
- Paths компонентов в targets.yaml — регулярные выражения (`api/.*`), не глоб.

## Чего не хватило
- Не было короткой команды «guard каталога документов».
