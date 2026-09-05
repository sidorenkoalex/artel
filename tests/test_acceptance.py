"""Юнит-тесты orchestrator/acceptance.py::run_full_suite (ADR-0007,
tasks/T066/SPEC.md, требование 2в — условие "полный набор tests/ в
worktree ветки зелёный" автогейта acceptance).
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance, config  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
