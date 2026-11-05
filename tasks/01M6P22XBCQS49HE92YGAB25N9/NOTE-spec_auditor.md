# Записка spec_auditor

## Выяснено
- Визит 2: SPEC c5d34516…, вердикт concerns, 14 пунктов в SPEC-AUDIT.md; guard ок.
- Прошлые 14 отклонений закрыты SPEC/ANSWER-1. Якоря кода верны (ANSWER-1 in_role_environment сдвинут на 2 строки).
- Главное новое: COMPOSE_ROLE_DIR — константа при импорте, песочницы тестов подменяют только config (tests/sandbox.py:1640); безопасная форма теста --fix не задана (cmd_doctor(fix=True) гоняет настоящие починки); необязательный тест с Docker пойдёт в CI ubuntu-latest (Docker есть); правило сокета — по путям машины, не демона; фасад doctor/__init__.py не в зонах; _check_rerun_ban пропускает compose без command.
- Прочее: гонка уборки .artel-report с фоновым suite-run в той же рабочей копии (у не артели suite_tree = wt); отслеживаемый compose_env_file; Codex workspace-write без сети; cliPluginsExtraDirs.

## Не сработало
- `ls`, `cat`, `$VAR` в Bash — отказ; помогают python3 -c / sed / grep.

## Где остановился
- Аудит сдан, status ready.

## Чего не хватило
- Docker CLI в шаге (подтверждение): поведение down для one-off run-контейнеров и монтирования сокета на Docker Desktop не проверено опытом.
