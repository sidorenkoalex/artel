# Записка analyst — 01M57PM7NBFX34319TR0F9CB4F

## Выяснено
- Возврат с spec_gate (аудит, визит 2, пункты 1–6) закрыт в SPEC:
  - треб. 3: сигнатура `touch_heartbeat(conn, task_id=None, session_id=None)`; вызовы fsm_merge_gate.py:355 (`_wait_for_branch_ci_green` :324), :631 (`_await_main_ci` :613-631), :1474 (повтор после сдвига main) передают task_id и `session.resolve_session_id`; прежняя форма `touch_heartbeat(conn)` — как сейчас (AC-17).
  - AC-7: оба варианта — другая задача и та же задача с другим session_id.
  - треб. 13 + AC-16: нормализация проекта как store.task_target (store.py:701-707): пустой/NULL/нет строки → DEFAULT_TARGET, исключение внутри артели сохраняется.
  - треб. 11/AC-15: + tests/test_doctor.py, tests/test_merge_gate_ci_wait.py, tests/test_main_ci_line.py без изменений.
  - Матрица: строка doctor с условием неизменности test_doctor.py, новая строка нормализации.
- Решение О-3 (doctor/* в зонах) подтверждено Оператором как замена ANSWER-1 3-B.
- tests/test_main_ci_line.py:318 мокает touch_heartbeat, вызов `_await_main_ci` на :320-321.

## Не сработало
- `$?`/переменные в Bash отклоняются — звать guard без них.

## Где остановился
- SPEC.md обновлён (13 требований, AC-1…AC-17, status: ready, budget 45 — решение Оператора), guard ок.

## Чего не хватило
- Ничего существенного: все факты сверены git grep/sed по fsm_merge_gate.py, merge_lock.py, store.py.
