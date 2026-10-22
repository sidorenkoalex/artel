# Записка developer

## Выяснено
- Возврат из verifying (CI 39862690857): SQL в `project_profile.for_task_target` (`SELECT zones, zones_extension FROM tasks`). Заменён на `store.task_exists` + `store.get_task` (store.py не тронут — «только чтение» по SPEC). Нет строки — пустые зоны, как раньше.
- `tests/test_multitarget.py::SqlOnlyInStoreTest` сканирует только `orchestrator/*.py` верхнего уровня; в диффе ветки SQL больше нет (grep по `git diff main -- orchestrator`).
- Прочее устройство — см. PLAN.md: `decide_task`/`for_task`/`for_task_target`/`for_row`/`is_multi`, `outcome_integrity._components_gate`, `tests_writing._tests_writing_foreign_plank_gate`, мандат по компонентам записи.

## Не сработало
- Длинный python-heredoc в Bash — «Parser aborted»; `cat`/`ls`/`sed -i` недоступны.

## Где остановился
- Шаг завершён: test_multitarget + 4 долгоживущих + components + project_profile_gates — 119 passed; plank-run — 69 passed; карта регенерирована; PLAN.md status: ready.

## Чего не хватило
- Правило «SQL только в store.py» (ADR-0003 3ж) не было в брифе — нашлось только красным CI.
