# Записка analyst

## Выяснено
- Шаг 4 (возврат с spec_gate, 13 решений Оператора): вношу все 13 в SPEC; якоря решений сверены по worktree (sandbox.py:1638-1641 подменяет атрибуты config; test_doctor_closed_ref_fix.py:177-183 подменяет починки; doctor/__init__.py:152-155 перечень orphans; targets.py:1194-1199 _check_rerun_ban по command; runner.role_env уже принимает provider; codex.py:136/143).
- COMPOSE_ROLE_DIR → функция `runner.compose_role_dir()` от config.ROOT (решение 1).
- config.json копии = `{}` (решение 11) — заменяет «копию без credsStore…» ANSWER-1.
- Новый AC-22 (решение 3, необязательные тесты с Docker), зоны + orchestrator/doctor/__init__.py (решение 5).
- Имена полей записи: compose_file, compose_service, compose_env_file, compose_env_template, compose_mount, compose_up_down_sec; config.COMPOSE_UP_DOWN_SEC.

## Не сработало
- `awk`/`head` в составной команде Bash требуют подтверждения — читать через Read/sed.

## Где остановился
- SPEC.md третьего варианта сдан (status: ready, 17 требований, AC-1…AC-22, зоны +doctor/__init__.py, деление 2 части $60+$30), guard ок. Каждое решение гейта 1–13 привязано к требованию и AC в «Материалах».

## Чего не хватило
- Docker CLI в шаге — `config --format json`, `down -p` без файла опытом не проверены.
