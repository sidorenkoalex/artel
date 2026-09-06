---
task: 01M1TKP45EM16ZMJGQKNZA5T7J
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

# ANSWER-3: ответ Оператора

## Ответы

1. Эскалация «приёмочные тесты красные после подтяжки main»: конфликт
   разрешён верно, планка на коде ветки 322afccc — 17/18. Красен только
   `test_ac7_skill_names_sandbox_module_and_thin_overlay_rule`:
   требование 3 SPEC не реализовано — `skills/test-authoring.md` в ветке
   не отличается от main (нет упоминаний `tests/sandbox.py`,
   `_sandbox.py`, «не переписывать», «надстройк»). Файл в зонах задачи.
   Сделай: добавь в скил правило «лёгкую песочницу переходов не
   переписывать — импортировать эталон из `tests/sandbox.py`; локальный
   `_sandbox.py` планки — только тонкая надстройка сценария» (формулировка
   с теми словами, что проверяет тест: `tests/sandbox.py`, `_sandbox.py`,
   «не переписывать», «надстройк»). Прогони планку синхронно
   (`python3 -m unittest discover -s tasks/<id>/acceptance_tests`),
   закоммить, PLAN.md — status: ready. Полный `tests/` не запускать.
