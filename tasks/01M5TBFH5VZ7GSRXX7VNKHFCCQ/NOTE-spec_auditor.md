# Записка spec_auditor — 01M5TBFH5VZ7GSRXX7VNKHFCCQ

## Выяснено
- Ветка задачи (HEAD 761b646e9 = локальный main) НЕ содержит Э1: мерж Э1 f909b7dd9 есть только в origin/main. `orchestrator/board.py`, `epics.py` — на origin/main; сверка фактов шла по `git show origin/main:<путь>`.
- Борд `report` — один на все проекты (`report.py:1396` `_board_html(tasks)`, `:1440` `store.all_tasks`), метка проекта на плитке; `_by_project` `:765` — только метрики (`:782`, `:1215`). Модель `board.build_model(conn, project)` — на один проект (`board.py:123`, `store.project_tasks`).
- В карточке модели (`board.py:39`) нет `review_iters`, `escalated_from`, `target`, нужных плитке (`report.py:565-593`).
- Нет AC «report из модели» (подмена модели) — AC-5/AC-6 проходят без board.py.
- Тесты внутренностей доски: `tests/test_report.py:213,220,230` (`_tile_html`) SPEC не назвал; назвал `:246,:255,:261`, `spec_audit_units.py:357`.
- Части деления (`catalog.spawn_subtask` `:786`, `fsm.py:1070`) идут мимо `new` → мимо `ref_required`.
- Э1 тест `test_01m5tbbdfs..._board_model.py:31` держит ключи верхнего уровня модели РОВНО — `refs` только внутри cards/epics.

## Не сработало
- Bash с `cd`/переменными/`ls` отклоняется правилами — только одиночные команды с абсолютными путями и `git show`.

## Где остановился
- SPEC-AUDIT.md написан: verdict concerns, status ready.

## Чего не хватило
- Что ветка задачи отстаёт от origin/main с мержем зависимости — обнаружил только по отсутствию board.py.
