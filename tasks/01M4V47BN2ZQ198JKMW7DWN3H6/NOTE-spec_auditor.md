## Выяснено
- Выкладка: runner.role_cwd (orchestrator/runner.py:1089-1162) -> artifact_branch.materialize_task_dir (artifact_branch.py:604-654), запасной путь — runner.py:1160-1161 (_place_harvested_docs); при сбое materialize диск не трогается вовсе.
- role_cwd без параметра роли; вызов с ролью в области видимости — runner.py:1466; doctor/isolation.py:102 зовёт role_cwd(None, None, target); ~10 тестов зовут role_cwd(conn, id, target) позиционно.
- Автокоммит не удалит отсутствующую записку: кандидаты на удаление — только type questions (checkpoint.py:1083-1144, 184).
- Бриф уже не несёт чужих записок проверяющим (brief.py:119-125).
- Ссылка refs/artifacts/<id> читается git'ом прямо из worktree роли (проверено ls-tree) — обходной канал.
- TZ «Рамка: $15» против budget_usd: 25 в SPEC; ANSWER нет.

## Не сработало
- ls в Bash недоступен, grep с `cd &&` требует подтверждения — абсолютные пути.

## Где остановился
- SPEC-AUDIT.md написан, вердикт concerns.

## Чего не хватило
- Нет.
