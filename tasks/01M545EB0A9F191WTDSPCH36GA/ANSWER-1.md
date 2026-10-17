---
task: 01M545EB0A9F191WTDSPCH36GA
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

## Ответы

Решение Оператора 17.10.2026 по эскалации автора тестов — вариант А, с уточнениями третьего аудита SPEC.

1. AC-7 — вариант А: публичная функция `brief.project_skills_refusal(target: str, entry: dict) -> str | None` в `orchestrator/brief.py`. `None` — отказа нет; строка — текст отказа, тот же, что входит в отказ шага. Её зовут и сборка брифа, и `doctor`.
2. В-1: для задачи артели `targets.yaml` на пути шага не читается (как `repo_context.py:82-89`), `project_skills` артели — `[]`; отказ AC-8 при нечитаемом `targets.yaml` или необъявленном `target` — только у внешнего проекта.
3. В-3: пустая колонка `target` задачи на пути шага — «проект не определён», именованный отказ шага; откат `t["target"] or config.DEFAULT_TARGET` (`runner.py:366`) на пути шага не используется.
