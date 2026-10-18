## Выяснено
- Вся правка в orchestrator/acceptance.py: `_own_path` (PATH прогона), параметр `run_dir` у `_place_env`/`_own_env`, `deselected` в `_RUN_CATEGORY`, `CommandNotFound(OSError)` + `_launch` (Popen с переводом FNF только при own и `exc.filename == argv[0]`).
- `CommandNotFound` — наследник OSError, не FNF: two_sided ловит OSError и пишет «pytest не запустился: …».
- 4 файла задачи + pytest_own_places: 23 passed.

## Не сработало
- suite-run: всё время шага (больше 15 мин) замок держала задача 01M56G23ZQDHV2BKEVWWC22R96, и полный набор не прогнан. В PATH роли нет `sleep`: шелловый цикл `until …; do sleep` холостой, ждать можно только через python3 time.sleep.

## Где остановился
- Код готов, тесты задачи и соседних модулей зелёные (100 passed), свой сторож tests/test_acceptance_own_launch.py проверен мутацией, карта регенерирована, PLAN ready.
- suite-run ждал замок машины (занят задачей 01M56G23ZQDHV2BKEVWWC22R96); xdist `-n` в шаге роли не работает (node down) — соседние тесты гонял без параллели.

## Чего не хватило
- Ничего существенного: места PLACES и каналы отказа названы в SPEC.
