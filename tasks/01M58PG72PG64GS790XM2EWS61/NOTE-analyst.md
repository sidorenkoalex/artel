## Выяснено
- Итерация 5: ANSWER-2 прочитан. Ответ 1: `tools` заполняет один помощник `project_profile`, зовут его `decide` и `acceptance._task_own_profile`; ключ рабочего дерева с `tools`+суммы блокировок (при непустых `tools`); ключ базы прежний (без `tools`), одинаков у гейта мержа и `suite-run`; пробел suite_run.py:294 — в «Не входит» до G1б. Ответы 2-4 — A (разбор строк, имена строк doctor `project-tools/paths/workdir-…`, stdout→stderr, шов `doctor.subprocess.run`/`doctor.shutil.which`). AC-3 + `3.1`↔`3.12.0`, `2`↔`22.1` fail.
- Факты кода: ключ рабочего дерева — acceptance.py:2269 (`full_suite`), ключ базы — acceptance.py:2318-2322 и suite_run.py:523; `_task_own_profile` acceptance.py:2384-2410; `_names` project_checks.py:26-29; цикл записей cli.py:93-102.

## Где остановился
- SPEC.md переписан (тр. 7-8 по ANSWER-2, AC-3/AC-8/AC-11/AC-12, новые AC разбора), QUESTIONS.md удалён (через python os.remove — `rm` в шаге недоступен), guard ок, status: ready. 15 AC, budget 30 (рамка ТЗ; калибровка ~45 — отмечено в «Оценке объёма»).

## Чего не хватило
- Карта не показывает, кто строит `Profile` в обход `decide` — grep `from_values`.
