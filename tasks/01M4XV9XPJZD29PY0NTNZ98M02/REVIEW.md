---
task: 01M4XV9XPJZD29PY0NTNZ98M02
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Lease — идентичность хоста при совпадении сессии и PID

## Соответствие SPEC

Фаза A — гейт плана пройден. Таблица покрывает требования 1–5; два шага проверяемы и соразмерны изменению. Подход сохраняет архитектуру и разрешённые зоны. Влияние на систему соответствует diff; откат описан, миграций нет.

Фаза B — обе части пакета проверены. Исполняемое изменение в `orchestrator/lease.py:148` ограничено добавлением hostname к проверке PID своей сессии. Остальные ветки, транзакции и вызыватели не изменены.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Продление требует session_id, hostname и PID. Remote коллизия попадает в существующий отказ без записи; матрица AC-1 и run_locked подтверждают отказ и блокировку тела. |
| 2 | OK | Remote same_host_ok своей сессии разрешает операцию без изменения всей строки при любом PID. AC-2 и budget проверяют разрешение; новый тест сохраняет строку и журнал также после исключения тела. Докстринг явно описывает исключение. |
| 3 | OK | Local продление, live/dead PID, строгая граница TTL и приоритет force сохранены. AC-3–AC-6 проверяют матрицу; remote PID не зондируется локально. Проверки budget и kill подтверждают прежние маршруты, включая --yes до force. |
| 4 | OK | BEGIN IMMEDIATE, commit/rollback, fresh и события не менялись. AC-7 проверяет закрытие транзакций, откат и единственного победителя для свободного, протухшего и мёртвого local lease. |
| 5 | OK | Матрица использует изолированную SQLite и синтетические часы/процессы; проверяет всю строку с pgid. В tests/test_lease.py добавлен только новый метод, существующие сценарии и assertions по diff базы сохранены. |

Долгоживущие свойства покрыты двумя зафиксированными файлами `tests/test_01m4xv9xpjzd29py0ntnz98m02_*.py` и существующими тестами lease/budget/kill. Новый `RunLockedTest.test_remote_parallel_lease_survives_body_exception` проверяет дополнительный сценарий исключения: возврат проверки только PID нарушит сравнение строки, а безусловный release удалит её. Заявка мутации соответствует наблюдаемым assertions; успешный маршрут зафиксированной матрицы этот сценарий не повторяет. Зафиксированные тесты и защищённые пути не изменены.

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved — обе фазы пройдены, blocker/major замечаний нет. Код не изменялся, артефакт не коммитился.

## Проверено исполнением

- `python3 -m pytest tests/test_lease.py tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py tests/test_budget_live_lease_and_escalation.py tests/test_kill_live_cycle_refusal.py tests/test_kill_cleanup.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 99 passed, 210 subtests passed за 35.34 с; код 0.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4XV9XPJZD29PY0NTNZ98M02` — зафиксированная планка `test_existing_assertions.py`: 1 passed, код pytest 0, таймаут раннера 120 с.
- `git diff --check 292edaf7822836ba54a7905cef259ccdbed47edd...HEAD` — код 0.

Полный набор tests/ не запускался согласно контракту роли. CI ddb316dd: 16 зелёных проверок по пакету; это сведения пакета, не собственный запуск.

## Предложения системе

Нет.
