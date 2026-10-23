---
task: 01M5MVSP9YW0DYA4YQ1KSG0AHF
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора 23.10.2026 по эскалации (тест-навязывает-устройство): вариант (а). Тест acceptance_tests/test_ac2_plan_appendix.py::PlanAppendixTest::test_ac2_lint_class_green_with_appendix поправлен командой amend-tests (планка 68489f27 -> 7d9ceee6): признак «приложение уже в дереве» берётся по скопированным файлам — git apply --check, иначе git apply --check --reverse; утверждения о зелёном DeterministicTestsLintTest и test_rule_corpus_is_frozen не менялись. Код задачи (4f30324d) не трогать ради этого теста; продолжай с перехода in_dev -> verifying. Системная причина (apply_check по HEAD против дерева прогона без коммита) вынесена строкой бэклога — в этой задаче её не чинить.
