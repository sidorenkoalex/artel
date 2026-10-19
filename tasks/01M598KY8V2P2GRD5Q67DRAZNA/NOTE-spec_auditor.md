# Записка spec_auditor — 01M598KY8V2P2GRD5Q67DRAZNA

## Выяснено
- Все места `файл:строка` в SPEC сверены, они верны: catalog.py:584-612, :617-620, :170-171, :518-646; artel.py:1440/1444/1631.
- База внешнего проекта — `targets.yaml[..]["base"]` (repo_context.py:95), а не `main`. SPEC фиксирует `origin/main`.
- `ensure_clone` существующий клон не fetch'ит (workspace.py:104-105). `workspace.repo("artel")` — это `.artel/projects/artel/repo`, а не `config.ROOT` (repo_context.py:75-79).
- Песочница `TmpRootTest`: `config.ROOT` — не git-репозиторий, у клона-заглушки нет коммитов (tests/sandbox.py:1581, :1473). `RealGitSandbox`: клон артели — симлинк на ROOT (:1518). Внешний клон с `origin` — `make_project_repo` (:1222).
- Существующие тесты `cmd_new` с ТЗ не содержат ни ссылок `*.py:N`, ни имён в кавычках с точкой. Требование 5 им не грозит, если дерево не открывается без кандидатов.
- `test_new_argv_parsing.py` проверяет справку только через `assertIn('new "<название>"')`, так что `[--strict-tz]` его не ломает.

## Не сработало
- В Bash не проходят `sed` после `cd`, `$var` и `xargs` — читал через Read и Explore.

## Где остановился
- SPEC-AUDIT.md готов: verdict concerns, status ready, guard ок. Шесть пунктов вердикта: база вместо `main`; недоступное или устаревшее дерево; пометка «общее имя» и `--strict-tz`; форма ссылки (`.py` или любой файл, неоднозначное имя); пробелы AC-5, AC-6, AC-11; «рядом», окно диапазона, строки `def`.

## Чего не хватило
- Сводки «какие песочницы tests/sandbox.py что подменяют (ROOT git или нет, есть ли origin)». Пришлось искать через Explore.
