# Записка analyst

## Выяснено
- ТЗ достаточно; SPEC.md написан (status: ready, 15 AC, budget_usd 45), guard — ок.
- Адреса ТЗ сверены: PASSED_ACTION — outcome_integrity.py:51, _checkouts — :303, _outcome_integrity_gate — :363; окно мержа fsm_merge_gate.py:1480–1487 (sync → acceptance_locks); _report_suite_result_key — acceptance.py:3170; in_outcome_bounds — advance_gates/acceptance.py:213; REFUSAL_CLASSES — refusal_classes.py:92.
- Сигналы деления: зона ≥5 файлов, AC ≥10. В SPEC — обоснование монолита; отмечено, что требование 6 (two_sided.py) технически отделимо — решение за Оператором.
- merge_after не ставлен: строки «Порядок: после …» в ТЗ нет, G3а-1б уже в main (d1a8e153).

## Не сработало
- Bash с `cd …;` и цепочками команд требует подтверждения — использовать абсолютные пути и одну команду.

## Где остановился
- Шаг завершён.

## Чего не хватило
- Ничего существенного.
