---
task: 01M1THKWFXFYNW28HDJGYHQWH6
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M1THKWFXFYNW28HDJGYHQWH6
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. Вариант **(a)**. Планка `acceptance_tests/` обновлена Оператором через
   `amend-tests` под порядок ADR-0015 (`in_dev -> verifying -> review ->
   acceptance`): в `_sandbox.py` `submit_plan` после первого `advance`
   при состоянии `verifying` пушит ветку в origin песочницы (заглушка
   зелёного CI) и зовёт второй `advance` (`verifying -> review`); при
   отказе перехода (AC-6) задача остаётся в `in_dev`, второго шага нет.
   `reach_acceptance` ведёт `review -> acceptance` одним `advance`,
   `verifying` уже позади. Остальные файлы планки не менялись.
   Код `orchestrator/` под старый порядок не подгонять.

2. После правки планки прогон Оператора: 12 из 13 зелёные. Красный —
   `test_ac1_ac2_ac3_first_submission.py::Ac1RaisesCeilingOnFirstSubmissionTest::
   test_ac1_higher_plan_budget_raises_ceiling_on_first_submission`, и
   это уже код, а не фикстура: журнальная запись «бюджет из PLAN |
   $90.00 (прежний потолок $45.00)» не называет источник `plan`, а
   AC-1 требует в журнале старый потолок, новый потолок И источник.
   Исправь текст записи (`orchestrator/fsm_advance.py::_apply_plan_budget`),
   например «бюджет из PLAN | $90.00 (прежний потолок $45.00, источник plan)»,
   прогони планку целиком, доведи PLAN.md до `status: ready`.

3. `docs/invariants.md` (инвариант 10) роль не правит — с 11.09
   инварианты и ADR меняет только Оператор своим коммитом. Сними правку
   строки 37 из ветки (верни файл к состоянию main) и приложи
   предлагаемую формулировку инварианта 10 в PLAN.md разделом
   «## Приложение: инвариант 10» — Оператор внесёт её после мержа.
   Так же с диффом `skills/coding-standards.md`: он остаётся приложением
   PLAN.md, в ветку не попадает (защищённый путь).
