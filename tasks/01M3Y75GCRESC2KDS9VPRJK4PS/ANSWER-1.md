---
task: 01M3Y75GCRESC2KDS9VPRJK4PS
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. Вопрос 1 — вариант а) исполнен Оператором через `amend-tests`: в `_PinUpdateSandbox.setUp` добавлена подмена `ci.main_line_status` зелёным статусом (`patcher.start()`/`addCleanup(patcher.stop)`), импорт `ci`; сумма в `acceptance_tests/long_lived.sha256.txt` обновлена командой, лок сдвинут. Прогон файла после правки — 8 passed. Сам файл планки больше не трогать.
2. Вопрос 2 — да, решение верное: проверку CI в `pin-update` (`_refuse_unless_main_ci_green`) не ослаблять.
3. Дальше: прогнать адресные тесты задачи и тесты pin/doctor после подтяжки, других правок не делать; PLAN.md — `status: ready`.
