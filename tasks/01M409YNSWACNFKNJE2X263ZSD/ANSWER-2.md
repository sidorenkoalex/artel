---
task: 01M409YNSWACNFKNJE2X263ZSD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

---
task: 01M409YNSWACNFKNJE2X263ZSD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. **Три метода `DonePathSnapshotTest` — вариант (а), мандат как
   сделано.** Основание: прежние утверждения требовали ссылку внешней
   задачи в `origin` пульта — прямо против AC-5 SPEC (ADR-0021 п.3);
   проверяемые строки RETRO и сообщения коммита сохранены. Каждый метод
   несёт «Ловит мутацию: …».

Ослабление тестов разрешено: tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_transition_publishes_a_snapshot_like_killed_does, tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_snapshot_retro_names_the_done_outcome_and_the_ref, tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_snapshot_removes_the_pult_artifact_branch

2. **`test_external_target_cwd_is_its_workspace` — вариант (а), принять.**
   Заведение клона проекта пультом — этап 2 ADR-0021; переписать метод
   там. Отметь это в PLAN, «Риски».

3. PLAN — в `status: ready`; прочее не менять.
