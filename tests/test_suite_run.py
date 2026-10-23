"""Юнит-тесты `orchestrator/suite_run.py` и сохранения итогов полного набора
в `orchestrator/acceptance.py` (SPEC 01M462QACEH29RPRD2RZHGHQFM) — углы, не
покрытые долгоживущим файлом задачи
(`tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`): разбор вывода без
сводки, признак pytest по исполняемому файлу, свежий пустой замок, итог гейта
на грязном дереве, неделимость «новые/на базе» без итога базы.
"""
import contextlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, appendix_tree, config, project_profile,
                          stack, store, suite_run, targets)
from tests.sandbox import RealGitSandbox, TmpRootTest, resilient_tmp_cleanup

XDIST_PARTIAL = """\
tests/test_a.py::test_a
[gw0] [ 25%] PASSED tests/test_a.py::test_a
tests/test_b.py::test_b
[gw0] [ 50%] FAILED tests/test_b.py::test_b
tests/test_c.py::test_c
[gw0] [ 75%] SKIPPED tests/test_c.py::test_c
tests/test_d.py::test_d
"""

FINISHED = """\
[gw0] [ 50%] PASSED tests/test_a.py::test_a
[gw0] [100%] FAILED tests/test_b.py::test_b
=========================== short test summary info ============================
FAILED tests/test_b.py::test_b - ValueError: сбой первой строки
вторая строка сообщения
ERROR tests/test_e.py
==================== 1 failed, 1 passed, 1 error in 0.21s ====================
"""


class ParseTest(unittest.TestCase):

    def test_partial_output_counts_progress_lines(self):
        """Оборванный прогон без сводки pytest считается по строкам хода.

        Ловит мутацию: разбор только по итоговой строке pytest — у
        оборванного прогона чисел нет (все нули), упавший не назван; тест,
        начатый, но не завершённый (строка без исхода), засчитан.
        """
        output = f"{acceptance._full_suite_timeout_note()}\n{XDIST_PARTIAL}"
        parsed = suite_run.parse(False, output)
        self.assertEqual(parsed.outcome, acceptance.FULL_SUITE_TIMEOUT)
        self.assertEqual((parsed.passed, parsed.failed, parsed.skipped),
                         (1, 1, 1))
        self.assertEqual([n for n, _ in parsed.failures],
                         ["tests/test_b.py::test_b"])
        self.assertFalse(parsed.finished)

    def test_finished_output_takes_summary_and_first_message_line(self):
        """Завершённый прогон: числа из сводки, ошибки сбора — упавшими,
        признак — первая строка сообщения.

        Ловит мутацию: `error` не входит в число упавших — «упало: 1»;
        признак берёт и вторую строку сообщения; ERROR без « - » теряется.
        """
        parsed = suite_run.parse(False, FINISHED)
        self.assertTrue(parsed.finished)
        self.assertEqual((parsed.passed, parsed.failed), (1, 2))
        self.assertEqual(dict(parsed.failures), {
            "tests/test_b.py::test_b": "ValueError: сбой первой строки",
            "tests/test_e.py": ""})

    def test_non_xdist_progress_format_is_read(self):
        """Строки хода без xdist («<id> PASSED [ 50%]») тоже считаются.

        Ловит мутацию: разбор знает только формат xdist — при
        `FULL_SUITE_WORKERS = 0` ход прогона и числа обрыва пропадают.
        """
        output = ("tests/test_a.py::test_a PASSED                  [ 50%]\n"
                  "tests/test_b.py::test_b FAILED                  [100%]\n")
        statuses = suite_run._progress(output)
        self.assertEqual(statuses, {"tests/test_a.py::test_a": "PASSED",
                                    "tests/test_b.py::test_b": "FAILED"})

    def test_captured_output_outside_summary_is_not_a_failure(self):
        """Захваченный лог и stdout упавшего теста не дают «упавших».

        Вывод `-vv` с секцией FAILURES, где захваченный лог
        `ERROR    m:test_x.py:3 boom` и stdout `FAILED fake/line - x` и
        `tests/fake.py::test_q PASSED` стоят до сводки; упавший — ровно
        один, из блока «short test summary info».

        Ловит мутацию: разбор `FAILED`/`ERROR` по всему выводу, а не по
        блоку сводки — в перечне появляются `m:test_x.py:3 boom` и
        `fake/line`, и `--failed` передал бы их pytest; строки хода
        читаются и в секциях отчёта — `tests/fake.py::test_q` засчитан.
        """
        output = (
            "============================= test session starts "
            "==============================\n"
            "[gw0] [100%] FAILED tests/test_x.py::test_a\n"
            "=================================== FAILURES "
            "===================================\n"
            "___________________________________ test_a "
            "____________________________________\n"
            "E       assert False\n"
            "----------------------------- Captured stdout call "
            "-----------------------------\n"
            "FAILED fake/line - x\n"
            "tests/fake.py::test_q PASSED\n"
            "------------------------------ Captured log call "
            "-------------------------------\n"
            "ERROR    m:test_x.py:3 boom\n"
            "=========================== short test summary info "
            "============================\n"
            "FAILED tests/test_x.py::test_a - assert False\n"
            "============================== 1 failed in 0.10s "
            "===============================\n")
        parsed = suite_run.parse(False, output)
        self.assertTrue(parsed.finished)
        self.assertEqual(parsed.failures,
                         [("tests/test_x.py::test_a", "assert False")])
        self.assertEqual(acceptance.failed_entries(output),
                         [("tests/test_x.py::test_a", "assert False")])
        self.assertEqual(suite_run._progress(output),
                         {"tests/test_x.py::test_a": "FAILED"})


class RenderTest(unittest.TestCase):

    def test_without_base_failures_are_not_split(self):
        """Без итога базы отчёт не делит упавших и не печатает чисел рядом
        с «новые на ветке»/«падают и на базе».

        Ловит мутацию: при `base_failed=None` все упавшие объявлены новыми
        (`новые на ветке: N`) — сравнение выдумано.
        """
        parsed = suite_run.parse(False, FINISHED)
        text = suite_run.render("T1", 3, suite_run.MODE_FULL, parsed, None,
                                "прогон базы не завершён", Path("/x.log"))
        self.assertIn(suite_run.NO_BASE, text)
        self.assertNotIn(suite_run.NEW_ON_BRANCH, text)
        self.assertNotIn(suite_run.ALSO_ON_BASE, text)
        self.assertIn("tests/test_b.py::test_b", text)

    def test_summary_mismatch_line_only_when_parsed_fewer(self):
        """Строка «итог pytest: N упавших, разобрано M» — только при M < N.

        Сценарий: завершённый вывод, где разобраны все упавшие (2 из 2 —
        FINISHED), — строки сверки нет; тот же вывод, где итог называет 3
        упавших, — строка есть с числами 3 и 2.

        Ловит мутацию: строка сверки печатается всегда или при M <= N —
        полностью разобранный прогон получает ложную тревогу; сверка
        сравнивает с числом строк хода — 3 упавших итога не названы.
        """
        def text(output):
            return suite_run.render("T1", 1, suite_run.MODE_FULL,
                                    suite_run.parse(False, output), None,
                                    "база фикстуры", Path("/x.log"))
        self.assertNotIn("итог pytest:", text(FINISHED))
        more = FINISHED.replace("1 failed, 1 passed, 1 error",
                                "2 failed, 1 passed, 1 error")
        self.assertIn("итог pytest: 3 упавших, разобрано 2", text(more))

    def test_plural_forms(self):
        """Формы «тест/теста/тестов» и «группа/группы/групп» по числу.

        Ловит мутацию: форма по последней цифре без исключения 11-14 —
        «11 тест», «12 теста».
        """
        cases = {1: "тест", 2: "теста", 5: "тестов", 11: "тестов",
                 12: "тестов", 21: "тест", 104: "теста"}
        for n, form in cases.items():
            self.assertEqual(suite_run._plural(n, "тест", "теста", "тестов"),
                             form, n)


class PytestCommandTest(unittest.TestCase):

    def test_pytest_executable_and_module_forms(self):
        """Запуск pytest — исполняемый `pytest`/`py.test` или `-m pytest`.

        Ловит мутацию: признаётся только `-m pytest` — профиль
        `[.venv/bin/pytest]` отклонён; признаётся любое упоминание
        «pytest» в аргументах — `-m unittest pytest_like` принят.
        """
        self.assertTrue(suite_run._is_pytest(["/v/bin/pytest"]))
        self.assertTrue(suite_run._is_pytest(["py.test", "-q"]))
        self.assertTrue(suite_run._is_pytest(["python3", "-m", "pytest"]))
        self.assertFalse(suite_run._is_pytest(["python3", "-m", "unittest",
                                               "pytest_like"]))
        self.assertFalse(suite_run._is_pytest([]))


class LockTest(TmpRootTest):

    def test_fresh_empty_lock_counts_as_busy(self):
        """Пустой только что созданный замок не снимается как брошенный.

        Ловит мутацию: нечитаемый замок всегда считается брошенным — сосед,
        успевший создать файл, но не дописавший его, теряет замок, и два
        прогона идут разом.
        """
        path = suite_run._lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        self.assertIsNotNone(suite_run._acquire_lock("T1", 1))
        old = path.stat().st_mtime - suite_run._FRESH_LOCK_SEC - 5
        os.utime(path, (old, old))
        self.assertIsNone(suite_run._acquire_lock("T1", 1))
        self.assertEqual(json.loads(path.read_text())["pid"], os.getpid())
        suite_run._release_lock()
        self.assertFalse(path.exists())

    def test_release_keeps_foreign_lock(self):
        """Снятие замка не трогает чужой замок.

        Ловит мутацию: `_release_lock` удаляет файл безусловно — фоновый
        прогон, не взявший замок, снял бы замок идущего прогона.
        """
        path = suite_run._lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"task_id": "T2", "pid": os.getppid()}),
                        encoding="utf-8")
        suite_run._release_lock()
        self.assertTrue(path.exists())

    def launch(self, task_id: str, child_pid: int) -> dict:
        """`cmd_suite_run` с подменённым запуском фонового процесса; замок
        в момент запуска — в ответе."""
        seen = {}
        log = suite_run._log_path(task_id, 7)

        def popen(*args, **kwargs):
            seen["at_popen"] = json.loads(suite_run._lock_path().read_text())
            return mock.Mock(pid=child_pid)

        with mock.patch.object(suite_run.store, "db"), \
                mock.patch.object(suite_run.store, "resolve_task_id",
                                  return_value=task_id), \
                mock.patch.object(suite_run.store, "task_target",
                                  return_value="artel"), \
                mock.patch.object(suite_run, "_profile_command",
                                  return_value=(["pytest"], "")), \
                mock.patch.object(suite_run.workspace, "path",
                                  return_value=self.root), \
                mock.patch.object(suite_run, "_new_log", return_value=log), \
                mock.patch.object(suite_run.subprocess, "Popen", popen):
            suite_run.cmd_suite_run([task_id])
        return seen

    def test_command_takes_lock_before_background_start(self):
        """Замок берёт команда до запуска фонового процесса и передаёт ему;
        второй запуск (другая задача) отказывает сразу, с держателем.

        Ловит мутацию: замок берёт только фоновый процесс — в момент
        запуска замка нет, второй запуск при живом первом печатает
        «запущен» с кодом 0 вместо немедленного отказа (R1-F2).
        """
        child = os.getppid()  # живой процесс — «фоновый прогон» первого
        seen = self.launch("T1", child)
        self.assertEqual(seen["at_popen"],
                         {"task_id": "T1", "pid": os.getpid(), "run": 7})
        self.assertEqual(json.loads(suite_run._lock_path().read_text()),
                         {"task_id": "T1", "pid": child, "run": 7})
        with self.assertRaises(SystemExit) as refused:
            self.launch("T2", 4242)
        self.assertIn("T1", str(refused.exception.code))
        self.assertIn(str(child), str(refused.exception.code))

    def test_background_adopts_handed_lock(self):
        """Фоновый процесс принимает замок своей задачи и номера прогона,
        а чужой живой замок — отказ без прогона.

        Ловит мутацию: фоновый процесс берёт замок заново — переданный
        командой замок (держатель жив) он принял бы за чужой и отказал;
        принимается замок любой задачи — прогон идёт поверх чужого.
        """
        suite_run._hand_lock("T1", 7, os.getppid())
        self.assertIsNone(suite_run._adopt_lock("T1", 7))
        self.assertEqual(json.loads(suite_run._lock_path().read_text())["pid"],
                         os.getpid())
        suite_run._hand_lock("T2", 3, os.getppid())
        self.assertEqual(suite_run._adopt_lock("T1", 8)["task_id"], "T2")


class GateSaveTest(RealGitSandbox):

    SUMMARY = ("=========== short test summary info ===========\n"
               "FAILED tests/test_x.py::test_x - ValueError: x\n"
               "========== 1 failed, 2 passed in 0.10s ==========\n")

    def test_dirty_tree_result_is_not_saved(self):
        """Итог гейта на грязном дереве не сохраняется по sha HEAD.

        Ловит мутацию: `clean_tree_sha` не смотрит на рабочее дерево — итог
        незакоммиченных правок записан как итог коммита, и `suite-run`
        другой задачи с этой базой взял бы чужие упавшие.
        """
        head = self.git("rev-parse", "HEAD").strip()
        (self.root / "marker.txt").write_text("правка\n", encoding="utf-8")
        with mock.patch.object(acceptance, "run_full_suite",
                               return_value=(False, self.SUMMARY)):
            acceptance.full_suite(self.root, "T1")
        self.assertIsNone(acceptance.saved_failures(head))

        self.git("checkout", "--", "marker.txt")
        with mock.patch.object(acceptance, "run_full_suite",
                               return_value=(False, self.SUMMARY)):
            run = acceptance.full_suite(self.root, "T1")
        self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED)
        self.assertEqual(acceptance.saved_failures(head),
                         ["tests/test_x.py::test_x"])

    def test_red_run_without_summary_is_not_saved(self):
        """Красный прогон без итоговой строки pytest (сбой запуска) итогом
        не служит.

        Ловит мутацию: сохраняется любой не-таймаутный исход — пустой
        перечень упавших сбойного прогона выдаётся за итог базы, и все
        упавшие ветки объявляются «новыми».
        """
        head = self.git("rev-parse", "HEAD").strip()
        with mock.patch.object(acceptance, "run_full_suite",
                               return_value=(False, "ImportError: xdist\n")):
            acceptance.full_suite(self.root, "T1")
        self.assertIsNone(acceptance.saved_failures(head))


class GateArgvTest(TmpRootTest):

    def test_gate_call_argv_unchanged(self):
        """Вызов гейта без новых параметров — прежняя команда pytest.

        Интерпретатор подменён на весь метод: и прогон гейта, и ожидание
        видят одно значение, а не `stack._main_copy_root`, чей вызов git
        перехватывает подмена `acceptance.subprocess.run`.

        Ловит мутацию: флаги `suite-run` (`-vv`, вывод в файл) или иной
        порядок путей попадают в прогон гейта по умолчанию; правка общей
        части команды `_pytest_command` (потерянный `-p timeout`, иной
        порядок её флагов) — ожидание теперь литерал, а не та же функция.
        """
        (self.root / "tests").mkdir()
        done = subprocess.CompletedProcess([], 0, "1 passed in 0.1s", "")
        with mock.patch.object(acceptance.stack, "pytest_python_executable",
                               return_value="/fake/venv/bin/python3"):
            with mock.patch.object(acceptance.subprocess, "run",
                                   return_value=done) as run:
                acceptance.run_full_suite(self.root)
            argv = run.call_args.args[0]
            expected = ["/fake/venv/bin/python3", "-m", "pytest", "tests", "-p",
                        "no:cacheprovider", "-p", "timeout", "-o",
                        f"timeout={stack.PER_TEST_TIMEOUT_SEC}", "-n",
                        str(config.FULL_SUITE_WORKERS), "-p", "xdist"]
            self.assertEqual(argv, expected)


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    *args], cwd=cwd, check=True, capture_output=True)


class GateArgvInterpreterIndependenceTest(unittest.TestCase):

    def test_gate_argv_test_passes_in_worktree_without_venv(self):
        """Метод argv гейта зелёный в рабочей копии `git worktree` без
        `.artel/venv` при интерпретаторе процесса не из venv (условие
        ревизии CR-2026-10-22-20).

        Ловит мутацию: ожидание `test_gate_call_argv_unchanged` снова
        собирается `_pytest_command` вне подмены интерпретатора — ожидание
        получает venv временной главной копии, фактический argv —
        `/fake/bin/python`, и вложенный прогон метода красный.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        main = Path(tmp.name) / "main"
        copy = Path(tmp.name) / "copy"
        venv_python = main / ".artel" / "venv" / "bin" / "python3"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("", encoding="utf-8")
        _git(tmp.name, "init", "-q", str(main))
        (main / "README").write_text("x\n", encoding="utf-8")
        _git(main, "add", "README")
        _git(main, "commit", "-q", "-m", "init")
        _git(main, "worktree", "add", "-q", "--detach", str(copy))

        result = unittest.TestResult()
        with mock.patch.object(stack, "_MODULE_ROOT", copy), \
                mock.patch.object(config, "VENV_DIR",
                                  Path(tmp.name) / "no-venv"), \
                mock.patch.object(stack.sys, "executable", "/fake/bin/python"):
            GateArgvTest("test_gate_call_argv_unchanged").run(result)
        self.assertTrue(result.wasSuccessful(),
                        result.failures + result.errors)


class GateArgvInterpreterSourceTest(TmpRootTest):

    def test_first_argv_element_is_selected_interpreter(self):
        """Первый элемент argv `run_full_suite` — значение
        `stack.pytest_python_executable`.

        Ловит мутацию: `run_full_suite`/`_pytest_command` ставит первым
        элементом голый `python3` или `sys.executable` в обход функции
        выбора интерпретатора.
        """
        (self.root / "tests").mkdir()
        done = subprocess.CompletedProcess([], 0, "1 passed in 0.1s", "")
        with mock.patch.object(acceptance.stack, "pytest_python_executable",
                               return_value="/selected/bin/python3"), \
                mock.patch.object(acceptance.subprocess, "run",
                                  return_value=done) as run:
            acceptance.run_full_suite(self.root)
        self.assertEqual(run.call_args.args[0][0], "/selected/bin/python3")


class SuiteRunJournalTest(TmpRootTest):

    def test_suite_run_preserves_task_steps_on_every_outcome(self):
        """Команда не меняет журнал задачи; таймаут называет нагрузку.

        Ловит мутацию: полный `suite-run` снова пишет измерение в журнал
        задачи, хотя у гейта запись остаётся; при удалении снимка нагрузки
        отчёт о таймауте теряет строку с load average и процессом.
        """
        store.create_schema(store.db())
        task_id = "T001"
        store.insert_task(store.db(), task_id, "Прогон", "in_dev",
                          "task/t001-progon", config.DEFAULT_TARGET, 25.0)
        steps_before = [dict(row) for row in store.task_steps(store.db(), task_id)]
        metrics = {"load_end_1": 8.0, "load_end_5": 6.0,
                   "top_processes": [{"pid": 42, "cpu_percent": 410.0,
                                      "name": "foreign"}]}
        tree = appendix_tree.SuiteTree(self.root, "", "", "")
        cases = (
            (suite_run.MODE_FULL, True, "1 passed in 0.1s", False),
            (suite_run.MODE_FULL, False, "1 failed in 0.1s", False),
            (suite_run.MODE_FULL, False,
             acceptance._full_suite_timeout_note(), True),
            (suite_run.MODE_FAILED, False,
             acceptance._full_suite_timeout_note(), True),
        )
        for number, (mode, green, output, timeout) in enumerate(cases, 1):
            with self.subTest(mode=mode, output=output):
                def run(*args, **kwargs):
                    acceptance._last_full_suite_metrics = metrics
                    return green, output

                with mock.patch.object(suite_run, "_profile_command",
                                       return_value=(["pytest"], "")), \
                        mock.patch.object(suite_run.project_profile,
                                          "full_suite_limit",
                                          return_value=(10, "config")), \
                        mock.patch.object(suite_run.appendix_tree, "suite_tree",
                                          return_value=contextlib.nullcontext(tree)), \
                        mock.patch.object(acceptance, "run_full_suite",
                                          side_effect=run), \
                        mock.patch.object(suite_run, "_base",
                                          return_value=(None, "base unavailable")), \
                        mock.patch.object(suite_run, "_read_failed",
                                          return_value=["tests/test_x.py::test_x"]):
                    report, _ = suite_run._run(
                        task_id, number, mode, self.root / f"run-{number}.log")
                self.assertEqual([dict(row) for row in store.task_steps(
                    store.db(), task_id)], steps_before)
                self.assertEqual("нагрузка: load average" in report, timeout)
                if timeout:
                    self.assertIn("pid 42 410.0% foreign", report)


class FailedIdsByProfileTest(TmpRootTest):

    def test_failed_rerun_ids_go_as_test_ids_only_for_own_profile(self):
        """Повтор упавших у `pytest-own` передаёт id каналом `test_ids`, у
        списка команды — прежними целями.

        Ловит мутацию: у `pytest-own` id упавших идут целями `targets` —
        `run_full_suite` переводит их пути к `workdir`, хотя pytest
        напечатал их уже из `workdir`; либо `test_ids` уходят и списку
        команды — меняется вызов `pult-pytest`.
        """
        store.create_schema(store.db())
        task_id = "T001"
        store.insert_task(store.db(), task_id, "Прогон", "in_dev",
                          "task/t001-progon", config.DEFAULT_TARGET, 25.0)
        tree = appendix_tree.SuiteTree(self.root, "", "", "")
        failed = ["checks/test_x.py::test_x", "checks/test_y.py::test_y"]
        own = project_profile.Profile(
            command=("python3", "-m", "pytest"), long_lived_dir="sub/checks",
            long_lived_name="test_<id>_<name>.py", weakening_scope=(),
            mutation_claim_scope=(), runner=targets.PROFILE_RUNNER_OWN,
            workdir="sub")
        cases = ((own, (), tuple(failed)), (["pytest"], tuple(failed), None))
        for number, (command, targets_seen, ids_seen) in enumerate(cases, 1):
            with self.subTest(command=command):
                with mock.patch.object(suite_run, "_profile_command",
                                       return_value=(command, "")), \
                        mock.patch.object(suite_run.project_profile,
                                          "full_suite_limit",
                                          return_value=(10, "config")), \
                        mock.patch.object(suite_run.appendix_tree, "suite_tree",
                                          return_value=contextlib.nullcontext(tree)), \
                        mock.patch.object(acceptance, "run_full_suite",
                                          return_value=(True, "2 passed in 0.1s")
                                          ) as run, \
                        mock.patch.object(suite_run, "_base",
                                          return_value=(None, "base unavailable")), \
                        mock.patch.object(suite_run, "_read_failed",
                                          return_value=failed):
                    suite_run._run(task_id, number, suite_run.MODE_FAILED,
                                   self.root / f"run-{number}.log")
                kwargs = run.call_args.kwargs
                self.assertIs(kwargs["command"], command)
                self.assertEqual(tuple(kwargs["targets"]), targets_seen)
                self.assertEqual(kwargs.get("test_ids"), ids_seen)


if __name__ == "__main__":
    unittest.main()
