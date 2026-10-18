## Выяснено
- Итерация 1: approved, реестр пуст. Тесты задачи и соседних модулей зелёные (28 passed, 226 subtests). Карта кодовой базы свежая (расходится только `built_at_sha`).
- Путь полного прогона без наблюдения идёт `_run_pytest` → `_run_in_session` → `_launch`; `CommandNotFound` ловится в `run_full_suite` до кеширования.
- У `pult-pytest` `run`/`collect` идут через `subprocess.run`, не через `_launch`. Поэтому `_launch(own=False)` сторожит только `tests/test_acceptance_own_launch.py`.

## Не сработало
- `plank-run` — отказ «планки нет»: `acceptance_tests/` у задачи нет, критерии закрыты долгоживущими тестами в `tests/`.

## Где остановился
- REVIEW.md записан, вердикт approved.

## Чего не хватило
- Что `plank-run` отказывает при законно отсутствующей планке, стало видно только после запуска.
