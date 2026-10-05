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


class GateSaveTest(RealGitSandbox):

    SUMMARY = ("FAILED tests/test_x.py::test_x - ValueError: x\n"
               "1 failed, 2 passed in 0.10s\n")

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
