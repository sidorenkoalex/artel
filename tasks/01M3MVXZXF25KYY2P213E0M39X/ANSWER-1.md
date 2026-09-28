---
task: 01M3MVXZXF25KYY2P213E0M39X
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора на QUESTIONS задачи 01M3MVXZXF25KYY2P213E0M39X (решение Оператора 29.09.2026).

Вопрос 1 — вариант A. Единый помощник сравнения пути с перечнем защищённых путей в orchestrator/config.py; все шесть мест сравнения зовут его вместо своей формулы. Смысл существующих 12 записей не меняется. Запись-маска `**/conftest.py` и корневые литералы — как предложено в QUESTIONS.

Вопрос 2 — вариант A. Пометка «только чтение» с orchestrator/advance_gates/zones.py и scripts/guard.py снимается ровно в объёме замены формулы сравнения на вызов общего помощника; иной логики этих файлов задача не меняет. Остальные пути из «только чтение» ТЗ — по-прежнему только чтение.

Вопрос 3 — вариант A. orchestrator/gates.py из зон убрать: в ТЗ он назван ошибочно, гейт диффа защищённых путей — orchestrator/fsm_merge_gate.py.

Вопрос 4 — вариант B. budget_usd: 45; задача — монолит, обоснование — в «Оценке объёма».

Расширение зон разрешено: orchestrator/advance_gates/zones.py, scripts/guard.py, scripts/ci_protected_paths.py, orchestrator/github_adapter.py
