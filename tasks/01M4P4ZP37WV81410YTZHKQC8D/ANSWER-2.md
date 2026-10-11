---
task: 01M4P4ZP37WV81410YTZHKQC8D
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

---
task: 01M4P4ZP37WV81410YTZHKQC8D
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: планка поправлена Оператором (amend-tests, вариант A)

## Ответы

1. Вариант A исполнен Оператором командой `amend-tests` (ADR-0012 п.(а)):
   `test_ac8_skill_appendix.py` признаёт уже наложенное приложение по
   `git apply --reverse --check` на копии (частично наложенное — отказ) и
   дополнительно требует абзац «`artel.py preflight` … перед сдачей» в
   строках «+» приложения к скилу. Лок сдвинут (95eae7c5). Код и
   приложение PLAN не менять; повторить переход. Если планка на рубеже
   снова красна — эскалация с причиной.
