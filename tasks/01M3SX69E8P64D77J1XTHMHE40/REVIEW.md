---
task: 01M3SX69E8P64D77J1XTHMHE40
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Контроль фоновых запусков и состояние наблюдения

## Проверка плана

Таблица покрытия PLAN.md покрывает требования 1–11 шагами 1–3; перенос SQL в шаге 4 соответствует фактической доработке и не меняет публичное поведение. Шаги проверяемы, обратимость миграции описана. Конфликта с существующей архитектурой не найдено.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Использованы существующие маршруты `run`, `auto`, `watch`, lease, session и журнал. |
| 2 | OK | Схема и `observe show --json` хранят и показывают идентичность, набор, состояние, связь и запуски. |
| 3 | OK | Добавлены штатные команды; мутации наблюдения и heartbeat запрещены среде роли. |
| 4 | OK | Heartbeat выполняется циклом `watch`; период и трёхпериодный порог именованы. |
| 5 | Не реализовано | Отказ до `Popen` есть, но подходящее наблюдение не сверяется с текущими client/chat. См. R1-F1. |
| 6 | Не реализовано | Фильтр учитывает проект, задачу и session_id, но не текущие клиент и чат. См. R1-F1. |
| 7 | OK | Остановка отключает только остановленную задачу, другие назначения и связь наблюдения сохраняются; возобновление требует явного add/register. |
| 8 | OK | Новые действия не расширяют полномочия наблюдателя; lease и существующие ограничения сохранены. |
| 9 | OK | Есть inspect/apply/restore для Codex и Claude, отсутствие и неизвестная форма диагностируются. |
| 10 | OK | Миграция удаляет только распознанный guard после `--verified`, сохраняя соседние настройки. |
| 11 | OK | До записи создаётся резервная копия, restore возвращает исходные байты. |

## Замечания

- major — orchestrator/artel.py:636-637, orchestrator/store.py:100-108, orchestrator/session.py:92-107, tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py:181 — отсоединённый запуск выбирает наблюдение только по `target`, задаче и `session_id`. `resolve_session_id` получает ID из параметра/`ARTEL_SESSION_ID`/общего файла сессии и не содержит client/chat; `matching_observation` также не принимает их. Поэтому из одной сессии можно зарегистрировать наблюдение `--client claude --chat чужой-чат` и затем запустить `artel.py run <задача>` из другого клиента или чата: запуск будет разрешён, хотя наблюдение не подходит текущему client/chat. Это нарушает fail-closed требования 5–6 и AC-8. Нужен доверенный источник либо явная передача текущих client/chat в путь запуска, фильтрация по обоим полям и отрицательный тест перекрёстных client/chat. `orchestrator/session.py` прочитан адресно только для проверки, несёт ли уже существующий идентификатор сессии эту необходимую идентичность.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/artel.py:636-637; orchestrator/store.py:100-108; orchestrator/session.py:92-107; tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py:181 | Выбор наблюдения не проверяет client/chat текущего запуска. | Наблюдение другого чата либо клиента той же сессии разрешает отсоединённый запуск. | Передавать или получать доверенную текущую пару client/chat, фильтровать по ней и добавить отрицательную проверку. |

## Вердикт

changes_requested: закрыть R1-F1. После исправления нужен адресный прогон тестов наблюдения и миграции.

## Проверено исполнением

- `python3 -m pytest tests/test_detached_cycle.py tests/test_watch.py tests/test_artel_role_restricted_commands.py tests/test_store_schema_migration_parity.py tests/test_observation_edges.py tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py -q -p no:cacheprovider -p timeout -o timeout=120` — 71 passed, 23 subtests passed.
- `python3 -m pytest tests/test_multitarget.py::SqlOnlyInStoreTest tests/test_observation_edges.py tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py -q -p no:cacheprovider -p timeout -o timeout=120` — 18 passed, 15 subtests passed.
- `git diff --check 7f55c29abdb91a21030b90bcb3e6dd3332486d3d...HEAD` — без ошибок пробелов.

