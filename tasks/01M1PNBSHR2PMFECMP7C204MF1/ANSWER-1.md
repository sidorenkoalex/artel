---
task: 01M1PNBSHR2PMFECMP7C204MF1
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответы на QUESTIONS.md.

Вопрос 1 — вариант A: алерт сторожа зависших прогонов — `kind=incident`
по прецеденту `check_leases` (тот же класс: процесс без живого lease);
`orchestrator/alerts.py` не трогается, формулировка «warning» в ТЗ была
неточной. Авто-ack при исчезновении — тем же приёмом `_auto_ack_gone`.

Вопрос 2 — вариант B: при мёртвом lease группа снимается только под
`doctor --fix`; обычный `doctor` остаётся наблюдательным (только алерт).
Немедленные пути требования 2 — таймаут шага, `kill`, `pause --now`,
`release` — бьют группу без флага, как в ТЗ.
