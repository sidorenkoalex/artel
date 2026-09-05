---
task: 01M1R9YEK08XEQWBFX0929WFVJ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. Расширение зон разрешено: orchestrator/canary.py, orchestrator/fsm_advance.py
   Основание — раздел «Расширение зон» PLAN.md: два вызова
   `fsm._pull_main_or_escalate` вне зон задачи обязаны различать новый
   исход `"refused"`; правки по одной строке условия в каждом файле.
   Зоны SPEC не меняются, расширение действует только на эту задачу.
