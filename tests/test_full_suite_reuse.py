"""Границы ключа и разбора полного прогона, не покрытые планкой задачи."""

import unittest
from unittest import mock

from orchestrator import acceptance, suite_run
from tests.sandbox import RealGitSandbox


class SuiteReuseBoundaryTest(RealGitSandbox):
    def test_staged_new_file_enters_tree_key(self):
        """Ловит мутацию: временный индекс начинается с HEAD и теряет новый файл, уже добавленный в индекс."""
        before = acceptance.suite_tree_hash(self.root)
        (self.root / "new.txt").write_text("новый файл\n", encoding="utf-8")
        self.git("add", "new.txt")
        after = acceptance.suite_tree_hash(self.root)
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertNotEqual(after, before)

    def test_environment_failure_forces_run(self):
        """Ловит мутацию: неудача отпечатка пакетов превращается в постоянный пустой ключ и повторяет чужой итог."""
        red = "========== 1 failed in 0.10s ==========\n"
        with mock.patch.object(acceptance.importlib.metadata, "distributions",
                               side_effect=OSError("пакеты недоступны")), \
             mock.patch.object(acceptance, "run_full_suite",
                               side_effect=[(False, red), (True, red)]) as run:
            acceptance.full_suite(self.root, "ENV-FAIL")
            acceptance.full_suite(self.root, "ENV-FAIL")
        self.assertEqual(run.call_count, 2)


class SuiteSummaryTest(unittest.TestCase):
    def test_subtests_summary_is_finished(self):
        """Ловит мутацию: категория subtests в итоговой строке снова скрывает завершённый прогон базы."""
        output = ("= 1 failed, 4491 passed, 2 skipped, "
                  "1624 subtests passed in 753.22s (0:12:33) ==\n")
        self.assertIn("subtests passed", acceptance.run_summary_line(output))
        self.assertTrue(suite_run.parse(False, output).finished)
