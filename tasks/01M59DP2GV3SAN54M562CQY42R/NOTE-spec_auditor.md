# Записка spec_auditor — 01M59DP2GV3SAN54M562CQY42R

## Выяснено
- `spend.known_cost_pairs` (orchestrator/spend.py:630-680) — НЕ по задаче: обходит все задачи, ключ (роль, модель), значения (расчёт по тарифу, факт); отбрасывает строки до даты тарифа и без модели каталога. Разбор одной строки — `spend.known_cost_breakdown` (spend.py:579), его же зовёт `report._known_cost_breakdown` (report.py:407).
- Тексты событий подтверждены: spec_audit.py:36 RETURN_ACTION, spec_audit.py:289 detail «аудит SPEC: вердикт fail…», fsm.py:1617 «возврат из spec_gate: », fsm.py:1487 «эскалация разрешена, продолжаем», store.py:852 `state -> <state>`.
- `raise_alert` дедуплицирует только среди открытых (alerts.py:93-108): после ack тот же текст заводится заново — признак в журнале нужен.
- tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py:524-580 — `store.db()` открывается в report один раз; если rounds.py откроет своё соединение, тест упадёт.
- auto останавливается на escalated (auto.py:1015 условие цикла) — проверка порога эскалаций должна стоять до выхода.

## Не сработало
- Нет.

## Где остановился
- SPEC-AUDIT.md записан, вердикт fail.

## Чего не хватило
- Пришлось читать spend.known_cost_pairs целиком: в ТЗ он назван разбором по задаче, а это сводка по паре (роль, модель).
