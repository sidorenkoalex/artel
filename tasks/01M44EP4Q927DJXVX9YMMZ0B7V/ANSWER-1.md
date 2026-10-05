---
task: 01M44EP4Q927DJXVX9YMMZ0B7V
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора по эскалации разработчика.

Вопрос 1 — вариант A: в orchestrator/pull.py и orchestrator/advance_gates/acceptance.py заменить проверку `(…/"acceptance_tests").is_dir()` на `acceptance.plank_present(…/"acceptance_tests")` — ровно две строки, поведение отказа «планка не найдена в источнике» сохраняется. Добавь в PLAN.md раздел «## Расширение зон» со строкой «Пути: orchestrator/pull.py, orchestrator/advance_gates/acceptance.py» и обоснованием.

Вопрос 2 — мандат на 2.1–2.6 в предложенном виде: в 2.1–2.5 меняется только текст рецепта/подсказки под требование 6; в 2.6 из снимка каталога выкладки в observed_run (setUp) исключается acceptance.PLANK_HELPER_NAME, утверждения методов не меняются. Методы не удаляются и не переименовываются.

Расширение зон разрешено: orchestrator/pull.py, orchestrator/advance_gates/acceptance.py
Ослабление тестов разрешено: tests/test_guard_artifact_disk_read.py::DiskReadFormsTest::test_error_text_carries_the_artifact_branch_recipe, tests/test_guard_artifact_disk_read.py::DiskReadFormsTest::test_every_artifact_name_is_covered, tests/test_guard_artifact_disk_read.py::AnchoringTest::test_recipe_names_the_artifact_not_the_literal_fragment, tests/test_fsm_advance_tests_writing_artifact_source.py::ArtifactSourceGateTest::test_disk_reading_plank_is_refused_with_named_action, tests/test_fsm_advance_tests_writing_artifact_source.py::RefusalClassTest::test_refusal_surfaces_in_test_author_brief_history, tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py::DraftInTestsWritingTest::test_ac1_tests_writing_runs_draft_with_pult_runner, tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py::FixedPlankAfterTestsWritingTest::test_ac2_later_states_run_fixed_plank_and_single_file
