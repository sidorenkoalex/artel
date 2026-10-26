# Записка spec_auditor — 01M5WDB7F14SQ30QVWJY2XYBG2 (аудит 2, spec_sha e4c4ffd3)

## Выяснено
- Факты SPEC верны: catalog.py:918, fsm.py:1037/1067 (эпик до частей), gitcmd.py:37/86-118/164/341/413/441/469. `_division_check` определён на fsm.py:1016, :1403 — место вызова в approve (до записей :1408-1444).
- Места push: artifact_cleanup.py:103, github_adapter.py:166/241, artifact_branch.py:427, cleanup.py:265/268 (`_bounded` добавляет `-c http.lowSpeed*` перед push, :257), fsm_merge_gate.py:744/1316, snapshot.py:297, doctor/project_checks.py:98 (`push --dry-run` — белый список его отказывает для target-human), doctor/artifact_branches.py:140 (push по URL из `source`, может быть ROOT).
- `_hosting_project` (gitcmd.py:94) распознаёт push только после пар `-C`/`-c`; URL-проект — через `project_by_url`, при нечитаемом targets — None.
- ARTEL_TASK (config.py:103) ставится только в окружении роли (runner.py:1182) — «контекст задачи» для команд Оператора не определён.
- Вердикт: concerns (11 пунктов).

## Не сработало
- `$(...)` в Bash требует подтверждения — только простые команды.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns, 11 отклонений), guard: ок. Шаг завершён.

## Чего не хватило
- Перечня всех push-мест — grep '"push"' orchestrator/.
