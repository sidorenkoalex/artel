---
task: 01M443HPZBMJGCHVGV4JQN88RS
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тесты не подменяют time.sleep на весь процесс

## Подход
Один приём на все места — заместитель ссылки модуля пульта на `time`
(требование 1). В `tests/sandbox.py` добавлены:
- `TimeWithSleep(sleep)` — объект, у которого `sleep` подменён, а любой
  другой атрибут читается из настоящего `time` в момент обращения
  (`__getattr__`). Поэтому глобальные подмены `time.monotonic`/`time.time`
  теста, которые SPEC оставляет вне задачи («Не входит»), видны модулю и
  через заместитель — фиктивные часы тестов работают как раньше;
- `patch_sleep(module, sleep)` — `mock.patch.object(module, "time",
  TimeWithSleep(sleep))` (патчер с `start/stop` и `with`);
- `patch_pult_sleep(sleep)` — `patch_sleep` у каждого модуля пульта,
  чья ссылка `time` — модуль `time` (обход `sys.modules` после импорта
  перечня модулей с паузой, найденного `grep -rn "sleep(" orchestrator/`).
  Нужен там, где раньше `mock.patch("time.sleep")` покрывал сценарий
  целиком (мерж через несколько модулей), чтобы не сузить подмену.

Утверждения не трогаются (требование 2): имя `sleep`/`self.pauses`/
`fake_sleep` в каждом методе остаётся тем же объектом, что и раньше;
`mock.patch("time.sleep") as sleep` в `tests/test_main_ci_line.py` стал
`sleep = mock.Mock()` + `patch_sleep(fsm_merge_gate, sleep)`, проверка
`sleep.assert_not_called()` на месте.

Сторож требования 3 — долгоживущий файл test_author
`tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` (не правился).
`tests/test_invariants.py` (защищённый путь) едет приложением ниже:
обе подмены переведены на тот же приём, добавлен метод
`NoGlobalSleepPatchInInvariantsTest::test_this_file_has_no_global_time_sleep_patch`,
прогоняющий поиск сторожа по исходнику самого файла (требование 5).
Код пульта не менялся (требование 7): все места решились без обёртки
паузы в `orchestrator/`.

## Шаги
1. `tests/sandbox.py`: `TimeWithSleep`, `patch_sleep`, `patch_pult_sleep`.
2. Перевод 32 мест в 16 файлах `tests/` (коммит c55b4c7d):
   - `mock.patch.object(<mod>.time, "sleep", f)` → `patch_sleep(<mod>, f)`:
     `test_acceptance_tests_flow.py` 1126, `test_agent_failure.py` 108,
     `test_runner_role_model.py` 110, `test_step_cost.py` 722, 950;
   - `mock.patch.object(time, "sleep", f)` → `patch_sleep(merge_queue, f)`:
     `test_merge_queue.py` 179, 268, 308;
   - `mock.patch("time.sleep") as sleep` → `patch_sleep(fsm_merge_gate, sleep)`:
     `test_main_ci_line.py` 360;
   - вспомогательный метод `self.patch_object/self.patch(<mod>.time, "sleep", f)`
     → `(<mod>, "time", TimeWithSleep(f))`: `test_auto_cycle.py` 1243, 1267,
     1304, 1364, 1390, 1428, 1482; `test_runner_model_preflight.py` 110, 111;
     `test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py` 129;
   - кортеж `(runner.time, "sleep", f)` → `(runner, "time", TimeWithSleep(f))`:
     `test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py` 320,
     `test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py` 202,
     `test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py` 124;
   - `mock.patch.object(watch.time, "sleep", side_effect=…)` →
     `patch_sleep(watch, mock.Mock(side_effect=…))`:
     `test_01m3sx69e8p64d77j1xthmhe40_observation.py` 63, 123, 146, 191,
     213, 242, 273, 298;
   - глобальные часы `("time.sleep", f)` / `mock.patch("time.sleep", …)` →
     `patch_pult_sleep(…)`: `test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` 201,
     `test_01m42pencs26d0656x8fr7dfa7_project_area.py` 1367
     (`time.monotonic`/`time.time` в них не тронуты — «Не входит»).
   - устаревший комментарий в `test_agent_failure.py` (~125: «`time.sleep`
     подменён выше глобально») поправлен под новый приём.
3. Приложение к `tests/test_invariants.py` (ниже) + `docs/codebase-map.md`
   регенерирован.
4. `tests/test_sandbox_time_with_sleep.py` (коммит a0b573c1) — юнит-тесты
   помощников шага 1: пауза модуля подменена, `time.sleep` модуля `time`
   настоящий, атрибуты читаются из `time` в момент обращения;
   `patch_pult_sleep` покрывает вложенные модули и снимается `close()`.
   Временные мутации `tests/sandbox.py` проверены: `patch_sleep` →
   `mock.patch.object(time, "sleep", …)` — 2 failed; обход `sys.modules`
   без вложенных пакетов — красный; `close()` без снятия — красный; после
   возврата кода — 2 passed.
5. Отказ advance (гейт заявки мутации): четыре метода, изменённые шагом 2,
   не несли строку «Ловит мутацию: …» в докстринге — дописана, утверждения
   и тела не тронуты:
   `test_auto_cycle.py::WaitForZoneTest::test_exit_record_names_the_actual_last_holder_on_handoff`
   (была «Ловит мутацию R1-F1:» — не та форма), `::test_enter_and_exit_are_journaled_exactly_once`,
   `::test_lease_lost_during_wait_stops_the_cycle_named`,
   `test_merge_queue.py::WaitForWindowTest::test_ceiling_expiry_dequeues_and_exits_without_touching_state`.
   Каждая заявка проверена временной мутацией `orchestrator/` (код возвращён):
   не обновлять `occupier_id` в цикле `auto._wait_for_zone` — 1 failed;
   запись входа на каждой паузе — 1 failed; `if lease_refusal is not None`
   → `if False` — 1 failed; `finally` в `merge_queue.wait_for_window` без
   `dequeue_merge_wait` — 1 failed. Класс закрыт целиком:
   `guard.test_functions_without_mutation_claim(base, HEAD)` по всем 18
   изменённым файлам `tests/` ветки — пусто.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2, 3 (приложение), 4 |
| 2 | 2 — утверждения не менялись; AC-5 планки `test_task_diff_facts.py` |
| 3 | долгоживущий сторож test_author; зелёный после шага 2 |
| 4 | `tests/test_merge_gate_clock_isolation.py` не изменён |
| 5 | 3 — приложение, `git apply --check` пройден |
| 6 | 2 — методы долгоживущих файлов не удалены/не переименованы, пропусков нет |
| 7 | `orchestrator/` не менялся |

## Влияние на систему
- Затронуты только `tests/` (+ карта). Ни одно утверждение не удалено и
  не смягчено; методы не удалялись и не переименовывались; пропусков не
  добавлено. Гейт неослабления увидит изменённые строки setUp/тел, но не
  утверждения.
- Подмена стала уже: пауза подменена только у модулей пульта; паузы
  стандартной библиотеки (`subprocess.Popen._wait`) теперь настоящие —
  это и есть цель. Для мест с одним модулем (`patch_sleep`) сужение до
  модуля, зовущего паузу в проверяемом пути (`runner`, `auto`, `watch`,
  `merge_queue`, `fsm_merge_gate`); там, где сценарий проходит несколько
  модулей, — `patch_pult_sleep` по всем модулям пульта.
- Откат — revert коммитов c55b4c7d и a0b573c1 (+ неналожение приложения).

Прогоны в шаге (`-p no:cacheprovider -p timeout -o timeout=120`):
- сторож задачи, `test_merge_queue.py`, `test_agent_failure.py`,
  `test_runner_role_model.py`, `test_runner_model_preflight.py`,
  `test_merge_gate_clock_isolation.py`, `test_main_ci_line.py` — 80 passed,
  3 failed: `test_main_ci_line.py::FixesMainArgTest::*` — отказ
  `artel.py approve: команда недоступна процессу роли developer`
  (признак роли в окружении шага; этих методов правка не касалась);
- `test_auto_cycle.py`, `test_step_cost.py`, `test_acceptance_tests_flow.py`,
  `test_01m3sx69e8p64d77j1xthmhe40_observation.py` — 214 passed;
- `test_01m3ychs4…`, `test_01m3ychvv…`, `test_01m3yxyax…`,
  `test_01m409ykm…` — зелёные; `test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`
  — 16 failed, все — отказ `approve`/`pin-update` процессу роли (11) и его
  следствие `merge_gate != done` (5); вне окружения роли их гоняет CI;
- `test_01m42pencs26d0656x8fr7dfa7_project_area.py` — 30 passed;
- с наложенным приложением: `test_invariants.py::MergeNeedsGreenCiTest`,
  `::CountersNeverResetTest`, `::NoGlobalSleepPatchInInvariantsTest` —
  6 passed;
- `tests/test_sandbox_time_with_sleep.py` + долгоживущий сторож задачи —
  6 passed;
- планка (`artel.py plank-run`): 3 passed, 1 failed —
  `test_ac6_invariants_appendix.py`: «PLAN.md не прочитан из ссылки
  документов задачи» (PLAN попадёт в `refs/artifacts/<id>` автокоммитом
  по итогам шага). Та же проверка AC-6 с PLAN.md с диска (те же шаги:
  `guard.plan_appendices`, `git apply --check`/`git apply` на `git archive
  HEAD`, поиск сторожа, прогон добавленного метода, дописка
  `mock.patch("time.sleep")`) — находок нет, метод зелёный (rc 0), после
  дописки красный (rc 1).

## Риски
- `patch_pult_sleep` берёт перечень модулей с паузой из `grep` на пине;
  новый модуль пульта с паузой, не импортированный к моменту вызова,
  останется с настоящей паузой — тест с фиктивными часами тогда зависнет
  до таймаута pytest, а не пройдёт молча (видимо, не тихо).

## Предложения системе
- Класс «глобальная подмена часов» шире `time.sleep`: `mock.patch("time.monotonic")`/
  `"time.time"` (в `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
  `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`,
  `tests/test_merge_queue.py`, `tests/test_invariants.py` ~704) так же
  сдвигают часы стандартной библиотеки — кандидат на ту же задачу
  (`TimeWithSleep` легко расширить до заместителя часов).
- Новый метод `tests/test_invariants.py::NoGlobalSleepPatchInInvariantsTest`
  не внесён в реестр `docs/invariants.md` (docs вне зоны задачи) —
  Оператору решить, инвариант ли это реестра.
- Шаг роли не может прогнать тесты, зовущие `artel.main` с командами
  Оператора (`approve`, `pin-update`): признак роли отказывает им, и
  локальный прогон затронутого модуля даёт ложно-красное
  (`test_main_ci_line.py::FixesMainArgTest`, `test_01m3sf7d…_main_ci.py`).

## Приложение: tests/test_invariants.py

Проверка: `git apply --check` на чистом дереве ветки (HEAD a0b573c1, файл
не изменён) — проходит, вывод пуст, код 0.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index db7195a7..26907ae0 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -42,6 +42,7 @@ from scripts import guard  # noqa: E402
 from tests.sandbox import (FakeProc, SpyRun, TmpRootTest, _stub_check_stack,  # noqa: E402
                            capture, capture_new_task_id,
                            disk_backed_ls_tree_files, disk_backed_show,
+                           patch_pult_sleep, patch_sleep,
                            resilient_tmp_cleanup)
 
 REPO_ROOT = Path(__file__).resolve().parent.parent
@@ -699,7 +700,7 @@ class MergeNeedsGreenCiTest(FsmTest):
                 self.set_ci(stdout, returncode)
                 clock["value"] = 0.0
 
-                with mock.patch.object(time, "sleep", fake_sleep), \
+                with patch_pult_sleep(fake_sleep), \
                      mock.patch.object(time, "monotonic", fake_monotonic), \
                      self.assertRaises(SystemExit) as exit_:
                     self.capture(fsm.cmd_approve, self.TASK)
@@ -1340,7 +1341,7 @@ class CountersNeverResetTest(FsmTest):
         self.write_spec("ready")
         self.write_plan("ready")
         self.set_state("review")
-        patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
+        patcher = patch_sleep(runner, lambda _: None)
         patcher.start()
         self.addCleanup(patcher.stop)
 
@@ -1933,6 +1934,31 @@ class NoNetworkAddressesInTestsTest(unittest.TestCase):
         self.assertEqual([url], hits)
 
 
+class NoGlobalSleepPatchInInvariantsTest(unittest.TestCase):
+    """SPEC 01M443HPZBMJGCHVGV4JQN88RS, требование 5: этот файл не
+    подменяет `time.sleep` на весь процесс.
+
+    Остальное дерево `tests/` держит сторож
+    `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`, но этот файл —
+    защищённый путь, и сторож дерева его не читает: то же свойство здесь
+    проверяет тот же поиск по исходнику самого файла.
+    """
+
+    def test_this_file_has_no_global_time_sleep_patch(self):
+        """Поиск сторожа по исходнику `tests/test_invariants.py` находок не даёт.
+
+        Ловит мутацию: в файл возвращена `mock.patch.object(time, "sleep",
+        fake_sleep)` (FSM-сценарий ожидания CI) или
+        `mock.patch.object(runner.time, "sleep", …)` — поиск вернёт файл и
+        строку подмены, тест покраснеет.
+        """
+        from tests.test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard import (
+            global_sleep_patches)
+        source = Path(__file__).read_text(encoding="utf-8")
+        findings = global_sleep_patches(source, "tests/test_invariants.py")
+        self.assertEqual(findings, [], "\n".join(findings))
+
+
 class StdlibOnlyImportsInvariantTest(unittest.TestCase):
     """Требование 3 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md): код пульта
     импортирует только стандартную библиотеку — `orchestrator/`,
```
