# Записка spec_auditor

## Выяснено
- Вердикт fail, 14 отклонений в SPEC-AUDIT.md (sha SPEC 681d7d4a…).
- Главное: не заданы имена полей compose, канал поиска/подмены `docker`, реестр живых прогонов (doctor), `config` без `--project-name` оставляет `name:` сетей/томов общими (по документации, опытом не проверено).
- Опытом: сокет /var/run/docker.sock из шага роли отвечает на /_ping; он — ссылка на ~/.docker/run/docker.sock; config.json пульта: credsStore=desktop, currentContext=desktop-linux; /usr/local/bin содержит docker-credential-osxkeychain, kubectl и пр.
- suite_run.py (только чтение) правки не требует — ветка по `report`; mutation_run отказывает не-default runner (:385-389).
- Существующие тесты doctor с cmd_doctor(fix=True)/all_checks рискуют позвать настоящий docker.

## Не сработало
- `cd …; sed` — отказ песочницы; `$?` в команде — отказ; `docker compose version` — требует подтверждения (опыт Compose невозможен).

## Где остановился
- Аудит сдан, guard ок.

## Чего не хватило
- Docker CLI в шаге: утверждения о `config` (разрешение путей, `name:` сетей) и `up --wait` ≥2.1.1 не проверены опытом.
