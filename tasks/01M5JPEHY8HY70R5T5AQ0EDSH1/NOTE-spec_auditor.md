# Записка spec_auditor — 01M5JPEHY8HY70R5T5AQ0EDSH1

## Выяснено
- Факты SPEC о zone_lock.py сверены: _occupier :487, _queue_members :504, _waiting_dependency :537 (сигнатура (t, members) — новой понадобится conn), _holds_queue :547, _start_conflict :565 (dep_row берётся из members :585), _reason :598 (для «зависимость» состояние не печатает), _ancestors :785, queue_wait :834, BLOCKING_STATES :110. Состояния `new` нет — задача заводится в spec_writing (catalog.py:712); zones/merge_after колонки заполнены уже с new (catalog.py:399).
- QueueWait (zone_lock.py:823) не несёт id держателя — doctor для взаимной блокировки должен звать blocking_conflict + _ancestors (zone_lock менять нельзя по ограничению зон).
- answer принимает «Зависимости мержа» только в escalated/in_dev/review/merge_gate (answer.py:400-440), не в verifying/acceptance.
- Существующие тесты: assertIn подстроки (test_zone_lock.py:609; zone_queue_start.py:122) — «(состояние)» их не ломает; тройка blocking_conflict (test_zone_lock.py:600-608) не меняется.

## Не сработало
- grep с `cd`/`;`/`|` в Bash требует подтверждения — только одиночные команды с абсолютными путями.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан, guard «ок». Главное: AC-6 не ловит мутацию «_holds_queue по старому правилу» (нет живого цикла C и старта D позади); выход answer для держателя в verifying/acceptance не работает.

## Чего не хватило
- Как doctor получит id держателя без правки zone_lock — QueueWait его не несёт (zone_lock.py:823).
