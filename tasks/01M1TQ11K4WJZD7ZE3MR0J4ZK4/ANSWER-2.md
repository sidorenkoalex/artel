---
task: 01M1TQ11K4WJZD7ZE3MR0J4ZK4
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: мандат на расширение зон — docs/adr/0014-budget-default-and-role-cap.md

## Ответы

Гейт зон отказал переход за правку
`docs/adr/0014-budget-default-and-role-cap.md`. Правка требуется самим
SPEC (требование 1, AC-3: ADR ссылается на имя калибровочной константы
вместо повторения чисел), зона в SPEC не объявлена — упущение ТЗ
Оператора, не превышение мандата.

Что сделать разработчику в этом ходе: добавить в PLAN.md раздел
`## Расширение зон` со строкой `Пути: docs/adr/0014-budget-default-and-role-cap.md`
и обоснованием (AC-3), кода не менять, сдать шаг. Мандат Оператора —
строка ниже; гейт зон засчитает раздел PLAN вместе с ней.

Расширение зон разрешено: docs/adr/0014-budget-default-and-role-cap.md
