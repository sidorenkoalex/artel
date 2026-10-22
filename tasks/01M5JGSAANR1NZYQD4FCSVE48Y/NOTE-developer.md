# Записка developer

## Выяснено
- Итерация 2 (R1-F1): добавлен `tests/test_task_component_places.py`, 14 тестов на лёгкой песочнице `TaskIdSchemaConnTmpRootTest` с учебной записью `uchplaces` (`backend`/`frontend`), id задач детерминированы. Места: `acceptance_suite`, `_test_integrity_diff_gate`, `_external_helpers`, `matrix_refusals`, предел `full_suite`/`suite-run`, заявка мутации, `_plank_rule_refusal`, `_exit_without_profile`, `pull._materialize_and_run_plank`. Идёт 5 с.
- 12 временных мутаций (скрипт в worktree, удалён) — все красят свой класс, включая мутацию ревьювера (`acceptance_suite` → `profile = None`; `elif False` в `_test_integrity_diff_gate`).
- REVIEW.md: R1-F1 → `fixed`. PLAN.md: шаг 7, status: ready. Карта регенерирована.
- Ранее: SQL в `project_profile` заменён функциями store (`SqlOnlyInStoreTest`).

## Не сработало
- `rm`, `cat`, `ls` в песочнице нет; удалял через `python3 -c "os.remove(...)"`. В Bash `$var` требует подтверждения.

## Где остановился
- Шаг завершён: новые тесты + test_multitarget + task_component — 78 passed; guard ок.

## Чего не хватило
- Готовой песочницы учебной записи в `tests/` (она живёт только в разовой планке `_training.py`) — пришлось скопировать минимум в новый файл.
