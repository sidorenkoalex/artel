# Записка spec_auditor

## Выяснено
- Круг 2 (spec_sha e8c0b2ee…): все три решения Оператора круга 1 перенесены в SPEC (треб. 2/3/4(б)(в)(г), AC-3, AC-4, AC-7, AC-10).
- Факты кода подтверждены заново: fsm.py:1678/1766, pull_main.py:35, workspace.py:255, ci_rerun.py:44, runner.py:153, answer.py:488, lease.py:334; текст отказа lease.py:189-191 с `int(age)` от liveness._age_seconds (liveness.py:54) — подмена фиксирует.
- Существующие моки run_locked позиционные (conn, task, sid, fn[, **kwargs]) и патчат модуль `lease`/`store` — run_task_command с ними совместим (role_refusal:468/500, role_environment:53/138, autogate:74, canary_suite_skip:191).
- test_01m4xv9xpjzd29py0ntnz98m02_commands.py:35 ищет force=True у acquire/run_locked — новая функция без kwargs не задевает.

## Где остановился
Вердикт pass, SPEC-AUDIT.md записан.

## Чего не хватило
—
