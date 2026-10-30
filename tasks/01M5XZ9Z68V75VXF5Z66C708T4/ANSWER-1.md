---
task: 01M5XZ9Z68V75VXF5Z66C708T4
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Уточнения сессии при Операторе (права волны G) разработчику, по замечаниям аудита SPEC, принятым на гейте 27.10.2026. SPEC не меняется; это толкование требований.

1. `targets.delivery_policy(entry)` отдаёт `mr_assignee` как `int | str | None`; `int` и строка из одних цифр — id исполнителя.
2. Вход в `escalated` из `awaiting_human` — существующими путями (`fixation.py:239`, `store.py:1281`, `budget.py:384`), `escalated_from` = `awaiting_human`; возврат после ответа — в `awaiting_human`. Новых путей входа не добавлять.
3. `kill` задачи с `target-human`: коммит закрытия досылается в `refs/artifacts/<id>` как сейчас (`cleanup.py:644-645`); не трогаются только ветка задачи на сервере и MR.
4. `max_awaiting` — целое > 0, `bool` не допускается.
5. Запрет отправки ветки в `awaiting_human` — и на входе `gitcmd.in_repo` (`gitcmd.py:1064`), не только `gitcmd.git`.
6. В матрице — строка «`awaiting_human` не занимает место в лимите параллельности эпика» (`auto.py:1168`, `:1338-1342`).
