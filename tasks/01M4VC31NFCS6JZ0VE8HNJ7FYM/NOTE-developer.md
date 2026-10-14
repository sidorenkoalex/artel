# Записка developer 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- Реализация: `canary.escalation_roles(steps)` (+ `_source_state_role`),
  `_run_one_task` передаёт `escalation_roles(steps)` в `_record_canary_run`
  (новый kw-параметр, по умолчанию None) → `store.insert_canary_run(escalation_roles=)`.
- `store._ensure_canary_tables`: колонка в CREATE TABLE и `add_column` без DEFAULT
  (старые строки — NULL).
- `models.unclean_reason`: при данных о ролях — `_excess_escalation_role`
  («эскалаций роли X: N»), иначе прежняя ветка `escalations > 1`. Отсутствие
  ключа: `sqlite3.Row` даёт IndexError, dict — KeyError.
- Долгоживущий файл задачи + планка (3) зелёные; тесты canary_drive/model_sets/
  set_trial_suspension/parity зелёные.

## Не сработало
- `cd … && find`/awk в Bash просят подтверждения — абсолютные пути.

## Где остановился
- Шаг завершён: свой тест tests/test_canary_escalation_roles_storage.py
  (проверен мутацией), карта регенерирована, PLAN.md ready (guard ок),
  suite-run №1 зелёный: 5469 прошло, 0 упало, 2 пропущено.

## Чего не хватило
- —
