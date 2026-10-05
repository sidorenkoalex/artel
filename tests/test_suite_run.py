"""Юнит-тесты `orchestrator/suite_run.py` и сохранения итогов полного набора
в `orchestrator/acceptance.py` (SPEC 01M462QACEH29RPRD2RZHGHQFM) — углы, не
покрытые долгоживущим файлом задачи
(`tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`): разбор вывода без
сводки, признак pytest по исполняемому файлу, свежий пустой замок, итог гейта
на грязном дереве, неделимость «новые/на базе» без итога базы.
"""
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, suite_run
from tests.sandbox import RealGitSandbox, TmpRootTest

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
        log = config.LOGS / f"{task_id}-{suite_run.LOG_KIND}-7.log"

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
                mock.patch.object(suite_run.agent_log, "new_agent_log",
                                  return_value=log), \
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

        Ловит мутацию: флаги `suite-run` (`-vv`, вывод в файл) или иной
        порядок путей попадают в прогон гейта по умолчанию.
        """
        (self.root / "tests").mkdir()
        done = subprocess.CompletedProcess([], 0, "1 passed in 0.1s", "")
        with mock.patch.object(acceptance.subprocess, "run",
                               return_value=done) as run:
            acceptance.run_full_suite(self.root)
        argv = run.call_args.args[0]
        self.assertEqual(argv, acceptance._pytest_command("tests") + [
            "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"])


if __name__ == "__main__":
    unittest.main()
