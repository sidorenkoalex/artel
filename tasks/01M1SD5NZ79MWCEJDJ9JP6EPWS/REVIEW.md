---
task: 01M1SD5NZ79MWCEJDJ9JP6EPWS
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 4    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: R6 — `store.py`: схема и миграции отдельно, запросы по областям

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 — `orchestrator/schema.py`: `SCHEMA`/`migrate`/`add_column`/проверки версии, `store.create_schema`/`store.migrate` — реэкспорт | OK | `schema.py` — новый модуль, все объекты определены В НЁМ (не тонкие обёртки над `store.py`): `schema.migrate.__module__ == "orchestrator.schema"` подтверждено AC-1. `store.py:27` — `from .schema import SCHEMA, add_column, create_schema, migrate, table_columns`; проверил лично: `store.migrate is schema.migrate` → `True`, `store.create_schema is schema.create_schema` → `True`. `store.db()` (store.py:65-71) по-прежнему зовёт голое имя `migrate(conn)`, поэтому `mock.patch.object(store, "migrate", ...)` продолжает перехватывать — AC-2 зелёный. |
| 2 — запросы `store.py` сгруппированы заголовками по 6 областям (задачи и переходы; журнал steps; lease; алерты; канарейка; зоны и очередь) | OK | `grep -n '^#'` подтвердил все 6 заголовков строго в порядке SPEC: store.py:92, 563, 604, 695, 768, 842. AC-3 (регекс-проверка порядка) зелёный. |
| 3 — перенос функций с единственным потребителем (правило ≤3/не ломает `mock.patch.object`) | OK (обоснованно не применено) | PLAN «Подход», п.4: все 12 модулей-кандидатов вне зоны SPEC (`orchestrator/store.py, orchestrator/schema.py, tests/`) — перенос потребовал бы мандата на расширение зоны, которого нет. Требование 3 разрешает, но не обязывает; `test_ac5_single_consumer_relocation.py` — легальный `# AC-5: manual` с тем же обоснованием. |
| 4 — смоук байт-в-байт (`status`/`report`/DDL) | OK | AC-6 (golden `cmd_status`), AC-7 (SHA-256 `report.html`), AC-8 (`sqlite3 .schema` byte-parity) — все три зелёные, прогнал лично. |
| 5 — `test_store*.py`, тесты миграций, `mock.patch.object(store, ...)` — зелёные без правки утверждений | OK | AC-9 зелёный (агрегированный прогон найденных файлов). Дополнительно прогнал вручную: `test_multitarget.py`, `test_store_journal.py`, `test_store_db_connection_close.py`, `test_store_schema_migration_parity.py`, `test_release.py` (единственный потребитель `mock.patch.object(store, "lease_row", ...)`), `test_lease_pgid_store.py` — 72 passed, 14 subtests passed, 0 failures. |
| 6 — поведение и инварианты не меняются | OK | DDL байт-в-байт (AC-8), сигнатуры не менялись (AC-4, `inspect.signature` golden snapshot). Единственная правка вне `store.py`/`schema.py` — `tests/test_multitarget.py::SqlOnlyInStoreTest`: исключение расширено на `schema.py` с обоснованием в докстринге (SQL по-прежнему живёт ровно в двух явно перечисленных файлах, не расползается) — инвариант ADR-0003 3ж не ослаблен, только распространён на новый файл, куда переехал сам DDL. `docs/codebase-map.md` — перегенерировал локально: расходится с веткой только строкой `built_at_sha` (легитимно, см. review-checklist), содержимое совпадает; правку не коммитил, дерево вернул `git checkout --`. |

## Замечания

(пусто — 0 blocker/major/minor, требующих действия разработчика)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| — | — | — | записей нет | — | — |

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/acceptance_tests/ -v` — 11 passed (AC-1..AC-4, AC-6..AC-9; AC-5 — легальный manual).
- `python3 -m pytest tests/test_multitarget.py tests/test_store_journal.py tests/test_store_db_connection_close.py tests/test_store_schema_migration_parity.py tests/test_release.py tests/test_lease_pgid_store.py -v` — 72 passed, 14 subtests passed, 0 failures/errors.
- `python3 -c "from orchestrator import store, schema; print(store.migrate is schema.migrate, store.create_schema is schema.create_schema)"` — `True True`.
- `grep -n "^def \|^# ====="  orchestrator/store.py` — подтвердил порядок и позиции 6 заголовков-разделителей (AC-3 требование SPEC 2).
- `python3 scripts/codebase_map.py` — перегенерировал, `git diff docs/codebase-map.md` показал расхождение только в `built_at_sha` (карта свежая по содержимому); откатил через `git checkout -- docs/codebase-map.md` (ревьювер код не правит).
- Полный набор `tests/` не гонял (решение Оператора 05.09, гоняет CI на каждый пуш) — только планка задачи и модули, затронутые диффом.

## Предложения системе

- `tests/test_multitarget.py:500-510` (`SqlOnlyInStoreTest`, правка этой задачи): изменённый тестовый метод (`test_no_sql_outside_store`, добавлено исключение `schema.py`) обоснован докстрингом класса по существу, но без формального маркера `Ловит мутацию: …` — конвенция test-authoring.md регулярно проседает именно в существующих `tests/*.py` при точечной правке (не в новых acceptance_tests, где дисциплина соблюдается) — тот же класс уже отмечался ранее ([[feedback_test_authoring_mutation_claim_gap]]). Не блокирую как замечание задачи (обоснование по существу присутствует, инвариант не ослаблен), но стоит явно решить на уровне скила: распространяется ли требование маркера на точечные правки существующих юнит-тестов или только на новые тестовые файлы/методы.
