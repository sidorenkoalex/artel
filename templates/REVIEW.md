---
task: TASK_ID
type: review
author_role: reviewer
status: draft        # draft | approved | changes_requested | escalate
iteration: 1
---

# REVIEW: <название задачи>

## Соответствие SPEC
<Каждое требование SPEC: реализовано / не реализовано / реализовано не так.>

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания
<Формат: severity (blocker/major/minor) — файл:строка — суть — предложение.
Пустой раздел при аппруве — норм.>

- ...

## Вердикт
<approved ИЛИ changes_requested + что именно исправить, ИЛИ escalate + вопрос.>
