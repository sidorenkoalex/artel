## Выяснено
- Итерация 1 ревью: plank-run — 1 passed; 5 долгоживущих файлов задачи + test_epics_board_units + test_multitarget + test_merge_after_module — 162 passed.
- `new --after` без `--tz`: `declared` пишется общим `merge_after.record_declared` (catalog.py:697) — путь рабочий.
- `lease.run_locked` снимает lease в `finally` — отказ внутри `_transaction` у `epic add/remove` lease не оставляет.
- Вердикт: approved, только minor-наблюдения (двойной вызов `zone_lock.queue_wait` в status с эпиками; лишние ключи `parent`/`divisions` в модели — надмножество SPEC).

## Не сработало
- Составные bash-команды с sed/; требуют подтверждения — дробить.

## Где остановился
- REVIEW.md записан, status: approved.

## Чего не хватило
- Ничего существенного.
