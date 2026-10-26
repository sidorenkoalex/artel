# Записка developer — 01M5WDB7F14SQ30QVWJY2XYBG2

## Выяснено
- Планка AC-6..AC-9 — `acceptance_tests/test_push_point.py` (75 passed); долгоживущие AC-1..AC-5 — tests/test_01m5wdb7f14sq30qvwjy2xybg2_{record_fields,branch_template}.py (44 passed).
- Ветка: `catalog.branch_template/branch_name/_branch_ref_key/branch_refusal/division_branches`; `cmd_new` проверяет после id и до `_new_task_row(branch=…)`; деление — `fsm._division_check` (теперь четвёрка: order, frames, parts, reason) -> `_spawn_division_subtasks(parts=…)` -> `spawn_subtask(task_id=…, branch=…)`.
- Точка отправки: `gitcmd._push_plan` во всех пяти точках (+`in_repo`), у всех параметр `task_id`; белый список — `_whitelist_refusal`; предикат `targets.push_whitelisted`, норма опции `targets.push_option_error`.
- Запись «ветка отправлена»: action `ветка отправлена`, detail `<sha> <ветка>`; аренда сверяется с первым словом detail последней записи.
- Нечитаемый targets.yaml — отправка из клона внешнего проекта отказана (fail-closed); мой тест сначала упал именно так из-за неполной записи песочницы — запись песочницы обязана нести long_lived_dir/name и scopes, как в планке.

## Не сработало
- `pytest -n 4` в этой рабочей копии роняет воркеры (node down) — гонял последовательно.

## Где остановился
- Шаг завершён: PLAN.md status: ready, guard ок, карта регенерирована. Соседние модули: 252 + 460 + 86 passed.

## Чего не хватило
- Где фикстура `initialized_tmp_root` — в tests/fixtures.py (не conftest).
