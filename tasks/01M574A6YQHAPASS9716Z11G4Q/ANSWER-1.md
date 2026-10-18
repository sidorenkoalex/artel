---
task: 01M574A6YQHAPASS9716Z11G4Q
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

## Ответ Оператора (последнее замечание аудита SPEC, визит 3)

doctor, проверка токена проекта на CI: 403 с текстом лимита запросов («API rate limit exceeded …») или иной временный отказ — от любого из двух эндпоинтов (check-runs или Actions) — даёт `skip` с причиной. `fail` за «Actions недоступны» — только для отказа правами: 403 «Resource not accessible …», 401, 404. Если оба эндпоинта ответили лимитом — `skip`.

Тесты автора тестов этому не противоречат (сценарий «check-runs 403 rate limit» → `skip`; «Actions недоступны» — только 403 «Resource not accessible» и 404). Случай «Actions 403 rate limit» в долгоживущих тестах не закреплён — покрой его своим тестом в зоне `tests/`, не правя файлы автора тестов.
