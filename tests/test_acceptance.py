"""Юнит-тесты orchestrator/acceptance.py::run_full_suite (ADR-0007,
tasks/T066/SPEC.md, требование 2в — условие "полный набор tests/ в
worktree ветки зелёный" автогейта acceptance).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance, ci, config  # noqa: E402

PASSING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_always_passes(self):
        self.assertTrue(True)
"""

FAILING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_deliberately_fails(self):
        self.fail("MARKER-RED")
"""

SLEEPING_TEST = """import time
import unittest


class MarkerTest(unittest.TestCase):
    def test_sleeps_past_the_timeout(self):
        time.sleep(3)
"""


class RunFullSuiteTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write_test(self, content: str) -> None:
        tests_dir = self.root / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_marker.py").write_text(content, encoding="utf-8")

    def test_missing_tests_dir_is_not_green(self):
        green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("tests/", tail)

    def test_passing_suite_is_green(self):
        self.write_test(PASSING_TEST)
        green, _ = acceptance.run_full_suite(self.root)
        self.assertTrue(green)

    def test_failing_suite_is_not_green(self):
        self.write_test(FAILING_TEST)
        green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("MARKER-RED", tail)

    def test_timeout_is_not_green(self):
        self.write_test(SLEEPING_TEST)
        with mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 1):
            green, tail = acceptance.run_full_suite(self.root)
        self.assertFalse(green)
        self.assertIn("превысил", tail)


class RunFullSuiteUsesWorkersAndXdistTest(unittest.TestCase):
    """01M291M2Z76M84GVP25J387A66, требование 1/AC-1/AC-7(а): полный набор
    гонится через pytest-xdist — `-n <config.FULL_SUITE_WORKERS>` и явная
    загрузка `-p xdist`, тем же приёмом, что `_pytest_command` уже несёт
    для `-p timeout`.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "tests").mkdir()

    def test_command_carries_worker_count_and_explicit_xdist_plugin(self):
        """Ловит мутацию: параллель снята из `run_full_suite` (`-n`/
        `-p xdist` отсутствуют в команде) — полный набор снова гонится
        последовательно без предупреждения."""
        with mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "3 passed", "")
            acceptance.run_full_suite(self.root)

        command = run_.call_args.args[0]
        self.assertIn("-n", command, f"команда без -n: {command}")
        n_pos = command.index("-n")
        self.assertEqual(
            command[n_pos + 1], str(config.FULL_SUITE_WORKERS),
            f"-n несёт не значение config.FULL_SUITE_WORKERS: {command}")
        p_values = [command[i + 1] for i, token in enumerate(command)
                   if token == "-p" and i + 1 < len(command)]
        self.assertIn("xdist", p_values,
                      f"нет явной загрузки -p xdist в команде: {command}")

    def test_full_suite_workers_set_to_one_is_still_a_valid_command(self):
        """AC-7(б): `config.FULL_SUITE_WORKERS = 1` — команда остаётся
        валидной (`-n 1`), параллель не выключается тихо."""
        with mock.patch.object(config, "FULL_SUITE_WORKERS", 1), \
             mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "3 passed", "")
            green, _ = acceptance.run_full_suite(self.root)

        command = run_.call_args.args[0]
        n_pos = command.index("-n")
        self.assertEqual(command[n_pos + 1], "1", f"-n не несёт '1': {command}")
        self.assertTrue(green)


class MaterializeFromBranchGitFailureTest(unittest.TestCase):
    """R2-F2 (REVIEW.md 01M1RNZ6V7TTTTYAHBMF8JBQQS итерации 2): фикс R1-F1
    (`orchestrator/acceptance.py::materialize_from_branch`) до сих пор был
    подтверждён только ручным репро в тексте REVIEW.md, не персистентным
    тестом — по образцу
    `tests/test_artifact_materialization.py::MaterializeTaskDirTest::
    test_no_branch_returns_empty_sha_and_leaves_disk_untouched`, но для
    `acceptance.materialize_from_branch`.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.code_dir = Path(tmp.name)

    def test_none_from_ls_tree_files_leaves_existing_plank_untouched(self):
        """Ловит мутацию: `ls_tree_files(...) or []` смешивает `None`
        (git не ответил) с легитимно пустой веткой (`[]`) — прунинг ниже
        стирал бы уже материализованную планку транзиентным сбоем git."""
        task_id = "01UTMATERIALIZEGITFAIL"
        tests_dir = self.code_dir / "tasks" / task_id / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        existing = tests_dir / "test_ac.py"
        existing.write_text("реальный тест\n", encoding="utf-8")

        with mock.patch.object(acceptance.gitcmd, "ls_tree_files",
                               return_value=None):
            tdir = acceptance.materialize_from_branch(
                task_id, "artifact/does-not-matter", self.code_dir)

        self.assertEqual(tdir, self.code_dir / "tasks" / task_id)
        self.assertEqual(existing.read_text(encoding="utf-8"),
                         "реальный тест\n")


class SummaryCiCriteriaTest(unittest.TestCase):
    """`acceptance.summary` — категория `ci` в сводке гейта приёмки
    (01M1SHJTT0V516BWHYXWS50F3G, требование 4/AC-6): показывается вместе
    с результатом проверки CI, так же явно, как manual-критерии."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_marker.py").write_text(
            '"""Планка с единственной пометкой ci."""\n'
            "# AC-1: ci — CI ветки уже подтверждает зелёный набор.\n",
            encoding="utf-8")

    def test_ci_criterion_is_counted_in_the_header_line(self):
        summary = acceptance.summary(self.tdir)

        self.assertIn("1 ci", summary)

    def test_without_a_branch_ci_criteria_are_named_but_not_polled(self):
        """`branch=None` (вызывающий не назвал ветку) — критерии `ci`
        всё равно называются, но CI не опрашивается (нечем)."""
        with mock.patch.object(
                ci, "verifying_status",
                side_effect=AssertionError("CI не должен опрашиваться "
                                           "без ветки")):
            summary = acceptance.summary(self.tdir)

        self.assertIn("AC-1", summary)
        self.assertIn("ветка не названа", summary)

    def test_with_a_branch_ci_criteria_show_the_verifying_status(self):
        with mock.patch.object(
                ci, "verifying_status",
                return_value=(ci.VERIFYING_GREEN,
                              "CI коммита abc12345 зелёный (2 проверок)")):
            summary = acceptance.summary(self.tdir, branch="task/t001-x")

        self.assertIn("AC-1", summary)
        self.assertIn("CI ветки уже подтверждает зелёный набор", summary)
        self.assertIn("CI коммита abc12345 зелёный (2 проверок)", summary)


if __name__ == "__main__":
    unittest.main()
