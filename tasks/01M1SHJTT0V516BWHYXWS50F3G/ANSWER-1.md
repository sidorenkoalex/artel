---
task: 01M1SHJTT0V516BWHYXWS50F3G
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: расширение зон задачи 01M1SHJTT0V516BWHYXWS50F3G

## Ответы

Мост Оператора 06.09.2026 (задача в in_dev, переход `in_dev -> review`
отклонён гейтом зон: дифф трогает `orchestrator/fsm_advance.py` вне
заявленных зон; команда `answer` доступна только из escalated, поэтому
мандат положен коммитом Оператора в артефактную ветку).

Правка в `orchestrator/fsm_advance.py` — одна строка: вызов
`acceptance.summary(acc_tdir, branch=t["branch"])` вместо
`acceptance.summary(acc_tdir)`, чтобы сводка гейта показывала критерий
`ci` с результатом CI (требование 4 SPEC, AC-6). Это адрес уже
названного требования, не новое требование. Мандат ограничен этим
файлом и этим вызовом.

Расширение зон разрешено: orchestrator/fsm_advance.py

Что сделать разработчику: добавить в PLAN.md раздел «## Расширение зон»
со строкой `Пути: orchestrator/fsm_advance.py` и обоснованием (одна
строка вызова для AC-6), затем повторить переход.
