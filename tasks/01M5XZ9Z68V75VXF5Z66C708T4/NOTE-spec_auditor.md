# Записка spec_auditor — 01M5XZ9Z68V75VXF5Z66C708T4

## Выяснено
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок.
- Адреса строк SPEC совпадают с кодом на a6af742bf (auto `:1338` — фактически `view.free` на `:1342`).
- targets.py:648-651 на main отказывает `mr_assignee: 42` (yamlmini.scalar → int): треб. 1 «без изменений, строка либо целое» неверно, AC-2 требует правки, в матрице строки нет.
- Не названы функция чтения полей доставки (AC-1) и носитель ссылки на MR в БД (AC-10/13).
- gitcmd._push_plan: удаление (`deleting`, gitcmd.py:816) отделено от `branches` — отказ рядом с plan.sent пропустит `--delete`.
- amend.py:1079-1086: push только при долгоживущих файлах; правка одной планки не отправляет ничего.
- AC-13 без `in_dev` после возврата из review (ветка уже отправлена).
- AC-8 (merge_after.py:769) и AC-12 (fsm.py:1757 escalated_from) зелёные на main.

## Не сработало
- `cd …; grep` в составной команде требует подтверждения — работают только абсолютные пути без `cd`.

## Где остановился
Готово.

## Чего не хватило
Дольше всего искал, через что `amend-tests` отправляет (github_adapter.ensure_head_in_origin → gitcmd.in_repo push).
