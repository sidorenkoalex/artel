# Записка test_author

## Выяснено
- Все AC — свойство кода, оба файла долгоживущие, в tests/:
  `tests/test_01m6mzaeg0m8q2gpbx4rsak71z_junit_hidden_dir.py` (AC-1…AC-4, AC-6, красный)
  и `tests/test_01m6mzaeg0m8q2gpbx4rsak71z_junit_prior_parse.py` (AC-5, зелёный с рождения).
  Каталог acceptance_tests/ планки не используется.
- Публичный вход: `outcome.parse_junit`, `outcome.parse_forge_report`,
  гейт — `advance_gates.acceptance.criterion_files` + `file_records`,
  профиль — запись `components:` в `config.TARGETS` фикстуры `tmp_root`.
- Дочерний pytest: путь к файлу, `-c <sb>/pytest.ini`, `--rootdir`, пустой
  PYTEST_ADDOPTS, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, своя группа процессов.
- Стаб (пустая часть classname → «.» к следующей части) — 17/17 зелёных;
  мутация «одна точка» краснит 4 случая AC-6. Стаб удалён, outcome.py чист.

## Не сработало
- `ls`/`cat` в Bash нет; `for … $f` отклоняется (simple_expansion).

## Где остановился
- `preflight` — все проверки пройдены. Шаг сдан.
- `plank-run` отказывает «планки нет» (в acceptance_tests/ нет test_*.py —
  все файлы долгоживущие); прогнаны pytest напрямую: hidden_dir 12 failed
  (краснота по причине задачи), prior_parse 5 passed. Каталог планки
  станет непустым, когда пульт на выходе запишет long_lived.sha256.txt.

## Чего не хватило
- Ничего существенного.
