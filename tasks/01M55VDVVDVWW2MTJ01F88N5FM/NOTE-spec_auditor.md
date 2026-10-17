# Записка spec_auditor — 01M55VDVVDVWW2MTJ01F88N5FM

## Выяснено
- Все ссылки SPEC на код сверены и верны (mandate.py:103-111/159-165/264/346-350/362-394, answer.py:113/157/487, test_integrity.py:227-244/664/1509-1518, fsm_merge_gate.py:137-146, targets.yaml:49/87).
- Продакшен-вызовы гейта (test_integrity:1518, fsm_merge_gate:146, review:644) все передают scope профиля; `_in_scope` — только запасная ветка `_compare` при scope=None.
- `mandate.refusals` из продакшена зовёт только answer.py:113, conn/task_id передаются; все три канала answer (escalated, in_dev/review, spec_gate) идут через `_read_checked_answer_file`.
- `_matrix_problems(raw)` в answer.py:149 задачи не получает — для требования 4 сигнатуру придётся расширить (в зоне).
- Песочница tests/sandbox.py::seed_artel_targets даёт артели test_profile → существующие тесты answer с мандатом у артели не сломаются от требования 2. Тестов, фиксирующих отказ `backend/tests/…`, в tests/ нет — «Меняемое поведение» не нужно.
- Маска `tests/**/*.py` через mask_matches практически эквивалентна startswith/endswith у in_weakening_scope.

## Не сработало
- Составные bash-команды с `$`/xargs/awk отклоняются песочницей — только простые grep/sed.

## Где остановился
- Вердикт concerns: AC-5 не называет канал zones-extend; требование 4 не говорит, засчитывается ли `tests/…` у внешнего проекта с профилем; требование 2 vs 3 у артели при отказе решения профиля.

## Чего не хватило
- Ничего существенного.
