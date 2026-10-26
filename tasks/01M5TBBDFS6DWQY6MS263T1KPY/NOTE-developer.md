# Записка developer — 01M5TBBDFS6DWQY6MS263T1KPY

## Выяснено
- Э0 уже в ветке (подтяжка main dbbc8fb71): `fsm.STATES`, `fsm.TERMINAL_STATES`, `tasks.closed_as` есть.
- Реализация: `orchestrator/epics.py` (команды, `binding_refusal`, `create_from_division`, вид `epic show`), `orchestrator/board.py` (`build_model`, `_ordered`), SQL эпиков — `store.py` (`begin_immediate`, `get_epic`, `insert_epic`, `update_epic`, `set_task_epic`, `project_tasks`, …), миграция `schema._migrate_epics` (последней в `migrate`), `catalog._status_line`/`_print_status_blocks`, `fsm._as_epic_goal`, `merge_after.declared_for_new`.
- `artifact_source.resolve` всегда (ветка документов, True) — предчтение SPEC для `--as-epic` через `artifact_branch.show`, без журнала.
- `store.journal`/`insert_task` сами делают commit — в транзакциях BEGIN IMMEDIATE журнал последним.

## Не сработало
- Дедупликация всех элементов (ТЗ + --after) сломала `test_merge_after_module.py::test_ac6_…` (повтор внутри строки ТЗ должен отказывать) — схлопываю только элементы `--after`.
- `pytest -n` в этом окружении падает (node down) — гонял без xdist.

## Где остановился
- Готово: 56 долгоживущих + планка AC-29 + ~45 файлов затронутых модулей зелёные; свой tests/test_epics_board_units.py (2 теста, мутации проверены); карта регенерирована; PLAN.md status: ready, guard ок.

## Чего не хватило
- Формат заголовка группы/таблицы `epic show` SPEC не задаёт — подогнан под разбор долгоживущих тестов (`|`-таблица).
