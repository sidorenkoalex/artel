# Записка test_author

## Выяснено
- Планка — один разовый файл `acceptance_tests/test_synthetic_answer_marks_batch.py` (AC-1…AC-4, функции pytest, фикстура `light_transition`). Разовый, потому что шов SPEC — закрытые имена (`canary._pass_escalated_with_synthetic_answer`), а долгоживущему файлу они запрещены; прецедент — `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`.
- Синтетический ANSWER пишет подменённый `canary.answer.cmd_answer` (путь (1) Решения 2): кладёт `ANSWER-<max+1>.md` в `sb.tdir`.
- Стаб (вызов `fsm._mark_questions_answered(conn, task_id)` при `t["escalated_from"] == "spec_writing" and t["answer_baseline"] is not None` между `get_task` и `update_task`) — 7/7 зелёных. Мутанты «по истинности», «безусловно», «только escalated_from», «только baseline», «после set_state» красят свои тесты. Стаб откачен, дерево чистое.
- Красная фаза: 4 красных (AC-1, AC-2 ×2 случая), 3 зелёных (AC-3 ×2, AC-4). preflight пройдена.

## Не сработало
- —

## Где остановился
- Шаг завершён: планка готова, preflight зелёная.

## Чего не хватило
- —
