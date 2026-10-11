---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: мандат на смену вида утверждения в test_ac5 — с обязательной заменой

## Ответы

Ослабление тестов разрешено: tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::MergeGateStepsOnCloneTest::test_ac5_code_map_and_retro_are_committed_in_the_clone_merge_copy
Основание: решение Оператора 11.10.2026 — требование 2 SPEC убирает RETRO из main; смена вида утверждения (assertIn → assertNotIn) гейтом засчитывается как ослабление; независимая проверка Оператора: допустимо только с условием ниже.

Гейт неослабления отказал объявленной строке «Меняемое поведение» для этого
метода: смена вида утверждения разделом SPEC не покрывается, только мандатом.

Обязательное условие (без него — ослабление: метод ловит мутацию «шаги
артели для мержа из клона пропускают RETRO», а после одной лишь замены
пропущенный RETRO прошёл бы тест; AC-2 долгоживущего файла сценарий клона
не воспроизводит):

1. `self.assertIn(f"docs/retro/{task}.md", self.origin_tree(), self.msg(out))`
   → `self.assertNotIn(f"docs/retro/{task}.md", self.origin_tree(), self.msg(out))`.
2. В тот же метод, после `assert_merged_in_clone`, добавить проверку, что на
   origin клона в коммите закрытия есть RETRO задачи с итогом done, например:
   ```python
   retro = self.in_repo(self.origin, "show",
                        f"refs/artifacts/{task}:tasks/{task}/RETRO.md")
   self.assertIn("Итог: done", retro, self.msg(out))
   ```
   (путь `tasks/` — из константы, если она есть в модуле).
3. Остальные утверждения метода (`assert_merged_in_clone`, карта кодовой
   базы в origin/main) — без изменений; docstring поправить: RETRO в ссылке
   документов, не в main.

Иных правок существующих тестов этот ответ не разрешает.
