# Записка test_author

## Выяснено
- Долгоживущие: tests/test_01m563e1sh9sb63s2mw4a9b82n_observation.py (AC-1..7, AC-10, AC-11 через artel.main) и tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py (AC-8 через catalog.cmd_status, AC-9 через report.cmd_report → .artel/report.html, разбор плитки HTMLParser, элемент с собственным текстом = имя проекта).
- Разовый: acceptance_tests/test_ac9_tile_without_target.py — `report._tile_html` на dict без ключа `target` (закрытое имя, долгоживущему недоступно).
- До кода: AC-5 и первая часть AC-6 зелены (держат прежнее), плитка без ключа зелена; остальное красно по верным причинам.
- Стаб-валидация сделана: временная правка artel.py/watch.py/catalog.py/report.py — все тесты задачи + test_launch_observation_refusals, test_01m3sx69…_observation, test_report зелёные (97 passed); стаб откачен `git checkout`.
- watch: одна итерация — patch_sleep(watch, RuntimeError) + redirect_stdout (capture теряет вывод при исключении).
- preflight: все проверки пройдены.

## Не сработало
- `cat`/`ls` в шелле недоступны; heredoc с f-строками отклоняется песочницей — стаб вносил через Edit.

## Где остановился
- Шаг завершён.

## Чего не хватило
- —
