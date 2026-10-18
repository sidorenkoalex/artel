# Записка developer — 01M57PM7NBFX34319TR0F9CB4F

## Выяснено
- Код ветки до шага не содержал правок разработчика (только два долгоживущих файла test_author).
- Реализация: store — `merge_lock_rows` (rowid + нормализованный `target` через LEFT JOIN tasks),
  `project_merge_lock_row`, `touch_merge_lock_heartbeat(rowids, ts)`, `project_merge_queue_rows`;
  `set_merge_lock` сносит только строку проекта задачи. merge_lock.acquire/touch_heartbeat — по проекту;
  merge_queue помощники с необязательным `target`; notes и doctor — по всем строкам.
- fsm_merge_gate: :355/:631 → `touch_heartbeat(conn, task_id, session.resolve_session_id())`, :1474 → `sid`.
- Долгоживущие тесты задачи, test_merge_lock/queue/notes/doctor/ci_wait/main_ci_line, планка — зелёные.

## Не сработало
- `pytest -n 8` в шаге роли падает (node down) — гонять без xdist.

## Где остановился
- Шаг завершён: свои тесты `tests/test_merge_lock_by_project.py` (ANSWER-2 пп. 2-4, проверены мутациями),
  карта регенерирована, suite-run №1 зелёный (5848 прошло, 0 упало), planka 2 passed, PLAN.md status: ready.

## Чего не хватило
- Причина возврата «sha разошёлся» не объясняет, какой артефакт; ответ — ANSWER-2.
