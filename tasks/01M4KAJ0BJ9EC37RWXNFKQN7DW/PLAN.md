---
task: 01M4KAJ0BJ9EC37RWXNFKQN7DW
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: amend-tests — признак сетевых адресов только для артели

## Подход
`orchestrator/amend.py::_long_lived_errors` звал
`guard.long_lived_errors_from_files` без `network_addresses` (умолчание
`True`), поэтому у чужого проекта `amend-tests` отказывал по инварианту 35.
Правка — передать признак проекта так же, как выход из `tests_writing`
(`orchestrator/fsm_advance.py:468`):
`network_addresses=repo_context.is_artel(workspace.task_target(task_id))`.
Проект задачи берётся `workspace.task_target` — тем же путём, что уже
использует соседний `_task_profile` того же модуля. Признак читается через
атрибут модуля `repo_context.is_artel` (не импортом имени), чтобы подмена
признака проекта в тесте действовала. Обе точки вызова
`_long_lived_errors` (обычная правка ~796 и `--from-branch` ~1065) идут
через эту функцию, так что правка покрывает обе.

## Шаги
1. `orchestrator/amend.py`: импорт `repo_context`; в `_long_lived_errors`
   вызов узла с `network_addresses=repo_context.is_artel(...)`.
   Регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).
   Проверка — долгоживущий файл задачи
   `tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py`
   (AC-1..AC-4) и тесты модуля `amend`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (остальные проверки узла и `_long_lived_errors` не тронуты; AC-3) |
| 3 | 1 (у артели `is_artel` → `True`, поведение прежнее; AC-1) |
| 4 | 1 (существующие тесты не менялись; своих новых тестов нет — свойства покрыты долгоживущим файлом задачи) |

## Влияние на систему
- Затронут один вызов в `orchestrator/amend.py`; `scripts/guard.py`,
  `guard.network_address_hits` и инвариант 35 для артели не меняются.
- Прочие проверки долгоживущих файлов у чужого проекта сохраняются
  (строка группы, «Ловит мутацию», литералы каталога задач, удаление без
  потери методов).
- Проверено: долгоживущий файл задачи — 4 passed; тесты `amend`
  (`test_amend.py`, `test_amend_long_lived.py`, `test_amend_remove.py`,
  `test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`,
  `test_01m4jd36367e5cg3gxdv429xte_amend_pult.py` и файл задачи) —
  71 passed, 11 subtests passed. Временная мутация (вызов без признака)
  — AC-2 и оба подтеста AC-3 красные, правка возвращена.
- Полный набор: `suite-run` №1 — «зелёный прогон» (ветка ~4.9 тыс.
  тестов по логу; сводка печатает «прошло: 1, упало: 0»).
- Откат — revert одного коммита.

## Риски
- `workspace.task_target` при непригодной БД возвращает артель — признак
  тогда включён; это строгая сторона (ослабления нет).

## Предложения системе
- `plank-run` задачи только с долгоживущими файлами (без `test_*.py` в
  планке) отвечает «планки нет» — для такой задачи нет команды пульта,
  прогоняющей именно её долгоживущие файлы; гонял их `pytest` по имени.
- `suite-run --wait` зелёного полного прогона печатает «прошло: 1» при
  ~4.9 тыс. выполненных тестов по логу — счётчик сводки, похоже, считает
  не тесты (orchestrator/suite_run.py, `render`).
