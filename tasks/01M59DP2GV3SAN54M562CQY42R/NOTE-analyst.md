# Записка analyst — 01M59DP2GV3SAN54M562CQY42R

## Выяснено
- ТЗ достаточно, пишу SPEC без вопросов.
- orchestrator/config.py — общая зона (config.COMMON_ZONES, config.py:803), пороги туда класть можно без расширения зон.
- Тексты событий в коде: «аудит SPEC: возврат аналитику по fail» — advance_gates/spec_audit.py:36 (RETURN_ACTION); «возврат из spec_gate: » — brief.py:62 (SPEC_GATE_RETURN_PREFIX), пишется fsm.py:1617; «эскалация разрешена, продолжаем» — fsm.py:1487.
- report.OPERATOR_WINDOW_DAYS = 14 (report.py:59); raise_alert — alerts.py:93, дедуп по открытым одинаковым алертам.

## Не сработало
- ничего

## Где остановился
- SPEC написан (11 AC, budget 35 = рамка ТЗ), status: ready, guard: ок.
- Сработали сигналы объёма (AC ≥ 10, budget ≥ 30) — в SPEC дан материал на монолит, решение за Оператором на гейте.

## Чего не хватило
- ничего существенного.
