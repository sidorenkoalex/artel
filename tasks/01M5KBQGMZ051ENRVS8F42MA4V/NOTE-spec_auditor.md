# Записка spec_auditor

## Выяснено
- Факты SPEC о коде подтверждены: prune.py:35/57/65/102/120, config.py:498/499/654, suite_lock.py:40/225, gitcmd.py:374, artel.py:70–77/625. orphans.py: функция `_live_suite_run_in` начинается на :58, чтение pid — :61–67.
- `gitcmd.in_repo` = `git -C <repo>` с cwd=config.ROOT (gitcmd.py:185, :385): если в `.artel/notes-work` нет своего `.git`, git ответит о репозитории пульта выше по дереву.
- `idgen.is_task_id_form` принимает и префиксы id (idgen.py:59–60): имя `TMP`, `ABC` — «форма id».
- docs/codebase-map.md и tests/ — в config.COMMON_ZONES (config.py:814), зоны достаточны.
- Нет AC: каталог suite-run задачи из «оставляемых» (открытая/последние 20) не отбирается; строки «не удалён» для новых видов; причина «git не ответил»; пустой каталог suite-run.

## Где остановился
Вердикт concerns записан в SPEC-AUDIT.md.

## Чего не хватило
Поиск запрещён в составных командах bash с cd/переменными — только абсолютные пути по одной команде.
