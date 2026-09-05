---
task: 01M1RHFRQ2C0P4A57XJJ1WZV8N
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

---
task: 01M1RHFRQ2C0P4A57XJJ1WZV8N
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. Поправка к ответу 3 ANSWER-1: случай 3B реален и включается в объём.
   Сразу после ANSWER-1 цикл `auto` этой же задачи из `spec_writing`
   сделал пред-advance, прочитал прежний QUESTIONS.md (`status: ready`) и
   снова перевёл задачу в `escalated` («шаг analyst не нужен: переход
   выполнен по готовым артефактам, spec_writing -> escalated», журнал
   10:29:25), не дав аналитику шага. Требование: после возврата из
   `escalated` в состояние роли (любое: `spec_writing`, `tests_writing`,
   `in_dev`) пред-advance не выполняется до первого завершённого шага
   этой роли после возврата; артефакт-основание прежней эскалации
   (QUESTIONS.md, PLAN.md со `status: escalate`, маркеры `AC-n: escalate`)
   не считается «готовым артефактом» для перехода, пока роль его не
   переписала. Отдельный AC и тест: «возврат из escalated по ANSWER →
   `auto` запускает роль, а не повторяет эскалацию».
2. Общий принцип для SPEC: пред-advance по готовым артефактам допустим
   только когда артефакт роли новее события возврата (замечания, reject,
   ANSWER); иначе — шаг роли.
