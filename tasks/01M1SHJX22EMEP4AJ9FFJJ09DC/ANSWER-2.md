---
task: 01M1SHJX22EMEP4AJ9FFJJ09DC
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

---
task: 01M1SHJX22EMEP4AJ9FFJJ09DC
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. Вариант (а) в части решения, но исполнителем правки был Оператор:
   планка поправлена штатным каналом `amend-tests` (11.09, лок сдвинут
   db814ba3 -> 45c18dee): в
   `test_ac6_spec_gate_approve_rereads_budget.py:82` строка
   `assertIn("выше дефолта", out)` заменена на
   `assertIn("выше потолка ролей", out)`. Больше ничего в планке не
   менялось. `apply_spec_budget`/`spec_budget` оставь как есть — в
   границах ADR-0014 ч.1, как и предвидела SPEC.

Дальше: планку не трогай; прогони её синхронно (16 из 16), полный
`tests/` по правилам скила, PLAN.md — раздел «## Возврат — правка планки
AC-6 (ADR-0014)», status: ready, коммит до конца хода. Бюджет поднят до
$40, израсходовано $25.68 — один короткий ход.
