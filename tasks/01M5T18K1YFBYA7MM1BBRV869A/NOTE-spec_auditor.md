# Записка spec_auditor (итерация 2, SPEC sha 73f667c9…)

## Выяснено
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.
- Факты brief.py/review.py/role_prompt.py/yamlmini/branch_commit/doctor cli.py:139 подтверждены; номера строк тестов совпадают.
- Соседняя 01M5T19041 (на spec_gate): AGENT_WRAPPER_MARKERS = ("**/.claude/", ".mcp.json", "**/CLAUDE.md", "**/AGENTS.md"); треб. 8 соседки (отказ загрузки knowledge внутри обвязки, кроме корневых CLAUDE/AGENTS) совместимо с AC-5.
- Находки: О1 путь config.PROJECTS мимо repo_context.projects_root() (NO_AREA); О2 пустой sources → вечный ok doctor, AC не ловит; О3 symlink conventions.md не в AC; П4/М1 «без сети» без AC, NoNetworkTest вырождается без knowledge; М2 эталон «из нового кода»; Н1 счёт N обвязки неоднозначен.

## Не сработало
- Составные bash (`|xargs`) требуют подтверждения; `ls` недоступен.

## Где остановился
- Аудит завершён.

## Чего не хватило
- Состояние соседки — через `git show refs/artifacts/01M5T19041XE2KB6A52F0AT0NF --stat` (паспорт).
