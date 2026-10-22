# Записка spec_auditor — 01M5JPEHY8HY70R5T5AQ0EDSH1

## Выяснено
- Аудит №3 (SPEC sha 532e25ba…, после возврата с гейта №2). Правки решения №2 внесены: отрицательный сценарий AC-7 (X не зависит от A, в т.ч. X — зависимость A), мутация «без проверки зависимости держателя» в AC-9, держатель в in_dev — answer прямо.
- Факты сверены заново: _occupier zone_lock.py:487, _queue_members :504, _waiting_dependency :537, _holds_queue :547, _start_conflict :565, _reason :598, _ancestors :785, QueueWait :823, queue_wait :834, BLOCKING_STATES :110 (включает escalated); check_zone_waits hung_test_watchdog.py:271; DEPENDENCY_TEXT zone_queue_start.py:33, assertIn test_zone_lock.py:609.
- Существующие тесты с merge_after + zone_lock: test_zone_lock.py (цикл :487 — только queue_order, не claim), zone_queue_start AC-3/AC-4 — новое правило их не ломает.
- Вердикт pass. Непокрытые формы answer для держателя в review/escalated/acceptance — решение №2 («прочее не менять»), не поднимаю.

## Не сработало
- Bash с `;`, `$(...)`, `| xargs` требует подтверждения — только одиночные grep.

## Где остановился
- SPEC-AUDIT.md записан, verdict pass; guard прогнан.

## Чего не хватило
- Ничего существенного; QueueWait не несёт id держателя — doctor возьмёт его через blocking_conflict.
