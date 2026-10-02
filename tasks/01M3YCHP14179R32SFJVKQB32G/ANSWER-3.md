---
task: 01M3YCHP14179R32SFJVKQB32G
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

1. Перенос SQL в `orchestrator/store.py` уже сделан и лежит в worktree незакоммиченным: пульт коммитит результат шага только в пределах zones и `zones_extension`, а `zones_extension` выставляется лишь при разделе «## Расширение зон» в PLAN.md. Единственное действие этого шага — добавить в `tasks/01M3YCHP14179R32SFJVKQB32G/PLAN.md` раздел «## Расширение зон» со строкой «Пути: orchestrator/store.py» и одним предложением основания (мандат ANSWER-2, инвариант «SQL только в store.py»). Код не менять, `orchestrator/store.py` и прочие файлы не трогать.

Расширение зон разрешено: orchestrator/store.py
