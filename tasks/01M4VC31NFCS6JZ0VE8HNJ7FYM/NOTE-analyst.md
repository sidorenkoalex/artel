# Записка analyst — 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- ТЗ достаточно; SPEC.md написан, status: ready, guard — ок. 8 AC, budget 40, монолит (сигнал — budget ≥ 30).
- Форма данных выбрана SPEC: перечень ролей по порядку эскалаций (ТЗ давало выбор).
- Карта состояние→роль: `orchestrator/config.py:805` STATE_ROLE (без spec_writing — analyst отдельно).
- Сбор эскалаций: `orchestrator/canary.py:1848` `_escalation_notes` (только detail); запись — `insert_canary_run` (вызовы canary.py:2416, 2645, 2762); миграции `canary_runs` — `orchestrator/store.py:1442-1477` (`add_column`).
- Критерий: `orchestrator/models.py:1136` `unclean_reason`; сводка — `pair_admission` :1174.
- Долгоживущий тест `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py` (~строки 927-970) проверяет старое правило на строках без ролей — по требованию 4 должен остаться зелёным без правок.

## Не сработало
- grep после `cd` в составной команде требует подтверждения — нужны абсолютные пути.

## Где остановился
- Шаг завершён: SPEC готов.

## Чего не хватило
- Ничего существенного.
