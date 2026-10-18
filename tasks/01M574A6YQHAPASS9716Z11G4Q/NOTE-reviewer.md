## Выяснено
- Итерация 1: approved, замечаний нет. Тесты задачи 17 passed, tests/test_ci*.py + tests/test_doctor*.py — 314 passed; карта свежа.
- Мутация `checks_forbidden` без сверки "403" ловится tests/test_ci_actions_fallback.py.

## Не сработало
- `plank-run` — отказ «нет файлов test_*.py»: планка — только долгоживущие tests/test_01m574…_*.py, гонял pytest напрямую.

## Где остановился
- REVIEW.md записан со status: approved.

## Чего не хватило
- Ничего существенного; сигнатуры `_no_checks_by_branch`/`_inherited_from_main` пришлось читать в ci.py (588, 1054).
