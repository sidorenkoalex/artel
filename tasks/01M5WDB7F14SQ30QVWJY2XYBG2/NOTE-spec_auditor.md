# Записка spec_auditor — 01M5WDB7F14SQ30QVWJY2XYBG2

## Выяснено
- Факты SPEC сверены: catalog.py:918 (ветка), :1031-1038 (spawn_subtask: ветка до copy_external_refs), fsm.py:1037/1070 (_spawn_division_subtasks), gitcmd.py:37/86-118/164/341/413/441/469 — верно. Ещё один запуск git — gitcmd.py:549 (check_ignore, не push).
- `policy.push_options_forbidden` нигде не объявлено (ни в коде, ни в ADR); targets._check_local_sections (:441) отказывает неизвестному полю policy — поле надо объявлять, SPEC его формы не задаёт.
- Деление: _division_check (fsm.py:1403) — место отказа «до первой записи»; zones/merge_after/budget пишутся на :1431-1444, эпик `--as-epic` — fsm.py:1067 до частей. AC-5 не ловит отказ, поставленный позже этих записей.
- Требование 3(г) «нечитаемая запись — отказ» противоречит 3 «operator — прежние» (merge_gate при нечитаемой записи неизвестен).
- Журнал отказа для отправки, не связанной с задачей (в `main`), не определён — store.journal пишет по task_id.
- Вердикт: concerns.

## Не сработало
- Bash с `cd …;` и переменными требует подтверждения — только одиночные команды с относительными путями.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns, 11 отклонений + мелкие), guard: ок. Шаг завершён.

## Чего не хватило
- Списка всех мест `push` в коде — собрал grep '"push"' orchestrator/ (16 мест, cleanup.py:268 уже шлёт --force-with-lease сам).
