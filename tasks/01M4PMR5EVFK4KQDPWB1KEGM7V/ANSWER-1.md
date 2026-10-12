---
task: 01M4PMR5EVFK4KQDPWB1KEGM7V
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M4PMR5EVFK4KQDPWB1KEGM7V
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: мандат (а) на смену ожидаемого набора состояний метки конфликта

## Ответы

Решение Оператора 12.10.2026: вариант (а).

1. Смена ожидаемого кортежа в
   `tests/test_pull_conflict_marker_states.py::MarkedStatesSetTest::test_marked_states_are_exactly_the_three_returning_to_in_dev`
   с `("in_dev", "acceptance", "merge_gate")` на
   `("in_dev", "acceptance", "merge_gate", "verifying")` разрешена. Вид
   утверждения `assertEqual` прежний; докстринг и заявка «Ловит мутацию»
   обновляются под четыре состояния и продолжают называть дефектом
   дописанное пятое состояние (`review`, `spec_gate`) и выпадение любого
   из четырёх. Остальные методы файла не меняются.

2. Обязательная замена: добавить тест по образцу
   `MergeGateReturnGivesDeveloperItsStepTest` — конфликт подтяжки из
   `verifying` (через `pull-main`), `approve` с ANSWER возвращает задачу
   в `in_dev`, следующий `auto` запускает шаг developer без
   предварительного advance.

Ослабление тестов разрешено: tests/test_pull_conflict_marker_states.py::MarkedStatesSetTest::test_marked_states_are_exactly_the_three_returning_to_in_dev

Независимая проверка: спецаудитор задачи (SPEC-AUDIT, матрица, строка «PULL_CONFLICT_MARKED_STATES += verifying») — свойство «набор помечаемых состояний равен заданному» остаётся тем же assertEqual с кортежем из четырёх элементов; решение о переносе — за Оператором; принято.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| tests/test_pull_conflict_marker_states.py::MarkedStatesSetTest::test_marked_states_are_exactly_the_three_returning_to_in_dev — ожидаемый кортеж += verifying | Лишнее состояние в наборе меток ловится (review, spec_gate) — tests/test_pull_conflict_marker_states.py:169-179 | остаётся: тот же assertEqual на точный кортеж из четырёх | tests/test_pull_conflict_marker_states.py:178 с новым кортежем | ок |
| tests/test_pull_conflict_marker_states.py::MarkedStatesSetTest::test_marked_states_are_exactly_the_three_returning_to_in_dev — выпадение состояния | Выпавшее из набора состояние ловится — тот же assertEqual | остаётся | tests/test_pull_conflict_marker_states.py:178; tests/test_stack_zones_pull_section.py:106 (каждое состояние набора названо в docs/stack.md) | ок |
| Обоснование набора для verifying: возврат из эскалации конфликта подтяжки ведёт в in_dev к шагу разработчика | Кодом: pull.py:536 (эскалация без escalated_from), fsm.py:1379 (escalated_from or "in_dev"); тестом — только merge_gate, tests/test_pull_conflict_marker_states.py:270 | остаётся для трёх прежних; для verifying держится кодом, тестом не покрыто | не покрыто для verifying | ок при условии: разработчик добавляет тест по образцу MergeGateReturnGivesDeveloperItsStepTest — конфликт подтяжки из verifying, approve с ANSWER ведёт в in_dev, следующий auto запускает шаг developer без предварительного advance |
| Метка на эскалации конфликта подтяжки из verifying — проверка ответа на approve | fsm.py:1356 unanswered_role_step_escalation: после метки approve без ANSWER отказывает — tests/test_approve_no_answer_units.py | усиливается: эскалация pull-main с конфликтом требует ANSWER; прочие эскалации из verifying метку не получают (её пишет только pull.py:542) | tests/test_approve_no_answer_units.py без изменений | ок |
| Метка из verifying — читатели в auto и runner | auto.py:348 _role_step_since_state_entry, auto.py:736 _pull_conflict_marker_streak, runner.py:535 _pull_conflict_awaits_role_step — tests/test_runner_pre_step_pull.py, tests/test_pull_conflict_marker_states.py:321 | остаётся: метка гасится первым шагом developer или переходом состояния, как для merge_gate | tests/test_runner_pre_step_pull.py; tests/test_pull_conflict_marker_states.py:321 | ок |
