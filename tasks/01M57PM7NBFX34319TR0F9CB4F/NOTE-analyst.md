# Записка analyst — 01M57PM7NBFX34319TR0F9CB4F

## Выяснено
- Таблица `merge_locks` (schema.py:148) без ключа. «Одна строка на пульт» держит store.py:1249 `set_merge_lock` (`DELETE FROM merge_locks` без WHERE), а `merge_lock_row` (store.py:1232) читает первую строку без ORDER BY. store.py по ТЗ только для чтения.
- Ещё две функции читают одну строку мьютекса: notes.py:281 `_silence_window_reason` (окно тишины) и doctor/leases.py:174 `check_merge_lock`. notes.py только для чтения, doctor/ не в зонах и не в списке.
- Окно тишины: пока задача в merge_gate, её прикрывает второй триггер (config.py:509 NOTE_SILENCE_WINDOW_STATES). Но после `_finalize_done_state` под мьютексом ещё идут `_commit_closing`, уборка, `_await_main_ci` и `_rebuild_core_reference` (fsm_merge_gate.py:1357-1363). На этом отрезке окно держит только строка держателя.
- Главную копию артели (config.ROOT) мерж не трогает: scratch-worktree в клоне проекта, пин двигает только `pin-update`. Автокоммит закрытия идёт в refs/artifacts репозитория задачи. `merge_after` проверяется до мьютекса. Общее у мержей — только БД.
- `catalog.py:955` зовёт `merge_queue.wait_suffix`, правка внутри зоны.

## Не сработало
- Ничего.

## Где остановился
- Записан QUESTIONS.md (4 вопроса), SPEC не писался.

## Чего не хватило
- Дольше всего искал, кто кроме merge_lock/merge_queue читает `merge_lock_row`: notes.py и doctor/leases.py.
