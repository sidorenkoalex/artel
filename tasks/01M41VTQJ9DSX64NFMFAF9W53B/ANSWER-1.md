---
task: 01M41VTQJ9DSX64NFMFAF9W53B
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M41VTQJ9DSX64NFMFAF9W53B
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. **Мандат на тесты снимаемого механизма (требование 6 SPEC) — выдан
   по эскалации developer.** Тесты ниже проверяют режим
   `scripts/guard.py --artifact-branch` и класс `artifact/` в
   `scripts/ci_push_class.py`, которые задача по ADR-0021 (пп. 12–13,
   этап 1) убирает. Удаление или правка — только в объёме снятия
   механизма, с перечнем в PLAN; остальные тесты этих файлов (если
   проверяют не снимаемое) не ослабляются. Решение Оператора 04.10.2026
   («по рекомендациям»).

2. **Перечень — по разделу «Эскалация» PLAN** (первый тест переименован
   с заменой утверждения на обратное — класс `artifact/` снят, ветка
   теперь «код»; второй удалён, его держит долгоживущий AC-1; третий —
   смена входа; методы режима guard удалены вместе с функциями, их
   держат долгоживущие `test_ac2_*`). Принято.

Ослабление тестов разрешено: tests/test_ci_push_class.py::AdrClassificationTest::test_artifact_branch_is_code_false_without_touching_git_or_gh, tests/test_ci_push_class.py::AdrClassificationTest::test_artifact_branch_code_is_false, tests/test_ci_push_class.py::OutputFormatTest::test_script_prints_code_and_reason_lines, tests/test_guard_artifact_branch_mode.py::IsDraftLenientTest, tests/test_guard_artifact_branch_mode.py::BasicFrontmatterErrorsTest, tests/test_guard_artifact_branch_mode.py::CheckContentDefaultIsUnaffectedTest::test_explicit_false_matches_the_default, tests/test_guard_artifact_branch_mode.py::CheckContentDefaultIsUnaffectedTest::test_mode_true_on_a_lenient_draft_returns_only_basic_errors, tests/test_guard_artifact_branch_mode.py::CheckContentDefaultIsUnaffectedTest::test_mode_true_on_a_non_lenient_type_is_unaffected
