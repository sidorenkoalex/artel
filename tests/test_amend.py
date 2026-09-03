"""Юнит-тесты orchestrator/amend.py (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md).

Приёмочные тесты (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/)
кроют AC-1..AC-12 сквозным путём через настоящий git; здесь — чистые
хелперы в изоляции: разбор `git status --porcelain` (модификация,
untracked, переименование), извлечение итоговой строки прогона
(`Ran N`/`OK`/`FAILED`), окно из НЕСКОЛЬКИХ залоченных задач program-wide
(сценарий, которого приёмочные тесты сознательно не покрывают — там
окно всегда из одной задачи, см. докстринг
`acceptance_tests/test_ac9_threshold_alert.py`) и счёт событий строго по
task_id окна, а также разбор argv `--reason` (`artel._reason_arg`).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import amend, artel, catalog, config, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class RunSummaryTest(unittest.TestCase):

    def test_extracts_ran_line_and_ok(self):
        tail = ("..\n"
               "----------------------------------------------------------------------\n"
               "Ran 2 tests in 0.001s\n\nOK\n")
        self.assertEqual(amend._run_summary(tail), "Ran 2 tests in 0.001s\n\nOK")

    def test_extracts_ran_line_and_failed_with_count(self):
        tail = ("F\n"
               "======================================================================\n"
               "FAIL: test_ac1_first_criterion\n"
               "----------------------------------------------------------------------\n"
               "AssertionError: намеренно красный тест без маркера\n\n"
               "----------------------------------------------------------------------\n"
               "Ran 1 test in 0.000s\n\nFAILED (failures=1)\n")
        summary = amend._run_summary(tail)
        self.assertIn("Ran 1 test in 0.000s", summary)
        self.assertIn("FAILED (failures=1)", summary)
        self.assertNotIn("AssertionError", summary,
                         "итоговая строка не обязана тащить весь traceback")

    def test_missing_ran_line_falls_back_to_full_tail(self):
        tail = "что-то совсем не похожее на вывод unittest"
        self.assertEqual(amend._run_summary(tail), tail)


class WorktreeChangedPathsTest(unittest.TestCase):

    def _paths(self, output: str, returncode: int = 0):
        fake = lambda *args: subprocess.CompletedProcess(
            list(args), returncode, output, "")
        with mock.patch.object(gitcmd, "git", fake):
            return amend._worktree_changed_paths(Path("/irrelevant"))

    def test_parses_modified_and_untracked_paths(self):
        output = (" M tasks/T001/acceptance_tests/test_ac.py\n"
                 "?? tasks/T001/PLAN.md\n")
        self.assertEqual(
            sorted(self._paths(output)),
            ["tasks/T001/PLAN.md", "tasks/T001/acceptance_tests/test_ac.py"])

    def test_rename_keeps_only_the_new_side(self):
        output = ("R  tasks/T001/acceptance_tests/old.py -> "
                 "tasks/T001/acceptance_tests/new.py\n")
        self.assertEqual(self._paths(output),
                         ["tasks/T001/acceptance_tests/new.py"])

    def test_blank_lines_are_ignored(self):
        output = " M tasks/T001/acceptance_tests/test_ac.py\n\n"
        self.assertEqual(self._paths(output),
                         ["tasks/T001/acceptance_tests/test_ac.py"])

    def test_git_not_responding_returns_none(self):
        self.assertIsNone(self._paths("", returncode=128))


class LockedWindowTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.conn = store.db()

    def _make_task(self, task_id: str, created_at: str, *, locked: bool,
                   target: str = config.DEFAULT_TARGET) -> None:
        store.insert_task(self.conn, task_id, task_id, "in_dev",
                          f"task/{task_id.lower()}", target,
                          config.DEFAULT_BUDGET_USD)
        self.conn.execute("UPDATE tasks SET created_at=? WHERE id=?",
                          (created_at, task_id))
        if locked:
            store.update_task(self.conn, task_id, tests_locked_sha=f"sha-{task_id}")
        self.conn.commit()

    def test_unlocked_tasks_are_excluded(self):
        self._make_task("T001", "2026-09-01 10:00:00Z", locked=True)
        self._make_task("T002", "2026-09-01 11:00:00Z", locked=False)

        self.assertEqual(amend._locked_window_task_ids(self.conn), ["T001"])

    def test_window_keeps_last_five_by_creation_order_program_wide(self):
        ids = [f"P{i:03d}" for i in range(1, 8)]  # 7 залоченных задач
        for i, task_id in enumerate(ids):
            target = config.DEFAULT_TARGET if i % 2 == 0 else "other-target"
            self._make_task(task_id, f"2026-09-01 10:{i:02d}:00Z",
                            locked=True, target=target)

        window = amend._locked_window_task_ids(self.conn)

        self.assertEqual(window, ids[-5:],
                         "окно обязано взять последние 5 по порядку "
                         "заведения независимо от target")

    def test_fewer_than_five_locked_tasks_returns_all_of_them(self):
        self._make_task("T001", "2026-09-01 10:00:00Z", locked=True)
        self._make_task("T002", "2026-09-01 11:00:00Z", locked=True)

        self.assertEqual(amend._locked_window_task_ids(self.conn),
                         ["T001", "T002"])


class AmendEventsInWindowTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.conn = store.db()
        for task_id in ("T001", "T002"):
            store.insert_task(self.conn, task_id, task_id, "in_dev",
                              f"task/{task_id.lower()}",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def test_counts_only_amend_events_of_tasks_in_window(self):
        store.journal(self.conn, "T001", "operator", amend.AMEND_ACTION, "x")
        store.journal(self.conn, "T001", "operator", amend.AMEND_ACTION, "y")
        store.journal(self.conn, "T002", "operator", amend.AMEND_ACTION, "z")
        store.journal(self.conn, "T002", "fsm", "sha зафиксирован",
                      "не должно попасть в счёт")

        self.assertEqual(amend._amend_events_in_window(self.conn, ["T001"]), 2)
        self.assertEqual(
            amend._amend_events_in_window(self.conn, ["T001", "T002"]), 3)

    def test_task_outside_window_is_not_counted(self):
        store.journal(self.conn, "T002", "operator", amend.AMEND_ACTION, "z")

        self.assertEqual(amend._amend_events_in_window(self.conn, ["T001"]), 0)

    def test_empty_window_counts_zero(self):
        self.assertEqual(amend._amend_events_in_window(self.conn, []), 0)


class ReasonArgTest(unittest.TestCase):

    def test_flag_absent_returns_none(self):
        self.assertIsNone(artel._reason_arg(["T001"]))

    def test_flag_with_value_returns_it(self):
        self.assertEqual(
            artel._reason_arg(["T001", "--reason", "опечатка"]), "опечатка")

    def test_flag_with_empty_string_value_returns_empty_string(self):
        self.assertEqual(artel._reason_arg(["T001", "--reason", ""]), "")

    def test_dangling_flag_without_value_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            artel._reason_arg(["T001", "--reason"])
        self.assertIn("--reason", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
