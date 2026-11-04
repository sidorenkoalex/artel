# NOTE reviewer — итерация 1

## Выяснено
- Тесты файлов задачи зелёные: 211 passed (долгоживущие задачи, надзор 01M5TBF7, crash_series_units, auto_cycle, pause, epic_supervisor_units); 215 passed — answer/lease/zone-wait/verify_flow (16 файлов).
- plank-run: «планки нет» — каталог приёмки пуст, планка — долгоживущие tests/test_01m6hvpm*.
- Временные мутации `_run_begins` (без сверки pid) и `_resets_crash_count` (budget сбрасывает) ловятся tests/test_epic_crash_series_units.py; код возвращён, дерево чистое.
- Карта docs/codebase-map.md свежая (регенерация без расхождений кроме built_at_sha).
- Дифф файла надзора 01M5TBF7 — только ac9, ac18, ac27, ac30[все окончательны] + импорт auto и помощник end_records.

## Не сработало
- `xargs`/`$F` в Bash отклоняются сторожем — список файлов pytest передавать явно.

## Где остановился
- Вердикт approved, реестр пуст.

## Чего не хватило
- Нет публичного «состав очереди зоны» в zone_lock — надзор зовёт `_queue_members`/`_own_paths` (уже в предложениях PLAN).
