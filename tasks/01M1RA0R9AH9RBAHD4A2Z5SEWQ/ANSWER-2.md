---
task: 01M1RA0R9AH9RBAHD4A2Z5SEWQ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

# ANSWER-2

Диагноз принят: оба дефекта были в песочнице планки, не в коде. Вариант (а)
исполнен Оператором командой `amend-tests` (лок планки сдвинут на
4df2eedd): `_sandbox.py::advance_from_in_dev` теперь кладёт на диск SPEC.md
и непустой `acceptance_tests/` до перехода (метод `write_acceptance_plank`,
по образцу `tests/test_fsm_map_conflict_autoresolve.py`), а два ожидания
вызова приёмки проверяют позиционный каталог планки и
`code_root=<worktree>` отдельно.

Планка на коде ветки (77f3cfc1 + подтяжки) — 7/7 OK; на main — 6 падений,
то есть планка ловит отсутствие фичи. Код менять не нужно: обнови PLAN.md
(status: ready, вопросы сняты) и заверши шаг. Полный `tests/` не запускай.
