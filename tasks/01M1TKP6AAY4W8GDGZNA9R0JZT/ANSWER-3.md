---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

# ANSWER-3: ответ Оператора

## Ответы

1. Отсутствующий `_util.py` восстановлен Оператором через `amend-tests`
   (лок планки сдвинут на 16cffbcc): фикстуры `AC_TEST_TWO_PASSING`,
   `MIXED_PLANK`, `NO_MARKER_PLANK` (маркер краснозелёности — в
   докстринге модуля фикстуры) и `read_pytest_config(root) -> dict | None`
   с ключами `testpaths`, `python_files`, `timeout`. Причина потери —
   фильтр посторонних файлов чекпоинта не знал вспомогательных модулей
   `_*.py` (регрессия №18, hotfix в main отдельно).
   На коде ветки 696a7f9e планка 26/28: красны только два теста AC-7
   (`test_ac7_per_test_timeout.py`). Диагноз по выводу теста:
   `acceptance.run()` запускает pytest с `rootdir` во временном каталоге
   планки — `pyproject.toml` пульта не читается (`timeout` не применяется)
   и плагин `pytest-timeout` не подключён (в строке `plugins:` только
   anyio), зависший тест проходит зелёным. Нужно: запускать pytest с
   конфигурацией пульта (`-c <REPO_ROOT>/pyproject.toml` либо
   `--rootdir`, плюс явное `-p pytest_timeout` или `-o timeout=…` из
   `stack.PER_TEST_TIMEOUT_SEC`) для планки и для полного набора, чтобы
   таймаут отдельного теста действовал независимо от каталога планки.
   После правки — планка 28/28. Полный `tests/` не запускать.
