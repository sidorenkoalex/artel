# Записка spec_auditor

## Выяснено
- Визит 2 (SPEC sha 22488aeb…, после решения Оператора О-1…О-6). Ссылки SPEC на код снова подтверждены: gitcmd.py:22/32-45/232-241, ci.py:56-66, misc_checks.py:91-94, claude.py:45/155-175, runner.py:964-1048, brief.py:519-550, role_prompt.py:238-246/323, knowledge_cards.py:953-956, workspace.py:111.
- gitcmd.git всегда cwd=config.ROOT (gitcmd.py:43) — ветка «или по рабочему каталогу» мертва; carpentry — только локальные операции.
- Клон проекта — `.artel/projects/<имя>/repo` (repo_context.py:75-79), не сам каталог проекта; клон артели тоже под .artel/projects/artel/.
- `git clone` не пишет FETCH_HEAD — у клона без fetch пульта 8.1 не определена.
- artel-token (targets.yaml:28) = token_fallback подписки модели (roles.yaml:46) — 8.5 сравнит PAT проекта с токеном подписки.
- doctor/artifact_branches.py:137 пушит из `source` (может быть главная копия) в url клона — механизм «проект по -C» его не узнает.
- Скилы читаются с main пульта (brief.py:543), не с диска.
- Вердикт: concerns.

## Где остановился
SPEC-AUDIT.md написан, guard прогнан.

## Чего не хватило
Карты «хостинговый git-вызов → откуда -C»; собирал grep по "push"/"fetch".
