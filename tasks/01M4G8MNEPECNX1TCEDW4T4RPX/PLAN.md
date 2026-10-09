---
task: 01M4G8MNEPECNX1TCEDW4T4RPX
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Детерминизм тестов — линт ожидания по часам и чтения живых файлов, починка неустойчивых тестов

## Подход

Четыре независимые правки. Код ветки — коммиты ea0d184d и следующий за ним
(этот шаг). Линт идёт приложением к `tests/test_invariants.py` (защищённый
путь, вносит Оператор).

**Причина исчезновения `artel-canary-origin-*` (требование 4) — установлена
по коду и проверена исполнением.**
`orchestrator/canary.py::_ephemeral_clone` (main af5e1111, строки 1174-1206)
создавал оба каталога `tempfile.mkdtemp(prefix="artel-canary-…")` и писал
маркер владельца `.artel-canary-owner` только ПОСЛЕ успешного `git clone`
в каталог. Уборка сирот `orchestrator/doctor/orphans.py::_fix_orphan_temp_dirs`
обходит `tempfile.gettempdir()` и удаляет каждый `artel-canary-*`, у
которого `_temp_owner_alive` ложно: для `artel-canary-origin-*` — нет
маркера с живым pid и нет клона, чей `.git/config` называет этот origin
(remote URL пишется ещё позже, `git remote set-url`). Значит всё время от
`mkdtemp` до записи маркера (клонирование `dest`, `checkout`, сам
`git clone --bare` в origin) каталог для уборки — сирота. Тест любого
другого процесса xdist, звавший `doctor --fix` с настоящей уборкой в
системном временном каталоге (`tests/test_doctor_closed_ref_fix.py::
DoctorFixOrderTest` подменял все починки, кроме `_fix_orphan_temp_dirs`;
`TmpRootTest` не уводил `tempfile` модуля уборки), удалял пустой каталог,
и `git clone --bare` в путь, которого уже нет / который удаляется
посреди записи, падал «could not lock config file …/config». Исполнением:
долгоживущий тест `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`
(test_author) запускает уборку в момент клонирования origin — на main он
красен (каталог удалён, «origin-заглушка не создана»), на ветке зелёный.

Устранение — с двух сторон:
- требование 6: `canary._owned_temp_dir` пишет маркер сразу за `mkdtemp`, до
  любого git; `canary._clone_into_owned` клонирует в подкаталог
  `.artel-canary-stage` (git не клонирует в непустой каталог, а маркер уже
  там) и поднимает содержимое в сам каталог. Подкаталог не верхнего уровня
  — уборка его не видит; `doctor/` не правится.
- требование 5: `tests/sandbox.py::isolate_orphan_sweep` (зовётся в
  `TmpRootTest.setUp`) подменяет `tempfile` модуля `doctor/orphans` на
  `TempfileInTestRoot` — уборка теста идёт в его собственном каталоге;
  `DoctorFixOrderTest` подменяет и `_fix_orphan_temp_dirs`.

**Требование 3.** Тест дозора ждёт итераций опроса, а не секунд:
`tests/sandbox.py::PollGate` — подмена паузы `watch` (`patch_sleep`),
цикл дозора после каждой итерации встаёт и ждёт `step` теста; `wait_until`
и `hold` считают итерации (`polls_in(seconds)` при `INTERVAL`), не часы.
Пробник `SuiteRunProfileLimitTest` держится числом пауз
(`range(int(hold/0.05)+1)`), а не `while time.time() < deadline`; уборка
его процессов — `sandbox.wait_processes_gone`. Утверждения тестов не
менялись; в `Ac4ProgressSummaryTest` проверка «второй сводки нет до
отметки 2·N» стала безусловной (раньше выполнялась только при
`remaining > 0.4`) — часы дозора стоят до `advance_watch_clock`.

**Требование 8.** `TempTreeRemovedTest::test_ac8_…` гонял десять настоящих
прогонов гейта в одном методе; теперь метод исполняет свой сценарий
`CASE`, девять подклассов несут остальные девять (тот же метод, те же
утверждения), `TempTreeCasesCoverEveryOutcomeTest` следит, что семейство
покрывает все десять сценариев ровно по разу. `DoctorDurationTest::
test_ac7_…`: (а) живой смок CLI роли в `doctor_checks` подменён — к
сигналу времени не относится; (б) прогоны `full_suite` идут с кешем
байткода, общим для прогонов теста (`warm_pytest_env`; каждый свежий
`PYTHONPYCACHEPREFIX` заново компилировал pytest+xdist, ~0.7 с на каждый
из 19 прогонов), байткод переписываемого `test_case.py` перед каждым
прогоном убирается — устаревший `.pyc` с прежней паузой исключён.
Паузы и число прогонов сценария не менялись.

**Требования 1-2 — линт** `DeterministicTestsLintTest` (приложение ниже):
обход `tests/**/*.py` кроме `tests/sandbox.py` по AST; нарушение
адресуется функцией верхнего уровня («файл::Класс::метод» или
«файл::функция»). (а) `time.sleep`/`from time import sleep` с паузой не
литерал 0; цикл `while`/`for`, в условии которого или в условиях `if` его
тела зовётся `time.monotonic()/time()/…_ns()`. (б) путь (`/`, `joinpath`,
`os.path.join`) от `__file__` или имени, связанного с таким путём
(модульного или локального, до неподвижной точки), с частью
`targets.yaml`/`roles.yaml`/`model_sets.yaml`/`docs…` или
`config.MODEL_SETS_REL`; путь от `config.ROOT` (песочница) — не
нарушение. Перечень `_EXCEPTIONS` — словарь «файл::метод» → обоснование;
`test_exceptions_name_existing_methods_with_reasons` требует непустое
обоснование и существующий метод. 60 записей — существующие нарушения:
предмет теста — живой документ/карта; заместитель сна (не настоящий сон);
время старта настоящих процессов; ожидание отдельных процессов пульта /
проверка отсутствия события; `tests/test_watch.py` — тот же класс, что
тест дозора, перевод на `PollGate` вынесен в «Предложения системе».

## Шаги

1. Канарейка: маркер владельца до клонирования (`orchestrator/canary.py`),
   правка подмен клона в `tests/test_canary.py`.
2. Песочница: `PollGate`, `wait_processes_gone`, `TempfileInTestRoot`/
   `isolate_orphan_sweep` (`tests/sandbox.py`) + сторожа
   `tests/test_sandbox_determinism_helpers.py`; уборка сирот в
   `DoctorFixOrderTest`.
3. Тесты требования 3 на `PollGate` / счёт пауз.
4. Ускорение тестов требования 8 и замер до/после.
5. Линт — приложение к `tests/test_invariants.py` (ниже); существующие
   нарушения — в перечне.
6. Карта кодовой базы перегенерирована (`scripts/codebase_map.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 5 |
| 2 | 5 (перечень), 3 (исправленные тест дозора и пробник) |
| 3 | 2, 3 |
| 4 | 1 (причина — раздел «Подход») |
| 5 | 2 |
| 6 | 1 |
| 7 | долгоживущий `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`; сторож `OrphanSweepStaysInTestRootTest` |
| 8 | 4 |
| 9 | утверждения долгоживущих тестов не менялись |

### Замер времени (требование 8, AC-8)

Параллельный прогон: тесты в отдельных процессах pytest одновременно
(старая версия из копии main рядом с новой, плюс соседи для нагрузки;
xdist внутри шага запрещён сторожем роли), `--durations=0`, время фазы
`call`. Три параллельных замера 09.10.2026; ниже худший (самый
нагруженный) для каждого теста; «после» у семейства `TempTreeRemovedTest`
— самый медленный из десяти классов.

| Тест | до, с | после, с |
|---|---|---|
| `DoctorDurationTest::test_ac7_duration_calibrates_and_ignores_worker_changes` | 112.9 | 33.7 |
| `TempTreeRemovedTest::test_ac8_temp_tree_absent_after_each_outcome` | 129.9 | 26.4 |

Прочие замеры: ac7 — до 65.7 / 77.2 с, после 28.8 / 33.7 с (один в
одиночку — 25 с); ac8 — до 41.6 / 46.1 с, после (худший класс) 8.5 /
9.2 с.

## Влияние на систему

- `orchestrator/canary.py`: каталог клона и origin получают маркер раньше
  — уборка сирот видит их живыми с момента создания; удаление в `finally`
  `_ephemeral_clone` прежнее. Клон через подкаталог: `.git`/объекты
  переносятся `rename` в пределах одного каталога; ссылки bare-origin
  (`alternates` на `dest/.git/objects`) указывают на `dest`, не на
  подкаталог. `doctor/` не правился.
- Песочница: `TmpRootTest` теперь уводит `tempfile` модуля уборки сирот —
  тесты, проверяющие саму уборку, и так подменяют `tempfile.tempdir`
  (тогда `TempfileInTestRoot` отдаёт его как есть).
- Утверждения существующих тестов не ослаблены, методы не удалены и не
  переименованы; лимит pytest-timeout (120 с) не трогался.
- Линт только добавляет класс тестов; его перечень растёт лишь правкой
  `tests/test_invariants.py` (защищённый путь).
- Откат — revert merge-коммита и снятие приложения.

## Риски

- `TempTreeRemovedTest::test_ac8_…` в базовом классе теперь исполняет
  один сценарий из десяти (`if (state, outcome) != self.CASE: continue`);
  девять остальных — подклассы с тем же методом и утверждениями, полноту
  семейства держит `TempTreeCasesCoverEveryOutcomeTest`. Если гейт
  неослабления прочтёт добавленный `continue` как сужение метода —
  это повод для решения Оператора, не тихой правки.
- `tests/test_liveness.py::TerminateProcessGroupTest::
  test_kills_the_leader_and_returns_a_positive_count` красен в окружении
  роли и на файлах, которые ветка не меняет (`orchestrator/liveness.py`,
  сам тест) — не следствие задачи; сверка с базой — `suite-run`.
- Запас ac7 под тяжёлой нагрузкой ~6 с до 40 с: ~9 с — паузы самого
  сценария, остальное — 19 настоящих прогонов pytest и пять `doctor`.

## Предложения системе

- `tests/test_watch.py` (`_settle`, `_wait_until`, тест с паузами) ждёт
  дозор по часам тем же приёмом, что тест дозора 01M446X1 до этой задачи;
  в перечне линта с обоснованием — перевести на `tests/sandbox.py::PollGate`
  отдельной задачей и снять три записи.
- `orchestrator/acceptance.py::_pytest_env` даёт каждому прогону свежий
  `PYTHONPYCACHEPREFIX` — полный прогон гейта компилирует pytest/xdist и
  все `site-packages` заново (~0.7 с на процесс, на каждый рабочий xdist);
  кеш стороннего кода можно держать общим, свежим — только кеш дерева
  прогона.

## Приложение: линт ожидания по часам и чтения живых файлов (`tests/test_invariants.py`)

Проверено на чистом дереве ветки: `git apply --check` — применяется;
после наложения `python3 -m pytest tests/test_invariants.py::DeterministicTestsLintTest`
— 5 passed.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index ec0f457d..fc99473c 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -27,6 +27,7 @@ import socket
 import subprocess
 import sys
 import tempfile
+import textwrap
 import time
 import unittest
 from pathlib import Path
@@ -1982,6 +1983,569 @@ class NoGlobalSleepPatchInInvariantsTest(unittest.TestCase):
         self.assertEqual(findings, [], "\n".join(findings))
 
 
+class DeterministicTestsLintTest(unittest.TestCase):
+    """SPEC 01M4G8MNEPECNX1TCEDW4T4RPX, требования 1-2: тесты `tests/` не
+    ждут по настоящим часам и не читают живые файлы репозитория.
+
+    (а) Ожидание по часам — вызов `time.sleep` с ненулевой (или не
+    литеральной) паузой и цикл (`while`/`for`), чьё условие или сравнение
+    в теле зовёт `time.monotonic()`/`time.time()`: под нагрузкой такой
+    тест краснеет без вины кода (09.10.2026 — три красных гейта приёмки за
+    день). Ожидание — событием, подменённым временем или числом итераций;
+    пауза, без которой не обойтись, — помощник песочницы `tests/sandbox.py`,
+    он вне обхода.
+
+    (б) Чтение настоящих `targets.yaml`, `roles.yaml`, `model_sets.yaml`,
+    `docs/` — путь, собранный от `__file__` (прямо, через имя модуля или
+    локальное имя функции), а не от корня песочницы: тест зависит от
+    содержимого живого файла, который правят параллельные задачи.
+
+    Нарушение адресуется функцией верхнего уровня — методом класса или
+    функцией модуля; исключение — запись `_EXCEPTIONS` «файл::метод» с
+    непустым обоснованием. Перечень пополняется только правкой этого
+    файла (защищённый путь, на виду у Оператора).
+    """
+
+    _CLOCK_CALLS = ("monotonic", "time", "monotonic_ns", "time_ns")
+    _LIVE_FILES = ("targets.yaml", "roles.yaml", "model_sets.yaml")
+    # Имена `config`, равные имени живого файла (относительный путь от
+    # корня, а не путь песочницы).
+    _LIVE_FILE_CONFIG_ATTRS = ("MODEL_SETS_REL",)
+    _SANDBOX_HELPERS = "tests/sandbox.py"
+
+    # «файл::метод» -> обоснование (SPEC 01M4G8MNEPECNX1TCEDW4T4RPX,
+    # требование 2): нарушения, найденные линтом при его заведении и не
+    # исправленные той задачей. Пауза «минимальный сдвиг» — нагрузка делает
+    # прошедшее время только больше, утверждение от этого не краснеет.
+    _EXCEPTIONS = {
+        # --- живые документы и карты — сам предмет проверки -------------------
+        "tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py::StackDocTest::bullet":
+            "предмет теста — живой docs/stack.md: пункт стека сверяется с "
+            "манифестом кода; копия в песочнице проверяла бы саму себя",
+        "tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py::CanaryCodexHomeTest::setUp":
+            "docs/reference/role-home/codex — программный ресурс канарейки "
+            "(референс дома роли, как templates/), копируется в песочницу из "
+            "дерева проверяемого кода, а не данные параллельных задач",
+        "tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py::CanaryProfileTest::setUp":
+            "тот же референс docs/reference/role-home/codex — ресурс кода "
+            "канарейки, копируется в песочницу как есть",
+        "tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py::HelpAndOperatorSessionTest::test_ac8_operator_session_mentions_flag_and_journal":
+            "предмет приёмки — абзац живого docs/operator-session.md о "
+            "--no-answer; документ правится Оператором, копии нет",
+        "tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py::ProfileTimeoutAcceptanceTest::test_ac18_profile_timeout_tests_pass_with_and_without_field":
+            "проверяет, что тестовый модуль профиля работает с настоящей "
+            "записью артели в targets.yaml с подполем и без него; текст "
+            "копируется во временный каталог и правится там",
+        "tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py::HookAndDocumentationTest::test_ac10_doctor_names_migration_for_both_hook_locations":
+            "предмет — указания о миграции хуков в живых "
+            "docs/operator-session.md и docs/stack.md",
+        "tests/test_01m4c954hbjwegd3azs7q3eha4_documentation.py::DocumentationAcceptanceTest::test_ac16_reviewed_position_is_shared_by_chats":
+            "предмет приёмки — правило в живом docs/operator-session.md",
+        "tests/test_models.py::DocsTemplateTest::test_example_file_equals_the_template":
+            "сверяет пример docs/reference/models-local.example.yaml с "
+            "шаблоном кода — расхождение живого файла и есть находка",
+        "tests/test_multitarget.py::TargetsFileTest::test_repository_file_is_valid":
+            "предмет — валидность настоящего targets.yaml репозитория",
+        "tests/test_roles_map_fixture.py::RoleMapFixtureSourceTest::test_config_roles_of_the_test_process_is_the_fixture_not_the_live_file":
+            "путь живой карты нужен для сравнения: тест доказывает, что "
+            "песочница читает фикстуру, а не этот файл",
+        "tests/test_roles_map_fixture.py::RoleMapFixtureSourceTest::test_the_fixture_does_not_read_the_map_it_is_pointed_at":
+            "путь живой карты — для доказательства, что фикстура её не читает",
+        "tests/test_roles_map_fixture.py::LiveRolesMapConsistencyTest::live_roles":
+            "класс сверяет живой roles.yaml с пультом и фикстурой — "
+            "несогласованная правка карты обязана краснеть (требование 4 "
+            "его SPEC)",
+        "tests/test_roles_map_fixture.py::LiveRolesMapConsistencyTest::test_every_agent_role_of_the_live_map_is_runnable_as_written":
+            "предмет — исполнимость ролей живого roles.yaml",
+        "tests/test_roles_map_fixture.py::LiveRolesMapConsistencyTest::test_the_live_map_describes_every_role_the_pult_and_the_fixture_know":
+            "предмет — полнота живого roles.yaml относительно пульта",
+        "tests/test_yaml_parsing.py::MappingTest::test_the_real_roles_file_parses":
+            "предмет — разбор настоящего roles.yaml подмножеством YAML",
+        "tests/test_yaml_parsing.py::RolesTest::test_the_repository_file_answers_for_both_agent_roles":
+            "предмет — ответы настоящего roles.yaml для обеих ролей",
+        # --- пауза подменена: зовётся заместитель, не настоящий сон -----------
+        "tests/test_sandbox_retry_pause.py::TmpRootTestRetryPauseTest::test_default_records_pause_instead_of_sleeping":
+            "runner.time.sleep здесь — заместитель песочницы; тест "
+            "доказывает, что пауза записана, а не проспана",
+        "tests/test_sandbox_retry_pause.py::TmpRootTestRetryPauseTest::test_pult_sleep_patch_overrides_the_default":
+            "runner.time.sleep — подмена patch_pult_sleep, сна нет",
+        "tests/test_sandbox_retry_pause.py::PlainTestCaseRetryPauseTest::test_plain_sandboxes_patch_the_retry_pause":
+            "runner.time.sleep — заместитель песочницы, пауза записывается",
+        "tests/test_sandbox_time_with_sleep.py::PatchSleepTest::test_module_sleep_is_fake_and_stdlib_sleep_stays_real":
+            "runner.time.sleep — заместитель patch_sleep, предмет теста",
+        "tests/test_sandbox_time_with_sleep.py::PatchPultSleepTest::test_every_pult_module_with_a_pause_gets_the_fake_sleep":
+            "module.time.sleep каждого модуля — подмена patch_pult_sleep, "
+            "тест проверяет, что сна нет",
+        # --- настоящее время старта процессов — предмет ------------------------
+        "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateNamesStaleCyclesTest::test_ac1_cycles_started_before_shift_are_named_in_output_and_journal":
+            "минимальный сдвиг GAP_SEC между стартом настоящего процесса "
+            "цикла и записью пина: пульт сравнивает время старта из ps/proc, "
+            "его не подменить; под нагрузкой зазор только растёт",
+        "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateNamesStaleCyclesTest::test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not":
+            "тот же минимальный сдвиг GAP_SEC между стартом процесса и пином",
+        "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateSelectionTest::test_ac3_cycle_started_after_shift_is_not_named":
+            "минимальные сдвиги GAP_SEC до и после пина для двух настоящих "
+            "процессов: порядок стартов — предмет, зазор под нагрузкой "
+            "только растёт",
+        "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateSelectionTest::test_ac4_lease_with_dead_pid_is_not_named":
+            "минимальный сдвиг GAP_SEC между стартом процесса и пином",
+        "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateRobustnessTest::test_ac5_undetermined_start_time_is_marked_and_pin_still_moves":
+            "минимальный сдвиг GAP_SEC между стартом процесса и пином",
+        "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::PinUpdateRobustnessTest::test_ac6_pin_update_sends_no_signals_to_cycles":
+            "минимальный сдвиг GAP_SEC между стартом процесса и пином",
+        "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::DoctorStaleCyclesTest::test_ac7_doctor_warns_about_cycle_older_than_last_pin_record":
+            "минимальные сдвиги GAP_SEC между записями пина и стартами "
+            "настоящих процессов — их порядок и есть предмет",
+        "tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py::DoctorStaleCyclesTest::test_ac7_doctor_is_silent_without_cycles_older_than_pin":
+            "минимальный сдвиг GAP_SEC между пином и стартом процесса",
+        "tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py::sleep_until":
+            "старт процесса ставится на границу целой секунды настоящих "
+            "часов — предмет теста точность времени старта из ps/proc",
+        "tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py::PinUpdateStartPrecisionTest::test_ac1_cycle_started_after_shift_is_not_named_with_proc":
+            "минимальный сдвиг старта процесса после пина (доли секунды) — "
+            "предмет точность времени старта",
+        "tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py::PinUpdateStartPrecisionTest::test_ac3_ps_two_seconds_early_after_shift_is_not_named_silently":
+            "старт процесса в случайной доле секунды после пина — предмет "
+            "округление времени старта ps",
+        "tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py::DoctorStartPrecisionTest::test_ac1_doctor_does_not_name_cycle_started_after_pin_with_proc":
+            "минимальный сдвиг старта процесса после записи пина",
+        "tests/test_01m3yqb4kmady0bet5n8279n6b_start_precision.py::DoctorStartPrecisionTest::test_ac3_doctor_ps_two_seconds_early_after_pin_is_not_named_silently":
+            "старт процесса в случайной доле секунды после пина",
+        "tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py::ObservationCliTest::test_ac6_run_and_auto_refuse_before_spawn_without_live_observer":
+            "минимальный сдвиг 10 мс: порог свежести heartbeat подменён на 0, "
+            "пауза делает отметку наблюдения старше порога по часам пульта",
+        # --- ожидание отдельных процессов пульта -------------------------------
+        "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::SuiteRunSandbox::wait_until":
+            "ожидание фонового suite-run — отдельного процесса пульта в своей "
+            "сессии: события ему не передать, ждётся запись его журнала; "
+            "срок 60 с — страховка от зависания",
+        "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::SuiteRunSandbox::stop_everything":
+            "уборка: дождаться смерти отпущенных процессов прогона, потом "
+            "добить; срок — потолок уборки, не предмет",
+        "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::ProfileRefusalTest::assert_no_run":
+            "проверка отсутствия события (прогон не запущен): пауза даёт "
+            "отказавшей команде время запустить прогон, будь он; нагрузка "
+            "может дать ложно-зелёный, не ложно-красный",
+        "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::BackgroundTest::test_ac6_returns_before_run_ends_and_run_survives_caller":
+            "проверка выживания фонового прогона через секунду после возврата "
+            "вызвавшей команды; под нагрузкой не краснеет",
+        "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::BackgroundTest::test_ac8_wait_reports_finished_or_still_running":
+            "пауза держит --wait в состоянии «ещё идёт» до отпускания "
+            "прогона; дольше под нагрузкой — тот же исход",
+        "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::BackgroundTest::test_ac9_wait_without_any_run_is_refused":
+            "проверка отсутствия события после отказа (прогон не запущен)",
+        "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::FailedRerunTest::test_ac20_failed_without_previous_run_is_refused":
+            "проверка отсутствия события после отказа (прогон не запущен)",
+        "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::LockTest::test_ac21_single_run_lock_refuses_and_releases":
+            "проверка отсутствия события: второй прогон не стартовал",
+        "tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py::SuiteRunAppendixSandbox::settle":
+            "уборка: конец фоновых процессов прогона другой сессии; срок — "
+            "потолок уборки",
+        "tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py::SuiteRunAppendixSandbox::assert_no_temp_tree":
+            "фоновый процесс прогона убирает своё дерево после возврата "
+            "команды; ожидание этой уборки, срок — страховка",
+        "tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py::SuiteRunAppendixSandbox::stop_everything":
+            "уборка: дождаться смерти отпущенных процессов, потом добить",
+        "tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py::LockSandbox::wait_until":
+            "ожидание событий отдельных процессов пульта (журнал пробника "
+            "соперников за замок); срок 60 с — страховка",
+        "tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py::LockSandbox::stop_everything":
+            "уборка: дождаться отпущенных дочерних процессов, потом добить",
+        "tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py::LockSandbox::hold_then_contend":
+            "проверка отсутствия события: соперник не стартовал pytest, пока "
+            "держатель идёт; под нагрузкой — ложно-зелёный, не ложно-красный",
+        "tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py::SuiteRunAndNotesWaitTest::test_ac2_gate_run_waits_for_suite_run":
+            "проверка отсутствия события: прогон гейта не стартовал при "
+            "идущем suite-run",
+        "tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py::SuiteRunRefusesTest::test_ac3_suite_run_refuses_at_once_while_gate_run_holds":
+            "проверка отсутствия события: отказавший suite-run не запустил "
+            "прогон ни при держателе, ни после него",
+        "tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py::RunLimitTest::test_ac5_wait_longer_than_run_limit_keeps_full_run_limit":
+            "предмет — ожидание замка дольше предела прогона: пауза длиннее "
+            "предела по настоящим часам пульта",
+        "tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::launch_signalled":
+            "ожидание файла наблюдения от дочернего процесса канарейки; срок "
+            "20 с — страховка, выход и по смерти дочернего",
+        "tests/test_agent_log.py::RealSubprocessPumpTest::test_first_line_lands_in_log_while_process_is_alive":
+            "предмет — первая строка в логе, пока настоящий процесс жив: "
+            "ожидание записи насоса, срок 10 с — страховка",
+        "tests/test_canary_drive.py::InterruptedPultTest::test_interrupt_while_waiting_kills_the_clone_process_group":
+            "пауза перед KeyboardInterrupt даёт ведению запустить группу "
+            "процессов клона, которую прерывание обязано снять",
+        "tests/test_liveness.py::_wait_for":
+            "ожидание состояния настоящей группы процессов после сигнала; "
+            "срок — страховка, ответ — по предикату",
+        "tests/test_liveness.py::_wait_dead":
+            "ожидание смерти настоящего процесса после сигнала; срок — "
+            "страховка",
+        # --- дозор test_watch: тот же класс, что тест дозора задачи ------------
+        "tests/test_watch.py::_WatchThreadTestCase::_settle":
+            "пауза итераций дозора в потоке; перевод на "
+            "tests/sandbox.py::PollGate, как у теста дозора "
+            "01M446X1B7FB8JDMYFP5APWTVE, — отдельная правка (PLAN "
+            "01M4G8MNEPECNX1TCEDW4T4RPX, «Предложения системе»)",
+        "tests/test_watch.py::_WatchThreadTestCase::_wait_until":
+            "ожидание строки дозора по сроку; перевод на PollGate — та же "
+            "отдельная правка",
+        "tests/test_watch.py::AlertsSurviveDynamicSelectionDropTest::test_alert_for_task_that_left_selection_still_prints":
+            "паузы «итерация дозора прошла»; перевод на PollGate — та же "
+            "отдельная правка",
+    }
+
+    # --- разбор -----------------------------------------------------------
+
+    @classmethod
+    def _is_time_module(cls, node) -> bool:
+        return ((isinstance(node, ast.Name) and node.id == "time")
+                or (isinstance(node, ast.Attribute) and node.attr == "time"))
+
+    @classmethod
+    def _is_clock_call(cls, node, from_time: set) -> bool:
+        if not isinstance(node, ast.Call):
+            return False
+        func = node.func
+        if isinstance(func, ast.Attribute):
+            return (func.attr in cls._CLOCK_CALLS
+                    and cls._is_time_module(func.value))
+        return isinstance(func, ast.Name) and func.id in from_time & set(
+            cls._CLOCK_CALLS)
+
+    @classmethod
+    def _is_sleep_call(cls, node, from_time: set) -> bool:
+        if not isinstance(node, ast.Call):
+            return False
+        func = node.func
+        if isinstance(func, ast.Attribute):
+            return func.attr == "sleep" and cls._is_time_module(func.value)
+        return isinstance(func, ast.Name) and func.id == "sleep" and (
+            "sleep" in from_time)
+
+    @staticmethod
+    def _zero_pause(call: ast.Call) -> bool:
+        args = list(call.args) + [k.value for k in call.keywords]
+        return (len(args) == 1 and isinstance(args[0], ast.Constant)
+                and not isinstance(args[0].value, bool)
+                and args[0].value == 0)
+
+    @staticmethod
+    def _walk_own(node):
+        """Узлы `node` без тел вложенных функций и классов — у вложенной
+        функции свой обход (её нарушение адресуется той же функцией
+        верхнего уровня)."""
+        stack = [node]
+        while stack:
+            current = stack.pop()
+            yield current
+            for child in ast.iter_child_nodes(current):
+                if current is not node and isinstance(
+                        current, (ast.FunctionDef, ast.AsyncFunctionDef,
+                                  ast.Lambda, ast.ClassDef)):
+                    continue
+                stack.append(child)
+
+    @staticmethod
+    def _from_time_names(tree) -> set:
+        return {alias.asname or alias.name for node in ast.walk(tree)
+                if isinstance(node, ast.ImportFrom) and node.module == "time"
+                for alias in node.names}
+
+    @classmethod
+    def _wall_clock_waits(cls, func, from_time: set) -> list:
+        """Строки ожидания по часам внутри функции `func` (вместе с
+        вложенными функциями)."""
+        found = []
+        for node in ast.walk(func):
+            if cls._is_sleep_call(node, from_time) and not cls._zero_pause(node):
+                found.append(f"строка {node.lineno}: time.sleep с ненулевой "
+                             f"паузой")
+            elif isinstance(node, (ast.While, ast.For, ast.AsyncFor)):
+                # Условие цикла и условия `if` в его теле: срок проверяется
+                # там; сравнение меток времени в утверждении — не ожидание.
+                checks = [node.test] if isinstance(node, ast.While) else []
+                checks += [sub.test for stmt in node.body
+                           for sub in cls._walk_own(stmt)
+                           if isinstance(sub, ast.If)]
+                if any(cls._is_clock_call(sub, from_time)
+                       for check in checks for sub in ast.walk(check)):
+                    found.append(f"строка {node.lineno}: цикл до срока по "
+                                 f"time.monotonic()/time.time()")
+        return found
+
+    @classmethod
+    def _mentions_file(cls, node) -> bool:
+        return any(isinstance(sub, ast.Name) and sub.id == "__file__"
+                   or isinstance(sub, ast.Attribute) and sub.attr == "__file__"
+                   for sub in ast.walk(node))
+
+    @classmethod
+    def _is_live_name(cls, node) -> bool:
+        if isinstance(node, ast.Constant) and isinstance(node.value, str):
+            value = node.value.strip("/")
+            return (value in cls._LIVE_FILES or value == "docs"
+                    or value.startswith("docs/"))
+        return (isinstance(node, ast.Attribute)
+                and node.attr in cls._LIVE_FILE_CONFIG_ATTRS)
+
+    @classmethod
+    def _rooted(cls, node, roots: set) -> bool:
+        """Выражение — путь от настоящего корня: несёт `__file__` или имя,
+        связанное с таким путём."""
+        return cls._mentions_file(node) or any(
+            isinstance(sub, ast.Name) and sub.id in roots
+            for sub in ast.walk(node))
+
+    @classmethod
+    def _path_parts(cls, node) -> list | None:
+        """Части выражения-пути: операнды цепочки `/`, получатель и
+        аргументы `joinpath`/`os.path.join`; `None` — не путь."""
+        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
+            return [*(cls._path_parts(node.left) or [node.left]),
+                    *(cls._path_parts(node.right) or [node.right])]
+        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
+            if node.func.attr == "joinpath":
+                return [node.func.value, *node.args]
+            if node.func.attr == "join" and ast.unparse(node.func.value) in (
+                    "os.path", "path"):
+                return list(node.args)
+        return None
+
+    @classmethod
+    def _live_path(cls, node, roots: set) -> bool:
+        parts = cls._path_parts(node)
+        return bool(parts) and any(cls._rooted(p, roots) for p in parts) and any(
+            cls._is_live_name(p) for p in parts)
+
+    @classmethod
+    def _bound_names(cls, statements, test) -> set:
+        """Имена, связанные присваиванием в `statements` со значением,
+        удовлетворяющим `test` (до неподвижной точки: имя от имени)."""
+        names: set = set()
+        assigns = [node for stmt in statements for node in ast.walk(stmt)
+                   if isinstance(node, (ast.Assign, ast.AnnAssign))
+                   and node.value is not None]
+        changed = True
+        while changed:
+            changed = False
+            for node in assigns:
+                targets = node.targets if isinstance(node, ast.Assign) else [
+                    node.target]
+                new = {t.id for t in targets if isinstance(t, ast.Name)} - names
+                if new and test(node.value, names):
+                    names |= new
+                    changed = True
+        return names
+
+    @classmethod
+    def _live_reads(cls, func, module_roots: set, module_live: set) -> list:
+        local_roots = cls._bound_names(
+            func.body, lambda value, names: cls._rooted(
+                value, module_roots | names))
+        roots = module_roots | local_roots
+        found = []
+        for node in ast.walk(func):
+            if cls._live_path(node, roots):
+                found.append(f"строка {node.lineno}: путь к живому файлу "
+                             f"репозитория {ast.unparse(node)}")
+            elif (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
+                  and node.id in module_live):
+                found.append(f"строка {node.lineno}: имя модуля {node.id} — "
+                             f"путь к живому файлу репозитория")
+        return found
+
+    @classmethod
+    def _top_level_functions(cls, tree):
+        """(«Класс::метод» или «функция», узел) — функции верхнего уровня
+        модуля и методы его классов."""
+        for node in tree.body:
+            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
+                yield node.name, node
+            elif isinstance(node, ast.ClassDef):
+                for item in node.body:
+                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
+                        yield f"{node.name}::{item.name}", item
+
+    @classmethod
+    def findings(cls, source: str, rel: str) -> dict:
+        """{«файл::метод»: [нарушения]} исходника `source` файла `rel`.
+
+        Код модуля вне функций (кроме определений имён) не исполняет
+        ожиданий — его присваивания лишь связывают имена корня."""
+        tree = ast.parse(source)
+        from_time = cls._from_time_names(tree)
+        module_stmts = [node for node in tree.body
+                        if isinstance(node, (ast.Assign, ast.AnnAssign))]
+        module_roots = cls._bound_names(
+            module_stmts, lambda value, names: cls._rooted(value, names))
+        module_live = cls._bound_names(
+            module_stmts, lambda value, names: (
+                cls._live_path(value, module_roots)
+                or any(isinstance(sub, ast.Name) and sub.id in names
+                       for sub in ast.walk(value))))
+        result = {}
+        for qualname, func in cls._top_level_functions(tree):
+            hits = (cls._wall_clock_waits(func, from_time)
+                    + cls._live_reads(func, module_roots, module_live))
+            if hits:
+                result[f"{rel}::{qualname}"] = hits
+        return result
+
+    @classmethod
+    def tree_findings(cls, tests_dir: Path) -> dict:
+        found = {}
+        for path in sorted(tests_dir.rglob("*.py")):
+            rel = f"tests/{path.relative_to(tests_dir).as_posix()}"
+            if rel == cls._SANDBOX_HELPERS:
+                continue
+            found.update(cls.findings(path.read_text(encoding="utf-8"), rel))
+        return found
+
+    # --- дерево tests/ ------------------------------------------------------
+
+    def test_tests_tree_has_no_wall_clock_waits_or_live_file_reads(self):
+        """AC-5: на дереве `tests/` нарушений вне перечня исключений нет.
+
+        Ловит мутацию: в метод теста вернули `time.sleep(0.05)` или цикл
+        `while time.monotonic() < deadline` (ожидание дозора до правки
+        01M4G8MNEPECNX1TCEDW4T4RPX), либо чтение `Path(__file__).parent.
+        parent / "targets.yaml"` — сообщение называет «файл::метод» и
+        строку.
+        """
+        tests_dir = Path(__file__).resolve().parent
+        offenders = {key: hits for key, hits in self.tree_findings(
+            tests_dir).items() if key not in self._EXCEPTIONS}
+        self.assertEqual({}, offenders, "\n".join(
+            f"{key}: {'; '.join(hits)}" for key, hits in offenders.items()))
+
+    def test_exceptions_name_existing_methods_with_reasons(self):
+        """AC-4: каждая запись перечня — «файл::метод» существующего метода
+        с непустым обоснованием.
+
+        Ловит мутацию: обоснование записи пусто; запись называет метод,
+        которого в файле нет (опечатка — исключение ничего не снимает,
+        нарушение спрятано иначе); запись называет помощник песочницы.
+        """
+        root = Path(__file__).resolve().parent.parent
+        problems = []
+        for key, reason in self._EXCEPTIONS.items():
+            rel, _, qualname = key.partition("::")
+            if not str(reason).strip():
+                problems.append(f"{key}: нет обоснования")
+            path = root / rel
+            if (rel == self._SANDBOX_HELPERS or not rel.startswith("tests/")
+                    or not path.is_file()):
+                problems.append(f"{key}: файла нет в tests/ (или это "
+                                f"помощники песочницы)")
+                continue
+            names = {name for name, _ in self._top_level_functions(
+                ast.parse(path.read_text(encoding="utf-8")))}
+            if qualname not in names:
+                problems.append(f"{key}: метода нет в файле")
+        self.assertEqual([], problems, "\n".join(problems))
+
+    # --- образцы ------------------------------------------------------------
+
+    def assert_caught(self, source: str) -> None:
+        found = self.findings(textwrap.dedent(source), "tests/test_probe.py")
+        self.assertTrue(found, f"линт не поймал образец:\n{source}")
+
+    def test_sleep_in_method_and_module_helper_is_caught(self):
+        """AC-1: `time.sleep(1)` в методе теста и в помощнике модуля.
+
+        Ловит мутацию: линт ищет только `mock.patch(… "sleep" …)`, а не
+        вызов; линт смотрит лишь методы классов — помощник модуля пропущен;
+        `from time import sleep` пропущен.
+        """
+        self.assert_caught("""
+            import time
+            class ProbeTest:
+                def test_x(self):
+                    time.sleep(1)
+            """)
+        self.assert_caught("""
+            import time
+            def settle():
+                time.sleep(1)
+            """)
+        self.assert_caught("""
+            from time import sleep
+            def settle(pause):
+                sleep(pause)
+            """)
+        self.assertEqual({}, self.findings(textwrap.dedent("""
+            import time
+            def yield_thread():
+                time.sleep(0)
+            """), "tests/test_probe.py"))
+
+    def test_deadline_loops_on_clock_are_caught(self):
+        """AC-2: циклы до срока по `time.monotonic()`/`time.time()` без паузы.
+
+        Ловит мутацию: правило (а) проверяет лишь `time.sleep` — цикл без
+        паузы проходит; цикл распознаётся лишь в форме `< deadline` —
+        разность и проверка в теле `while True` проходят.
+        """
+        self.assert_caught("""
+            import time
+            class ProbeTest:
+                def test_x(self):
+                    deadline = time.monotonic() + 5
+                    while time.monotonic() < deadline:
+                        pass
+            """)
+        self.assert_caught("""
+            import time
+            def wait(started):
+                while time.monotonic() - started < 5:
+                    pass
+            """)
+        self.assert_caught("""
+            import time
+            def wait(deadline, ready):
+                while not ready():
+                    if time.time() > deadline:
+                        raise TimeoutError
+            """)
+
+    def test_live_repository_file_reads_are_caught(self):
+        """AC-3: путь к настоящим `targets.yaml`/`docs/` от `__file__`.
+
+        Ловит мутацию: правило (б) знает только `roles.yaml`; ищет лишь
+        `read_text` выражения с `__file__` — путь через имя модуля
+        `REPO_ROOT` и `open(...)` проходит; путь через локальное имя.
+        """
+        self.assert_caught("""
+            from pathlib import Path
+            class ProbeTest:
+                def test_x(self):
+                    (Path(__file__).resolve().parent.parent
+                     / "targets.yaml").read_text()
+            """)
+        self.assert_caught("""
+            from pathlib import Path
+            REPO_ROOT = Path(__file__).resolve().parents[1]
+            def read():
+                with open(REPO_ROOT / "targets.yaml") as fh:
+                    return fh.read()
+            """)
+        self.assert_caught("""
+            from pathlib import Path
+            def read():
+                root = Path(__file__).resolve().parent.parent
+                return (root / "docs" / "invariants.md").read_text()
+            """)
+        self.assert_caught("""
+            from pathlib import Path
+            DOCS = Path(__file__).resolve().parent.parent / "docs"
+            def read():
+                return sorted(DOCS.glob("*.md"))
+            """)
+        self.assertEqual({}, self.findings(textwrap.dedent("""
+            from orchestrator import config
+            def read():
+                return (config.ROOT / "targets.yaml").read_text()
+            """), "tests/test_probe.py"))
+
+
 class StdlibOnlyImportsInvariantTest(unittest.TestCase):
     """Требование 3 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md): код пульта
     импортирует только стандартную библиотеку — `orchestrator/`,
```
