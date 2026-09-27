---
task: 01M3GKJFN90ATK2KECNDZXPPP6
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Индекс журнала и одна выборка для report/watch; нормализация явного --sha канарейки (CR-2, CR-3 ревизии 26.09)

# ТЗ: Индекс журнала и одна выборка для status/report/watch; нормализация явного --sha канарейки (CR-2, CR-3 ревизии 26.09)

Источник: docs/audits/code-revision-2026-09-26.md, находки
CR-2026-09-26-2 (★) и CR-2026-09-26-3 (★); условие «после мержа 6б
(01M3FQ2Z)» наступило 27.09. Задача вне линии провайдеров.

Факты (origin/main после мержа 01M3FQ2Z):
- CR-2: `status` (orchestrator/catalog.py:530–558 `_tokens_field` →
  store.task_steps, `SELECT * FROM steps WHERE task_id=? ORDER BY id`,
  план SCAN) делает полную выборку журнала на каждую задачу: 268 задач ×
  38 362 строки — 0.63 с из 0.72 с (cProfile); 13.09 было 0.23 с на 228
  задачах, рост O(задачи × записи). Тот же приём: report.py:101
  `_all_steps`, :124 `_map_size_entries`; watch.py:201 `_emit_steps`
  (полная выборка на каждом опросе, фильтр `id > known` в Python).
  Индекса на steps нет (schema.py:62–66). Второе мнение ревизии: одна
  выборка `task_id, actor, action, detail … ORDER BY id` с фильтром по
  трём действиям (2 741 строка) и существующий `retro.task_token_total`
  по группам — 0.02–0.05 с при побайтно том же выводе; один индекс
  `steps(task_id)` без правки вызывающих — ~6×. Разбор токенов из
  `detail` (retro.py:99–180) в SQL не переносится: сумма считается парой
  записей одного актёра.
- CR-3: `canary --sha <sha>` (orchestrator/canary.py:879–900
  `_resolve_target_sha`) возвращает явный sha как напечатан;
  `canary_runs.main_sha = target_sha` (:1009). В БД 19 полных sha, 2
  коротких (прогоны 26.09 `195417d9`, `845ad27f`), 4 пустых (v1).
  Потребители со строковым сравнением: pin.py:100 `target == old_sha`
  (`pin --to` без аргумента слеп к «уже на пине» при коротком sha
  последнего зелёного прогона), canary.py:917 `_sha_label`
  (`target_sha == gitcmd.head_sha()` — пометка «код пина» с коротким
  sha не срабатывает никогда). tests/test_canary.py:530–538 требует
  `"deadbeef"` буквально (AC-2 той задачи «без обращения к origin»;
  локальный `rev-parse` его не нарушает).
- store.py и canary.py только что правились задачей 01M3FQ2Z (набор
  канарейки, миграция canary_baseline) — база этой задачи включает её.

Требуется:
1. Индекс `steps(task_id)` (и, если SPEC обоснует, составной
   `steps(task_id, id)`) — новой записью миграции `schema.migrate` по
   образцу существующих, идемпотентно (`CREATE INDEX IF NOT EXISTS`),
   с паритетом схемы новой БД и мигрированной
   (tests/test_store_schema_migration_parity.py).
2. `report._all_steps`/`_map_size_entries` и `watch._emit_steps`:
   одна выборка нужных колонок вместо `SELECT *` по каждой задаче, для
   watch — фильтр `id > known` в SQL; вывод команд побайтно прежний
   (тест сравнивает вывод до и после на одной песочной БД). `status`
   (orchestrator/catalog.py) в эту задачу НЕ входит: catalog.py — зона
   параллельной задачи о пересечении зон; после индекса `status`
   ускоряется без правки, одна выборка для него — следующей задачей.
3. Замер в PLAN: время `status` и `report` на живой БД пульта до/после
   индекса (cProfile или timeit, только чтение), число выполненных
   SQL-запросов report/watch до/после на песочной БД в тесте (счётчик через `sqlite3.Connection.set_trace_callback`
   или подмену execute) — ускорение и сокращение числа запросов
   фиксируются числом.
4. Нормализация sha: `_resolve_target_sha` приводит явный `--sha` к
   полному 40-символьному sha локальным `git rev-parse --verify`
   (без обращения к origin); неразрешимый sha — именованный отказ до
   клона; `canary_runs.main_sha` всегда полный; `_sha_label` и `pin --to`
   сравнивают полные sha. Существующие короткие строки в БД: миграция
   не дописывает их (история), но `pin` и отчёт канарейки при коротком
   `main_sha` в старой строке сравнивают по префиксу — обосновать в SPEC
   либо оставить как есть с пометкой в docs.
5. Тесты (tests/): индекс существует после миграции и в новой БД;
   `report` — тот же вывод и меньше запросов; watch не выбирает всё на
   каждом опросе (число строк выборки ограничено `id > known`); короткий
   `--sha` разрешается в полный, битый — отказ; `tests/test_canary.py`
   AC-2 «без origin» дополнен подменой точки резолва, не ослаблен;
   существующие tests/test_canary.py, tests/test_canary_sets.py,
   tests/test_pin.py, tests/test_report.py, tests/test_watch.py,
   tests/test_retro.py, tests/test_catalog_status_log.py зелёные.

Зоны: orchestrator/store.py, orchestrator/schema.py,
orchestrator/report.py, orchestrator/watch.py, orchestrator/canary.py,
orchestrator/pin.py, tests/.

Только чтение (не менять): orchestrator/catalog.py (зона параллельной
задачи; `status` ускоряется индексом без правки), orchestrator/retro.py,
orchestrator/artel.py, orchestrator/gitcmd.py,
docs/audits/code-revision-2026-09-26.md, docs/backlog.md,
tests/test_invariants.py.

Не входит: изменение формата журнала и разбора токенов из detail;
ретеншн журнала; правка orchestrator/catalog.py (`status` одной
выборкой — следующей задачей); остальные находки ревизии.

Рамка: $30.
