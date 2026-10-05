---
task: 01M45FJD46BX45VHC36S4VS9QN
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Решение Оператора по эскалации разработчика.

Вариант (а): мандат на смену утверждений восьми методов ровно по разделу SPEC «Меняемое поведение» — меняется исход «не блокирует» → «блокирует», утверждения наблюдения, мандатных отметок и ревью-пакета сохраняются, докстринги приведены к новому поведению. Методы не удаляются; переименование test_ac8_merge_gate_journals_and_does_not_escalate не делать (имя расходится с поведением — допустимо, отметь в PLAN «Риски»).

Ослабление тестов разрешено: tests/test_test_integrity_gate.py::AssertionObservationTest::test_transition_passes_and_journals_both_context_cases, tests/test_test_integrity_gate.py::AssertionObservationTest::test_mandate_marks_only_covered_findings, tests/test_test_integrity_gate.py::AssertionObservationTest::test_merge_gate_and_review_package_carry_the_same_findings, tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py::VanishedDeletedUnparsableTest::test_ac5_vanished_method_has_single_finding, tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py::VanishedDeletedUnparsableTest::test_ac5_deleted_file_has_no_assertion_finding, tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py::MandateMarkTest::test_ac7_method_mandate_marks_only_named_method, tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py::MandateMarkTest::test_ac7_other_method_mandate_does_not_mark, tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py::MergeGateObservationTest::test_ac8_merge_gate_journals_and_does_not_escalate
