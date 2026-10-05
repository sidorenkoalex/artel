---
task: 01M446WEVJXARR5CDED8RE9CCR
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора по эскалации разработчика.

Вопрос 1 — вариант A: правка шести тестовых методов ровно как описано в эскалации (меняются только утверждения и один текст сценария под новое поведение AC-3 и требования 5.2; методы не удаляются и не переименовываются, остальные утверждения сохраняются).

Вопрос 2 — вариант A: исключение подкласса «роль ещё не закончила» из повтор-остановки оставить; от кружения его держит AUTO_STALL_STEPS_LIMIT. Четыре теста из вопроса 2 не трогать. Исключение и его причину описать в PLAN («Влияние на систему») и в докстринге refusal_classes.py.

Ослабление тестов разрешено: tests/test_auto_cycle.py::AutoStopsOnRepeatedAdvanceRefusalTest::test_ac1_identical_refusal_twice_in_a_row_stops_the_cycle, tests/test_auto_cycle.py::AutoStopsOnRepeatedAdvanceRefusalTest::test_ac3_two_different_refusal_texts_do_not_stop_the_cycle, tests/test_auto_cycle.py::PreAdvanceStillTriesOnLegitFirstEntryTest::test_legit_first_entry_does_not_skip_the_pre_advance, tests/test_auto_cycle.py::AutoRunsDeveloperOnMandateWithoutPlanSectionTest::test_without_a_mandate_stops_without_running_the_role, tests/test_auto_cycle.py::PreAdvanceMandateRefusalRepeatTest::test_other_in_dev_refusal_still_stops_on_the_second_repeat, tests/test_external_code_copy_refusal.py::ExternalCodeCopyRefusalTest::test_acceptance_run_refuses_with_the_ensure_reason
