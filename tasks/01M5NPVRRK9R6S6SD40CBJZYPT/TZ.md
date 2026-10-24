---
task: 01M5NPVRRK9R6S6SD40CBJZYPT
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Прогон планки после подтяжки main — на дереве с приложениями PLAN, как на рубеже in_dev → verifying

# Прогон планки после подтяжки main — на дереве с приложениями PLAN, как на рубеже in_dev → verifying

## Факты

Строка копилки 23.10 «Ворота мержа после подтяжки main гоняют приёмочную планку ДО наложения приложений PLAN…» (третий случай). Случаи: 01M5KP57JX (AC-6, текст скила; исправлено amend-tests — пульт предупредил о девальвации планки), 01M5MVSP9Y (`_pult.apply_check` по HEAD), 01M5NHXJA3X7C66XTJN4J3E25W (ADR-0027, часть Б, 24.10.2026: после подтяжки main 8 тестов планки красные — `ImportError: cannot import name 'SharedFixturesWrapSandboxClassesInvariantTest' from 'tests.test_invariants'`, класс вводит Приложение 4; тот же прогон на рубеже verifying и на автогейте был зелёным «с приложениями PLAN»). Задача в `escalated`. Сверено с origin/main bee11bcc.

- После подтяжки main планку гоняет `pull._materialize_and_run_plank` (`orchestrator/pull.py:592`): `acceptance.materialize_from_branch` в рабочую копию задачи (:620), затем `acceptance.run(tdir, cwd=wt_path, …)` (около :677–681) — на рабочей копии без приложений; красный итог — `escalated` «приёмочные тесты красные после подтяжки …» (:684).
- Рубеж `in_dev → verifying` гоняет планку на дереве с приложениями: `appendix_tree.suite_tree(conn, task_id, run_cwd, not_run=PLANK_NOT_RUN)` (`orchestrator/advance_gates/acceptance.py:598`), затем `acceptance.plank_in_code_copy(task_id, branch, tree.root)`; отказ разбора или наложения — по `tree.fixable` (`PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION` либо `PLAN_APPENDIX_GATE_FAILURE_ACTION`). Автогейт — тот же узел (`orchestrator/fsm_autogate.py:417`). `suite_tree` пропускает приложение, уже наложенное в дереве (`plan_appendix.skip_in_base`).

## Требования

1. `pull._materialize_and_run_plank` гоняет планку и долгоживущие файлы перечня на дереве `appendix_tree.suite_tree(conn, task_id, wt_path, not_run=<«планка после подтяжки не прогнана»>)` — HEAD рабочей копии после слияния плюс приложения PLAN; планка выкладывается в это дерево тем же узлом, что на рубеже verifying (`acceptance.plank_in_code_copy`). Для задачи не артели и PLAN без приложений дерево — рабочая копия, поведение прежнее.
2. Отказ разбора или наложения приложений после подтяжки — переход отклоняется записью журнала того же класса, что на рубеже verifying (по `tree.fixable`), с причиной; состояние не меняется на `escalated` молча и не считается зелёным.
3. Красный итог — прежняя эскалация с прежним текстом; зелёный — прежнее `Pulled`. Слияние, его сохранение, тексты и порядок прочих проверок `pull` не меняются.
4. Тесты (новый файл в `tests/`, в стиле pytest — ADR-0027; у каждой функции — «Ловит мутацию:»): (а) задача артели, PLAN с приложением к защищённому файлу, планка проверяет результат приложения — после подтяжки main зелёная (на текущем коде красная); (б) задача без приложений — прежний прогон в рабочей копии (шпион на `cwd`); (в) приложение не накладывается после подтяжки — отказ записью журнала класса гейта применимости, не зелёный итог; (г) приложение уже в подтянутом main — пропускается (`skip_in_base`), планка зелёная; (д) временное дерево убрано после прогона и после исключения.
5. Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/pull.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу: в `orchestrator/pull.py` — только `_materialize_and_run_plank` (дерево прогона и отказ по приложениям); в `tests/` — только новые файлы.

Только чтение: orchestrator/appendix_tree.py, orchestrator/advance_gates/acceptance.py, orchestrator/fsm_autogate.py, orchestrator/acceptance.py, orchestrator/plan_appendix.py, orchestrator/fsm_merge_gate.py, tests/fixtures.py, tests/sandbox.py.

Не входит: изменение порядка наложения приложений в цикле мержа; правка планки задачи 01M5NHXJA3 (её снимают эта задача и повторный approve); изменение `suite_tree`.

Бюджет: $30.
