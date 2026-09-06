---
task: 01M1SD5NZ79MWCEJDJ9JP6EPWS
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 4    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: R6 — `store.py`: схема и миграции отдельно, запросы по областям

## Подход
Атомарное перемещение содержимого одного файла в два шага, как и
описывает SPEC («Обоснование монолита»): один MR, без промежуточных
состояний, потому что второй шаг переписывает те же строки файла,
которые сдвинул первый.

1. `SCHEMA` (DDL), `create_schema`, `table_columns`, `add_column`,
   `migrate` переехали байт-в-байт (без изменения логики/комментариев)
   в новый `orchestrator/schema.py`. `store.py` реэкспортирует все пять
   имён импортом `from .schema import SCHEMA, add_column, create_schema,
   migrate, table_columns` — `store.migrate`/`store.create_schema`
   остаются ТЕМИ ЖЕ объектами (`is`), что и `schema.migrate`/
   `schema.create_schema` (AC-2), а `store.db()` продолжает звать голое
   имя `migrate(conn)` — резолвится через пространство имён `store.py`
   на момент вызова, поэтому существующий `mock.patch.object(store,
   "migrate", ...)` продолжает перехватывать вызов внутри `db()`.
2. `seed_task_counters` НЕ переехала в `schema.py` — по букве требования
   1 SPEC переезжают `SCHEMA`/`migrate`/`add_column`/«проверки версии»
   (`table_columns`), а посев `task_counters` по наблюдаемому миру —
   отдельная забота (нумерация задач), не миграция схемы по существу.
   Она остаётся в `store.py`, а `schema.migrate()` зовёт её отложенным
   импортом `from . import store` ВНУТРИ функции (тем же приёмом, что
   уже применяют `store.record_fixation`/`store._append_passport_line`
   для `fixation`/`artifact_branch` — избегаем цикла импортов на уровне
   модуля: `store.py` импортирует `schema` на уровне модуля, а
   `schema.py` — `store` только отложенно, в момент вызова `migrate()`).
3. Оставшиеся в `store.py` запросы сгруппированы шестью заголовками-
   комментариями верхнего уровня буквально в порядке SPEC/AC-3: задачи и
   переходы; журнал `steps`; lease; алерты; канарейка; зоны и очередь.
   Функции, работающие с общей инфраструктурой соединения (`db`,
   `enable_wal`, `now`, `_AutoClosingConnection`, `TASK_ID`), — до первого
   заголовка: они не относятся ни к одной из шести областей отдельно.
   «Зоны и очередь» — единственная область без собственных SQL-функций:
   `zones`/`zones_extension`/`zone_queue_position` — обычные колонки
   `tasks`, читаемые/пишемые уже существующими `get_task`/`all_tasks`/
   `update_task` из группы «Задачи и переходы» (grep подтвердил: в
   сегодняшнем `store.py` нет ни одной SQL-функции с «zone» в теле,
   кроме колонок в `SCHEMA`/`migrate`) — заголовок с explaining-
   комментарием вместо кода, что и требует AC-3 (наличие и порядок
   заголовка, не обязательность кода под ним).
4. AC-5 (перенос функции с единственным потребителем) — НЕ применено.
   Зона задачи (frontmatter SPEC) — `orchestrator/store.py,
   orchestrator/schema.py, tests/`; все 12 модулей-кандидатов
   (`alerts.py`, `canary.py`, `doctor.py`, `brief.py`, `budget.py`,
   `checkpoint.py`, `coldstart.py`, `lease.py`, `merge_lock.py`,
   `prune.py`, `report.py`, `runner.py`, `spend.py`) вне зоны — перенос
   потребовал бы мандата Оператора на расширение зоны (`zones_extension`),
   которого нет и нет и оснований запрашивать: требование 3 РАЗРЕШАЕТ
   перенос, но не обязывает, а сам SPEC (AC-5, acceptance_tests) явно
   называет этот исход SPEC-совместимым и не проверяемым детерминированным
   тестом.
5. `tests/test_multitarget.py::SqlOnlyInStoreTest` (проверка «SQL только
   в store.py», ADR-0003 3ж) расширена на `schema.py` — правка ФАЙЛА, не
   ассерта существующего теста (тест AC-9 её не защищает: `test_no_sql_
   outside_store` не входит ни в `test_store*.py`, ни несёт
   `mock.patch.object(store, ...)`), `tests/` в зоне SPEC. Без этой
   правки регресс неизбежен: `schema.py` по определению AC-1 несёт
   `CREATE TABLE`/`ALTER TABLE` — предупреждение об этом есть в докстринге
   `test_ac2_store_reexports_schema.py`.

## Шаги
1. Выделить `orchestrator/schema.py` (SCHEMA/create_schema/table_columns/
   add_column/migrate), реэкспортировать в `store.py`, перегруппировать
   оставшиеся запросы `store.py` заголовками, расширить исключение
   `SqlOnlyInStoreTest` на `schema.py`, перегенерировать
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (schema.py: SCHEMA/migrate/add_column/проверки версии) | 1 |
| 2 (группировка запросов заголовками) | 1 |
| 3 (перенос функций с одним потребителем — правило ≤3, не ломает mock.patch) | 1 (не применено — обоснование в «Подходе», п.4) |
| 4 (смоук байт-в-байт status/report, DDL идентична) | 1 |
| 5 (существующие тесты store*/миграций/mock.patch зелёные) | 1 |
| 6 (поведение и инварианты не меняются) | 1 |

## Влияние на систему
- `orchestrator/schema.py` — новый модуль, добавлен в исключения
  `tests/test_multitarget.py::SqlOnlyInStoreTest` (единственная правка
  вне `store.py`/`schema.py`), инвариант «SQL только в store.py»
  (ADR-0003 3ж — цель, не пункт `docs/invariants.md`) остаётся истинным
  в расширенной форме: SQL живёт в двух явно перечисленных файлах, не
  расползается по кодовой базе.
- Импорт `store.py -> schema.py` на уровне модуля; обратный
  `schema.py -> store.py` — только отложенный, внутри `migrate()`, тем
  же приёмом, что уже несколько мест `store.py` (`record_fixation`,
  `_append_passport_line`, `_close_attention_alert`, `seed_task_counters`)
  используют для тех же целей (избежать цикла импортов при загрузке
  модуля). Циклов на уровне модуля нет — проверено импортом
  `from orchestrator import store, schema` и полным прогоном тестов
  ниже.
- Публичные сигнатуры не менялись (AC-4, стаб-провалидировано снятым
  golden-снимком `inspect.signature`) — вызывающий код по всей кодовой
  базе (`catalog.py`, `alerts.py`, `fsm.py` и т.д.) не тронут.
- DDL (`SCHEMA`) и алгоритм `migrate`/`add_column` — байт-в-байт те же
  строки/комментарии, просто в другом файле: ни одна колонка, дефолт
  или порядок `CREATE TABLE`/`add_column` не менялись (SPEC «Не входит»).
- Откат — `git revert` одного коммита: перенос механический, новых
  зависимостей (кроме описанной выше) не добавляет.

## Риски
- Отложенный импорт `store` внутри `schema.migrate()` — то же место
  кода теперь явно завязано на существование `store.seed_task_counters`;
  переименование этой функции без синхронной правки `schema.py` сломает
  миграцию НЕзаметно для статического анализа (импорт внутри функции).
  Смягчение: тест `tests/test_store_schema_migration_parity.py` и AC-9
  регресс гоняют `store.migrate(conn)` целиком на каждый прогон — падение
  будет замечено немедленно.

## Предложения системе
(пусто)
