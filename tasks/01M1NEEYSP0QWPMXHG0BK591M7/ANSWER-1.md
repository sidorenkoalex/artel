---
task: 01M1NEEYSP0QWPMXHG0BK591M7
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Вопрос 1 — вариант A: предупреждение до выполнения — только для pause
и release (единственных команд без защиты lease). Поведение approve,
reject, budget, kill, answer не меняется: именованный отказ при чужом
живом lease сохраняется (T044, ADR-0002). SPEC фиксирует это в
«Не входит» со ссылкой на находку analyst.
