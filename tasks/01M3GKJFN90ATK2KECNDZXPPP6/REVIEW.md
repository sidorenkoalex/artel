---
task: 01M3GKJFN90ATK2KECNDZXPPP6
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Индекс журнала и одна выборка для report/watch; нормализация явного --sha канарейки

## Фаза A: гейт плана

1. **Покрытие требований полно и после правок итерации 2.** Таблица
   покрытия по-прежнему несёт все 10 требований SPEC; вторая таблица
   («Где именно закрыто») обновлена под новый код — у требования 3
   добавлены `store.steps_of_action` и
   `tests/test_report.py::…::test_map_size_entries_reads_only_the_rows_of_its_own_action`,
   у требования 3/4 — новые тесты трассы SQL и повторной печати. Ни
   одного требования без адреса и теста.
2. **Шаг остался одним MR.** Дифф итерации 2 поверх базы вердикта —
   6 файлов, 225 вставок; суммарно ветка держится в зонах SPEC (список
   файлов собственных коммитов ветки — в «Проверено исполнением»).
3. **Подход не конфликтует с конвенциями.** Новый SQL заведён в
   `store.py` (`steps_of_action`, `orchestrator/store.py:649`), а не в
   `report.py` — ADR-0003 3ж соблюдён тем же приёмом, что `all_steps`/
   `task_steps_since` итерации 1. Защищённые пути (`skills/`,
   `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не тронуты,
   артефакты `tasks/` в кодовые коммиты не попали, карта регенерирована
   тем же коммитом (67cc467f).
4. **«Влияние на систему» соответствует фактическому диффу.** Раздел
   дополнен честной ценой нового решения: индекса по `action` задача не
   заводит, поэтому `steps_of_action` идёт сканом, но материализует
   только записи ряда — это ровно то, что я вижу в коде
   (`orchestrator/store.py:664-666`) и в плане запроса (см. «Проверено
   исполнением»). Замер требования 6 перемерен целиком на одной машине
   четырьмя состояниями, вклад правки R1-F2 назван числами
   (301 → 205 мс, 1092 → 228 прочитанных строк на 12 задачах).
   Путь откката не менялся и остаётся верным.
5. Наблюдение без последствий (не замечание): PLAN нумерует свои
   итерации собственным счётчиком — работа по замечаниям ревью итерации
   1 называется в «Подход» «Итерация 2», а в «Прогоны тестов» —
   «Итерация 3» (там итерацией 2 названо закрытие возврата из
   verifying). Читается, но требует сверки с `iteration` REVIEW.md.

Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `schema.py:62` (`STEPS_TASK_ID_INDEX_DDL`, `CREATE INDEX IF NOT EXISTS`), `:88` в `SCHEMA`, `:308` в `migrate` под `if table_columns(conn, "steps")`. Итерация 2 этих строк не касалась; `tests/test_steps_task_id_index.py` + планка AC-1/AC-2 + `tests/test_store_schema_migration_parity.py` зелены |
| 2 | OK | Составного индекса нет; проверил план фактических запросов сам (ниже) — `SEARCH steps USING INDEX idx_steps_task_id`, без `USE TEMP B-TREE FOR ORDER BY` |
| 3 | OK | `report._all_steps` (`report.py:114`) — одна `store.all_steps`; `report._map_size_entries` (`report.py:145`) — одна `store.steps_of_action(conn, MAP_SIZE_ACTION)`. Обе выборки берут ровно шесть колонок требования (`_BULK_STEP_COLUMNS`, `store.py:621`). Число запросов к `steps` от числа задач не зависит (7 при 3, 6 и 12 задачах — планка AC-5 и `test_steps_queries_do_not_grow_with_the_number_of_tasks`) |
| 4 | OK | `store.task_steps_since` (`store.py:669`), граница строгая; `watch._emit_steps` (`watch.py:206`) читает из SQL одну строку вместо истории — планка AC-6 и два теста `EmitStepsFiltersInSqlTest` |
| 5 | OK | Планка AC-4 сравнивает HTML побайтно с эталоном прежнего чтения, и подмена эталона (`acceptance_tests/_util.old_journal_reading`) по-прежнему перехватывает ОБА читателя, включая `_map_size_entries` — то есть переход на `steps_of_action` не вывел блок роста карты из-под побайтной сверки (прочитал `_util.py:230-252`, чтобы это подтвердить). Семантика отбора не изменилась: `action=?` в SQLite по умолчанию BINARY-сравнение, то есть точное равенство, которое прежде считалось в Python (`action TEXT` без `COLLATE`, `schema.py:83-87`). Порядок тот же (`ORDER BY id`) |
| 6 | OK | PLAN несёт оба замера числами: время четырьмя состояниями (692 → 83 мс `status`, 3393 → 205 мс `report`, вклады разделены) и таблицу «запросов/прочитанных строк» при 3/6/12 задачах. Живую БД пульта не перезамерял (она вне рабочего каталога шага); свойства «запросов не растёт» и «объём прочитанного не растёт» проверил на песочной БД прогоном планки AC-5 и обоих новых тестов-счётчиков |
| 7 | OK | `canary._local_full_sha` (`canary.py:1123-1141`) — `gitcmd.git("rev-parse", "--verify", "<rev>^{commit}")`, локально; `gitcmd.py` не правился. Отказ `sys.exit` до клона и до `catalog.cmd_new` — планка AC-8 (её подмены падают `AssertionError`, если клон или `cmd_new` случились раньше отказа) |
| 8 | OK | `main_sha` записи — полный резолв явного `--sha` либо `gitcmd.head_sha()`; `_sha_label` тело не менялось, планка AC-9/AC-10 зелена |
| 9 | OK | `pin._already_at_run_sha` — единственное префиксное сравнение; планка AC-11 и `tests/test_pin.py::AlreadyAtRunShaTest`/`PinToShortGreenShaTest` зелены |
| 10 | OK | Набор не ослаблен (сверка по диффу `tests/`, ниже). `tests/test_canary.py::ResolveTargetShaTest` держит `fetch_ref_sha.assert_not_called()`; итерация 2 в `tests/test_canary.py` только УСИЛИЛА фикстуру отказа (`LocalFullShaTest`: к случаю пустого `stdout` добавлен случай эха ревизии при `returncode=128`) — ассертов прибыло, ни один не убыл. Заявки «Ловит мутацию» просеяны мной прогоном под мутациями: все проверенные краснеют (таблица ниже) |

## Замечания

Блокирующих и major-замечаний нет.

Наблюдение вне реестра (minor, вердикта не блокирует — регистрация
записи закрыла бы `approved` машинным гейтом реестра ради копии
тестового помощника, см. «Предложения системе» итерации 1):
`tests/test_report.py:896-932` (`_StepsRows` + `_FetchedRows`) — третья
копия одного и того же помощника «обёртка соединения, считающая строки
выборок `steps`»: первая живёт в `tests/test_watch.py:370-406`
(`_RowCountingConn` + `_FetchedRows`, итерация 1 этой же задачи), вторая
— в планке (`acceptance_tests/_util.py:136-189`, её трогать нельзя).
Общий дом для такого кода в наборе есть — `tests/sandbox.py` (там уже
живут `SpyRun`, `fake_git`, песочницы). Последствие мягкое и целиком
внутри тестов: следующая правка семантики счётчика (например, учёт
`JOIN steps`, который планка уже учитывает, а оба юнит-помощника — нет)
потребует троих правок вместо одной, и копии разъедутся молча.
Кандидат в попутную уборку следующей задачи, трогающей эти модули; чинить
в этой итерации не требую.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_store_journal.py:65, tests/test_report.py:936, tests/test_watch.py:458 | три заявки «Ловит мутацию» описывали мутацию, которую тест не ловил; хронология `store.all_steps` не была закреплена ничем | правка `all_steps`, роняющая `ORDER BY id`, прошла бы набор зелёной | Закрыто. Проверил прогоном под мутациями, а не чтением докстрингов: `ORDER BY id` убран из `store.all_steps` → краснеет `tests/test_store_journal.py::BulkJournalReadsTest::test_all_steps_asks_sql_itself_for_the_chronological_order` (трасса `set_trace_callback` + `assertRegex`), то есть ровно та мутация, которую итерация 1 не ловила НИКЕМ; `ORDER BY task_id` → краснеют оба переписанных теста (`test_all_steps_returns_the_whole_journal_ordered_by_id`, `test_all_steps_reads_the_same_rows_as_the_per_task_selection`) — то есть усиление фикстуры `test_report.py` (две записи `state -> done` после `seed`) действительно сделало заявку ловимой; `id>?` → `id>=?` → краснеет новый `tests/test_watch.py::…::test_the_already_shown_row_is_not_printed_a_second_time`, как и обещала заявка; снятый `_matches_class` и несдвинутый курсор → краснеют оба теста `EmitStepsFiltersInSqlTest` (сдвиг окна на `ids[-4]` завёл в него запись класса `steps`); `_local_full_sha` без `returncode`/без `strip()` → краснеет `LocalFullShaTest` (и `ResolveTargetShaTest`/`ShaLabelTest` для `strip()`). Переписанные докстринги теперь честно называют то, что тест НЕ ловит, и адресуют место, где свойство закреплено — заявок-обещаний в диффе больше нет |
| R1-F2 | accepted | orchestrator/report.py:122 (вызовы :153, :184, :264) | `_map_size_entries` читал весь журнал пульта на каждый из трёх вызовов на target — прочитанный объём рос с числом target'ов | на шести target'ах один `report` делал бы 18 полных проходов по журналу | Закрыто третьим путём (`store.steps_of_action`), и путь лучше обоих предложенных мной: подписи не менялись, мемо на соединение не понадобилось, объём прочитанного перестал зависеть и от числа задач, и от числа target'ов. Проверил не по PLAN, а сам: подмена `steps_of_action` на «весь журнал + отбор в Python» краснит `tests/test_report.py::…::test_map_size_entries_reads_only_the_rows_of_its_own_action` и `tests/test_store_journal.py::…::test_steps_of_action_takes_only_that_action_and_filters_in_sql`; побайтная сверка AC-4 при этом осталась действующей на этом читателе (планка подменяет `report._map_size_entries` целиком, `_util.py:246-252`), и отбор по каталогу задач в теле сохранён — его снятие краснит `test_map_size_entries_still_belong_to_the_asked_target`. Цена решения (скан без индекса по `action`) названа в PLAN «Влияние на систему» и подтверждена замером 301 → 205 мс |

## Вердикт

`approved`. Оба замечания итерации 1 закрыты по сути, а не по форме:
ловимость заявок я перепроверил прогоном десяти мутаций (все краснеют,
таблица ниже), а сокращение прочитанного объёма — счётчиком строк на
песочной БД. Новых дефектов корректности, безопасности, ослабления
тестов/гейтов/лимитов в диффе итерации 2 не нашёл; требования 1–10 SPEC
реализованы и покрыты планкой (11 тестов, ни одной пометки
`manual`/`skip`).

## Проверено исполнением

Прогоны в переднем плане, явный таймаут (`-p no:cacheprovider -p timeout
-o timeout=400`). Полный набор `tests/` в шаге не гонял (решение
Оператора 05.09) — его гоняет CI ветки: на коммите 1ed2f50f зелёный,
14 проверок.

- `tasks/01M3GKJFN90ATK2KECNDZXPPP6/acceptance_tests/` + `tests/test_report.py
  tests/test_store_journal.py tests/test_watch.py tests/test_canary.py
  tests/test_pin.py tests/test_steps_task_id_index.py` — **203 passed,
  16 subtests**. Пометок `# AC-n: manual|skip` в планке нет ни одной
  (grep по каталогу планки) — автогейт acceptance задачи не выключен.
- Второй батч, «рядом со `store`/`schema`/журналом»: `tests/test_retro.py
  tests/test_catalog_status_log.py tests/test_store_schema_migration_parity.py
  tests/test_store_db_connection_close.py tests/test_prune.py
  tests/test_invariants.py tests/test_multitarget.py tests/test_doctor.py
  tests/test_canary_sets.py tests/test_agent_failure.py
  tests/test_review_freshness.py` — **404 passed, 240 subtests**.
- **Мутационная сверка заявок (основание закрытия R1-F1/R1-F2).** Каждая
  мутация вносилась в `orchestrator/`, прогонялись ИМЕННО заявленные
  тесты, мутация откатывалась `git checkout -- <файл>`; дерево после
  сверки чистое (`git status --short` — только неотслеживаемый
  `tasks/<id>/`).

  | Мутация | Результат |
  |---|---|
  | `all_steps`: `ORDER BY id` убран | краснеет (1 failed) `test_all_steps_asks_sql_itself_for_the_chronological_order` |
  | `all_steps`: `ORDER BY id` → `ORDER BY task_id` | краснеют 2: `test_all_steps_returns_the_whole_journal_ordered_by_id`, `test_all_steps_reads_the_same_rows_as_the_per_task_selection` |
  | `task_steps_since`: `id>?` → `id>=?` | краснеют 3: оба теста `EmitStepsFiltersInSqlTest` о новых строках + `test_task_steps_since_takes_only_rows_of_that_task_after_the_id` |
  | `steps_of_action`: весь журнал, отбор в Python | краснеют 2: `test_steps_of_action_takes_only_that_action_and_filters_in_sql`, `test_map_size_entries_reads_only_the_rows_of_its_own_action` |
  | `_local_full_sha`: `returncode` не проверяется | краснеет `LocalFullShaTest::test_nonzero_exit_and_no_answer_both_give_an_empty_string` |
  | `_local_full_sha`: без `strip()` | краснеют 3 сценария (`LocalFullShaTest`, `ResolveTargetShaTest`, `ShaLabelTest`) |
  | `_map_size_entries`: отбор по каталогу задач снят | краснеет `test_map_size_entries_still_belong_to_the_asked_target` |
  | `watch._emit_steps`: фильтр класса снят | краснеет `test_prints_the_new_rows_of_the_asked_classes_and_moves_the_cursor` |
  | `watch._emit_steps`: курсор `known_step_id` не сдвигается | краснеют оба новых теста `EmitStepsFiltersInSqlTest` |
  | `report._all_steps`: фильтр по каталогу задач снят | краснеет `test_all_steps_drops_journal_rows_of_pseudo_tasks` (планка AC-4/AC-5 при этом остаётся зелёной — фильтр держится юнит-тестом, как и заявлено) |

- **План фактических запросов** на песочной БД со схемой ветки:
  `SELECT … FROM steps WHERE task_id=? AND id>? ORDER BY id` →
  `SEARCH steps USING INDEX idx_steps_task_id`, без `SCAN steps` и без
  `USE TEMP B-TREE FOR ORDER BY` (требование 2 подтверждено планом, не
  рассуждением); `… WHERE action=? ORDER BY id` — `SCAN steps`, как и
  честно написано в PLAN «Влияние на систему» (индекса по `action`
  задача не заводит).
- **Чужая залоченная планка блока роста карты**, чей предмет —
  переписанный `_map_size_entries`:
  `tasks/01M1RGQV4DG2FX1B90W4EEETTR/acceptance_tests/` — **20 passed,
  1 failed**, и красный не от этого диффа:
  `test_ac4_cost_combines_read_and_creation_rate_of_developer_role`
  падает `AttributeError: module 'orchestrator.config' has no attribute
  'TOKEN_RATES'` — такой константы нет в `orchestrator/config.py` вовсе
  (grep), а дифф ветки `config.py` не трогает. Ревью итерации 1 видело
  эту планку красной на той же причине.
- **Карта кодовой базы свежа**: `python3 scripts/codebase_map.py` →
  `git diff -- docs/codebase-map.md` даёт одну строку, и это
  `built_at_sha` (содержательных `+`/`-` строк ноль); `steps_of_action`
  в карте присутствует (`docs/codebase-map.md:1431`). Файл восстановлен
  `git checkout`.
- **Зоны не выходят за SPEC**: файлы, тронутые СОБСТВЕННЫМИ коммитами
  ветки (`git log --name-only --grep=<id> main..HEAD`) — `orchestrator/
  {store,schema,report,watch,canary,pin}.py`, `tests/test_{store_journal,
  steps_task_id_index,report,watch,canary,pin}.py`, `docs/codebase-map.md`.
  Ни `gates.yaml`, ни `roles.yaml`, ни `.github/`, ни `templates/`, ни
  `skills/`; артефактов `tasks/` в кодовых коммитах нет.
- **Сверка «набор не ослаблен» — по диффу `tests/`**, не прогоном. В
  диффе итерации 2 удалённых тестов нет; изменены три существующих
  сценария, и все три — усиление, не ослабление: `tests/test_canary.py:
  690-705` (к случаю «пустой `stdout`» добавлен случай «эхо ревизии при
  `returncode=128`», ассерт прежнего случая на месте),
  `tests/test_report.py:974-998` (фикстура перемешана двумя записями,
  ассерты не менялись), `tests/test_watch.py:453-476` (окно расширено с
  `ids[-3]` до `ids[-4]`, набор ассертов тот же). Ни один `assert` не
  удалён и не смягчён; планка задачи не правилась ни строкой.

## Предложения системе

- Ревью итерации 1 выдало верное замечание о заявке «Ловит мутацию»
  только потому, что ПРОГНАЛО мутации; итерация 2 закрыла его, снова
  прогнав мутации; я подтвердил закрытие, прогнав их третий раз. Один и
  тот же прогон делается трижды разными ролями, а его результат каждый
  раз живёт только текстом в артефакте. Класс: сверка заявок мутациями —
  повторяемая машинная работа без носителя. Кандидат: команда пульта
  «прогнать заявки диффа под мутациями» (мутация выводится из текста
  заявки автором, как это вручную сделал PLAN таблицей «мутация → какой
  тест краснеет»), чей вывод складывается в артефакт один раз и
  перечитывается ревью, а не воспроизводится им.
- Залоченная планка `tasks/01M1RGQV4DG2FX1B90W4EEETTR/acceptance_tests/
  test_map_growth_cost_estimate.py` красна на любой ветке: она читает
  `config.TOKEN_RATES`, которой в `orchestrator/config.py` нет вовсе.
  Это второе ревью подряд, которое обязано отдельно доказывать себе
  «красный чужой». Класс: планка, чей предмет не дожил до main, остаётся
  вечным шумом для всех последующих задач — нужен либо её ремонт
  Оператором, либо явный реестр «планок с известным красным и причиной».
