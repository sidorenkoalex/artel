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


if __name__ == "__main__":
    unittest.main()
