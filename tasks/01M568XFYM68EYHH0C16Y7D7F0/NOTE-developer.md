# Записка developer — 01M568XFYM68EYHH0C16Y7D7F0

## Выяснено
- Реализация — `orchestrator/cleanup.py`: `cleanup_project_remote` (зовёт только `_cmd_kill` при `won`, после `cleanup_killed_task`), помощники `_close_project_pr`, `_delete_origin_branch`, `_forge_of`, `_left_reason`; текст «перейди на … и повтори kill» — `_base_of(repo)`.
- Молчание: `gh` — stderr `ci.gh` начинается с «gh молчал дольше»; git-пуш — stderr несёт «Operation too slow»/«curl 28».
- Долгоживущий файл задачи: 11 passed; соседние тесты kill/деления/токена/областей проекта — 144 passed.
- Карта перегенерирована (`scripts/codebase_map.py`).

## Не сработало
- `pytest -n 4` в этом окружении — воркеры xdist падают «node down»; гонял без `-n`.

## Где остановился
- `suite-run` №1 зелёный (5654 прошло, 0 упало, 2 пропущено); PLAN.md — status: ready, guard ок. Шаг завершён.

## Чего не хватило
- Ничего существенного: записка test_author дала форму вызовов.
