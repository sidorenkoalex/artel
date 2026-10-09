---
task: 01M4G8MNEPECNX1TCEDW4T4RPX
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Детерминизм тестов — линт ожидания по часам и чтения живых файлов, неустойчивые тесты

## Фаза A — план

- Таблица покрытия полна: требования 1–9 привязаны к шагам; требование 7 закрыто долгоживущим `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py` и сторожем `OrphanSweepStaysInTestRootTest`.
- Шаги размером с MR, проверяемые (канарейка / песочница / тесты треб. 3 / ускорение треб. 8 / линт-приложение / карта).
- Подход согласован с конвенциями: правка `tests/test_invariants.py` (защищённый путь) идёт приложением; `git apply --check` приложения на дереве ветки я повторил — применяется. `orchestrator/doctor/` не тронут.
- «Влияние на систему» совпадает с diff: `orchestrator/canary.py`, `tests/sandbox.py`, тесты; путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `DeterministicTestsLintTest` в приложении PLAN: (а) `time.sleep` с ненулевой паузой, циклы с часами в условии `while`/условиях `if` тела; (б) пути от `__file__` к `targets.yaml`/`roles.yaml`/`model_sets.yaml`/`docs`. `tests/sandbox.py` вне обхода. Перечень «файл::метод → обоснование», пустое обоснование и несуществующий метод ловит `test_exceptions_name_existing_methods_with_reasons`. Пробелы распознавания — в «Наблюдениях» ниже (не блокируют). |
| 2 | OK | На дереве ветки с наложенным приложением линт зелёный (5 passed). Мой отдельный AST-обход циклов с вызовом часов в любом месте тела нашёл четыре места: `start_precision.py:188` (`sleep_until`) и `agent_log.py:423` внесены в перечень, `suite_reuse.py:175` и `canary_detach.py:45` — замеры длительности в утверждениях, а не ожидание. Скрытых нарушений нет. Алиасов `time` (`import time as …`, `from time import … as …`) в `tests/` нет. |
| 3 | OK | Дозор ждёт итерации через `PollGate`, `wait_until` и `hold` считают итерации; пробник `SuiteRunProfileLimitTest` держится числом пауз. Утверждения прежние. В Ac4 проверка «второй сводки нет до 2·N» стала безусловной (часы дозора заморожены) — это усиление, а не ослабление. Ac6 от настоящего времени не зависит: пороги превышены с запасом от 120 с. |
| 4 | OK | Причина в PLAN: маркер origin писался после `git clone --bare`, а remote URL ещё позже, поэтому каталог был сиротой для `_temp_owner_alive` (`doctor/orphans.py:83-102`, прочитан для сверки). Подтверждено исполнением: мутация «маркер не пишется в `_owned_temp_dir`» роняет `origin_sweep` (см. ниже). |
| 5 | OK | `TmpRootTest.setUp` вызывает `isolate_orphan_sweep`, `DoctorFixOrderTest` подменяет `_fix_orphan_temp_dirs`. По grep `fix=True`/`_fix_orphan_temp_dirs` в `tests/` все остальные вызовы идут в наследниках `TmpRootTest`/`RealGitSandbox` либо при подменённом `tempfile.tempdir` (`test_canary_doctor_owner.py`, `canary_doctor.py`). Субпроцессного `doctor --fix` в тестах нет. |
| 6 | OK | `canary._owned_temp_dir` пишет маркер сразу после `mkdtemp`; `_clone_into_owned` клонирует в подкаталог `.artel-canary-stage` и поднимает содержимое наверх. Ссылки (`alternates` → `dest/.git/objects`, remote URL → `origin_dir`) указывают на итоговые каталоги, а не на stage. Остаточное окно (микросекунды между `mkdtemp` и записью маркера) — в «Наблюдениях». |
| 7 | OK | Долгоживущий `origin_sweep` устроен так: уборка запускается на каждом вызове git, контрольный origin мёртвого владельца удаляется. Сторож песочницы `OrphanSweepStaysInTestRootTest` краснеет, если убрать `isolate_orphan_sweep`. |
| 8 | OK | Замер в PLAN: ac7 112.9 → 33.7 с, ac8 129.9 → 26.4 с (худший класс), лимит 120 с не тронут. У меня при двух параллельных pytest ac7 занял 28.0 с. Разбиение ac8 на 10 классов через `CASE`: данные метода сужены `continue`, но полноту семейства держит `TempTreeCasesCoverEveryOutcomeTest` (каждая пара «вход × исход» ровно один раз), утверждения прежние. Сужение компенсировано, это не ослабление. |
| 9 | OK | Утверждения долгоживущих тестов других задач не изменены (сверено по diff: Ac4 усилен, остальное — механика ожидания). Раздел «Меняемое поведение» не нужен. |

Сверка утверждений с base (`git diff af5e1111...`) по изменённым файлам `tests/`: удалённых или ослабленных `assert*` нет. В `test_canary.py` добавлены только `mkdir` фикстурного каталога (его требует новый порядок «маркер до клона») и докстринги с заявками мутаций. Заявки «Ловит мутацию» у новых и изменённых методов есть, расхождения в них наблюдаемые.

## Замечания

Блокирующих и major-замечаний нет. Ниже наблюдения, которые не блокируют: они не ломают поведение ветки и не прячут существующих нарушений (проверено). Оператору стоит учесть их при наложении приложения.

- Наблюдение — приложение PLAN, `DeterministicTestsLintTest._is_sleep_call`/`_is_time_module`/`_wall_clock_waits`. Линт не распознаёт: `import time as _t; _t.sleep(1)`; `from time import sleep as pause; pause(1)`; цикл до срока, где часы считаются присваиванием в теле, а `if` проверяет имя (`left = d - time.monotonic(); if left <= 0: break`, без `sleep`); методы вложенных классов (`class A: class B: def f`). Все четыре образца я прогнал через `findings` — `{}`. Сейчас в `tests/` таких форм нет, но так класс может вернуться мимо линта. Дёшево закрывается разрешением алиасов из импортов и учётом присваиваний в теле цикла.
- Наблюдение — `orchestrator/canary.py::_owned_temp_dir`. Между `mkdtemp` и записью маркера остаётся окно в микросекунды без вызовов git: уборка, попавшая ровно в него, удалит каталог, и `write_text` упадёт `FileNotFoundError`. Вероятность ничтожна. Окно закрывается полностью, если создать каталог с нейтральным префиксом, записать маркер и переименовать каталог в `artel-canary-…`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker/major/minor-замечаний в этой итерации не заведено (наблюдения выше не блокируют).

## Вердикт

approved.

## Проверено исполнением

- `python3 …/orchestrator/artel.py plank-run 01M4G8MNEPECNX1TCEDW4T4RPX` — `8 passed in 51.64s`, код выхода 0 (`test_jumping_clock.py`, `test_lint_appendix.py`, `test_plan_timings.py`).
- Приложение PLAN извлечено из PLAN.md: `git apply --check` — применяется. Наложено временно, затем `python3 -m pytest tests/test_invariants.py -k DeterministicTestsLintTest` — 5 passed; файл возвращён `git checkout`.
- Пробник пробелов линта (временный скрипт, удалён): четыре образца-обхода → `findings == {}`; обход `tests/` на алиасы `time`, вложенные классы со `sleep` и `sleep` на уровне модуля — ничего. Отдельный AST-обход циклов с вызовом часов в теле — 4 места, все разобраны в таблице (треб. 2).
- `pytest tests/test_canary.py tests/test_doctor_closed_ref_fix.py tests/test_sandbox_determinism_helpers.py tests/test_canary_doctor_owner.py tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py` — 126 passed, 8 subtests passed (ac7 28.0 с, `SuiteRunProfileLimitTest` 8.5 с).
- Параллельно с ним `pytest tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py` — 37 passed; ни один метод ac8 не попал в шесть самых медленных (верх — 14.3 с).
- Временные мутации (код возвращён, `git status` чистый):
  - убрана запись маркера в `canary._owned_temp_dir` → FAILED `OriginSweepTest::test_ac7_sweep_keeps_origin_created_before_owner_marker`;
  - убран `isolate_orphan_sweep(self)` из `TmpRootTest.setUp` → FAILED `OrphanSweepStaysInTestRootTest::test_sweep_under_sandbox_keeps_system_temp_canary_directory`.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, карта свежа (файл возвращён).
- Полный набор `tests/` не гонял (по правилу роли). CI коммита 87589b33 зелёный.

## Предложения системе

- `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py:45-60`: `assertLess(time.monotonic() - started, 3)` — утверждение по настоящим часам, под нагрузкой оно краснеет без вины кода. Это тот же класс неустойчивости, но линт этой задачи его не ловит (он про ожидание, не про замер в утверждении). Кандидат в следующую задачу о детерминизме.
- Линт ожидания (приложение этой задачи): разрешать алиасы импорта `time` и присваивания с часами в теле цикла — см. «Наблюдения»; без этого линт держит класс только в привычной записи.
