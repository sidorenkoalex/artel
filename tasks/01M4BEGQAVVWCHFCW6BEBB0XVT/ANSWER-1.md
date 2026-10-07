---
task: 01M4BEGQAVVWCHFCW6BEBB0XVT
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора 07.10 по эскалации: оба вопроса — предпочтительный вариант. Планка исправлена Оператором через amend-tests (лок 5c367926):
1. `CiAutogateTest`: в подставной ответ check-runs добавлен `details_url` с ID прогона (как в `CiAcceptanceTest`). `check_suite.id` как ID прогона не записывать — это не ID прогона.
2. `CiAcceptanceTest::test_ac4_bad_ci_or_stale_branch_runs_local_suite`: строки причины считаются только среди записей действия `полный набор локально`. Отдельная строка причины и запись об исходе локального набора сохраняются.
Подтяни ветку, прогони затронутые тесты и планку, отметь правку планки в PLAN со ссылкой на решение Оператора и сдай PLAN со статусом `ready`.
