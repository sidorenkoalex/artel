# NOTE developer

## Выяснено
- Э2а в main сверен (требование 14): маркер «agent run started» (`merge_after.role_step_started`), `start_after_pending` (мёртвые = killed/пропавшие), конверт `budget.epic_spent >= envelope` — совпадает со SPEC.
- Реализация: надзор `auto.cmd_auto_epic` (разбор линии `_epic_view`, удержание `_child_holds`, блокировка `_take_supervisor_lock`), запуск/спавн в `artel.py` (`_launch_epic_supervisor`, `_launch_epic_child`, `_spawn_detached` вынесен из `_launch_detached`), `epic parallel|stop|retry` в `epics.py`, таблицы `epic_supervisors`/`epic_children` + `epics.parallel` в `schema.py`, живость `lease.process_alive`, доставка в `watch._observation_events`.
- `lease.is_live` — только heartbeat; живость lease для надзора — `parallel_limit.busy_other_tasks`.
- `_cmd_stop` выключает задачу из наблюдений — надзор включает её снова перед каждым запуском.
- Долгоживущий файл 44/44 зелёный (несколько прогонов), свой tests/test_epic_supervisor_units.py 5/5, мутации заявок проверены. Наборы эпиков/watch/наблюдений/auto/lease/invariants зелёные. Карта регенерирована. Планки нет (plank-run: штатный отказ).

## Не сработало
- `cat`/`ls`, `;`/`for`/`echo $?` в Bash отказывают; `pytest -n` запрещён сторожем.

## Где остановился
- Всё сделано, PLAN.md status: ready.

## Чего не хватило
- Перечня журнальных действий команд Оператора (approve/answer/budget/…) в одном месте — собирал grep-ом по модулям (`auto._operator_actions`).
