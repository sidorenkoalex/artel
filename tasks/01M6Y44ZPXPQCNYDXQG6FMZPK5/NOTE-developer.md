# Записка developer

## Выяснено
- Код: forge.py (_gh_attempt_archive, _junit_xml вынесены; parse_junit_times, ci_suite_report, last_executed_commit через реестр IMPLEMENTATIONS), orchestrator/suite_cost.py, таблица suite_costs (schema.SUITE_COSTS_DDL в SCHEMA и migrate), store.insert_suite_cost/suite_costs/suite_cost_targets, doctor/suite_cost.py, команда suite-cost в artel.py.
- В фасаде doctor ядро импортировано как `suite_cost_core`: имя `doctor.suite_cost` занято подмодулем.
- В таблице НЕЛЬЗЯ хранить sha предыдущей сводки отдельной колонкой: тест ищет строку сводки по значению == sha.
- Долгоживущий файл задачи 55/55 зелёный.

## Где остановился
Шаг завершён: код, docs/triggers.md (строка 33), карта, свои юнит-тесты tests/test_suite_cost_units.py (мутации проверены), guard ок, PLAN ready. Соседние тесты зелёные (перечень — PLAN, шаг 6).

## Не сработало
- `python3 -m pytest … -n 4` на нескольких файлах — узлы xdist падают «Not properly terminated»; без `-n` всё идёт.
- Bash отклоняет heredoc с `{…}` и цепочки `cp && …` — мутации гонял временным файлом-сценарием, убрал `task-rm`.

## Чего не хватило
Конфликт имён в фасаде doctor (подмодуль `doctor/suite_cost.py` против ядра `orchestrator/suite_cost.py`) — нигде не описан, нашёлся чтением механики импорта пакета.
