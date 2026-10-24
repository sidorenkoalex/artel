# Записка developer — 01M5PWFGJQNV8YSAN5MF0CKHVW

## Выяснено
- Реализация целиком в `orchestrator/mutation_run.py`: `_take_lock` (ожидание, шаг 10 с),
  `_lock_minutes`/`_workers` (проверки), `_copy_path`/`_write_copy`/`_show_table` (копия),
  `_Run.header/row/sync_copy`, `-n` в конце `extra`, строка шапки `# рабочих процессов: N`.
  Признак копии — `copy_table` в `mutation-run.json`; фону флаги идут доп. аргументами argv.
- Долгоживущие файлы задачи: 45/45 зелёные (`-p no:xdist`: под ролью xdist падает сторожем).

## Не сработало
- `pytest -n 4` под ролью — рабочие процессы роняет сторож conftest; гонять `-p no:xdist`.

## Где остановился
Готово: код, `artel.py` (строка «Команды:», комментарий допуска), карта регенерирована;
существующие тесты mutation_run/таблицы/help_registry и читающие докстринг artel.py — зелёные;
guard ок; PLAN.md status: ready. Код не закоммичен — коммитит пульт.

## Чего не хватило
—
