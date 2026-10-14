## Выяснено
- Итерация 1: changes_requested, R1-F1 — у связки `_run_one_task` → колонка `escalation_roles` не было сторожа в tests/.
- Итерация 2: approved. R1-F1 → accepted. Новый `RunOneTaskRecordsEscalationRolesTest` краснеет на мутации `escalation_roles=None` (`canary.py:2633`). Планка — 3 passed, затронутые модули — 46 passed, карта свежая.

## Не сработало
- `pytest tests/ -k …` сторож роли блокирует как полный прогон — файлы нужно перечислять.

## Где остановился
- REVIEW.md итерации 2 записан со статусом approved.

## Чего не хватило
- Ничего.
