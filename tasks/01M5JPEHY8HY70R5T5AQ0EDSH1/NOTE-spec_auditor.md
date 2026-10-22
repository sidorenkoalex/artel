# Записка spec_auditor — 01M5JPEHY8HY70R5T5AQ0EDSH1

## Выяснено
- Аудит №2 (SPEC sha e0046a42…, после возврата с гейта №1). Правки п.1 (AC-6 живой цикл C + D позади; мутация _holds_queue в AC-9) и п.2 (вид answer по состоянию держателя) внесены корректно.
- Факты: _start_conflict zone_lock.py:565, _queue_members :504, _waiting_dependency :537, _holds_queue :547, _reason :598, _ancestors :785, QueueWait :823 (без id держателя), queue_wait :834; check_zone_waits hung_test_watchdog.py:271. answer «Зависимости мержа»: escalated/in_dev/review/merge_gate (answer.py:216, :400–427). zone-release <id> снимает ожидание самой <id> (zone_lock.py:696, :428) — «zone-release A» верно.
- Существующие тесты сравнивают текст зависимости через assertIn (test_zone_lock.py:609, zone_queue_start.py:276) — добавка «(состояние)» их не ломает.

## Не сработало
- Bash с `;`/`cd`/--include в zsh — ошибки; одиночные grep с -e работают.

## Где остановился
- SPEC-AUDIT.md записан, verdict concerns, guard «ок». Отклонения: (1) AC-7 без отрицательного сценария — ложная «взаимная блокировка» для любого ожидания занятой зоны не ловится; (2) вид answer без оговорки проверен только для merge_gate, сужение набора состояний не ловится.

## Чего не хватило
- Как doctor получит id держателя: QueueWait его не несёт — через blocking_conflict + _ancestors.
