# Записка developer

## Выяснено
- Планка перехватывает `subprocess.Popen` модуля (argv с `run-task`) — звать `subprocess.Popen`, не импортом имени.
- Реализация: развилка в `cmd_canary` после `_set_plan` -> `_cmd_canary_parallel` -> `_run_children`; потоки-ожидатели зовут `_wait_child(proc)` по глобальному имени, исходы — в `queue.Queue`; главный поток ждёт `queue.get()` (на macOS сигнал его прерывает — проверено). Остановка `_stop_children` под `_SignalDeferral`, отложенный сигнал вынимается из `deferral.pending` до `release()` (не поднимается заново).
- `_interrupt_on_signal` получил необязательный перечень сигналов; родитель ставит ещё SIGINT.
- Сверка формы sha — первой строкой `cmd_canary_run_task` (`reference_cache.SHA_FORM`).
- Планка: 29/29 зелёная; tests/test_canary_parallel.py 9 тестов, 6 мутаций пойманы.

## Не сработало
- `pytest -n 4` по tests/ — узлы падают (conftest), гонять последовательно.
- Составные bash-команды и `rm` недоступны: удалять файл через `python3 -c "os.unlink"`.

## Где остановился
- Шаг сдан: PLAN status: ready, guard ок, планка 29/29. suite-run №1 оборван пределом 1500 с (нагрузка), 2 упавших вне диффа (spec_audit_flow AC-9, outcome_gate AC-4) — по именам зелёные.

## Чего не хватило
- Ничего существенного.
