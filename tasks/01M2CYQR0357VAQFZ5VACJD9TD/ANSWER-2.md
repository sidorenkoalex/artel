---
task: 01M2CYQR0357VAQFZ5VACJD9TD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Повторная эскалация — не новая: цикл перечитал старую пометку
«# AC-3: escalate» из планки артефактной ветки, не запустив шаг
test_author после ANSWER-1 (дефект механики, записан в копилку 13.09).
Ответ по существу — ANSWER-1.md: пакет называется
`orchestrator/advance_gates/`, `orchestrator/gates.py` и его тесты не
трогаются, мандат на расширение зон дан там же. Автору тестов: перепиши
планку под новый путь пакета, пометку escalate с AC-3 сними (skip с
причиной «полный набор проверяет CI/автогейт» либо тест на сохранность
`orchestrator.gates.policy` после переноса), пометки manual AC-4/5/6
оставь.
