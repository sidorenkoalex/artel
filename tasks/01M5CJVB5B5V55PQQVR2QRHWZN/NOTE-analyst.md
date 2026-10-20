# Записка analyst

## Выяснено
- ТЗ достаточно; SPEC написан (14 AC, budget 45, монолит обоснован — сигналы ≥10 AC и бюджет ≥$30).
- Место вставки гейта: `orchestrator/fsm_advance.py:804-806` (между `_test_integrity_gate_refuses` и `_review_rework_gate_refuses`) — сверено.
- `tests/test_refusal_classes.py` — дополняется новыми действиями; «Меняемое поведение» не нужно.

## Не сработало
- `cd … && cat` в Bash отклоняется правилом Read-deny — читать файлы инструментом Read.

## Где остановился
- SPEC.md готов (status: ready), guard: ок. Шаг завершён.

## Чего не хватило
- Ничего существенного.
