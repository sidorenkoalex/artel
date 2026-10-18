# Записка spec_auditor — 01M57PM7NBFX34319TR0F9CB4F (визит 3, spec_sha 5d980ac2)

## Выяснено
- Решения гейта №1 (О-1…О-5) и №2 (визит 2, пп. 1-6) в SPEC отражены; факты store.py:701-707/1235/1249, merge_lock.py:56-122, merge_queue.py:41-146, notes.py:281-294, leases.py:174-193, lease_alerts.py:36-49, fsm_merge_gate.py:355/613/631/1456-1474 подтверждены.
- Новое: машинный замок полных прогонов `suite_lock` (suite_lock.py:1-9) общий для мержей всех проектов — гейт мержа гоняет полный набор (fsm_merge_gate.py:977-982 → acceptance.py:1568-1581, ждёт до 1800 с, config.py:238). Сверка треб. 2 ТЗ его не называет, SPEC.md:28 «общий ресурс — только БД».
- Вызовы touch_heartbeat в fsm_merge_gate не покрыты AC; LEASE_STALE_AFTER_SEC=7200 > 3600 смягчает.
- AC-8 не задаёт точку наблюдения (wait_for_window), AC-10 без «любого порядка вставки».
- Тесты test_doctor T001/T002 — оба артель (test_doctor.py:1052-1057), test_holder_changed совместим.
- Вердикт: concerns.

## Не сработало
- `D=...; cmd` в шелле требует подтверждения — писать абсолютный путь прямо в команду.

## Где остановился
- SPEC-AUDIT.md записан (concerns, 4 отклонения: suite_lock, вызовы touch_heartbeat без AC, AC-8 без точки wait_for_window, AC-10 без порядка вставки), guard ок. Шаг завершён.

## Чего не хватило
- Список общих ресурсов мержа: suite_lock нашёл через fsm_merge_gate._full_suite_or_refuse → acceptance.run_full_suite.
