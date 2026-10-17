# Записка developer

## Выяснено
- Схема: `ci._project_context(repo)` — (ctx, отказ) по пути клона: is_artel(path) → артель; путь под `repo_context.projects_root()/<имя>/` с не-артельным именем → `repo_context.resolve(имя)` (None → отказ Н-4); иначе артель (в т.ч. config.ROOT).
- `ci.gh(repo=<url>)`: для `gh api` — `GH_REPO` в env (разбор https/scp `_owner_and_name`), без `--repo`; для `gh run/pr` — `--repo` как было.
- Внутренние вызовы у артели — прежняя форма (без repo=) через `_project_kwargs`, иначе ломаются подмены `lambda sha:` в tests/.
- Вызывающие (`ci_rerun.py`, `fsm_merge_gate.py`) передают `**ci._repo_kwargs(workspace.task_repo(task_id))`.
- Тексты отказа `gh` обрезаются до 200 знаков в `check_runs_page` — имя/адрес в начале текста.
- Долгоживущий файл задачи (10 тестов) и планка (4) зелёные; свои тесты — tests/test_ci_project_gh_address.py (Н-1..Н-4), мутации проверены.

## Не сработало
- `ls`/`rm` в Bash недоступны (command not found); `python3 -m pytest -n 4` — воркеры xdist падают «node down», гонять без -n.
- `scripts/guard.py` на файле tests/ ругается на frontmatter — гонять его только на артефактах.

## Где остановился
- Код и тесты готовы, карта регенерирована, PLAN написан; жду suite-run №1, затем PLAN status: ready.

## Чего не хватило
- Ничего существенного; дольше всего — понять, что `config.ROOT` у `main_line_status` должен оставаться артелью отдельно от `_repo_kwargs`.
