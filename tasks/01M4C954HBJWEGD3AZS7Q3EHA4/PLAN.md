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

## Шаги

1. Расширить схему и `store.py`: миграция, регистрация, чтение событий, атомарные позиции и владение PID.
2. Реализовать `watch --observation`, просмотр, подтверждение, уведомления и безопасный вывод в `watch.py`/`artel.py`.
3. Добавить проверки окружения и `doctor`, обновить документацию и тесты, прогнать затронутые модули, планку и guard.
4. Закрыть красный CI: условная миграция и совместимость `observe show` со старой записью; закрепить обе регрессии тестами и повторить названные в возврате проверки.
5. Закрыть R1-F1: временно снять маркер роли в тестовом помощнике `force_stop` только для публичного `observe stop`, сохранив подстановку сессии и запрет команды для настоящего процесса роли.
6. Закрыть возврат из merge_gate: исправить распознавание песочницы и конфликт флагов дозора, добавить поведенческие регрессии, обновить документацию и повторить проверки.

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

## Предложения системе

- `artel.py suite-run` в изолированном шаге роли пытается создать `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json` вне разрешённых корней и падает с `PermissionError`; нужна команда прогона, доступная роли без обхода песочницы, либо явное разрешение этому каталогу.
- `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py` проверяет операторский `run`/`auto`, но наследует `CODEX_SANDBOX=seatbelt` из окружения роли и получает ранний отказ. Тестовой песочнице нужен явный сброс маркеров Codex для сценариев терминала Оператора.
