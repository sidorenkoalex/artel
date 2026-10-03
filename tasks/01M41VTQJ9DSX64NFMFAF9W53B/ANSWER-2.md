---
task: 01M41VTQJ9DSX64NFMFAF9W53B
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

---
task: 01M41VTQJ9DSX64NFMFAF9W53B
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. **Мандат ANSWER-1 уточнён.** Элементы уровня класса гейт не
   сопоставляет с методами, поэтому файл режима guard разрешён целиком
   (путём файла): все его методы проверяют снимаемый режим
   `--artifact-branch`, сохранённый метод не ослабляется. Три метода
   `tests/test_ci_push_class.py` — как в ANSWER-1. Решение Оператора
   04.10.2026.

Ослабление тестов разрешено: tests/test_guard_artifact_branch_mode.py, tests/test_ci_push_class.py::AdrClassificationTest::test_artifact_branch_is_code_false_without_touching_git_or_gh, tests/test_ci_push_class.py::AdrClassificationTest::test_artifact_branch_code_is_false, tests/test_ci_push_class.py::OutputFormatTest::test_script_prints_code_and_reason_lines
