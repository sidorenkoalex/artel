---
task: 01M3SX69E8P64D77J1XTHMHE40
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Контроль фоновых запусков и состояние наблюдения

## Проверка плана

Таблица покрытия PLAN.md покрывает требования 1–11: состояние и
fail-closed запуск — шагом 1, миграция — шагом 2, проверка — шагом 3,
SQL-инвариант — шагом 4, контекст client/chat после R1-F1 — шагом 5.
Шаги проверяемы и соразмерны MR; миграция обратима через резервную копию,
а перенос SQL не меняет публичный контракт. Конфликта с архитектурой и
конвенциями не найдено.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Использованы существующие маршруты `run`, `auto`, `watch`, lease, session и журнал. |
| 2 | OK | Схема и `observe show --json` хранят и показывают идентичность, набор, состояние, связь и запуски. |
| 3 | OK | Добавлены штатные команды; мутации наблюдения и heartbeat запрещены среде роли. |
| 4 | OK | Heartbeat выполняется циклом `watch`; период и трёхпериодный порог именованы. |
| 5 | OK | До `Popen` detach требует валидные `--client`/`--chat` и свежее подходящее наблюдение; `--attach` не ограничен. |
| 6 | OK | `matching_observation` сверяет проект, session_id, client, chat и назначенную задачу; отсутствие или несовпадение отказывает. |
| 7 | OK | Остановка отключает только остановленную задачу, другие назначения и связь наблюдения сохраняются; возобновление требует явного add/register. |
| 8 | OK | Новые действия не расширяют полномочия наблюдателя; lease и существующие ограничения сохранены. |
| 9 | OK | Есть inspect/apply/restore для Codex и Claude, отсутствие и неизвестная форма диагностируются. |
| 10 | OK | Миграция удаляет только распознанный guard после `--verified`, сохраняя соседние настройки. |
| 11 | OK | До записи создаётся резервная копия, restore возвращает исходные байты. |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/artel.py:627-738; orchestrator/store.py:100-107; tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py:167-192; tests/test_observation_edges.py:29-55 | Выбор наблюдения не проверяет client/chat текущего запуска. | Наблюдение другого чата либо клиента той же сессии разрешает отсоединённый запуск. | Подтверждено исправление по `ANSWER-5.md`: обязательная пара client/chat в detach CLI, фильтр по обоим полям, отрицательные сценарии и сторож точного выбора чата. |

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py tests/test_detached_cycle.py tests/test_observation_edges.py tests/test_watch.py tests/test_artel_role_restricted_commands.py tests/test_store_schema_migration_parity.py tests/test_multitarget.py::SqlOnlyInStoreTest -q -p no:cacheprovider -p timeout -o timeout=120` — 75 passed, 37 subtests passed.
- Временная мутация `orchestrator/store.py::matching_observation` на безусловный `return None` сделала `tests/test_observation_edges.py::ObservationEdgesTest::test_two_chats_allow_only_the_named_observation` красным; исходный код восстановлен.
- `git diff --check 66365c5e4794e0bcf78832a55977619c6ccc1ee3...HEAD` и `git diff --check` — без ошибок пробелов.
