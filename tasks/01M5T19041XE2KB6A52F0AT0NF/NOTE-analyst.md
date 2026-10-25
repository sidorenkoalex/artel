# Записка analyst — 01M5T19041XE2KB6A52F0AT0NF

## Выяснено
- ANSWER-1: вопрос 1 — A (обвязка внутри `repo_context.protected_paths`), вопрос 2 — A (`config.is_protected_path` понимает `**/<каталог>/`, config.py разрешён), вопрос 3 — прежний `target-wrapper` не трогается, новая проверка `target-wrapper-worktrees`. Мандат на 4 теста — строка в ANSWER-1.
- Константа решена в SPEC: `config.AGENT_WRAPPER_MARKERS = ("**/.claude/", ".mcp.json", "**/CLAUDE.md", "**/AGENTS.md")`. Порядок `protected_paths` внешнего: no_paths → маркеры → agent_wrapper, дубль — только совпадение строки.
- Расхождение внутри матрицы ANSWER-1: файл `frontend/.claude` формулой путей не покрыт, а зона `sub/.claude` (без `/`) отказывать обязана. В SPEC это разведено: сверка зон (`guard.protected_zones`, требование 6) и сверка путей файлов (требование 2) — разные проверки. Отсюда `scripts/guard.py` в зонах.
- Регистрация проверок doctor — `orchestrator/doctor/cli.py:142`, этот файл в зонах.

## Где остановился
SPEC.md сдан, `status: ready`, guard ок. QUESTIONS.md удалён. 19 AC, бюджет 45 (рамка ТЗ; по таблице класс ~85). В «Оценке объёма» предложен монолит: мандат ANSWER-1 привязан к этой задаче и подзадачи его не наследуют.

## Чего не хватило
Что guard считает классифицированным путём: пример `docs/` из критерия пришлось объявить в «Не входит».
