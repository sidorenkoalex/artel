---
task: 01M1THKRK8HPXA7Y2SRB0RFTN2
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

Расширение зон разрешено: orchestrator/doctor/

## Ответы

Гейт зон отклонил `orchestrator/doctor/cli.py`: зона SPEC
`orchestrator/doctor.py` устарела после разреза doctor на пакет (R5,
06.09). Путь `orchestrator/doctor/` разрешён как расширение зон задачи;
раздел «## Расширение зон» в PLAN.md положен тем же мостом Оператора
(команды `zones-extend` у пульта ещё нет — задача 01M1VBEFR9). Код не
менять, повторить переход `advance`.
