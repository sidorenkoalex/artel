---
task: 01M4C954HBJWEGD3AZS7Q3EHA4
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Дозор: позиции, просмотр, подтверждение, уведомление

## Подход

Добавить две пары позиций и владение процессом в `observations`. Для режима `--observation` читать журнал одним упорядоченным запросом по набору задач, хранить границу независимо от фильтра вывода. Общую выборку использовать в `observe events`; подтверждение делать атомарным и монотонным. Прежний `watch` без наблюдения оставить на существующем пути.

После возврата из verifying: в `schema.migrate` перед заполнением позиций читать наличие пустых позиций и обеих таблиц журнала. На обычном `store.db()` не выполнять `UPDATE observations`, когда заполнять нечего. В `observe show` дать запасные значения новым полям для старой подставленной записи; реальные строки БД сохраняют значения миграции.

После возврата из merge_gate: распознавать песочницу Codex по непустому `CODEX_SANDBOX` при отключённой сети, включая `seatbelt`. Для `watch --observation` отвергать `--once`, `--exit-on` и `--until` на этапе разбора аргументов, до чтения БД и захвата PID; пояснить отказ в документации.

После возврата с приёмки (Д-1…Д-6):
- Д-1: `watch._observation_events` в начале чтения берёт `store.journal_maxima` (`MAX(steps.id)`, `MAX(alerts.id)`), читает `steps`/`alerts` в полуинтервале (старт, максимум] и возвращает максимум, а не последнюю строку задач набора. Позиция «оповещено» и `POSITION=` в `observe events` идут за журналом и при молчащем наборе; записи, появившиеся после снятия максимума, остаются выше пары и придут следующим чтением. История задачи, добавленной через `observe add`, повторно не выводится.
- Д-2: `_watch_observation` снова печатает `STATE=<state>` при смене состояния задачи набора (первое появление задачи только запоминается, как в прежнем цикле), выводит ход живого шага (`_emit_progress` разделён на поиск записи и `_emit_live_step_progress`) и ограничивает строки класса `pytest` и хода шага общим `_LineBudget`. Живые шаги набора ищет один агрегирующий запрос `store.observation_live_steps`, а не 2N запросов по задачам: долгоживущий `test_ac2_steps_across_tasks_are_ordered_and_read_together` требует одного чтения потока `steps` за опрос.
- Д-3: `osascript` вызывается с `timeout=10` (`_NOTIFY_TIMEOUT_SEC`); `TimeoutExpired` печатает одну строку «уведомление недоступно», дозор продолжает.
- Д-4: `store.claim_observation` считает PID своим, только если совпал и хост.
- Д-6: `doctor` (`check_observations`) — `warn` при мёртвом PID или протухшей связи, с подсказкой перезапуска.
- Документация: `docs/operator-session.md` — отметка связи ставится при захвате и в конце каждого опроса, после чтения событий; раздел о ходе шага теперь включает `--observation`.

## Шаги

1. Расширить схему и `store.py`: миграция, регистрация, чтение событий, атомарные позиции и владение PID.
2. Реализовать `watch --observation`, просмотр, подтверждение, уведомления и безопасный вывод в `watch.py`/`artel.py`.
3. Добавить проверки окружения и `doctor`, обновить документацию и тесты, прогнать затронутые модули, планку и guard.
4. Закрыть красный CI: условная миграция и совместимость `observe show` со старой записью; закрепить обе регрессии тестами и повторить названные в возврате проверки.
5. Закрыть R1-F1: временно снять маркер роли в тестовом помощнике `force_stop` только для публичного `observe stop`, сохранив подстановку сессии и запрет команды для настоящего процесса роли.
6. Закрыть возврат из merge_gate: исправить распознавание песочницы и конфликт флагов дозора, добавить поведенческие регрессии, обновить документацию и повторить проверки.
7. Закрыть возврат с приёмки Д-1…Д-6 и текст документации (см. «Подход»); новые тесты — в отдельном файле `tests/test_observation_acceptance_return.py`, долгоживущие файлы не тронуты.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1–3 | 1, 2 |
| 4–5 | 1, 2 |
| 6 | 1, 2, 5 |
| 7–8 | 2, 3 |
| 9 | 3 |
| 10–15 | 1–3 |
| Возврат из verifying: старая БД, блокировка записи, show под ролью | 4 |
| R1-F1 | 5 |
| Возврат из merge_gate: `seatbelt` и флаги завершения наблюдателя | 6 |
| Возврат с приёмки: Д-1, Д-2, Д-3, Д-4, Д-6, текст ~486 | 7 |

## Влияние на систему

Миграция расширяет только `observations`; данные задач и lease не меняются. Ролевой доступ расширяется только на читающий `observe events`. Старый `watch` сохраняет своё поведение. Откат кода — revert одного коммита задачи; новые колонки остаются неиспользуемыми прежним кодом.

## Риски

Гонки при захвате PID и подтверждении устраняются транзакцией `BEGIN IMMEDIATE`. Безопасность терминала требует экранирования всех полей строк событий, включая имена и метаданные.

## Проверка

- `python3 -m pytest` по затронутым модулям (`test_watch.py`, `test_observation_edges.py`, `test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `test_store_schema_migration_parity.py`, `test_artel_role_restricted_commands.py`, `test_doctor.py`, трём долгоживущим файлам этой задачи и `test_observation_notification.py`): 175 passed, 54 subtests passed.
- `test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`: 13 passed; `force_stop` теперь вызывает `observe stop` без записи в `tasks`.
- Два новых теста `test_observation_notification.py` покраснели каждый на заявленной временной мутации и прошли после восстановления кода.
- `plank-run 01M4C954HBJWEGD3AZS7Q3EHA4`: 1 passed; `scripts/guard.py PLAN.md`: ок; `git diff --check`: ок.
- `suite-run` не стартовал: `PermissionError` при создании `.artel/logs/suite-run/lock.json` вне разрешённых корней песочницы роли.
- Возврат из verifying: 190 адресных тестов затронутых модулей и названных CI-регрессий прошли. Два новых теста `test_observation_migration_regression.py` покраснели на временных мутациях (безусловный `UPDATE`, чтение `steps` при отсутствии таблицы) и прошли после восстановления. `plank-run 01M4C954HBJWEGD3AZS7Q3EHA4`: 1 passed. `watch` продолжает вызывать `time.sleep` и `time.monotonic` через атрибут модуля; сторож сна: 4 passed.
- Повтор `suite-run` в этом шаге снова завершился `PermissionError` на том же `lock.json`; полный набор остаётся за CI и гейтом приёмки.
- После возврата: `python3 scripts/codebase_map.py` обновил карту; `python3 scripts/guard.py <путь к PLAN.md>`: `GUARD: ок (1 файлов)`; `git diff --check`: без замечаний.
- Ревью R1-F1: `python3 -m pytest tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py -p no:cacheprovider -p timeout -o timeout=120` — 13 passed в окружении роли; `ARTEL_ROLE=reviewer python3 -m pytest tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py tests/test_artel_role_restricted_commands.py -p no:cacheprovider -p timeout -o timeout=120` — 20 passed, включая проверку запрета команд роли.
- После R1-F1: `python3 scripts/codebase_map.py` обновил карту; `plank-run 01M4C954HBJWEGD3AZS7Q3EHA4` — 1 passed; `python3 scripts/guard.py <PLAN.md> <REVIEW.md>` — `GUARD: ок (2 файлов)`; `git diff --check` — без замечаний. `suite-run 01M4C954HBJWEGD3AZS7Q3EHA4` снова отказал на создании `.artel/logs/suite-run/lock.json` (`PermissionError: Operation not permitted`); полный набор в шаге не стартовал.
- После возврата из merge_gate: `env -u CODEX_SANDBOX -u CODEX_SANDBOX_NETWORK_DISABLED python3 -m pytest` по 12 адресным файлам, включая долгоживущие тесты задачи, — 183 passed. Новые тесты в `test_observation_notification.py` явно выставляют `seatbelt` и проверяют отказ `run`/`auto`, а также три несовместимых флага `watch --observation` до обращения к БД. Каждый сторож покраснел на заявленной временной мутации; исходный код восстановлен.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4C954HBJWEGD3AZS7Q3EHA4` — 1 passed. `suite-run` вновь отказал при создании `.artel/logs/suite-run/lock.json` (`PermissionError`), полный прогон не начался.
- После финальной правки: `test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py` и `test_observation_notification.py` — 20 passed; `python3 scripts/codebase_map.py` обновил карту; `python3 scripts/guard.py <PLAN.md>` — `GUARD: ок (1 файлов)`; `git diff --check` — без замечаний.

- Возврат с приёмки: `python3 -m pytest` по 16 адресным файлам (`test_watch.py`, `test_observation_edges.py`, `test_01m3sx69e8p64d77j1xthmhe40_observation.py`, `test_store_schema_migration_parity.py`, `test_artel_role_restricted_commands.py`, `test_doctor.py`, четыре долгоживущих файла задачи, `test_observation_notification.py`, `test_observation_migration_regression.py`, `test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`, `test_observation_acceptance_return.py`, сторож сна, `test_pair_suspension_units.py`) — 217 passed, 103 subtests passed. Долгоживущие файлы не правились.
- Новый `tests/test_observation_acceptance_return.py` (8 тестов): каждый покраснел на заявленной временной мутации (позиция по последней строке набора; без `STATE=`; без хода шага; без `_LineBudget`; свой PID без сверки хоста; `doctor` всегда ok; `osascript` без `timeout`) и прошёл после восстановления кода.
- `plank-run 01M4C954HBJWEGD3AZS7Q3EHA4` — 1 passed, код выхода 0. `python3 scripts/codebase_map.py` обновил карту; `git diff --check` — без замечаний.
- `suite-run` №1 (полный набор) на этот раз стартовал: красный, 7 новых на ветке `sqlite3.OperationalError: no such table: tasks` (`test_acceptance.py::MaterializeFromBranchGitFailureTest`, `test_fsm_autogate.py::ChecklistNamesRealChecksTest` и др.) и `test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`; повтор `--failed` (№2) — те же 8. Причина не в diff: на HEAD ветки без правок этого шага (правки временно отложены) оба названных теста падают так же. `artifact_branch.task_repo` читает БД, если `config.DB.exists()`, а в рабочей копии лежит игнорируемая пустая `.artel/state.db` без таблиц (создана 08.10 12:49 прошлым шагом). Прогон базы шёл в другом дереве, без этого файла. `test_liveness` убивает группу процессов, а песочница роли это не даёт. Файл не удалён: уборка рабочего каталога ролью запрещена; в CI на чистом checkout его нет.

## Предложения системе

- Тесты, не подменяющие `config.DB` (`tests/test_fsm_autogate.py::ChecklistNamesRealChecksTest`, `tests/test_acceptance.py::MaterializeFromBranchGitFailureTest` и др.), читают `<ROOT>/.artel/state.db` рабочей копии: пустая БД, оставленная прежним шагом в worktree задачи, даёт 7 ложных «новых на ветке» падений `suite-run`. Нужна либо изоляция `config.DB` в этих тестах, либо уборка `.artel/state.db` worktree пультом перед прогоном.

- `artel.py suite-run` в изолированном шаге роли пытается создать `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json` вне разрешённых корней и падает с `PermissionError`; нужна команда прогона, доступная роли без обхода песочницы, либо явное разрешение этому каталогу.
- `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py` проверяет операторский `run`/`auto`, но наследует `CODEX_SANDBOX=seatbelt` из окружения роли и получает ранний отказ. Тестовой песочнице нужен явный сброс маркеров Codex для сценариев терминала Оператора.
