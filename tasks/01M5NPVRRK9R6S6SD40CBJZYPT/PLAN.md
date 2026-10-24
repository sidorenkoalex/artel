---
task: 01M5NPVRRK9R6S6SD40CBJZYPT
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Прогон планки после подтяжки main — на дереве с приложениями PLAN

## Подход
Правка одной функции `pull._materialize_and_run_plank`
(`orchestrator/pull.py`) по образцу рубежа `in_dev -> verifying`
(`orchestrator/advance_gates/acceptance.py:598`):

- Прежние проверки (планка не найдена, перечень долгоживущих не прочитан,
  `ComponentsPending`) и прежняя материализация в рабочую копию с учётом
  `preexisting` остаются как есть и идут первыми (требование 3).
- Непосредственно перед `acceptance.run` — `appendix_tree.suite_tree(conn,
  task_id, wt_path, not_run="планка после подтяжки <ветка> не прогнана")`
  под `contextlib.ExitStack`.
- `tree.root is None` — запись журнала `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION`
  (`fixable=True`) либо `PLAN_APPENDIX_GATE_FAILURE_ACTION` (`fixable=False`)
  с `tree.refusal`, возврат `Refused(tree.refusal)`; планка не запускается,
  состояние не меняется.
- `tree.root != wt_path` — планка выкладывается во временное дерево
  `acceptance.plank_in_code_copy(task_id, <ветка документов>, tree.root)`,
  прогон (с долгоживущими `extra`, тем же вызовом) — с `cwd=tree.root`.
  Выход из `ExitStack` убирает выкладку и дерево на любом исходе, включая
  исключение (AC-5).
- `tree.root == wt_path` — прогон прежний: `tdir` из рабочей копии,
  `cwd=wt_path` (AC-2, `tests/test_pull.py:240`).
- Красный/зелёный итог — прежние тексты и исходы (`Conflict` + `escalated` /
  `Pulled`).

Тесты: все AC-1…AC-7 покрыты долгоживущим файлом задачи
`tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py` (pytest-стиль
`unittest`-классов песочницы, «Ловит мутацию:» у каждой функции; красен на
базе по записке test_author). Своих тестов сверх него не добавлял — свойств
вне его покрытия правка не вводит (правило coding-standards: свои тесты —
только на непокрытые свойства).

## Шаги
1. `orchestrator/pull.py::_materialize_and_run_plank` — дерево `suite_tree`,
   отказ по `tree.fixable`, выкладка `plank_in_code_copy` во временное дерево;
   импорт `contextlib`. Регенерация `docs/codebase-map.md`.
2. Прогон долгоживущего файла задачи и тестов затронутых модулей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 2 (долгоживущий файл test_author) |
| 6 | 1–2 (существующие тесты не правились) |

## Влияние на систему
- Затрагивает только путь подтяжки main (`pull.evaluate` → ворота мержа,
  `pull-main`, предшаговая подтяжка `runner`). Обработка `Refused` вызывающими
  не менялась: на `pull-main` отказ по приложению по-прежнему эскалируется.
- Гейты, лимиты, тесты не ослабляются: проверка стала строже/точнее —
  тот же узел дерева, что у рубежа verifying и автогейта; отказ по
  приложению теперь виден записью журнала до прогона.
- Прогоны: `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py` +
  `tests/test_pull.py` — 26 passed; тесты вызывающих pull (20 файлов:
  `test_pull_*`, `test_runner_pre_step_pull`, `test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main`,
  `test_long_lived_transitions`, `test_merge_gate_ci_wait` и др.) — 365 passed.
  `plank-run`: «планки нет … нет файлов test_*.py» — ожидаемо, планка целиком
  долгоживущая.
- Откат — revert коммита правки `pull.py`.

## Риски
- Временное дерево добавляет `git worktree add` + наложение на каждую
  подтяжку задачи артели с приложениями — секунды; без приложений поведение
  прежнее.

## Предложения системе
- `plank-run` отказывает «планки нет» для планки, целиком долгоживущей
  (только `long_lived.sha256.txt`), — не гоняет долгоживущие файлы перечня;
  разработчику приходится гонять их `pytest` напрямую (`orchestrator/plank_run.py`).
- `pytest -n` в рабочей копии роли падает «node down» на всех воркерах —
  в миссии/скиле стоит прямо сказать, что xdist в шаге не работает.
