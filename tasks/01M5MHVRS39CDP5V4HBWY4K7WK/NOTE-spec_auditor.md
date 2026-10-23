# Записка spec_auditor

## Выяснено
- Семь команд и строки ТЗ подтверждены по коду (fsm.py:1678/1766, pull_main.py:35, workspace.py:255, ci_rerun.py:44, runner.py:153, answer.py:488, lease.py:334); auto.py:928 зовёт cmd_run(session_id=...).
- «ЗДЕСЬ» есть только в докстрингах cmd_reject (fsm.py:1681), cmd_workspace (workspace.py:264), cmd_ci_rerun (ci_rerun.py:55), cmd_run (runner.py:160). У cmd_spec_audit утверждения о префиксе нет вовсе, у cmd_pull_main — без «ЗДЕСЬ», у cmd_zones_extend — «резолв префикса, что у cmd_answer». AC-7 требует утверждение у всех семи.
- Текст отказа acquire содержит `heartbeat {int(age)} сек` (lease.py:~190) — сравнение в (б) зависит от времени.
- Существующие моки run_locked позиционные (conn, task, sid, fn) — совместимы с run_task_command.
- Префикс-регрессия покрывает reject и workspace, но не ci_rerun/zones_extend; замыкание по внешнему `task_id` вместо `tid` новые проверки не ловят.

## Где остановился
Вердикт concerns, SPEC-AUDIT.md записан.

## Чего не хватило
—
