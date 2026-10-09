---
task: 01M4G8MNEPECNX1TCEDW4T4RPX
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, tests/sandbox.py, orchestrator/canary.py, orchestrator/liveness.py, docs/codebase-map.md
budget_usd: 40
---

# SPEC: Детерминизм тестов — линт ожидания по часам и чтения живых файлов, починка неустойчивых тестов

## Контекст
09.10.2026 полные прогоны гейтов приёмки трижды за день краснели без вины
задач (01M4C954HBJWEGD3AZS7Q3EHA4, 01M4FZ6QYPPKYQZFEX14QH8XT6). Причины
по сверке на main af5e1111: долгоживущие тесты ждут по настоящим часам
(`tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py` ~260–270 и
~480–485; `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`
~53–61); каталог origin канарейки, созданный `orchestrator/canary.py:1175`
(`tempfile.mkdtemp(prefix="artel-canary-origin-")`), исчезает до `git init`
при параллельном прогоне (гипотеза — уборка сирот
`orchestrator/doctor/orphans.py::_fix_orphan_temp_dirs` из теста другого
процесса xdist в системном временном каталоге, не установлена); два
медленных теста упираются в лимит pytest-timeout 120 с под нагрузкой.
Нужны починка этих мест и линт, который не даст классу вернуться.

## Требования

1. В `tests/test_invariants.py` добавлен линт (по образцу
   `NoNetworkAddressesInTestsTest` ~1876 и
   `NoGlobalSleepPatchInInvariantsTest` ~1960): в `tests/` запрещены
   (а) ожидание по настоящим часам — `time.sleep` с ненулевой паузой и
   циклы до срока по `time.monotonic()`/`time.time()` — вне помощников
   песочницы (`tests/sandbox.py`); (б) чтение настоящих файлов
   репозитория `targets.yaml`, `roles.yaml`, `model_sets.yaml`, `docs/`
   вне их копии в песочнице. Исключения — именованным перечнем записей
   «файл::метод — обоснование» внутри самого линта; запись без
   обоснования не допускается. Правка `tests/test_invariants.py` едет
   приложением к PLAN (вносит Оператор), не правкой ветки.
2. Существующие на момент сдачи нарушения линта требования 1 в `tests/`
   либо исправлены, либо внесены в перечень исключений с обоснованием;
   перечень не пополняется иначе, чем правкой самого линта (приложением
   PLAN, на виду у Оператора).
3. `Ac6NoCommitWarningTest::test_ac6_warning_once_per_step_and_again_for_new_step`
   (`tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py`) и
   `SuiteRunProfileLimitTest::test_ac5_suite_run_cuts_at_profile_limit_and_reports_it`
   (`tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`)
   переведены на подменённое время или на ожидание события без срока по
   настоящим часам; их утверждения не ослабляются.
4. Причина исчезновения каталога `artel-canary-origin-*` до `git init`
   («canary: origin-заглушка не создана: could not lock config file …»)
   установлена исполнением — воспроизведением или доказательством по
   коду — и записана в PLAN; причина устранена.
5. Ни один тест в `tests/` не запускает уборку сирот в системном
   временном каталоге (`tempfile.gettempdir()` процесса прогона) — только
   во временном корне своего теста.
6. Каталог origin канарейки защищён от уборки сирот с момента своего
   создания, а не с момента записи маркера владельца. Правка — на стороне
   `orchestrator/canary.py`/`orchestrator/liveness.py` и тестов;
   `orchestrator/doctor/` только читается.
7. Регрессионный тест на причину, найденную по требованию 4.
8. `DoctorDurationTest::test_ac7_duration_calibrates_and_ignores_worker_changes`
   (`tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`) и
   `TempTreeRemovedTest::test_ac8_temp_tree_absent_after_each_outcome`
   (`tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`) ускорены
   так, чтобы при параллельном прогоне укладываться не больше чем в треть
   лимита pytest-timeout (не больше 40 с каждый); замер времени до и после
   записан в PLAN; утверждения не ослабляются, лимит 120 с не повышается.
9. Смена утверждений долгоживущих тестов (`tests/test_<id>_*.py`) —
   только объявленная в разделе «Меняемое поведение» SPEC (инвариант 38).
   Требования этой задачи смены ожиданий не предполагают — раздел не
   заведён; понадобится смена — это эскалация, не тихая правка.

## Критерии приёмки

AC-1. Линт требования 1 краснеет на тесте-образце в `tests/` с
`time.sleep(1)` вне помощников песочницы и вне перечня исключений.

AC-2. Линт краснеет на тесте-образце с циклом до срока по
`time.monotonic()` вне помощников песочницы и вне перечня исключений.

AC-3. Линт краснеет на тесте-образце, читающем настоящий `targets.yaml`
репозитория (не копию в песочнице).

AC-4. Линт зелёный на методах из перечня исключений и на помощниках
песочницы `tests/sandbox.py`; каждая запись перечня имеет вид
«файл::метод — обоснование» с непустым обоснованием.

AC-5. Линт зелёный на дереве `tests/` ветки задачи с наложенным
приложением PLAN (существующие нарушения исправлены или внесены в
перечень — требование 2).

AC-6. Оба теста требования 3 проходят при искусственно замедленной машине
(подменённые часы идут скачком) без настоящего ожидания по часам, с
прежними утверждениями.

AC-7. Уборка сирот, запущенная тестом, не трогает каталог
`artel-canary-origin-*` другого процесса, созданный до записи маркера
владельца (регрессионный тест требования 7 на найденную причину).

AC-8. PLAN содержит замер времени обоих тестов требования 8 при
параллельном прогоне до и после правки; «после» — не больше 40 с у
каждого.

## Оценка объёма и деление
Сигналов подозрения на большой объём нет: зон вне общих
(`orchestrator/config.py::COMMON_ZONES` — `tests/`,
`docs/codebase-map.md`) — две (`orchestrator/canary.py`,
`orchestrator/liveness.py`), критериев — 8, `budget_usd` 40 ниже порога
`SPLIT_SIGNAL_BUDGET_USD`.

## Не входит

- Подмена паузы повтора агента (`tests/sandbox.py::patch_retry_pause`,
  сделано в 01M48WR0HK).
- Изоляция БД в тестах (задача 01M4FYTB8QWJNHYCP35K8QC4E3).
- Правка `orchestrator/doctor/` (занят 01M4FYTB8QWJNHYCP35K8QC4E3) —
  только чтение.
- Ускорение набора `tests/` в целом и выборочный прогон тестов.
- Повышение лимита pytest-timeout и правка `pytest.ini`.
- Правка `orchestrator/runner.py`, `orchestrator/auto.py`,
  `orchestrator/lease.py`, `orchestrator/fsm.py`, `orchestrator/providers/`,
  `orchestrator/acceptance.py`, `orchestrator/store.py`, `docs/adr/`,
  `docs/invariants.md`, `AGENTS.md`, `CLAUDE.md`, `docs/backlog.md`,
  прочих `docs/` (кроме `docs/codebase-map.md`), `.artel/` — только чтение.
- Неослабление существующих тестов вне объявленного (инвариант 38) — его
  держит пульт (гейт неослабления), отдельного критерия нет.

## Материалы
- ТЗ: `tasks/01M4G8MNEPECNX1TCEDW4T4RPX/TZ.md`.
- Красные прогоны: CI main 158aa0da (`Ac6NoCommitWarningTest`); гейт мержа
  01M48WTP12 (`SuiteRunProfileLimitTest`); 09.10 08:43Z
  `BaselineModelsChangeTest::test_ac12_…` и 11:12Z
  `RunSummaryModelsTest::test_ac10_…`
  (`tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`);
  прогон 1189 с против обычных ~830 (09.10 11:12Z).
- Код: `orchestrator/canary.py:1174-1175` (создание каталогов канарейки),
  `orchestrator/liveness.py:30-46` (`owner_pid`/`owner_alive`),
  `orchestrator/doctor/orphans.py:45-125` (`_fix_orphan_temp_dirs`, обход
  `tempfile.gettempdir()` по префиксам `artel-canary-`, `artel-suite-base-`).
