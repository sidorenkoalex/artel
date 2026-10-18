# Записка spec_auditor — 01M57PM7NBFX34319TR0F9CB4F

## Выяснено
- Факты SPEC о коде подтверждены: store.py:1235/1249/1264, merge_lock.py:56/95/125, merge_queue.py:41/71/97, notes.py:281, schema.py:148-155, fsm_merge_gate.py:355/631/1456-1458, fsm.py:1385 (merge_after до мьютекса). Ещё один вызов touch_heartbeat — fsm_merge_gate.py:1474 (в «Материалах» не назван).
- tests/test_merge_queue.py:77,83,89,95,101,149,160,210 зовут `_head_task_id`/`_current_holder_id`/`_current_holder_label` с одним `conn`; смена аргумента внутри утверждения — находка гейта неослабления (scripts/guard.py:1664), «Меняемое поведение» её не оформит.
- doctor: lease_alerts.py:36-49 + leases.py:174,192 — при двух строках авто-ack закрывает incident мёртвого держателя одного проекта, пока merge_lock_row отдаёт строку другого.
- Вердикт: concerns (5 отклонений, решаемы на гейте).

## Не сработало
- `cat`/`sed` в шелле нет — читать через Read.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Быстрого ответа, считает ли гейт неослабления смену аргумента вызова внутри assert находкой — искал в scripts/guard.py (changed_test_assertions, :1658).
