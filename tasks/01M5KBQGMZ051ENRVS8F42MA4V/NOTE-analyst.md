# Записка analyst

## Выяснено
- ТЗ полное (функции, константа, строки отчёта, тесты заданы) — пишу SPEC, без QUESTIONS.
- prune.py: `_log_candidates` (glob `*.log`), `_print_report(mode, logs, alert_rows, diag_files)`, `cmd_prune`. Признак живого pid — doctor/orphans.py:61.
- Бюджет ТЗ $15 ниже пола калибровки $25 (config.BUDGET_CALIBRATION_FLOOR_USD) — в SPEC 25.
- Инвариант 16 (docs/invariants.md:46) упоминает prune — возможный сигнал деления; секция «Оценка объёма» заполнена.

## Не сработало
- В шелле шага нет `cat`/`ls` — читать файлы инструментом Read.

## Где остановился
- SPEC написан (8 AC, status: ready), guard: ок. Шаг завершён.

## Чего не хватило
- Ничего существенного.
