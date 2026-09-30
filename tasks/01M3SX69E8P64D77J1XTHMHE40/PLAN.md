---
task: 01M3SX69E8P64D77J1XTHMHE40
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Контроль фоновых запусков и состояние наблюдения

## Подход

Сохранить наблюдения, явное назначение задач и сведения об отсоединённых запусках в существующей БД пульта. `watch --observation` использует тот же цикл чтения событий и в каждой итерации отмечает связь; регистрация не даёт свежести. Перед общим `Popen` для `run` и `auto` проверить свежесть и назначение задачи. `--attach` остаётся прежним путём. Миграция hook-конфигурации выполняется отдельной штатной командой с проверкой поддерживаемой формы, подтверждением замены, резервной копией и восстановлением.

После возврата из verifying перенести оставшиеся SQL-запросы `observe` и ручной остановки из `orchestrator/artel.py` в операции `orchestrator/store.py`, сохранив транзакции и ответы CLI. Это закрывает инвариант ADR-0003 3ж, который проверяет `SqlOnlyInStoreTest`.

Возврат из review, R1-F1: текущий `session_id` не содержит client/chat. Без явного контекста вызова `run`/`auto` нельзя проверить принадлежность вызывающего чата записи наблюдения. Решение о новом публичном контракте и исправлении залоченной планки требуется от Оператора; до него не подменять проверку выбором единственного наблюдения сессии.

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
| Возврат из review: R1-F1, требования 5–6 | 5 (блокирован решением Оператора) |

## Влияние на систему

Схема добавляет таблицы без изменения состояния задач и lease. `watch` пишет только heartbeat наблюдения; существующие фильтры событий и завершение дозора сохраняются. Проверка перед отвязкой касается только новых запусков без `--attach`; уже работающие процессы не прерываются. Миграция меняет только поддерживаемый guard после проверки и сохраняет исходные байты. Откат кода — revert коммита; резервная копия возвращает пользовательскую конфигурацию штатной командой.

Перенос SQL не меняет схему и сохраняет границы транзакций. Проверка `tests/test_multitarget.py::SqlOnlyInStoreTest` остаётся без правок.

## Риски

Между проверкой свежести и `Popen` остаётся короткое окно для конкурентной остановки наблюдения; остановка не прерывает уже идущую роль. При нескольких чатах с одной задачей и сессией запуск получает отказ вместо случайного выбора. Незнакомая форма hook-конфигурации получает отказ без записи.

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

## Предложения системе

- `store.db()` из task worktree создал пустую `.artel/state.db` в этом worktree при диагностике задачи; для чтения состояния роли нужна штатная команда, обращающаяся к БД главной копии без побочного создания локальной БД.
- Файловая песочница шага разрешает запись только в worktree, а git-index рабочего дерева находится во внешнем `.git/worktrees/<id>/`; `git add` получает `Operation not permitted`. Нужен штатный способ коммита кодовой ветки из роли без обхода песочницы.

## Эскалация

- **Вопросы.** Подтвердить обязательную передачу client/chat в отсоединённый `run`/`auto` (например, `--client codex|claude --chat <id>`) и разрешить Оператору согласовать залоченные тесты через `amend-tests`? Вариант А (рекомендуемый): обязательные аргументы, отсутствие любого из них отказывает до `Popen`; Оператор обновляет положительные тесты, сохраняя проверки PID, лога, heartbeat, `--attach` и запрета роли. Вариант Б: указать иной доверенный источник текущих client/chat и способ его передачи тестам. Дефолт при отсутствии ответа: сохранить существующий контролирующий hook, не разрешать запуск на основании одной записи сессии и не менять залоченные тесты.
- **Контекст.** `orchestrator/session.py:92–107` возвращает только `session_id` из параметра, окружения или общего файла. `orchestrator/store.py:100–108` выбирает наблюдение по проекту, задаче и `session_id`, без client/chat. `orchestrator/artel.py:636–637` вызывает этот поиск перед `Popen`; R1-F1 требует сверки обоих полей. Зафиксированный `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py:55–70` ожидает успешные фоновые `run` и `auto` без client/chat, а `tests/test_detached_cycle.py:116–124` проверяет тот же вызов без аргументов. Выбор единственной записи сессии не доказывает, из какого клиента и чата пришёл вызов, и сохраняет дефект R1-F1. Код и залоченные тесты на этом шаге не изменены.
- **Блокирует.** Исправление R1-F1, адресный прогон планки, статус `ready` и переход к повторному ревью. Без согласования публичного контракта и планки безопасная реализация неизбежно ломает положительный залоченный тест, а совместимая реализация не проверяет текущий client/chat.
