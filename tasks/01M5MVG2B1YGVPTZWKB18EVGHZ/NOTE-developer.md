# Записка developer

## Выяснено
- Реализовано: `canary._insert_interrupted_row` + `CHILD_ROW_WRITE_ATTEMPTS = 3`, отчёт в stderr в `except CanaryInterrupted` `cmd_canary_run_task`; сообщения `run.out`/`out` в двух тестах гонки; `run_cli` закрывает канал внука сразу; `read_grandchild_pid` → `AssertionError("внук не появился")`; новый `tests/test_canary_child_row_write.py`; карта перегенерирована.
- Тесты 4 файлов — 32 passed; plank-run — 8 passed. Мутации на новом файле краснеют.
- Подмена `canary.time.sleep` = глобальный `time.sleep`: `subprocess.run(timeout=10)` в `stale_cycles.process_start_time` (из `_write_child_record`) опрашивает паузами — шпион видит чужой вызов. Свой тест — на `tests.sandbox.patch_sleep`; планка AC-9 так не умеет, может изредка ложно краснеть (в PLAN «Риски»).

## Не сработало
- Bash: `ls`/`cat` недоступны в оболочке, `;`/циклы требуют подтверждения.

## Где остановился
- PLAN.md status: ready, guard ок. Код не закоммичен (коммитит пульт).

## Чего не хватило
- Источник лишнего `time.sleep` — `tests/sandbox.py::TimeWithSleep` объясняет его в докстринге.
