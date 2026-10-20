# Записка developer

## Выяснено
- Интерфейс задан долгоживущими tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_{outcome_gate,refusal_classes}.py: сквозной `fsm.cmd_advance`, сбои git — по кадрам модуля `orchestrator.advance_gates.outcome_integrity`.
- Образец выписок — `two_sided.run`; перепрогон — `acceptance._report_run(profile, tree, [файл], component_limit)`.
- `todo` у vitest — `CaseResult(outcome=skipped, mode="todo")`, `it.fails` — `passed` с `fails=True`.
- Покрытые мандатом находки в детали отказа писать нельзя (AC-11 проверяет отсутствие id); они — в записи пройденного гейта.

## Не сработало
- `pytest -n 8` в шаге роли: все воркеры xdist падают «node down». Долгоживущий файл гонять последовательно (~3,5 мин).

## Где остановился
- Шаг завершён: модуль, вызов в fsm_advance, REFUSAL_CLASSES, tests/test_outcome_integrity.py, метод в tests/test_refusal_classes.py, карта. Долгоживущие тесты задачи (23), smoke, fail_to_pass 01M5AQH8, планка (3) и полный suite-run (6214 passed) зелёные. PLAN ready.

## Чего не хватило
- Ничего существенного; имя действия пройденного гейта выбрано сам: «гейт неослабления по исходам пройден».
