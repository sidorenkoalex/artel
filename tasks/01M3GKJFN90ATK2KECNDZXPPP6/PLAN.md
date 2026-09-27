---
task: 01M3GKJFN90ATK2KECNDZXPPP6
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Индекс журнала и одна выборка для report/watch; нормализация явного --sha канарейки

## Подход

Два независимых по файлам узла SPEC делаются одним MR (деление SPEC уже
разобрала): CR-2 — `orchestrator/schema.py`, `orchestrator/store.py`,
`orchestrator/report.py`, `orchestrator/watch.py`; CR-3 —
`orchestrator/canary.py`, `orchestrator/pin.py`. Потолок задачи не
переоценивается: число файлов и шагов совпало с оценкой SPEC
(`budget_usd: 30` остаётся как есть, поле во frontmatter не
раскомментировано).

Ключевые решения:

1. **Индекс — одним литералом на два места.** `schema.STEPS_TASK_ID_INDEX_DDL`
   (`orchestrator/schema.py:62`) подставляется И в `SCHEMA`
   (`orchestrator/schema.py:88`, сразу после `CREATE TABLE steps`), И в
   `migrate` (`orchestrator/schema.py:300`) — тем же приёмом, каким в этом
   файле уже живёт `MODEL_TARIFFS_DDL`. Паритет свежей и мигрированной БД
   обеспечен одним текстом, а не двумя копиями, которые и расходятся
   (требования 1-2, AC-1/AC-2). `CREATE INDEX IF NOT EXISTS` — потому что
   `migrate` идёт на КАЖДОМ `store.db()`.
   Составной `steps(task_id, id)` не заводится (требование 2): `id` —
   алиас rowid, SQLite сам дописывает rowid хвостовым ключом каждой записи
   индекса rowid-таблицы, и план запроса это подтверждает (замер AC-3
   ниже: `SEARCH steps USING INDEX idx_steps_task_id (task_id=?)`, ни
   `SCAN`, ни `USE TEMP B-TREE FOR ORDER BY`).

2. **SQL остаётся в `store.py`** (ADR-0003 3ж): две новые выборки —
   `store.all_steps(conn)` (весь журнал одним запросом, `ORDER BY id`) и
   `store.task_steps_since(conn, task_id, since_id)` (`WHERE task_id=? AND
   id>?`). Обе берут ровно шесть колонок, названных требованием 3
   (`_BULK_STEP_COLUMNS`, `orchestrator/store.py:621`; сами функции — `:630`
   и `:649`). `store.task_steps`
   остаётся на `SELECT *` и не меняется: её зовёт десяток читателей, часть
   которых (`watch._owner_session_id`, `catalog.cmd_log`) читает
   `session_id`.

3. **`report._all_steps` фильтрует по каталогу задач, не отдаёт выборку как
   есть.** Журнал несёт записи псевдозадач (`config.PIN_UPDATE_JOURNAL_TASK_ID`,
   `config.PROGRAM_SPEND_RESEED_TASK_ID`) — строки `tasks` у них нет, и
   прежняя склейка «по задачам из `tasks`» их не включала. Без фильтра
   запись `pin откатан` актёра `operator` попала бы в «журнал Оператора по
   дням» (`report._operator_window` отбирает по актёру, не глядя на
   `task_id`) — то есть вывод изменился бы, а требование 5 это запрещает.
   Тот же довод у `report._map_size_entries`: принадлежность target'у
   по-прежнему берётся у `store.all_tasks`, не у колонки `steps.target`.
   Сортировка склеенного списка в Python убрана — `ORDER BY id` самой
   выборки уже даёт ту хронологию, которую она восстанавливала.

4. **Явный `--sha` нормализуется в точке входа, а не по пути.**
   `canary._local_full_sha` (новая, `orchestrator/canary.py:1124`) —
   `gitcmd.git("rev-parse", "--verify", "<rev>^{commit}")`, ЛОКАЛЬНО, без
   единого обращения к origin (`orchestrator/gitcmd.py` не правится:
   требование 7). `_resolve_target_sha` отдаёт полный sha либо отказывает
   `sys.exit` — и зовётся она в `cmd_canary` до `_ephemeral_clone` и до
   `catalog.cmd_new`, поэтому отказ приходит до первого клона и до
   заведения задачи (AC-8). Дальше полный sha сам доезжает и до
   `canary_runs.main_sha` (AC-9), и до `_sha_label` (AC-10) — тело
   `_sha_label` менять не пришлось, изменился только вход.

5. **Префиксное сравнение — ровно в одном месте.**
   `pin._already_at_run_sha(head_sha, main_sha)` (требование 9): короткий
   `main_sha` прогона, являющийся префиксом HEAD, читается как «уже на
   пине». Пустой/`NULL` `main_sha` намеренно НЕ считается совпадением —
   префиксом пустой строки является любой HEAD, а в живой БД четыре таких
   строки. Историю миграция не дописывает, как и требует SPEC.

**Замер требования 6.** Разовым скриптом (не коммитится), живая БД пульта
только читается — каждый прогон идёт на её КОПИИ во временном каталоге,
`config.DB` подменён на копию; «до» получено подменой `store.migrate`
(индекс не заводится) и подменой обоих читателей журнала на прежнюю
выборку на каждую задачу. Время — минимум из трёх прогонов.

Живая БД: 39 031 запись журнала, 272 задачи.

| Состояние | `status` | `report` |
|---|---|---|
| ДО (без индекса, выборка на задачу) | 602 мс | 3037 мс |
| только индекс | 66 мс | 285 мс |
| только одна выборка (без индекса) | 614 мс | 809 мс |
| ПОСЛЕ (индекс + одна выборка) | 66 мс | 273 мс |

`status` ускорился в 9,1 раза (602 -> 66 мс) — целиком за счёт индекса,
кода `status` задача не трогает. `report` ускорился в 11,1 раза
(3037 -> 273 мс); вклады разделимы: индекс даёт 3037 -> 285 мс, одна
выборка без индекса — 3037 -> 809 мс.

Число SQL-запросов к `steps` на песочной БД (счётчик через
`sqlite3.Connection.set_trace_callback`):

| Задач в БД | читатели журнала `report` до | после | полный `cmd_report` до | после |
|---|---|---|---|---|
| 3 | 12 | 7 | 15 | 10 |
| 6 | 24 | 7 | 30 | 13 |
| 12 | 48 | 7 | 60 | 19 |

Семь запросов после правки — это 1 (`_all_steps`) + 2 target × 3 вызова
`_map_size_entries` из блока роста карты; от числа задач не зависит
(требование 3, AC-5). Честная оговорка, которую нашла и планка
(`acceptance_tests/test_ac4_ac5_report_one_select.py`, докстринг):
ПОЛНЫЙ `cmd_report` читает журнал третьим путём —
`report.token_rate_divergence` -> `spend.known_cost_pairs`, по запросу на
каждую задачу. `orchestrator/spend.py` не входит ни в зоны задачи, ни в
«Не входит», поэтому суммарное число запросов `cmd_report` осталось
N + 7 (10/13/19 выше) и продолжает расти с числом задач. Материал для
Оператора; во времени это уже не видно (273 мс из 3037 мс), потому что
после индекса каждый такой запрос идёт по индексу, а не сканом.

`watch._emit_steps` на одном опросе делал и делает ОДИН запрос — предмет
требования 4 не число запросов, а объём прочитанного: на задаче с 4
записями и известной предпоследней SQL отдаёт 1 строку вместо 4; на самой
длинной истории живой БД (01M1H224X5A8W159MKF1Q24R5Y, 732 записи) каждый
опрос дозора читал 732 строки, теперь — 0-1.

## Шаги

Один шаг = один MR (Фаза 0).

1. Индекс `steps(task_id)` в `SCHEMA` и `migrate`; две выборки журнала в
   `store.py`; `report._all_steps`/`_map_size_entries` и
   `watch._emit_steps` на них; нормализация явного `--sha` в
   `canary._local_full_sha`/`_resolve_target_sha`; префиксное сравнение
   `pin._already_at_run_sha`; юнит-тесты; регенерация
   `docs/codebase-map.md` тем же коммитом.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1 |
| 9 | 1 |
| 10 | 1 |

Где именно закрыто:

| Требование | Место | Тест |
|---|---|---|
| 1 | `schema.py:45` (DDL), `:299` (`migrate`) | `tests/test_steps_task_id_index.py::test_migrate_adds_the_index_and_a_second_run_changes_nothing` |
| 2 | составной индекс не заводится; обоснование — комментарий у DDL | `tests/test_steps_task_id_index.py::test_journal_query_plan_searches_the_index_without_sorting` |
| 3 | `store.all_steps`, `report._all_steps`, `report._map_size_entries` | `tests/test_report.py::JournalIsReadInOneSelectTest`, `tests/test_store_journal.py::BulkJournalReadsTest` |
| 4 | `store.task_steps_since`, `watch._emit_steps` | `tests/test_watch.py::EmitStepsFiltersInSqlTest` |
| 5 | фильтр по каталогу задач в обоих читателях | планка `test_ac4_…` (побайтное сравнение), `tests/test_report.py::test_all_steps_drops_journal_rows_of_pseudo_tasks` |
| 6 | раздел «Подход» выше | — |
| 7 | `canary._local_full_sha`, `canary._resolve_target_sha` | `tests/test_canary.py::LocalFullShaTest`, `ResolveTargetShaTest::test_short_explicit_sha_is_normalized_to_the_full_sha`, `::test_unresolvable_explicit_sha_exits_naming_the_sha` |
| 8 | вход `_sha_label` (тело не менялось) | `tests/test_canary.py::ShaLabelTest::test_explicit_sha_resolved_to_the_pin_is_labelled_pin` |
| 9 | `pin._already_at_run_sha` | `tests/test_pin.py::AlreadyAtRunShaTest`, `::PinToShortGreenShaTest` |
| 10 | все тесты выше; `tests/test_canary.py::ResolveTargetShaTest::test_explicit_sha_is_resolved_locally_without_touching_origin` сохранил проверку `fetch_ref_sha.assert_not_called()` | — |

## Влияние на систему

**Что затронуто за пределами правки.** Индекс `steps(task_id)` меняет
план ВСЕХ чтений журнала, а не только двух переписанных: `catalog.cmd_status`,
`orchestrator/doctor/*`, `orchestrator/auto.py`, `orchestrator/zone_lock.py`,
`orchestrator/retro.py` — все они зовут `store.task_steps`, и все
ускоряются без правки (замер `status` выше). Результаты запросов при этом
те же: индекс не меняет ни состав строк, ни их порядок (`ORDER BY id`
задан явно). Запись в журнал (`store.journal`) становится чуть дороже —
одна запись индекса на строку; `INSERT` в `steps` идёт по одной строке за
вызов, на горячем пути этого не видно.

**Гейты, тесты, лимиты рядом.** Ни один не ослаблен:
- `tests/test_store_schema_migration_parity.py` (паритет схемы) остался
  как есть и зелён — новый индекс объявлен в обоих местах ровно затем,
  чтобы этот класс дефекта не появился.
- `tests/test_canary.py::ResolveTargetShaTest` — единственный тронутый
  существующий тест, и тронут ровно так, как предписывает требование 10
  SPEC: подменена точка ЛОКАЛЬНОГО резолва (`canary._local_full_sha`),
  проверка «`gitcmd.fetch_ref_sha` не вызван» осталась на месте, к ней
  добавился `local_mock.assert_called_once_with`. Сценариев не убыло.
- Планка задачи (`tasks/01M3GKJFN90ATK2KECNDZXPPP6/acceptance_tests/`) не
  правилась ни строкой — 11 тестов зелены.
- Гейт `pin-update` (ADR-0013) не тронут: правка CR-3 живёт только в
  ветке `pin --to` без аргумента.
- Требование 5 (побайтная неизменность вывода `report`/`watch`) —
  инвариант, который планка проверяет прямым сравнением документов.

**Как откатить.** Revert одного merge-коммита. Индекс при этом останется
в живой БД (revert DDL не исполняет) — это безвредно: он не меняет
результатов запросов, а прежний код его просто не использует. Убрать
руками, если понадобится: `DROP INDEX idx_steps_task_id`.

**Прогоны тестов** (передний план, явный таймаут, `-p no:cacheprovider
-p timeout -o timeout=300/400`):
- `tasks/01M3GKJFN90ATK2KECNDZXPPP6/acceptance_tests/` — 11 passed;
- `tests/test_report.py tests/test_watch.py tests/test_pin.py
  tests/test_canary.py tests/test_canary_sets.py tests/test_retro.py
  tests/test_catalog_status_log.py tests/test_prune.py
  tests/test_store_journal.py tests/test_store_db_connection_close.py
  tests/test_store_schema_migration_parity.py
  tests/test_steps_task_id_index.py` — 302 passed, 24 subtests;
- `tests/test_invariants.py tests/test_multitarget.py
  tests/test_multitarget_invariants.py tests/test_cas_set_state.py
  tests/test_spent_estimate_store.py tests/test_coldstart.py
  tests/test_model_tariffs.py` — 186 passed, 229 subtests.
Полный набор `tests/` в шаге не запускался (скил coding-standards: 3-4
минуты, уходит в фон) — его гоняет CI на каждый пуш ветки.

## Риски

- Индекс добавляет ~0,5-1 МБ к файлу БД на текущих 39 тысячах записей и
  одну запись индекса на каждый `store.journal`. Плата принята: чтений
  журнала на порядок больше, чем записей.
- `report._all_steps` держит весь журнал в памяти одним списком — как и
  прежде (прежний код склеивал ровно те же строки), плюс теперь читает
  шесть колонок вместо всех восьми. Роста памяти нет; ретеншн журнала —
  вне задачи («Не входит»).
- Отказ по нерезолвимому `--sha` — новое поведение команды `canary`:
  сценарий, где Оператор сознательно передавал sha, ещё не притянутый в
  локальную базу, теперь отказывает вместо клона. Это и есть требование 7
  (AC-8); обход — `git fetch` перед прогоном, отказ называет точную
  команду проверки.

## Предложения системе

- `orchestrator/spend.py::known_cost_pairs` — третий читатель журнала «по
  запросу на задачу», которого ТЗ этой задачи не назвало, из-за чего
  критерий AC-5 пришлось формулировать по подмножеству читателей (это
  нашла планка, не реализация). Класс: ТЗ, оптимизирующее читателей
  таблицы, стоит выводить из полного списка вызовов (`grep task_steps`),
  а не из списка, собранного профилем одной команды. Кандидат в бэклог
  одной строкой вместе с `catalog.py`, который SPEC уже отложила.
- `skills/coding-standards.md` требует прогонять «планку задачи и тесты
  затронутых модулей», но «затронутый модуль» для правки в `store.py`/
  `schema.py` — это половина набора: `store.task_steps` зовут 20 файлов
  `orchestrator/`. Формулировка не даёт критерия остановки, и выбор
  батчей остаётся на глазомере роли.
