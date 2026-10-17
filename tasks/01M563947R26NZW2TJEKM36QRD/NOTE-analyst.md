# Записка analyst — 01M563947R26NZW2TJEKM36QRD

## Выяснено
- ТЗ достаточно; SPEC.md написан, status: ready, guard ок. 4 AC, budget 25, zones: orchestrator/notes.py, tests/.
- Правка — `orchestrator/notes.py::_silence_window_reason` (строки 266-282): перебор `store.all_tasks` и держатель `merge_lock_row` без фильтра проекта.
- Признак артели — `repo_context.is_artel(task_row)` (пустой target = артель); неразрешённый проект — `repo_context.resolve(target) is None`, текст — `repo_context.unresolved_reason`.
- `tests/test_notes.py::SilenceWindowReasonTest::test_ac1_live_merge_lock_alone_without_any_task_state_opens_window` ставит держателя `T-LOCK` без строки задачи в БД и ждёт открытого окна — поэтому в SPEC (требование 2, AC-4) «строки задачи держателя нет» = неизвестный проект = окно открыто; ожидание теста не меняется.
- Песочница тестов окна — `tests/test_notes.py::NoteSilenceSandbox` (`insert_task_in_state`, `set_live_merge_lock`).

## Не сработало
- guard сначала отказал по сигналу «число модулей»: он считает все упоминания `orchestrator/*.py` в тексте, включая только-чтение; закрыто секцией «Оценка объёма» (монолит + прогноз диффа 12 КиБ).

## Где остановился
- Шаг завершён.

## Чего не хватило
- Что сигнал зон guard считает по всему тексту, а не по полю zones — нашлось в `scripts/guard.py::_zone_paths`.
