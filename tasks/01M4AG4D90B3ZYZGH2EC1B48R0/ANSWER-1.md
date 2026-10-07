---
task: 01M4AG4D90B3ZYZGH2EC1B48R0
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора 07.10: смена вида утверждения в объявленном тесте разрешена (вариант Б принят Оператором вместе с этой правкой теста).

Ослабление тестов разрешено: tests/test_codebase_map.py::SubpackageProjectionTest::test_tests_sections_still_keep_only_purpose

Объём мандата — ровно одна замена: `self.assertEqual(["Назначение"], self._labels(self.projected, "tests/test_x.py"))` → `self.assertNotIn("## tests/test_x.py\n", self.projected)` (новое свойство требования 5 SPEC: секции tests/* в проекции нет). Прочие утверждения метода и другие методы файла не меняются. Повтори advance.
