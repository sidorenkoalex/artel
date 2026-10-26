# Записка spec_auditor — 01M5TBFH5VZ7GSRXX7VNKHFCCQ (визит 5, SPEC sha f1e1f81f)

## Выяснено
- Ветка задачи без Э1; сверка по `git -C <wt> show origin/main:<файл>` (main 7f37c6dd7). Песочница режет `$VAR`, `cd &&`, sed-диапазоны в пайпе — работают `git -C <wt> show … | grep -n -A`, `git grep … origin/main`.
- Все шесть замечаний визита 4 внесены в SPEC (решение гейта №4).
- НОВОЕ: строка матрицы «report не меняет БД и не зовёт git — command_report.py:417» неверна: тест :417 (`CommandReadOnlyTest`) гоняет `explore-stats` (`self.explore()` → dispatch `explore-stats`, :201), не `report`. Ошибка пришла из моего же п.6 визита 4. «Не зовёт git» для report держит `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py:185` (git_spy + Popen); «не меняет БД» report не держит никто — `cmd_report` пишет алерт через `token_rate_divergence` (report.py:1452).
- Факты :48/:565/:596/:1378/:1428/:1440, catalog :687/:694/:738/:772/:786/:847, fsm:1070, canary_drive:54, targets:289-294 — подтверждены.

- НОВОЕ 2: `tests/test_epics_board_units.py:9` (`:28-29`) ждёт ровно одну запись журнала после `migrate` старой БД (ручная схема без новых таблиц) — догон `external_refs` с записью журнала по образцу `_migrate_epics` (schema.py:232-260) его покрасит.
- НОВОЕ 3: req 10 «до побочных эффектов» не охватывает отказы разбора/пустоты `--ref`.

## Где остановился
- SPEC-AUDIT.md готов: verdict concerns (3 отклонения выше), status ready, guard ок.

## Чего не хватило
- Проверка в визите 4 не открыла тело теста :417 — поверила docstring класса.
