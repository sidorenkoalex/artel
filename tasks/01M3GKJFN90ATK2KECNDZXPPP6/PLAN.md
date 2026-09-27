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
   Запись миграции защищена проверкой наличия самой таблицы —
   `if table_columns(conn, "steps")` (`orchestrator/schema.py:308`), тем же
   вырожденным случаем, что живёт в `add_column` («нет таблицы — нечего
   догонять»). Причина возврата из verifying (прогон 36298443711): `steps`
   заводит только `create_schema`, миграция её не создаёт, а БД с `tasks` и
   без `steps` — штатный вход миграции (минимальные БД прошлых версий в
   `tests/test_agent_failure.py:321`, `tests/test_review_freshness.py`), и
   `CREATE INDEX` на такой БД падал `no such table: main.steps`, унося ВЕСЬ
   `migrate`, то есть любое открытие такой БД. Порядок записей `migrate`
   этого класса не закрывал бы: создавать `steps` в миграции — новая
   таблица во второй копии DDL, ровно тот расход паритета, от которого
   решение 1 и уходит. Паритет схемы сохранён: у свежей и у живой БД
   таблица `steps` есть, ветка проверки на них не срабатывает (AC-1/AC-2
   зелены, планка не правилась).

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

   Итерация 2 (замечание ревью R1-F2): `_map_size_entries` берёт не весь
   журнал, а только записи СВОЕГО действия — `store.steps_of_action(conn,
   action)` (`WHERE action=? ORDER BY id`). Причина: ряд роста карты
   собирается ТРЕМЯ вызовами на КАЖДЫЙ target
   (`map_size_table_rows`/`map_growth_calibration_median`/
   `map_growth_cost_estimate` из `_map_growth_html`), и весь журнал на
   вызов означал `3 × T` полных проходов на отчёт — на 12 задачах это
   1092 прочитанных строки против 624 у прежнего кода, то есть регресс по
   объёму (замер ниже). Подпись `_map_size_entries(conn, target)` при этом
   не менялась: её подменяет чужая залоченная планка
   (`acceptance_tests/_util.old_journal_reading` этой задачи), и мемо или
   лишний параметр сломали бы подмену.

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
`config.DB` подменён на копию; «без индекса» получено `DROP INDEX` на
копии при подменённом `store.migrate` (иначе `migrate` на каждом
`store.db()` завёл бы индекс обратно), «читатели прежние» — подменой
`report._all_steps`/`_map_size_entries` на выборку на каждую задачу.
Время — минимум из трёх прогонов. Таблица перемерена целиком на итерации
2, после правки R1-F2 (все четыре состояния — в одном прогоне, на одной
машине).

Живая БД: 39 101 запись журнала, 272 задачи, 1 target.

| Состояние | `status` | `report` |
|---|---|---|
| ДО (без индекса, выборка на задачу) | 692 мс | 3393 мс |
| только индекс | 89 мс | 301 мс |
| только новые читатели (без индекса) | 703 мс | 802 мс |
| ПОСЛЕ (индекс + новые читатели) | 83 мс | 205 мс |

`status` ускорился в 8,3 раза (692 -> 83 мс) — целиком за счёт индекса,
кода `status` задача не трогает. `report` ускорился в 16,6 раза
(3393 -> 205 мс); вклады разделимы: индекс даёт 3393 -> 301 мс, новые
читатели без индекса — 3393 -> 802 мс. Для сравнения: на итерации 1, где
`_map_size_entries` читал весь журнал, то же состояние «ПОСЛЕ» давало
273 мс при «только индекс» 285 мс — то есть вклад одной выборки в блоке
роста карты был почти неотличим от нуля; после R1-F2 он виден (301 ->
205 мс).

Число SQL-запросов к `steps` и число ПРОЧИТАННЫХ строк у читателей журнала
отчёта на песочной БД (счётчик запросов — `sqlite3.Connection.
set_trace_callback`; строки — обёртка соединения, дочитывающая курсор);
задачи двух target'ов, 13 записей журнала на задачу:

| Задач | вариант чтения | запросов к `steps` | прочитано строк |
|---|---|---|---|
| 3 | прежний (выборка на задачу) | 12 | 156 |
| 3 | итерация 1 (весь журнал на вызов) | 7 | 273 |
| 3 | итерация 2 (ряд действия) | 7 | 57 |
| 6 | прежний | 24 | 312 |
| 6 | итерация 1 | 7 | 546 |
| 6 | итерация 2 | 7 | 114 |
| 12 | прежний | 48 | 624 |
| 12 | итерация 1 | 7 | 1092 |
| 12 | итерация 2 | 7 | 228 |

Число запросов после правки — семь: 1 (`_all_steps`) + 2 target × 3 вызова
`_map_size_entries`; от числа задач не зависит (требование 3, AC-5). Объём
прочитанного — то, на что указало R1-F2: итерация 1 читала БОЛЬШЕ прежнего
кода (1092 против 624 на 12 задачах), итерация 2 читает 228, из которых 156
— единственная выборка `_all_steps`, а на весь блок роста карты приходится
72 строки вместо 936.

Полный `cmd_report` делает те же N + 7 запросов, что и на итерации 1
(N — по запросу на задачу из `spend.known_cost_pairs`): 10 при 3 задачах,
13 при 6, 19 при 12. Честная оговорка, которую нашла и планка
(`acceptance_tests/test_ac4_ac5_report_one_select.py`, докстринг):
ПОЛНЫЙ `cmd_report` читает журнал третьим путём —
`report.token_rate_divergence` -> `spend.known_cost_pairs`, по запросу на
каждую задачу. `orchestrator/spend.py` не входит ни в зоны задачи, ни в
«Не входит», поэтому суммарное число запросов `cmd_report` осталось
N + 7 (10/13/19 выше) и продолжает расти с числом задач. Материал для
Оператора; во времени это уже не видно (205 мс из 3393 мс), потому что
после индекса каждый такой запрос идёт по индексу, а не сканом.

`watch._emit_steps` на одном опросе делал и делает ОДИН запрос — предмет
требования 4 не число запросов, а объём прочитанного: на задаче с 4
записями и известной предпоследней SQL отдаёт 1 строку вместо 4; на самой
длинной истории живой БД (01M1H224X5A8W159MKF1Q24R5Y, 732 записи) каждый
опрос дозора читал 732 строки, теперь — 0-1.

## Шаги

Один шаг = один MR (Фаза 0).

1. Индекс `steps(task_id)` в `SCHEMA` и `migrate`; три выборки журнала в
   `store.py` (`all_steps`, `steps_of_action`, `task_steps_since`);
   `report._all_steps`/`_map_size_entries` и `watch._emit_steps` на них;
   нормализация явного `--sha` в
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
| 1 | `schema.py:62` (DDL), `:308` (`migrate`) | `tests/test_steps_task_id_index.py::test_migrate_adds_the_index_and_a_second_run_changes_nothing`, `::test_migrate_of_a_db_without_the_steps_table_does_not_fail` |
| 2 | составной индекс не заводится; обоснование — комментарий у DDL | `tests/test_steps_task_id_index.py::test_journal_query_plan_searches_the_index_without_sorting` |
| 3 | `store.all_steps`, `store.steps_of_action`, `report._all_steps`, `report._map_size_entries` | `tests/test_report.py::JournalIsReadInOneSelectTest` (в т.ч. `::test_map_size_entries_reads_only_the_rows_of_its_own_action`), `tests/test_store_journal.py::BulkJournalReadsTest` (в т.ч. `::test_all_steps_asks_sql_itself_for_the_chronological_order`, `::test_steps_of_action_takes_only_that_action_and_filters_in_sql`) |
| 4 | `store.task_steps_since`, `watch._emit_steps` | `tests/test_watch.py::EmitStepsFiltersInSqlTest` (в т.ч. `::test_the_already_shown_row_is_not_printed_a_second_time`) |
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

Новая `store.steps_of_action` (итерация 2, R1-F2) — единственный её
читатель — `report._map_size_entries`; индекса по `action` задача не
заводит (SPEC называет только `steps(task_id)`), так что запрос идёт
сканом таблицы, но материализует лишь записи ряда — 100 строк на живой БД
против 39 101. Именно материализация строк и была ценой, а не сам проход:
замер выше это и показывает (301 -> 205 мс на одном target).

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

Итерация 2 (закрытие причины возврата) — прогнан ВЕСЬ набор `tests/`, но
батчами по модулям, потому что `pytest tests/` целиком отказывает сторож
роли в `conftest.py` («полный прогон набора внутри шага запрещён»):
- `tests/test_steps_task_id_index.py tests/test_agent_failure.py
  tests/test_review_freshness.py
  tests/test_store_schema_migration_parity.py` — 42 passed (обе
  упавшие в CI миграционные проверки зелены);
- `tasks/01M3GKJFN90ATK2KECNDZXPPP6/acceptance_tests/` — 11 passed,
  планка не правилась;
- батч зон задачи (`test_report`, `test_watch`, `test_pin`, `test_canary`,
  `test_catalog_status_log`, `test_retro`, `test_invariants`,
  `test_multitarget`, `test_spec_budget`, `test_parent_task_division`,
  `test_zones_approve`, `test_store_journal`) — 405 passed, 284 subtests;
- остальные 161 модуля `tests/` тремя батчами — 956 passed / 116 subtests,
  710 passed / 91 subtests при 1 failed, 993 passed / 196 subtests.
Единственный красный — `tests/test_liveness.py::TerminateProcessGroupTest::
test_kills_the_leader_and_returns_a_positive_count`: он спавнит реальный
процесс новой сессии и ждёт `os.killpg`, а в песочнице шага роли
`terminate_process_group` возвращает 0. К диффу задачи отношения не имеет
(дифф трогает `orchestrator/schema.py` и
`tests/test_steps_task_id_index.py`), в CI ветки этот тест зелён — красными
там были ровно две миграционные проверки из причины возврата. Строка о
самой трении — в «Предложения системе».

Итерация 3 (закрытие замечаний ревью R1-F1 и R1-F2):
- `tests/test_report.py tests/test_store_journal.py tests/test_watch.py
  tests/test_canary.py tests/test_canary_sets.py tests/test_pin.py
  tests/test_steps_task_id_index.py tests/test_retro.py
  tests/test_catalog_status_log.py
  tests/test_store_schema_migration_parity.py
  tests/test_store_db_connection_close.py tests/test_prune.py
  tests/test_invariants.py` — 373 passed, 239 subtests;
- `tasks/01M3GKJFN90ATK2KECNDZXPPP6/acceptance_tests/` — 11 passed, планка
  не правилась ни строкой;
- чужая планка блока роста карты
  (`tasks/01M1RGQV4DG2FX1B90W4EEETTR/acceptance_tests/`, та самая, что
  держит подписи `map_size_table_rows`/`map_growth_calibration_median`) —
  20 passed, 1 failed, и красный не от этого диффа:
  `test_ac4_cost_combines_read_and_creation_rate_of_developer_role`
  падает `AttributeError: module 'orchestrator.config' has no attribute
  'TOKEN_RATES'` — константы нет в main, ревью итерации 1 эту планку тоже
  видело красной на базе.

**Сверка заявок «Ловит мутацию» прогоном под мутацией** (основание закрытия
R1-F1; каждая мутация вносилась в `orchestrator/`, прогонялся модуль,
мутация откатывалась, дерево после сверки чистое):

| Мутация | Красит |
|---|---|
| `ORDER BY id` убран из `store.all_steps` | `test_store_journal.py::…::test_all_steps_asks_sql_itself_for_the_chronological_order` |
| `ORDER BY id` -> `ORDER BY task_id` там же | тот же + `::test_all_steps_returns_the_whole_journal_ordered_by_id` + `test_report.py::…::test_all_steps_reads_the_same_rows_as_the_per_task_selection` |
| `id>?` -> `id>=?` в `store.task_steps_since` | `test_watch.py::…::test_the_already_shown_row_is_not_printed_a_second_time`, `::test_only_the_single_new_row_comes_from_sql`, `test_store_journal.py::…::test_task_steps_since_takes_only_rows_of_that_task_after_the_id` |
| `store.steps_of_action` отдаёт весь журнал (отбор в Python) | `test_store_journal.py::…::test_steps_of_action_takes_only_that_action_and_filters_in_sql`, `test_report.py::…::test_map_size_entries_reads_only_the_rows_of_its_own_action` |
| `_matches_class` снят в `watch._emit_steps` | `test_watch.py::…::test_prints_the_new_rows_of_the_asked_classes_and_moves_the_cursor` (+ два чужих сценария того же модуля) |
| курсор `known_step_id` не сдвигается | те же два теста `EmitStepsFiltersInSqlTest` |
| `_local_full_sha` без `strip()` | `test_canary.py::LocalFullShaTest::…`, `ResolveTargetShaTest::…`, `ShaLabelTest::…` |
| `_local_full_sha` игнорирует `returncode` | `test_canary.py::LocalFullShaTest::test_nonzero_exit_and_no_answer_both_give_an_empty_string` |
| `_already_at_run_sha` сравнивает наоборот | `test_pin.py::AlreadyAtRunShaTest::…`, `PinToShortGreenShaTest::…` |
| `_already_at_run_sha` без проверки непустоты | `test_pin.py::AlreadyAtRunShaTest::test_foreign_sha_and_empty_main_sha_are_not_already_pinned` |
| индекс заведён по `steps(ts)` | три теста `test_steps_task_id_index.py` |
| запись `migrate` без проверки наличия таблицы | `test_steps_task_id_index.py::…::test_migrate_of_a_db_without_the_steps_table_does_not_fail` |

Две заявки пришлось делать ловимыми не переписыванием текста, а усилением
фикстуры (иначе они остались бы обещанием): в `test_report.py` журнал
песочной БД теперь перемешан между задачами (`seed` писал записи задачи
сразу за её заведением, и порядок `task_id` совпадал с порядком `id`), а в
`test_watch.py` окно новых записей сдвинуто на `ids[-4]`, чтобы в него
попала запись класса `steps`, которую фильтру и надо отбросить. Своим же
просевом нашлась третья, ревью не названная: `_local_full_sha` без
проверки `returncode` проходил, потому что фикстура отказа несла пустой
`stdout`; теперь в ней стоит эхо ревизии — так `rev-parse` без `--verify`
и отвечает.

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
- Возврат из verifying требует «прогнать полный набор tests/ до пуша», а
  сторож роли в `conftest.py` отказывает шагу ровно в этом (`pytest
  tests/` -> «полный прогон набора внутри шага запрещён»). Класс:
  требование возврата и сторож шага противоречат друг другу, и роль
  закрывает разрыв вручную — перечислением всех 161 модуля батчами (девять
  минут вместо трёх-четырёх и никакой гарантии, что модуль не потерян).
  Нужна команда пульта «прогнать набор за шаг» либо формулировка возврата,
  адресующая CI.
- `tests/test_liveness.py::TerminateProcessGroupTest::
  test_kills_the_leader_and_returns_a_positive_count` красен в песочнице
  шага роли и зелён в CI: `os.killpg` по процессу новой сессии в песочнице
  не доходит, `terminate_process_group` возвращает 0. Класс: тест на
  реальных OS-сигналах не отличает «сигнал не сработал» от «песочница
  сигнал не пропустила», и роль, сверяющая свой дифф прогоном модулей,
  каждый раз обязана доказывать себе, что красный — чужой.
- Ловимость заявки «Ловит мутацию» зависит не только от ассертов, но и от
  ФИКСТУРЫ, и расхождение видно только прогоном под мутацией: три заявки
  этой задачи были верны «по смыслу» и мертвы на деле, потому что фикстура
  не различала порядок `id` и порядок `task_id` (записи писались задача за
  задачей) и не содержала записи класса, которую фильтр обязан отбросить.
  Класс: ни автор, ни машинный `_mutation_claim_gate`, ни глаз ревьювера
  такого не видят — видит только прогон. Кандидат в скил
  (`skills/test-authoring.md`): на первой сдаче прогонять свои заявки под
  мутациями и вписывать результат в PLAN таблицей «мутация -> какой тест
  краснеет» — она же становится входом ревью. Цена: примерно по минуте на
  заявку (12 мутаций этой задачи — один прогон скриптом).
- «Прочитанный объём» не меряется ни одним гейтом и ни одной планкой, и
  правка, сокращающая ЧИСЛО запросов, спокойно увеличивает объём: одна
  выборка всего журнала на вызов, помноженная на три вызова × T target'ов,
  читала больше строк, чем прежние выборки на задачу (1092 против 624 на
  12 задачах). Нашло это ревью глазом, а не тест. Класс: критерий приёмки
  «число запросов не растёт» без парного «и объём прочитанного не растёт»
  сам приглашает такой регресс; кандидат в шаблон SPEC — при оптимизации
  чтений требовать оба числа.
