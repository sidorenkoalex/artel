---
task: 01M583RM59DHDRDH877AERAVMD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

# Ответ Оператора на вопрос 1 разработчика

Вариант (б), исполнен Оператором: исключение в `tests/test_invariants.py` не добавляется. Ожидание в `EarlySignalCanaryTest::reap_observed` переписано через помощник песочницы `tests/sandbox.py::wait_processes_gone` (тот же срок: 200 проверок по 0,05 с = 10 с), неиспользуемый `import time` снят; утверждения теста не менялись. Правка зафиксирована командой `amend-tests` (лок 749637c9 -> 6b3e6b27, кодовая ветка -> ffe7c593).

Дальше: повторить `suite-run --failed` и, если зелёный, продолжать без правок кода задачи.
