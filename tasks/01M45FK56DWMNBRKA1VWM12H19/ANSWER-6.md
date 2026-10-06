---
task: 01M45FK56DWMNBRKA1VWM12H19
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-6: ответ Оператора

## Ответы

Ответ Оператора (06.10) на вопрос 1: ни (а), ни (б). Решение — переписать приложение 1 под нынешний main (вариант Оператора C, проверен до ответа).

Почему: no_paths-зеркало уже в main (09256315), а «уже наложено» не признают гейт выхода in_dev по коду пульта (твоя правка придёт с мержем) и CI веток задач (scripts/plan_appendix_ci.py накладывает приложения прямо, неприменимое — CI красный). Приложение, применимое к нынешнему main прямо, проходит все узлы: гейт in_dev, планку (AC-13 и AC-14 — в ветви «применяется к HEAD»), CI, автогейт, мерж.

Сделай: в PLAN.md замени дифф в «## Приложение 1» ровно этим (проверено Оператором: git apply --check к targets.yaml main 09256315 проходит; guard.plan_appendices — без ошибок; после наложения no_paths = config.PROTECTED_PATHS, прочие поля и записи равны, «декларац» в файле нет):

```diff
diff --git a/targets.yaml b/targets.yaml
index f161d0c..ffc9cfd 100644
--- a/targets.yaml
+++ b/targets.yaml
@@ -28,6 +28,8 @@ targets:
     # гейты пульта (orchestrator/repo_context.py::protected_paths). У artel
     # перечень пульта — config.PROTECTED_PATHS, а это поле — его зеркало:
     # совпадение держит сторож tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py.
+    # Зеркало внесено в main вперёд кода задачи 01M45FK56DWMNBRKA1VWM12H19
+    # (решение Оператора 06.10, коммит 09256315).
     no_paths: [gates.yaml, roles.yaml, .github/, templates/, skills/, docs/invariants.md, tests/test_invariants.py, docs/adr/, CLAUDE.md, AGENTS.md, targets.yaml, models.yaml, model_sets.yaml, **/conftest.py, pyproject.toml, pytest.ini, setup.cfg, tox.ini]
     project_skills: []
     merge_gate: operator
```

Текст раздела над диффом обнови: приложение после операторского коммита 09256315 сводится к примечанию в комментарии записи artel; применимость — к main 09256315. Код задачи (в том числе правку _plan_appendix_gate и её тест) не меняй, планку не трогай. Сверь plank-run и сдавай ready.
