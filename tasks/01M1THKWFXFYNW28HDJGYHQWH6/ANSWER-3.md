---
task: 01M1THKWFXFYNW28HDJGYHQWH6
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

---
task: 01M1THKWFXFYNW28HDJGYHQWH6
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

1. Вариант **(a)**. Планка обновлена Оператором через `amend-tests`:
   метод `test_ac7_invariant_ten_names_plan_as_a_channel` снят и заменён
   маркером `# AC-7: manual` по прецеденту AC-9 — формулировку инварианта
   10 с каналом PLAN Оператор проверяет по приложению «## Приложение:
   инвариант 10» в PLAN.md и вносит в docs/invariants.md своим коммитом
   после мержа. Три остальных метода AC-7 остаются исполняемыми.
   Правило п.3 ANSWER-1/2 в силе: `docs/invariants.md` в код-ветке
   остаётся равным main, код не менять.

2. Дальше: прогони планку целиком (ожидается 12 из 12 исполняемых
   зелёные), доведи PLAN.md до `status: ready`.
