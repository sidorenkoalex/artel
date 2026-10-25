# Записка analyst — 01M5TBCY7WTN121S136XP2C6SR (Э2а)

## Выяснено
- Э1 (01M5TBBDFS6DWQY6MS263T1KPY) на 25.10 в `spec_writing`, его кода в main нет: `orchestrator/epics.py`, `orchestrator/board.py`, таблицы `epics`, `tasks.epic_id`, `tasks.closed_as` (Э0) — не существуют. Сверка «имени модуля команд эпика по коду Э1», которую просит ТЗ, невозможна; имена в SPEC взяты из ТЗ и ADR-0028 (п. 5, 8, 9, 12).
- Точка проверок перед шагом роли: `orchestrator/runner.py:341` (пауза) и `:352` (стоп-кран) — приём `store.journal(...)` + `return "exit", "... run отклонён: ..."`.
- `budget.spent_with_estimate` — `budget.py:251`; `spend.cli_number` — `spend.py:22`; `merge_after.check` — `merge_after.py:126`; `replace_divided` — `:299`.
- guard не требует существования путей зон — пути Э1 в zones проходят.

## Не сработало
- `artel.py docs` недоступна роли analyst.

## Где остановился
- SPEC написан (status: ready), budget 50 = рамка ТЗ; секция «Оценка объёма» — обоснование монолита (решение на гейте Оператора).

## Чего не хватило
- Кода Э1 в main: модель `board.py` (`waiting_on`) и модуль команд `epic` — только по ADR.
