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

## Шаги

1. Расширить схему и `store.py`: миграция, регистрация, чтение событий, атомарные позиции и владение PID.
2. Реализовать `watch --observation`, просмотр, подтверждение, уведомления и безопасный вывод в `watch.py`/`artel.py`.
3. Добавить проверки окружения и `doctor`, обновить документацию и тесты, прогнать затронутые модули, планку и guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1–3 | 1, 2 |
| 4–6 | 1, 2 |
| 7–8 | 2, 3 |
| 9 | 3 |
| 10–15 | 1–3 |

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

## Предложения системе

- `artel.py suite-run` в изолированном шаге роли пытается создать `/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/lock.json` вне разрешённых корней и падает с `PermissionError`; нужна команда прогона, доступная роли без обхода песочницы, либо явное разрешение этому каталогу.
