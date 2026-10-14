---
task: 01M4XV9XPJZD29PY0NTNZ98M02
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Lease — идентичность хоста при совпадении сессии и PID

## Подход
Продление своей сессии в `orchestrator/lease.py::acquire` требует совпадения hostname и PID. Remote коллизия попадает в существующую ветку отказа, разрешения same_host_ok без записи либо force. Порядок остальных веток и транзакция сохраняются. Докстринг уточняется по таблице SPEC: своя remote сессия с same_host_ok разрешена без мутации, чужая свежая remote сессия запрещена без force.

Зафиксированные `tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py` и `tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py` уже содержат юнит-тесты и проверки команд AC-1–AC-8. Они остаются неизменными. В `tests/test_lease.py` добавляется только непокрытый случай исключения из разрешённого remote тела run_locked: вся строка lease должна сохраниться.

## Шаги
1. Исправить проверку identity и документацию acquire; добавить тест сохранения remote lease после исключения тела run_locked, проверить его временным возвратом исходной ошибочной проверки PID.
2. Прогнать зафиксированные тесты задачи, тесты lease, budget и kill; выполнить планку через plank-run. Регенерировать карту кодовой базы и проверить PLAN командой scripts/guard.py.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1: тройная identity, отказ без записи | 1, 2 — AC-1, AC-6, run_locked |
| 2: remote same_host_ok своей сессии | 1, 2 — AC-2, AC-8 и исключение тела |
| 3: остальные разрешения, TTL, force, живость | 1, 2 — AC-3–AC-6 и команды budget/kill |
| 4: транзакция, журнал, fresh, конкуренция | 1, 2 — AC-7 и сохранение строки |
| 5: изолированная регрессия и неослабление | 1, 2 — зафиксированная матрица и новый тест |

## Влияние на систему
Меняется только право продления при remote коллизии своей сессии и PID. Это укрепляет защиту параллельного выполнения (инвариант 32), сохраняя принятые разрешения budget и kill. BEGIN IMMEDIATE, commit/rollback, TTL, журналирование, fresh и все вызыватели остаются прежними. Существующие методы и assertions, зафиксированные файлы тестов и защищённые пути не меняются. Карта `docs/codebase-map.md` обновляется генератором согласно conventions-core. Откат — обратный патч изменений кода, нового теста и карты; миграций нет. Бюджет SPEC достаточен.

## Риски
Общий запрет remote same_host_ok нарушил бы принятое разрешение budget; удаление проверки host перед проверкой живости привело бы к неверным выводам о remote PID. Оба свойства проверяет зафиксированная матрица. Смысл документации AC-8 дополнительно сверяется с таблицей SPEC вручную.

## Проверки и результат
- `python3 -m pytest tests/test_lease.py tests/test_01m4xv9xpjzd29py0ntnz98m02_lease.py tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py tests/test_budget_live_lease_and_escalation.py tests/test_kill_live_cycle_refusal.py tests/test_kill_cleanup.py -p no:cacheprovider -p timeout -o timeout=120 -q`: **99 passed, 210 subtests passed**, 36.57 с.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4XV9XPJZD29PY0NTNZ98M02`: **1 passed**, код 0; старые assertions сохранены.
- Новый `tests/test_lease.py::RunLockedTest::test_remote_parallel_lease_survives_body_exception` проверен временными мутациями: возврат проверки только PID дал **1 failed** (изменены hostname/heartbeat), безусловный release в finally дал **1 failed** (строка удалена). Обе мутации сняты в finally сценария; на восстановленном коде **1 passed**.
- `python3 scripts/codebase_map.py` выполнен; `git diff --check` прошёл.
- Ручная сверка документации AC-8: описаны тройная identity, разрешение своей remote сессии с S без записи при любом PID/возрасте, отказ чужой свежей remote сессии, приоритет F, local dead PID, TTL и fresh. Новых разрешающих вызывателей нет; зафиксированная проверка маршрута kill зелёная.
- Полный набор не запускался: в роли разработчика выполнены адресные проверки затронутых модулей и планка; CI и полный прогон остаются пульту.
- `python3 scripts/guard.py /Users/al.sidorenko/projects/artel/.artel/projects/artel/tasks/01M4XV9XPJZD29PY0NTNZ98M02/PLAN.md`: **GUARD: ок (1 файлов)**.
