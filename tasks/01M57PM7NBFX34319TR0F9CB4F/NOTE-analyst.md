# Записка analyst — 01M57PM7NBFX34319TR0F9CB4F

## Выяснено
- Возврат с spec_gate (О-1…О-5) закрыт в SPEC: зоны + doctor/leases.py, doctor/lease_alerts.py (требование 10, AC-14); touch_heartbeat — своя строка по проекту/задаче/сессии, перехваченную не продлевает (требование 3, AC-7), вызовы fsm_merge_gate.py:355, :631, :1474; помощники merge_queue с одним conn — требование 8, AC-12; неизменность test_merge_lock/test_notes/test_01m563947r…/test_merge_queue — требование 11, AC-15.
- Добавлен раздел «## Матрица неослабления» (5 столбцов, формат mandate.matrix_section): строки store, notes, doctor (свойство остаётся), FIFO очереди (по проекту намеренно), touch_heartbeat.
- tests/test_doctor.py:1362-1477 MergeLockCheckTest — один проект (T001/T002); test_holder_changed ожидает ack при смене держателя того же проекта — сохраняется.
- tests/test_main_ci_line.py:318 мокает touch_heartbeat — смена сигнатуры ему не мешает.

## Не сработало
- `$?`/переменные в Bash отклоняются («simple_expansion») — звать guard без них.

## Где остановился
- SPEC.md переписан (12 требований, AC-1…AC-15, status: ready, budget 45 — решение Оператора; калибровка ориентирует на ~85, отмечено в «Оценке объёма»), guard ок.

## Чего не хватило
- Формы матрицы в SPEC — нашёл в orchestrator/advance_gates/mandate.py:288-471.
