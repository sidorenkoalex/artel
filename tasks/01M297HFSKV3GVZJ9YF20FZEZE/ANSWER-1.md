---
task: 01M297HFSKV3GVZJ9YF20FZEZE
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

## Ответы

1. Вариант **A** — только self/артель. `workspace.ensure` заводит НОВУЮ
   ветку задачи от `origin/<MAIN_BRANCH>` артели (после `git fetch
   origin <MAIN_BRANCH>`), сигнатура `workspace.ensure(task_id, branch)`
   не меняется, `fsm._origin_main_source` из `workspace.py` не
   импортируется — self-случай там литерал `("origin", config.
   MAIN_BRANCH)`, его достаточно. Фраза ТЗ про внешний target — принцип
   источника на будущее, не новая способность сейчас; внешние target
   через worktree главной копии не ходят (`runner.role_cwd`), и это не
   меняется. Зоны — как в ТЗ (`orchestrator/workspace.py`,
   `orchestrator/doctor/`, `orchestrator/catalog.py`, `tests/`), рамка
   $35. Требования 2 и 3 (проверка doctor и предупреждение `new` о
   незапушенных коммитах главной копии) — без изменений, «главная
   копия» — одна, `config.ROOT`.
