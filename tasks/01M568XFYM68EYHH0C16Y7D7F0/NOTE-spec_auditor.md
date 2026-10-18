# Записка spec_auditor — 01M568XFYM68EYHH0C16Y7D7F0

## Выяснено
- `cleanup_killed_task` (orchestrator/cleanup.py:185) зовут два пути: `_cmd_kill` (cleanup.py:457) и деление на гейте SPEC (`fsm._cleanup_divided_parent`, fsm.py:979). Повторный kill `done`-задачи тоже доходит до уборки (cleanup.py:415-457: «уже done — kill не требуется», затем cleanup_killed_task).
- Токен: `ci.gh(repo=url)` берёт слот через `gitcmd.project_by_url` (ci.py:65-71) — нужен именно `url` записи (= `ctx.remote` внешнего проекта, repo_context.py:94). git-пуш через `gitcmd.in_repo(clone, "push", ...)` узнаёт проект по пути клона под PROJECTS (gitcmd.py:90-116). Без `token_slot` в записи — прежняя авторизация, не отказ (gitcmd.py:119-140).
- `gitcmd.git` (gitcmd.py:162-190) зовёт subprocess.run БЕЗ таймаута; `gh` — с GH_TIMEOUT_SEC (ci.py:73-80).
- cleanup.py:82 (`drop_task_dir`) — MAIN_BRANCH про главную копию артели, менять не нужно; кандидат AC-7 — только cleanup.py:211.
- Вердикт: concerns (8 отклонений, все решаемы на гейте).

## Не сработало
- `ls`/`xargs`/`$(...)` в Bash шага недоступны — пользоваться find/grep -l.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Где ещё вызывается cleanup_killed_task — нашёл grep'ом по orchestrator/ (fsm.py:979).
