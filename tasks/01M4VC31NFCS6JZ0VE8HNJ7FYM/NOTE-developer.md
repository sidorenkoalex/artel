# Записка developer 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- Реализация (итерация 1): `canary.escalation_roles(steps)` (+ `_source_state_role`),
  `_run_one_task` передаёт `escalation_roles(steps)` в `_record_canary_run`
  → `store.insert_canary_run(escalation_roles=)`; колонка без DEFAULT;
  `models.unclean_reason` — `_excess_escalation_role` при данных о ролях.
- Итерация 2 (R1-F1): сторож связки — `tests/test_canary_escalation_roles_storage.py::
  RunOneTaskRecordsEscalationRolesTest` по образцу `CommitMismatchSummaryTest`
  (`tests/test_canary_drive.py`): подмена `_run_task_in_ephemeral_clone`
  кортежем из 9 полей (4-е — steps). Мутация `escalation_roles=None` в
  `canary.py:2633` — красный; код возвращён. REVIEW реестр R1-F1 → fixed.

## Не сработало
- `cd … && cat/ls` в Bash: в оболочке роли нет cat/ls — пользоваться Read.

## Где остановился
- Шаг завершён: тест добавлен, карта регенерирована, PLAN.md ready (guard ок),
  suite-run №2 зелёный: 5470 прошло, 0 упало, 2 пропущено.

## Чего не хватило
- —
