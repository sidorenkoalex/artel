---
task: 01M4BEGQAVVWCHFCW6BEBB0XVT
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Гейт приёмки принимает итог CI того же дерева; разработчик не гоняет полный набор

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | Не выполнено | При ошибке чтения дерева путь не переходит на локальный набор. |
| 2 | Не выполнено | Вместо локального запуска при недоступности вычисления дерева выбрасывается исключение. |
| 3 | OK | Вызов полного набора гейтом мержа не менялся. |
| 4 | OK | Приложение PLAN заменяет штатный `suite-run` правилом о планке и тестах затронутых модулей; `suite-run --failed` сохранён. |
| 5 | Не выполнено | Планка покрывает основные условия, но не содержит сценария ошибки вычисления дерева, который выявил дефект общего узла. |

## Замечания

- major — orchestrator/acceptance.py:1609-1615 — обработчик `OSError`/`ValueError`/`TimeoutExpired` задаёт только `gate_tree`, а `head_tree` при сбое первого вызова не инициализирован. Следующая строка выбрасывает `UnboundLocalError`, поэтому ни `approve`, ни автогейт не записывают причину и не запускают обязательный локальный полный набор. Воспроизводится подменой первого `suite_tree_hash` на `OSError`: `local_full_suite_calls=0`. Инициализировать оба значения до `try` либо в обработчике и добавить долгоживущий тест на ошибку чтения каждого дерева, ожидающий локальный запуск и однострочную причину.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/acceptance.py:1609-1615 | При ошибке первого `suite_tree_hash` используется неинициализированный `head_tree`. | Приёмка аварийно завершается вместо fail-closed локального прогона. | Инициализировать оба значения при ошибке и покрыть ошибки чтения деревьев тестом. |

## Вердикт

changes_requested: закрыть R1-F1.

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4BEGQAVVWCHFCW6BEBB0XVT` — 1 passed.
- `python3 -m pytest tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py tests/test_fsm_autogate.py tests/test_acceptance.py tests/test_ci_status.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 126 passed, 37 subtests passed.
- Изолированная подмена первого `acceptance.suite_tree_hash` на `OSError` — `UnboundLocalError`, `local_full_suite_calls=0`.
- `git diff --check 2a5d4a84bd98e8fd8f73180a124d7601fef27b9e...HEAD` — без ошибок пробелов.
