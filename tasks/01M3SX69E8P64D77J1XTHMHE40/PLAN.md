---
task: 01M3SX69E8P64D77J1XTHMHE40
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Контроль фоновых запусков и состояние наблюдения

## Подход

Сохранить наблюдения, явное назначение задач и сведения об отсоединённых запусках в существующей БД пульта. `watch --observation` использует тот же цикл чтения событий и в каждой итерации отмечает связь; регистрация не даёт свежести. Перед общим `Popen` для `run` и `auto` проверить свежесть и назначение задачи. `--attach` остаётся прежним путём. Миграция hook-конфигурации выполняется отдельной штатной командой с проверкой поддерживаемой формы, подтверждением замены, резервной копией и восстановлением.

После возврата из verifying перенести оставшиеся SQL-запросы `observe` и ручной остановки из `orchestrator/artel.py` в операции `orchestrator/store.py`, сохранив транзакции и ответы CLI. Это закрывает инвариант ADR-0003 3ж, который проверяет `SqlOnlyInStoreTest`.

Возврат из review, R1-F1: по `ANSWER-5.md` отсоединённые `run`/`auto` требуют явные `--client codex|claude --chat <id>`. CLI валидирует их до `Popen`; запрос наблюдения сверяет эти поля вместе с сессией, проектом и задачей. Исправленная Оператором планка проверяет положительный и отрицательные пути.

## Шаги

1. Добавить схему и запросы наблюдений/запусков, CLI `observe`, heartbeat в `watch`, fail-closed проверку перед отвязкой и документацию.
2. Добавить CLI `hook-migrate` для инвентаризации, точечного изменения и восстановления Codex/Claude конфигураций.
3. Проверить зафиксированную планку и собственные юнит-тесты, регенерировать карту, прогнать guard и закоммитить код.
4. После красного CI перенести запросы `observe show/add/remove/stop` и `stop` задачи в `store.py`, проверить инвариант SQL и адресные сценарии.
5. После решения Оператора передать текущие client/chat в отсоединённый запуск, фильтровать запись наблюдения по обоим полям и добавить отрицательные тесты перекрёстных клиента и чата.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1–8 | 1, 3 |
| 9–11 | 2, 3 |
| Возврат из verifying: SQL только в `store.py`/`schema.py` | 4 |
| Возврат из review: R1-F1, требования 5–6 | 5 (решение `ANSWER-5.md`, реализовано) |

## Влияние на систему

Схема добавляет таблицы без изменения состояния задач и lease. `watch` пишет только heartbeat наблюдения; существующие фильтры событий и завершение дозора сохраняются. Проверка перед отвязкой касается только новых запусков без `--attach`; уже работающие процессы не прерываются. Миграция меняет только поддерживаемый guard после проверки и сохраняет исходные байты. Откат кода — revert коммита; резервная копия возвращает пользовательскую конфигурацию штатной командой.

Перенос SQL не меняет схему и сохраняет границы транзакций. Проверка `tests/test_multitarget.py::SqlOnlyInStoreTest` остаётся без правок.

## Риски

Между проверкой свежести и `Popen` остаётся короткое окно для конкурентной остановки наблюдения; остановка не прерывает уже идущую роль. При нескольких чатах с одной задачей и сессией запуск выбирает только явно названный чат; несовпадающий контекст получает отказ. Незнакомая форма hook-конфигурации получает отказ без записи.

## Проверка

- `python3 -m pytest tests/test_detached_cycle.py tests/test_watch.py tests/test_artel_role_restricted_commands.py tests/test_store_schema_migration_parity.py tests/test_observation_edges.py tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py -q -p no:cacheprovider -p timeout -o timeout=120` — 70 passed, 23 subtests passed.
- Сторожа `tests/test_observation_edges.py` проверены временными мутациями: удаление распознавания managed, отказа роли, вложенной формы Codex, догоняющей миграции таблиц и защиты от неоднозначного чата окрашивало соответствующие тесты; код восстановлен.
- `python3 scripts/codebase_map.py`, `git diff --check`, `python3 scripts/guard.py tasks/01M3SX69E8P64D77J1XTHMHE40/PLAN.md` — успешно.
- Ответ Оператора в `ANSWER-4.md` подтвердил автокоммит пульта `88cd4f2f1d4a1cbd6ccf7b0d37fadcc331de5c0d` как коммит разработчика; `git show --name-only HEAD` содержит реализацию, карту и тесты, рабочее дерево кода чистое.
- Возврат из verifying: CI 36778807735 на `88cd4f2` выявил шесть SQL-строк в `orchestrator/artel.py`; запросы перенесены в `store.py`, сам тест-инвариант не изменён.
- `python3 -m pytest tests/test_multitarget.py::SqlOnlyInStoreTest tests/test_observation_edges.py tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py -q -p no:cacheprovider -p timeout -o timeout=120` — 18 passed, 15 subtests passed.
- `python3 -m pytest tests/test_store_schema_migration_parity.py tests/test_detached_cycle.py tests/test_watch.py -q -p no:cacheprovider -p timeout -o timeout=120` — 43 passed.
- `python3 -m pytest tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py tests/test_artel_role_restricted_commands.py tests/test_observation_edges.py::ObservationEdgesTest::test_explicit_add_reenables_task_after_manual_stop -q -p no:cacheprovider -p timeout -o timeout=120` — 13 passed, 8 subtests passed.
- Новый сторож `test_explicit_add_reenables_task_after_manual_stop` покраснел при временной мутации `ON CONFLICT ... DO NOTHING`, после восстановления кода снова зелёный.
- `python3 scripts/codebase_map.py`, `git diff --check`, `python3 scripts/guard.py tasks/01M3SX69E8P64D77J1XTHMHE40/PLAN.md` — успешно после исправления CI.
- `git add orchestrator/artel.py orchestrator/store.py tests/test_observation_edges.py docs/codebase-map.md` получил `index.lock: Operation not permitted`: sandbox запрещает запись во внешний `.git/worktrees/...`. По одобренному в `ANSWER-4.md` пути эти четыре кодовых файла фиксирует автокоммит пульта после шага; права не расширялись.

- Возврат из review: `python3 -m pytest tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py tests/test_01m3sx69e8p64d77j1xthmhe40_migration.py tests/test_detached_cycle.py tests/test_observation_edges.py tests/test_watch.py tests/test_artel_role_restricted_commands.py tests/test_store_schema_migration_parity.py tests/test_multitarget.py::SqlOnlyInStoreTest -q -p no:cacheprovider -p timeout -o timeout=120` — 75 passed, 37 subtests passed.
- Новый сторож `test_two_chats_allow_only_the_named_observation` покраснел при временном `return None` в `store.matching_observation`; исходный код восстановлен.
- `python3 scripts/codebase_map.py`, `git diff --check`, `python3 scripts/guard.py tasks/01M3SX69E8P64D77J1XTHMHE40/PLAN.md tasks/01M3SX69E8P64D77J1XTHMHE40/REVIEW.md` — успешно после R1-F1.
- `git add orchestrator/artel.py orchestrator/store.py tests/test_detached_cycle.py tests/test_observation_edges.py docs/operator-session.md docs/codebase-map.md` отказал: внешний `.git/worktrees/.../index.lock` недоступен песочнице. По `ANSWER-4.md` код зафиксирует автокоммит пульта после шага; доступ не расширялся.

## Предложения системе

- `store.db()` из task worktree создал пустую `.artel/state.db` в этом worktree при диагностике задачи; для чтения состояния роли нужна штатная команда, обращающаяся к БД главной копии без побочного создания локальной БД.
- Файловая песочница шага разрешает запись только в worktree, а git-index рабочего дерева находится во внешнем `.git/worktrees/<id>/`; `git add` получает `Operation not permitted`. Нужен штатный способ коммита кодовой ветки из роли без обхода песочницы.

