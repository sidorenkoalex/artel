---
task: 01M1KVGD18P9H5WR7VM8TGPV1T
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Вопрос 1 — вариант A: все три защищённых пути (сторож в
.github/workflows/ci.yml, запись в docs/invariants.md, инвариант-тест
в tests/test_invariants.py) остаются в объёме; поставка — unified-diff-
приложениями к PLAN.md (git apply --check перед сдачей), Оператор
применяет их после merge_gate. Механика требования 1 — «оба»:
проверка в tests/sandbox.py плюс CI-сторож. Старт in_dev — после мержа
задачи 01M1KVG3KSCY47HWXWF5HM0E76 (автокоммит с .gitignore).
