---
task: T024
type: spec
author_role: analyst
status: ready
schema_version: 2
budget_usd: 15
---

# SPEC: пустышка для живой проверки test_author (AC9 задачи T023)

## Контекст

Служебная задача-пустышка: единственная цель — прогнать живого
агента test_author через состояние tests_writing (manual-критерий 9
задачи T023). После прогона задача убивается.

## Требования

1. В orchestrator/config.py существует константа DEFAULT_BUDGET_USD.

## Критерии приёмки

AC-1. python3 -c "from orchestrator import config; assert
config.DEFAULT_BUDGET_USD > 0" завершается без ошибки.

AC-2. (manual) Оператор видит значение константы в выводе status/доки.

## Не входит

- Любые изменения кода: задача не будет реализовываться.

## Материалы

- tasks/T023/SPEC.md, критерий 9.
