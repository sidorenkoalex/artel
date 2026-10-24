---
task: 01M5NPVRRK9R6S6SD40CBJZYPT
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/pull.py, docs/codebase-map.md, tests/
budget_usd: 30
---

# SPEC: Прогон планки после подтяжки main — на дереве с приложениями PLAN, как на рубеже in_dev → verifying

## Контекст
После подтяжки main в ветку задачи `pull._materialize_and_run_plank`
(`orchestrator/pull.py:592`) материализует планку в рабочую копию задачи и
гоняет её `acceptance.run(tdir, cwd=wt_path, …)` (около :677–681) — на дереве
БЕЗ приложений PLAN. Рубеж `in_dev → verifying`
(`orchestrator/advance_gates/acceptance.py:598`) и автогейт
(`orchestrator/fsm_autogate.py:417`) гоняют ту же планку на дереве
`appendix_tree.suite_tree(…)` — HEAD рабочей копии плюс приложения PLAN.
Расхождение дало три ложные эскалации (01M5KP57JX, 01M5MVSP9Y,
01M5NHXJA3X7C66XTJN4J3E25W — 8 тестов планки красные после подтяжки
`ImportError` на классе, который вводит Приложение 4, при зелёном прогоне на
рубеже verifying и на автогейте). Сверено ТЗ с origin/main bee11bcc.

## Требования

1. `pull._materialize_and_run_plank` гоняет планку и долгоживущие файлы
   перечня на дереве `appendix_tree.suite_tree(conn, task_id, wt_path,
   not_run=<«планка после подтяжки не прогнана»>)` — HEAD рабочей копии после
   слияния плюс приложения PLAN. Когда дерево временное (`tree.root` ≠
   `wt_path`), планка выкладывается в него тем же узлом, что на рубеже
   verifying, — `acceptance.plank_in_code_copy(task_id, <ветка документов
   задачи>, tree.root)`. Когда `tree.root == wt_path` (задача не артели или
   PLAN без приложений) — прежняя материализация
   `acceptance.materialize_from_branch` в рабочую копию с прежним учётом
   `preexisting`: каталог `tasks/<id>/acceptance_tests/`, лежавший в рабочей
   копии до вызова, сохраняется (`tests/test_pull.py:240`); поведение прежнее.
2. Отказ разбора или наложения приложений после подтяжки — переход
   отклоняется записью журнала того же класса, что на рубеже verifying (по
   `tree.fixable`: `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION` при
   `fixable=True`, `PLAN_APPENDIX_GATE_FAILURE_ACTION` при `fixable=False`,
   например при сбое git во время построения дерева), с причиной; планка не
   запускается, итог не зелёный (не `Pulled`), состояние не меняется на
   `escalated` молча. Обработка такого `Refused` вызывающим кодом не
   меняется: на пути `pull-main` (`operator_pull`) любой `Refused`
   по-прежнему эскалируется (`orchestrator/pull.py:833–839`, вне зоны), и
   это допустимо.
3. Порядок проверок: прежние проверки «планка не найдена в источнике»,
   «перечень долгоживущих файлов не прочитан» и `ComponentsPending` идут
   раньше построения дерева, без изменения порядка и текстов; `suite_tree`
   строится непосредственно перед прогоном (`acceptance.run`).
4. Красный итог — прежняя эскалация с прежним текстом («приёмочные тесты
   красные после подтяжки …»); зелёный — прежнее `Pulled`. Слияние, его
   сохранение, тексты и порядок прочих проверок `pull` не меняются.
5. Тесты — новый файл в `tests/`, в стиле pytest (ADR-0027); у каждой
   тестовой функции — строка «Ловит мутацию:». Файл покрывает случаи
   критериев AC-1–AC-5.
6. Существующие тесты не правятся.

## Критерии приёмки

AC-1. Задача артели, PLAN несёт приложение к защищённому файлу, планка
проверяет результат этого приложения: после подтяжки main
`_materialize_and_run_plank` даёт зелёный итог (`Pulled`), планка выложена в
дерево с приложениями и исполнена в нём (на текущем коде main тот же сценарий
даёт красный итог и `escalated`).

AC-2. Задача без приложений PLAN (в том числе задача не артели): планка и
долгоживущие файлы перечня гоняются прежним прогоном с `cwd` — рабочей копией
задачи `wt_path` (проверяется шпионом на `cwd` вызова прогона).

AC-3. Вне пути `pull-main` (без `operator_pull`) приложение PLAN не
разбирается или не накладывается после подтяжки: в журнале задачи запись с
действием `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION` и причиной отказа;
итог — не `Pulled`, состояние задачи не становится `escalated`, планка не
запускается. Сбой построения дерева с `tree.fixable=False` (например, сбой
git) — то же, но запись с действием `PLAN_APPENDIX_GATE_FAILURE_ACTION`.

AC-4. Приложение, уже наложенное в подтянутом main, пропускается
(`plan_appendix.skip_in_base`), планка на дереве прогона зелёная, итог
`Pulled`.

AC-5. Временное дерево прогона после зелёного прогона и после исключения,
поднятого во время прогона, удалено с диска.

AC-6. Красный итог планки на дереве с приложениями — переход в `escalated` с
прежним текстом «приёмочные тесты красные после подтяжки <имя главной
ветки> (слияние сохранено, откат не выполняется)» и хвостом прогона; итог
`Conflict`.

AC-7. Долгоживущие файлы перечня (при зафиксированной планке) гоняются в том
же прогоне и на том же дереве, что планка.

## Оценка объёма и деление

Сработавший сигнал: `budget_usd` ≥ $30 (бюджет $30 задан в ТЗ Оператором).
Прочие сигналы не срабатывают: зон 3, критериев 7, прогноз диффа мал.

Обоснование монолита (материал для решения Оператора): правка — одна функция
`pull._materialize_and_run_plank` (смена дерева прогона и отказ по
приложениям) и новый файл тестов к ней. Разрезать её по зонам нечего: смена
дерева без отказа по `tree.fixable` оставила бы отказ наложения без записи
журнала (требование 2), а тесты без правки красны по случаю AC-1.

## Не входит

- Изменение порядка наложения приложений в цикле мержа.
- Правка планки задачи 01M5NHXJA3 (её снимают эта задача и повторный approve).
- Изменение `appendix_tree.suite_tree` и прочих модулей «только чтение» ТЗ
  (`orchestrator/appendix_tree.py`, `orchestrator/advance_gates/acceptance.py`,
  `orchestrator/fsm_autogate.py`, `orchestrator/acceptance.py`,
  `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/fsm_merge_gate.py`,
  `tests/fixtures.py`, `tests/sandbox.py`).
- В `orchestrator/pull.py` — что-либо вне `_materialize_and_run_plank`, в том
  числе обработка `Refused` на пути `pull-main` (:833–839): там отказ
  наложения по-прежнему эскалируется; в `tests/` — правка существующих файлов
  (только новые).
- Зелёный полный набор `tests/` (существующие тесты остаются зелёными) — её
  держит пульт.

## Материалы

- Строка копилки 23.10 «Ворота мержа после подтяжки main гоняют приёмочную
  планку ДО наложения приложений PLAN…».
- `orchestrator/pull.py:592` (`_materialize_and_run_plank`), :620, :677–684;
  обработка `Refused` вызывающим — :833–839.
- `orchestrator/advance_gates/acceptance.py:598` — образец: `suite_tree` →
  `plank_in_code_copy`, отказ по `tree.fixable`;
  `PLANK_NOT_RUN` — `orchestrator/advance_gates/acceptance.py:34`.
- `acceptance.plank_in_code_copy` (`orchestrator/acceptance.py:2027`) в
  `finally` удаляет `tasks/<id>/` целиком без учёта `preexisting` — поэтому
  для `tree.root == wt_path` прежняя материализация (требование 1).
- Константы действий — `orchestrator/advance_gates/plan_appendix.py:28`, :40.
- В ТЗ путь «orchestrator/plan_appendix.py» — фактически
  `orchestrator/advance_gates/plan_appendix.py`.
- Решения Оператора на гейте SPEC 24.10.2026, круг 1 (по SPEC-AUDIT.md):
  пп. 1–4 и мелочи внесены в требования 1–3 и AC-3, AC-6.
