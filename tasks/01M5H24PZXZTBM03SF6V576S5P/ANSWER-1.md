---
task: 01M5H24PZXZTBM03SF6V576S5P
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора на эскалацию test_author (AC-6, AC-13, AC-19, AC-20, AC-21): имена — по дефолтам роли, обязательны для разработчика.

- Константа срока остановки дочерних (60 с): orchestrator/canary.py PARALLEL_STOP_GRACE_SEC.
- Константа предела одновременных дочерних (2): orchestrator/canary.py PARALLEL_CHILD_LIMIT.
- Функция ожидания дочернего процесса (шов подмены AC-20, AC-21): orchestrator/canary.py _wait_child.
- Функция сборки argv дочернего — имя также назначается до кода: orchestrator/canary.py _child_argv (если планке нужен этот шов).
Значения констант — по SPEC (60 и 2); тест сверяет PARALLEL_STOP_GRACE_SEC > 2 × GROUP_TERMINATE_GRACE_SEC.
