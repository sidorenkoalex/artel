# Записка developer — 01M6KBD9FC36WARWSY9Z0JDMG5

## Выяснено
- Реализация: `projects.cmd_target_set` (+ `_backup_stamp`, `_field_keys`, `_argument_value`, `_loses_text`, `_comment_line`, `_target_set_mismatches`, `_backup_copy`, `_target_set_show`); `artel.py` — запись `target-set` в `table` и две строки в блоке «Команды:»; `doctor/cli.target_failure_errors_check` после цикла проектов в `all_checks`.
- `project_profile.component_profiles` для `test_profile` тоже ставит `from_components=True` — поэтому строка doctor фильтрует записи по наличию `components` сама.
- Долгоживущие 42 теста задачи и планка AC-2 зелёные.

## Не сработало
- `ls`/`cat` в Bash недоступны — Read/find.

## Где остановился
- Шаг завершён: документация (docs/operator-session.md, docs/stack.md «Локальный слой проектов») готова, карта регенерирована, свой сторож tests/test_projects_target_set.py (2 теста, проверен мутацией), тесты соседних модулей зелёные, guard ок, PLAN status: ready.
- `-n 4` (xdist) в шаге роли падает «node down» — гонять последовательно.

## Чего не хватило
- —
