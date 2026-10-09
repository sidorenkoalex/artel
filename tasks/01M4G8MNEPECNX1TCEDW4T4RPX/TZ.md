---
task: 01M4G8MNEPECNX1TCEDW4T4RPX
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Детерминизм тестов: линт ожидания по часам и чтения живых файлов, неустойчивые тесты

# ТЗ: Детерминизм тестов — линт ожидания по часам и чтения живых файлов, починка неустойчивых тестов

Источник: строка бэклога «Детерминизм тестов…» (приоритет 1, анализ
07.10); решение Оператора 09.10.2026 после трёх красных полных прогонов
гейтов приёмки за день без вины задач (01M4C954HBJWEGD3AZS7Q3EHA4,
01M4FZ6QYPPKYQZFEX14QH8XT6; копилка 09.10).

Факты (main af5e1111, сверка 09.10):
- Ожидание по настоящим часам в долгоживущих тестах:
  `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py` (~260–270:
  цикл до `time.monotonic()`-срока с `time.sleep(0.05)`; ~480–485: запас
  по `time.monotonic()`), `Ac6NoCommitWarningTest::test_ac6_warning_once_per_step_and_again_for_new_step`
  краснел случайно (CI main 158aa0da);
  `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`
  (~53–61: дочерний сценарий держит процесс до `time.time()`-срока),
  `SuiteRunProfileLimitTest::test_ac5_suite_run_cuts_at_profile_limit_and_reports_it`
  краснел на гейте мержа 01M48WTP12.
- Гонка временного каталога канарейки, дважды 09.10:
  `test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`
  (`BaselineModelsChangeTest::test_ac12_…` в 08:43Z,
  `RunSummaryModelsTest::test_ac10_…` в 11:12Z) — «canary:
  origin-заглушка не создана: could not lock config file
  …/T/artel-canary-origin-*/config: No such file or directory»: каталог,
  созданный `orchestrator/canary.py` ~1175 (`tempfile.mkdtemp(prefix=
  "artel-canary-origin-")`), исчезает до `git init`. Отдельно файл
  зелёный. Гипотеза, не установленный факт: уборка сирот
  `orchestrator/doctor/orphans.py::_fix_orphan_temp_dirs` (обход
  `tempfile.gettempdir()` по префиксам `artel-canary-`,
  `artel-suite-base-`), вызванная тестом другого процесса xdist в
  системном временном каталоге, удаляет origin, у которого ещё нет
  маркера владельца.
- Лимит pytest-timeout 120 с под нагрузкой (прогон 1189 с против обычных
  ~830, 09.10 11:12Z):
  `test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac7_duration_calibrates_and_ignores_worker_changes`,
  `test_01m46c776szemypbqgpnjn1txy_appendix_gates.py::TempTreeRemovedTest::test_ac8_temp_tree_absent_after_each_outcome`;
  отдельно зелёные, но медленные (вместе с файлом канарейки — 98 с).
- Пауза повтора агента в песочнице уже подменена
  (`tests/sandbox.py::patch_retry_pause`, задача 01M48WR0HK) — в задачу
  не входит.
- Образец линта в CI — `tests/test_invariants.py::NoNetworkAddressesInTestsTest`
  (~1876), `NoGlobalSleepPatchInInvariantsTest` (~1960).

Требуется:
1. Линт в `tests/test_invariants.py` (приложением к PLAN, правку
   вносит Оператор): в `tests/` запрещены ожидание по настоящим часам
   (`time.sleep` с ненулевой паузой, циклы до срока по `time.monotonic()`/
   `time.time()`) вне помощников песочницы и чтение настоящих файлов
   репозитория (`targets.yaml`, `roles.yaml`, `model_sets.yaml`, `docs/`)
   вне копии в песочнице. Исключения — именованным перечнем
   «файл::метод — обоснование». Существующие нарушения либо исправлены,
   либо внесены в перечень с обоснованием; перечень не растёт молча.
2. Два названных теста ожидания по часам переведены на подменённое время
   или на ожидание события без срока по часам; утверждения не ослабляются.
3. Гонка каталога канарейки: причина установлена исполнением
   (воспроизведение или доказательство по коду) и устранена. Ни один тест
   не убирает сироты в системном временном каталоге — только во
   временном корне своего теста; каталог origin канарейки защищён от
   уборки с момента создания, а не после записи маркера. Правка — на
   стороне `orchestrator/canary.py`/`orchestrator/liveness.py` и тестов:
   `orchestrator/doctor/` занят задачей 01M4FYTB8QWJNHYCP35K8QC4E3 и здесь
   только читается. Регрессионный тест на найденную причину.
4. Два теста, упавшие по лимиту 120 с, ускорены так, чтобы при
   параллельном прогоне укладываться не больше чем в треть лимита
   (замер до и после — в PLAN), без ослабления утверждений и без
   повышения лимита.
5. Смена утверждений долгоживущих тестов — только объявленная в разделе
   «Меняемое поведение» SPEC (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Линт краснеет на тесте-образце с `time.sleep(1)`, с циклом до срока по
  `time.monotonic()` и с чтением настоящего `targets.yaml`; зелёный на
  перечне исключений и на помощниках песочницы.
- Два теста ожидания по часам проходят при искусственно замедленной
  машине (подменённые часы идут скачком) — без настоящего ожидания.
- Уборка сирот, запущенная тестом, не трогает каталог `artel-canary-origin-*`
  другого процесса, созданный до маркера владельца.
- Время двух медленных тестов в PLAN: до и после, не больше 40 с
  каждого при параллельном прогоне.

Зоны: tests/, tests/sandbox.py,
orchestrator/canary.py, orchestrator/liveness.py, docs/codebase-map.md.

Приложением: tests/test_invariants.py (линт требования 1; правку вносит
Оператор).

Только чтение (не менять): orchestrator/runner.py, orchestrator/auto.py,
orchestrator/lease.py, orchestrator/fsm.py, orchestrator/providers/,
orchestrator/acceptance.py, orchestrator/store.py, orchestrator/doctor/
(занят 01M4FYTB8QWJNHYCP35K8QC4E3), pytest.ini и
конфигурация pytest-timeout (лимит 120 с не повышать), docs/adr/,
docs/invariants.md, AGENTS.md, CLAUDE.md, docs/backlog.md, docs/ (прочие
документы), .artel/.

Не входит: подмена паузы повтора агента (сделано в 01M48WR0HK);
изоляция БД в тестах (задача 01M4FYTB8QWJNHYCP35K8QC4E3); ускорение
набора в целом; выборочный прогон тестов.

Рамка: $40.

Набор моделей: по умолчанию.
