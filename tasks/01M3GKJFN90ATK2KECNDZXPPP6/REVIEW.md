---
task: 01M3GKJFN90ATK2KECNDZXPPP6
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Индекс журнала и одна выборка для report/watch; нормализация явного --sha канарейки

## Фаза A: гейт плана

1. **Покрытие требований полно.** SPEC несёт 10 требований, таблица PLAN
   перечисляет 1–10, вторая таблица («Где именно закрыто») даёт адрес и
   тест на каждое. Пропусков нет.
2. **Шаг проверяем как один MR.** Один шаг на два узла (CR-2 + CR-3) —
   это решение самой SPEC («Оценка объёма и деление», монолит), зоны
   узлов не пересекаются ни одним файлом; фактический дифф 833 строки
   при прогнозе 20 КиБ. Не микрооперация и не «сделать всё».
3. **Подход не конфликтует с конвенциями.** SQL остаётся в `store.py`
   (ADR-0003 3ж) — новые `all_steps`/`task_steps_since` заведены там, а
   не в `report.py`; один литерал DDL на `SCHEMA` и `migrate` — тем же
   приёмом, что действующий `MODEL_TARIFFS_DDL`, то есть паритет схемы
   держится текстом, а не двумя копиями; `docs/codebase-map.md`
   регенерирована тем же коммитом (проверено, см. «Проверено
   исполнением»). Защищённые пути (`skills/`, `templates/`,
   `gates.yaml`, `roles.yaml`, `.github/`) не тронуты; диффа по
   защищённому пути в приложении к PLAN нет — он и не требовался.
4. «Влияние на систему» соответствует диффу: затронуты ровно шесть
   файлов зон плюс `tests/` плюс сгенерированная карта, ничего сверх.
   Путь откката описан (revert merge-коммита, `DROP INDEX
   idx_steps_task_id` руками) и честно оговаривает, что revert DDL не
   исполняет.

Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `schema.py:62` (`STEPS_TASK_ID_INDEX_DDL`, `CREATE INDEX IF NOT EXISTS`), `:88` в `SCHEMA`, `:307` в `migrate` под `if table_columns(conn, "steps")`. Идемпотентность и паритет проверены прогоном `tests/test_steps_task_id_index.py` и планкой AC-1/AC-2 |
| 2 | OK | Составной индекс не заведён; обоснование не осталось рассуждением — проверил план запроса сам: `SEARCH steps USING INDEX idx_steps_task_id (task_id=? AND rowid>?)` для фактического запроса `task_steps_since`, без `USE TEMP B-TREE FOR ORDER BY` |
| 3 | OK | `store.all_steps` (`store.py:646`), оба читателя на ней (`report.py:114`, `:138`). Число запросов к `steps` не растёт с числом задач — подтверждено счётчиком планки (`test_ac5_…`) и юнит-тестом |
| 4 | OK | `store.task_steps_since` (`store.py:658`), `watch._emit_steps` (`watch.py:206`); граница строгая (`id>?`), полная история на опросе не читается |
| 5 | OK | Планка AC-4 сравнивает HTML побайтно с эталоном прежнего способа чтения и зелена; фильтр по каталогу задач в `_all_steps` сохранён именно ради этого (записи псевдозадач не попадают в журнал Оператора). Консьюмеры строк журнала сверены: `report.py` и `retro.py` читают только `id`/`task_id`/`ts`/`actor`/`action`/`detail`, ни `session_id`, ни `target`, — сужение списка колонок вывод не меняет. `watch._emit_steps` печатает через `_print_line(ts, task_id, actor, action, detail)` — тем же набором |
| 6 | OK | PLAN несёт оба замера числами: время `status` 602→66 мс, `report` 3037→273 мс с разделёнными вкладами, и таблицу запросов при 3/6/12 задачах. Живую БД пульта я не перезамерял (она вне рабочего каталога шага), свойство «не растёт с числом задач» проверил счётчиком на песочной БД |
| 7 | OK | `canary._local_full_sha` (`canary.py:1124`) — `gitcmd.git("rev-parse", "--verify", "<rev>^{commit}")`, локально; `gitcmd.py` не правился. Отказ `sys.exit` в `_resolve_target_sha` идёт из `cmd_canary:1481` — до `_run_one_task`/`_ephemeral_clone` и до `catalog.cmd_new` (`canary.py:1417`, `:1251`), то есть до первого клона и до заведения задачи |
| 8 | OK | `main_sha` записи — `target_sha` (`canary.py:1312`), а он либо полный резолв явного `--sha`, либо `gitcmd.head_sha()` (`:1309`); обе ветки дают 40 символов. `_sha_label` тело не менял, сравнение полных строк работает (планка AC-10 зелена) |
| 9 | OK | `pin._already_at_run_sha` (`pin.py:79`) — единственное место префиксного сравнения; проверил, что другого СТРОКОВОГО сравнения `main_sha` в коде нет: `canary.py:957` сравнивает через `gitcmd.is_ancestor`, остальные `*_main_sha` — про origin и к `canary_runs` не относятся. Пустой/`NULL` `main_sha` намеренно не «уже на пине» |
| 10 | OK с замечанием | `tests/test_canary.py::ResolveTargetShaTest` не ослаблен: подменена именно точка локального резолва, `fetch_mock.assert_not_called()` на месте, добавлен `local_mock.assert_called_once_with`. Набор зелён (прогоны ниже). Замечание R1-F1 — о ТОЧНОСТИ трёх заявок «Ловит мутацию», а не о покрытии AC |

## Замечания

- **major — tests/test_store_journal.py:65, tests/test_report.py:936,
  tests/test_watch.py:458 — три заявки «Ловит мутацию» описывают
  мутацию, которую тест фактически не ловит; для первых двух это
  означает, что хронология журнала — то самое свойство, за которое
  отвечает новая одна выборка, — не закреплена ни одним тестом.**
  Проверено исполнением, не глазомером:
  1. Мутация «`ORDER BY id` убран из `store.all_steps`»
     (`store.py:646`) — `tests/test_store_journal.py::
     BulkJournalReadsTest::test_all_steps_returns_the_whole_journal_ordered_by_id`
     и `tests/test_report.py::JournalIsReadInOneSelectTest::
     test_all_steps_reads_the_same_rows_as_the_per_task_selection` обе
     ПРОХОДЯТ, хотя обе заявляют этот случай первым. Причина: `steps` —
     rowid-таблица, выборка без `ORDER BY` идёт `SCAN steps` в порядке
     rowid, а `id` — алиас rowid, то есть тот же порядок. Прогнал под
     мутацией и всю остальную обвязку — `tasks/01M3GKJFN90ATK2KECNDZXPPP6/
     acceptance_tests/` (включая побайтный AC-4), `tests/test_report.py`,
     `tests/test_store_journal.py`, `tests/test_retro.py`: 118 passed,
     20 subtests. Ни один тест мутацию не видит.
     Сценарий последствия: следующая правка `all_steps` (добавили
     `WHERE`/`GROUP BY`, сузили колонки под покрывающий индекс, перешли
     на `UNION`) роняет хронологию журнала молча — на ней стоят доли
     гейтов (`report._gate_ratio`), журнал Оператора по дням
     (`_operator_journal_by_day`), ряд роста карты и метрика трения, а
     два теста в это время рапортуют, что порядок закреплён.
  2. Мутация «граница взята нестрого (`id >= ?`)» в
     `store.task_steps_since` — `tests/test_watch.py::
     EmitStepsFiltersInSqlTest::
     test_prints_the_new_rows_of_the_asked_classes_and_moves_the_cursor`
     ПРОХОДИТ под ней. Причина: `known = self.ids[-3]` — это запись
     `developer / agent run завершён`, а `events={"transitions"}` её всё
     равно не печатает, так что повторная выдача незаметна. Класс
     мутации при этом пойман в другом месте (планка
     `test_ac6_…::test_ac6_only_the_single_new_row_comes_from_sql` под
     той же мутацией краснеет: «SQL отдал 2 строк»), то есть дыры в
     покрытии здесь нет — неверна только заявка.
  Предложение: (а) для пп. 1 либо закрепить порядок наблюдаемо — снять
  выполненный SQL тем же приёмом `set_trace_callback`, который уже живёт
  в `tests/test_report.py::_StepsQueries`, и проверить наличие `ORDER BY
  id`, либо переписать докстринги на то, что тесты реально ловят
  («склейка по задачам вместо одной выборки», «`ORDER BY task_id`»), не
  оставляя в заявке случай, который структурно непойманим; (б) для п. 2
  взять `known = self.ids[-2]` (запись `operator / state -> merge_gate`,
  входящая в класс `transitions`) и утверждать, что она НЕ напечатана —
  тогда `>=` красит тест, как заявка и обещает.

- **minor — orchestrator/report.py:122 (`_map_size_entries`) — каждый из
  трёх вызовов на target читает ВЕСЬ журнал пульта, поэтому объём
  прочитанного растёт с числом target'ов: `3 × T` полных выборок на
  отчёт.** Вызовы: `report.py:153` (`map_size_table_rows`), `:184`
  (`map_growth_calibration_median`), `:264` (оценка стоимости карты); все
  три идут из `_map_growth_html` на каждый target. Прежний код на этих
  же трёх вызовах читал только журналы задач ЭТОГО target, то есть в
  сумме по target'ам — один журнал на вызов, а не `T`.
  Сценарий последствия: на двух target'ах живой БД это 6 × 39 тыс. строк
  за отчёт (в замере PLAN не видно — 273 мс), но каждый новый внешний
  target добавляет три полных прохода по всему журналу; на шести
  target'ах это уже 18 проходов, 700 тыс. материализованных строк на один
  `report`. Требование 3 («не зависит от числа ЗАДАЧ») этим не нарушено —
  отсюда minor, а не major.
  Предложение: прочитать журнал один раз в `_map_growth_html` и раздать
  тремя аргументами — но подписи `map_size_table_rows`/
  `map_growth_calibration_median` закреплены чужой планкой
  (`tasks/01M1RGQV4DG2FX1B90W4EEETTR/acceptance_tests/`, менять её эта
  задача не вправе), поэтому дешёвый вариант — внутренний мемо на
  соединение либо приватный `_map_size_entries_all(conn)` с фильтром по
  target у вызывающих. Если считаешь плату несоразмерной текущим двум
  target'ам — отклоняй с этим обоснованием, запись закрою как
  `rejected`; чего не надо — молчать, потому что в диффе это не видно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_store_journal.py:65, tests/test_report.py:936, tests/test_watch.py:458 | три заявки «Ловит мутацию» описывают мутацию, которую тест не ловит (проверено прогоном под мутацией); для двух первых хронология `store.all_steps` остаётся незакреплённой ничем, включая планку AC-4 | правка `all_steps`, роняющая `ORDER BY id`, проходит весь набор зелёной, а доли гейтов/журнал Оператора по дням/ряд роста карты встают на неверный порядок | закрепить порядок наблюдаемо (`set_trace_callback`, как в `_StepsQueries`) либо переписать заявки на реально ловимую мутацию; в test_watch.py взять `known = ids[-2]` — запись класса `transitions` — и утверждать, что она не напечатана |
| R1-F2 | open | orchestrator/report.py:122 (вызовы :153, :184, :264) | `_map_size_entries` читает весь журнал пульта на каждый из трёх вызовов на target — прочитанный объём растёт с числом target'ов (`3 × T` полных выборок) | на шести target'ах один `report` делает 18 полных проходов по журналу (≈700 тыс. строк) там, где прежний код делал три | читать журнал один раз в `_map_growth_html` (подписи публичных функций закреплены чужой планкой — годится мемо на соединение или приватная выборка с фильтром у вызывающих), либо отклонить с обоснованием соразмерности |

## Вердикт

`changes_requested` — исправить R1-F1 (заявки «Ловит мутацию» и
закрепление хронологии `all_steps`), R1-F2 рассмотреть и либо поправить,
либо отклонить с обоснованием. Сам код требований 1–10 реализован и
проверен; ни одного дефекта корректности, безопасности или ослабления
гейтов/тестов я не нашёл.

## Проверено исполнением

Прогоны в переднем плане, явный таймаут, `-p no:cacheprovider -p timeout
-o timeout=300/400`. Полный набор `tests/` не гонял (решение Оператора
05.09, его гоняет CI ветки — на коммите 56545b77 зелёный, 14 проверок).

- `tasks/01M3GKJFN90ATK2KECNDZXPPP6/acceptance_tests/` — 11 passed;
  пометок `# AC-n: manual|skip` в планке нет ни одной (`grep`), автогейт
  acceptance задачи не выключен.
- `tests/test_steps_task_id_index.py tests/test_report.py
  tests/test_watch.py tests/test_pin.py tests/test_canary.py
  tests/test_canary_sets.py tests/test_store_journal.py
  tests/test_store_schema_migration_parity.py tests/test_retro.py
  tests/test_catalog_status_log.py tests/test_agent_failure.py
  tests/test_review_freshness.py` — 322 passed, 24 subtests.
- Второй батч «рядом со `store`/`schema`» (23 модуля: `test_invariants`,
  `test_doctor`, `test_coldstart`, `test_prune`, `test_zone_lock`,
  `test_auto_cycle`, `test_fsm_autogate`, `test_fsm_retro`,
  `test_guard_schema`, `test_step_autocommit`, `test_program_spend_reseed`,
  `test_spent_estimate_store`, `test_store_db_connection_close`,
  `test_zones_approve`, `test_agent_log`, `test_retro_corpus`,
  `test_multitarget_invariants`, `test_catalog_*`, `test_checkpoint_zone_filter`,
  `test_auto_escalated_return_rework_gate`) — 538 passed, 278 subtests.
- **Мутационная сверка заявок (основание R1-F1).** `ORDER BY id` убран из
  `store.all_steps` → планка задачи + `tests/test_report.py` +
  `tests/test_store_journal.py` + `tests/test_retro.py`: 118 passed, 20
  subtests, то есть мутация не поймана никем. `id>?` заменён на `id>=?` в
  `store.task_steps_since` → `tests/test_watch.py::…::
  test_prints_the_new_rows_…` passed (заявка неверна), планка
  `test_ac6_…` failed «SQL отдал 2 строк» (класс всё-таки закрыт).
  Мутации откатывались `git checkout -- orchestrator/store.py`, дерево
  после проверки чистое (`git diff --stat` пуст).
- **План запросов фактических читателей** (не только запроса из AC-3):
  `EXPLAIN QUERY PLAN` на песочной БД со схемой ветки — `SELECT … FROM
  steps WHERE task_id=? AND id>? ORDER BY id` → `SEARCH steps USING INDEX
  idx_steps_task_id (task_id=? AND rowid>?)`, ни `SCAN steps`, ни `USE
  TEMP B-TREE FOR ORDER BY`; `SELECT … FROM steps ORDER BY id` → `SCAN
  steps` (неизбежно, это вся таблица; он же и есть причина, по которой
  мутация из R1-F1 незаметна).
- **Карта кодовой базы свежа**: `python3 scripts/codebase_map.py` →
  `git diff -- docs/codebase-map.md` даёт одну строку, и это
  `built_at_sha` (содержательных `+`/`-` строк ноль). Файл восстановлен
  `git checkout`.
- **Чужие залоченные планки, читающие журнал/отчёт/дозор** (интеграция
  требования 5): `tasks/01M2B6K02YVJBWE1JDWP85EJH0/` (планка прежней
  задачи про целевой sha) + `tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/` — 24
  passed; `01M1VBEKRN0GA029J98S0K2DAQ` — 14 passed;
  `01M290PP4KBTG1KYS1PWKQJH6T` — 18 passed; `01M1RFVWV6WWTXRC5F40K61632`
  — 32 passed; `01M300A14KRHCFB0DQXVCBJEKF` — 22 passed.
  Восемь планок (`T092`, `T096`, `01M1RGQV4DG2FX1B90W4EEETTR`,
  `01M1SD5NZ79MWCEJDJ9JP6EPWS`, `01M1KS8K9RXWHX2PW3ZKB0P903`,
  `01M1NWCM3TDY0YABEKE8DYQA1C`, `01M1PP0VYRT55WN8GGVG66X89Y`,
  `01M31ZHWJWRSACYMRWTCPBC0DM`) дают красные — но НЕ от этого диффа:
  прогнал каждую дважды, второй раз откатив `orchestrator/` на базу
  `ec0d34f6` (`git checkout ec0d34f6 -- orchestrator/`, затем `git
  checkout HEAD -- orchestrator/`), набор упавших ИМЁН тестов до и после
  совпал во всех восьми каталогах. Часть красных структурно чужая
  (`T092::test_ac12_branch_diff_does_not_touch_forbidden_modules` судит
  дифф ЭТОЙ ветки по списку защищённых модулей ТОЙ задачи). Дерево после
  сверки чистое.
- Сверка «набор не ослаблен» — по диффу `tests/`, не прогоном: единственный
  тронутый существующий тест — `tests/test_canary.py::ResolveTargetShaTest::
  test_explicit_sha_is_resolved_locally_without_touching_origin`
  (переименован, ожидание `sha` переведено на полный sha), и он
  разрешён требованием 10 SPEC дословно; `fetch_mock.assert_not_called()`
  сохранён, ассертов не убыло, добавлен `local_mock.assert_called_once_with`.
  Ни один другой `assert` в диффе `tests/` не изменён и не удалён,
  удалённых тестов нет. Планка задачи не правилась ни строкой.

## Предложения системе

- Реестр замечаний (`_registry_gate`) закрывает `approved` на ЛЮБОЙ
  записи не в `accepted`, а «Формат замечаний» скила одновременно велит
  заводить запись и на `minor` («вкус»). Из этих двух правил следует, что
  ревьювер, нашедший один minor и ноль major, обязан либо выдать
  `changes_requested` (вопреки правилу «0 blocker/major → approved»),
  либо промолчать о minor. Класс: правило вердикта и машинный гейт
  реестра расходятся на классе `minor`; нужна либо пометка «minor не
  блокирует реестр», либо явное указание, что minor выносится вне
  реестра.
- `skills/test-authoring.md` требует заявку «Ловит мутацию», но ничто не
  требует её ПРОВЕРЯЕМОСТИ — заявка на структурно непойманимое свойство
  (как `ORDER BY id` на rowid-таблице, R1-F1) читается как покрытие и
  проходит и ревью автора, и машинный `_mutation_claim_gate`. Класс:
  заявка-обещание без способа отличить «мутация поймана» от «мутация
  невозможна к поимке». Кандидат — рекомендация скилу: если мутация
  структурно не наблюдаема, закреплять сам запрос (трасса SQL), а не
  результат.
- Прогон чужих залоченных планок как проверки интеграции стоит ревьюверу
  двух прогонов каждой (свой дифф и база), потому что часть планок красна
  на любой чужой ветке by design (`T092::test_ac12_…` судит дифф текущей
  ветки списком защищённых модулей своей задачи). Класс: залоченная
  планка, чей критерий привязан к СВОЕЙ ветке, становится вечно красной
  для всех последующих задач — таким тестам нужен либо скип вне своей
  задачи, либо переезд в `tests/` с параметром «какая задача».
