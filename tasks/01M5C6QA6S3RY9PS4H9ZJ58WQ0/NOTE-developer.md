# Записка developer — 01M5C6QA6S3RY9PS4H9ZJ58WQ0

## Выяснено
- Реестр — в `orchestrator/canary.py` (`_live_run_record`, `live_runs`, `live_run_note`, `refuse_main_move_during_canary`); каталог `config.ROOT/.artel/config.CANARY_LIVE_DIRNAME` считается от ROOT в момент вызова — правка `tests/sandbox.py` не понадобилась.
- Потребители (`notes`, `pool_seal`, `fsm_merge_gate`) импортируют `canary` лениво: `canary` тянет `pool_seal`→`notes` и `fsm`. Флаг `DURING_CANARY_FLAG` определён в `fsm` (canary берёт оттуда).
- `from .doctor import stale_cycles` даёт функцию, модуль — `importlib.import_module(".doctor.stale_cycles", __package__)`.
- Заглушки тела мержа в tests/test_merge_gate_ci_wait.py имеют сигнатуру без нового параметра — `during_canary` передаётся kwargs только когда не None (fsm → cycle → body).
- Оба долгоживущих файла задачи зелёные (registry 9 тестов ~20 с; window 12 тестов ~2 мин).

## Не сработало
- (пусто)

## Где остановился
- Код готов, долгоживущие и затронутые тесты зелёные, карта регенерирована, свой тест tests/test_canary_live_registry_units.py, guard ок. Полный набор suite-run №1 зелёный (6181 прошло, 0 упало). PLAN.md — status: ready. Шаг завершён, код оставлен незакоммиченным для пульта.
- `pytest -n` в этом окружении падает (node down) — гонять последовательно.

## Чего не хватило
- Ничего существенного.
