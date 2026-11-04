# NOTE reviewer, iteration 1

## Выяснено
- Вердикт approved, реестр пуст; два наблюдения без severity в REVIEW.md: ValueError на «### Решение ²» (`spec_gate_decision.py`, `int()` после `isdigit()`), частичный повтор долгоживущего AC-8 в `tests/test_spec_gate_decision.py`.
- `mandate.line_elements` требует маркер в начале строки, поэтому сверка строк мандата решения и ANSWER-n корректна.
- `artifact_source.resolve` всегда даёт foreign=True: `_answer_texts` читает с артефактной ветки, как и соседние функции.

## Не сработало
- `pytest -n 6` — воркеры xdist падают на старте; запускать с `-p no:xdist`. Шесть файлов идут около 7 минут.

## Где остановился
- Ревью завершено, REVIEW.md записан.

## Чего не хватило
- Не знал, что xdist в шаге не работает: одна попытка потрачена зря.
