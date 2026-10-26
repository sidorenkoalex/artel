# Записка developer — 01M5TBCY7WTN121S136XP2C6SR

## Выяснено
- Э1 смержен (f909b7dd9): интерфейсы epics.py/board.py/new --epic совпадают с SPEC и тестами test_author — эскалации нет.
- Дедуп алерта 80 % — по журналу эпика (последняя из записей budget.EPIC_ENVELOPE_ACTION / EPIC_ALERT_ACTION), без новой колонки; схема меняется одной колонкой tasks.start_after.
- merge_after.check строит граф цикла из merge_after ∪ start_after (`_dependency_graph`), параметр `column`; причины канала start_after переименовываются префиксом.
- Отказы первого шага — runner._first_step_refusal (после стоп-крана волны), действия ENVELOPE_REFUSAL_ACTION / START_AFTER_REFUSAL_ACTION; auto узнаёт их `_run_first_step_refusal`.
- watch: `_EpicWarnings` в `_emit_steps`.

## Не сработало
- `ls`, `$?`, heredoc с `{"…"}` в Bash отклоняются; `pytest -n` запрещён сторожем роли — гонять последовательно.
- guard.py на файле tests/ — ошибка «нет frontmatter» (он только для артефактов); линт тестов — через guard.lint_errors_from_files([(путь, текст)]).

## Где остановился
- Готово: код, свой тест tests/test_start_after_units.py (4 теста, мутации пойманы), долгоживущие 36/36, ~680 тестов затронутых модулей зелёные, карта регенерирована, PLAN status: ready, guard ок.

## Чего не хватило
- Ничего существенного; дольше всего искал, где watch обрабатывает новые записи журнала (`_emit_steps`).
