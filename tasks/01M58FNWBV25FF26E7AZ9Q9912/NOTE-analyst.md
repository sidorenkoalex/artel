# Записка analyst — 01M58FNWBV25FF26E7AZ9Q9912 (шаг 4, возврат со spec_gate по SPEC-AUDIT)

## Выяснено
- Возврат закрыт целиком: признак `ProfileAnswer.multi` (по умолчанию False — прежние конструкторы в tests/ не ломаются); `_task_own_profile` бросает `targets.TargetsError` только при multi, иначе прежнее → `tests/test_acceptance_suite_profile.py` не меняется, раздел «Меняемое поведение» удалён.
- `drop_from_code_copy` (acceptance.py:1285-1302): rmtree tasks/<id> остаётся, при multi пропускается `_drop_layout`, перехват узкий. Вызывающие вне зон записаны как недостижимые при отказе decide.
- Интерфейс в project_profile.py: `components`, `select_components` (кортеж имён в порядке записи, ABSENT → пусто), `test_id`/`parse_test_id`; AC-7 — литералы.
- Правило workdir/env — только у записи с одним компонентом; `repo` ≠ имени записи — отказ у любого компонента (моё прочтение п. 6, записано в «Материалах»).
- Нумерация требований сдвинулась: интерфейс — 6, выбор — 7, идентификатор — 8, отказ читателей — 9, `_task_own_profile` — 10, тесты — 11.

## Где остановился
- SPEC.md переписан, status: ready, guard ок.

## Чего не хватило
- Ничего существенного; `rm`/`ls` в шаге не разрешены, `cd … &&` ловит запрет simple_expansion — звать guard относительным путём из рабочего каталога.
