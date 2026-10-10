---
task: 01M4JC58GZFHZ4PZHW254P22M2
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Деление переписывает merge_after зависящих задач

Родительская задача: 01M4JASKTKX6XYG5P2SACJYJH7 — Порядок старта в очереди зоны
Зоны: orchestrator/fsm.py, orchestrator/merge_after.py, docs/codebase-map.md, tests/
Порядок: первая, без зависимостей
Рамка: $25

Деление задачи на гейте SPEC (approve на `spec_gate` с секцией
«## Деление», `orchestrator/fsm.py::_spawn_division_subtasks`, ~819)
переводит родителя в `killed`, а `merge_after` задач, зависящих от
родителя, остаётся на нём — `orchestrator/merge_after.py::check` (~126) и
`merge_gate_refuses` (~387) отказывают зависящей задаче «зависимость
убита» (случай 05.10: 01M45FJD46 → подзадачи).

Требуется:
1. Деление задачи на гейте SPEC переписывает `merge_after` каждой задачи,
   зависящей от родителя: элемент-родитель заменяется последней
   подзадачей деления, прочие элементы остаются. Запись — через
   `merge_after.rewrite` (~286), с записью журнала зависящей задачи
   «было → стало».
2. Смена ожидания существующих тестов — только разделом SPEC «Меняемое
   поведение» (инвариант 38).

Критерий приёмки (направление): деление на гейте SPEC переписывает
`merge_after` зависящей задачи на последнюю подзадачу, журнал называет
«было → стало», гейт мержа зависящей задачи больше не отказывает
«зависимость убита» из-за родителя.

Только чтение: orchestrator/zone_lock.py, orchestrator/catalog.py,
orchestrator/runner.py, orchestrator/auto.py, scripts/guard.py,
orchestrator/advance_gates/, tests/test_invariants.py, docs/invariants.md,
docs/adr/, templates/, skills/.

Не входит: очередь старта зоны (отдельная подзадача); наследование набора
моделей подзадачами деления; поле «Порядок:» в ТЗ.