---
task: 01M4BEGQAVVWCHFCW6BEBB0XVT
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Гейт приёмки принимает итог CI того же дерева; разработчик не гоняет полный набор

## Соответствие SPEC

### Фаза A: гейт плана

Покрытие полное: шаг 1 реализует общий узел для `approve` и автогейта, условия CI и регенерацию карты; шаг 2 содержит замену правила разработчика проверяемым приложением; шаг 3 закрывает найденный сценарий отказа чтения дерева. Шаги имеют проверяемый размер и не меняют гейт мержа. Подход соответствует существующей архитектуре: оба пути используют один `acceptance.acceptance_suite`, а гейт мержа сохраняет прямой вызов `full_suite`.

### Фаза B: ревью MR

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `approve` и автогейт вызывают общий `acceptance_suite`; CI принимается лишь после совпадения деревьев, свежести от `origin/main` и доказанного зелёного полного набора. |
| 2 | OK | Любое недоказанное условие и отсутствие ответа CI ведут к локальному `full_suite` с однострочной причиной в журнале; `fresh_suite` принудительно выбирает локальный запуск. |
| 3 | OK | Гейт мержа не переведён на новый узел и продолжает вызывать `full_suite` напрямую. |
| 4 | OK | Приложение PLAN заменяет штатный полный запуск правилом о планке и затронутых модулях, сохраняет `suite-run --failed`; защищённый файл в кодовой ветке не изменён. |
| 5 | OK | Долгоживущая планка покрывает принятие CI, все причины локального запуска и свежий запуск; R1-F1 добавляет постоянный тест отказа чтения каждого из двух деревьев. Тесты не ослаблены. |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:1609-1615; tests/test_acceptance.py:430-465 | При сбое первого `suite_tree_hash` использовалось неинициализированное `head_tree`. | Приёмка аварийно завершалась вместо fail-closed локального прогона. | Обработчик задаёт `None` обоим деревьям; `AcceptanceSuiteTreeFailureTest` подтверждает локальный запуск и однострочную причину при сбое чтения дерева гейта и головы. |

## Вердикт

approved

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4BEGQAVVWCHFCW6BEBB0XVT` — 1 passed.
- `python3 -m pytest tests/test_acceptance.py tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py tests/test_fsm_autogate.py tests/test_ci_status.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 127 passed, 39 subtests passed.
- `git diff --check main...HEAD` — ошибок пробелов нет.
- `python3 scripts/guard.py /Users/al.sidorenko/projects/artel/.artel/projects/artel/tasks/01M4BEGQAVVWCHFCW6BEBB0XVT/REVIEW.md` — `GUARD: ок (1 файлов)`.
- Точечно прочитан полный diff затронутых модулей и тестов (`git diff main...HEAD -- orchestrator/acceptance.py orchestrator/ci.py orchestrator/fsm.py orchestrator/fsm_autogate.py tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py tests/test_acceptance.py tests/test_fsm_autogate.py tests/test_ci_status.py`), поскольку инкрементальный пакет содержал только изменение после R1-F1, а для вердикта требовалась сверка всех требований SPEC с MR.
