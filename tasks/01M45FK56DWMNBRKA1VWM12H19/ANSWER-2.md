---
task: 01M45FK56DWMNBRKA1VWM12H19
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Ответ Оператора (06.10) на эскалацию разработчика.

1. Вариант (б): обе правки как описано в эскалации, с переименованием методов — имена после правки должны говорить то, что метод проверяет (например, test_unresolved_external_target_refuses_without_git и test_external_target_checks_diff_by_project_perimeter; точные имена — на твоё усмотрение, по смыслу проверки). Подмена gitcmd.diff_base → boom в первом тесте остаётся; утверждение assertFalse(escalated) во втором остаётся. Основание: требования SPEC 1, 3, AC-5, AC-12 — пропуск проверки для внешнего проекта заменяется отказом/сверкой по перечню проекта.
Ослабление тестов разрешено: tests/test_plan_appendix.py::PlanAppendixGateTest::test_external_target_skips_the_gate
Ослабление тестов разрешено: tests/test_protected_paths_gate.py::MergeGateProtectedPathDiffGateTest::test_external_target_never_calls_diff_base

2. Вариант (а): сверка защищённых путей в зонах на гейте SPEC — у любого проекта, у артели — по config.PROTECTED_PATHS (согласуется с отказом new на защищённый путь в «Зоны:» ТЗ).

Красный tests/test_liveness.py::TerminateProcessGroupTest в suite-run — окружение роли (в PATH роли нет /bin, ps недоступен), к задаче не относится; не разбирай и не чини.
