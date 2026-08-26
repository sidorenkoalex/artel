"""Юнит-тесты `runner.commit_timeout_checkpoint` (tasks/T041/SPEC.md).

Приёмочные тесты (tasks/T041/acceptance_tests) проверяют критерии
приёмки целиком через `cmd_run` с подложным процессом агента; здесь —
изолированные случаи самой функции чекпоинта: пустое дерево, отказ git
на любом из шагов, повторная фиксация sha (`store.record_fixation`) и
чтение результата `fixation.check_integrity` сразу после коммита.

Песочница — `RealPultGitTest` (tests/test_git_fixation.py): чекпоинт —
это реальные `git add`/`git diff`/`git commit`, заглушкой `gitcmd.git`
эту механику не проверить (тот же довод, что в acceptance_tests T041).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fixation, gitcmd, runner, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class CommitTimeoutCheckpointTest(RealPultGitTest):

    def orchestrator_steps(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"]

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.head()

        detail = runner.commit_timeout_checkpoint(
            store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_with_message_sha_and_journal_entry(self):
        self.enter_in_dev()
        (self.root / "tasks" / self.TASK / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = runner.commit_timeout_checkpoint(
            store.db(), self.TASK, "developer")

        subject = self.git("log", "-1", "--format=%s").strip()
        self.assertEqual(subject,
                         f"{self.TASK}: WIP-чекпоинт после таймаута шага developer")
        self.assertIn(subject, detail)
        self.assertIn(self.head(), detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("таймаут", entries[0]["action"].lower())

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.root / "tasks" / self.TASK / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        runner.commit_timeout_checkpoint(store.db(), self.TASK, "developer")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def test_git_add_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        (self.root / "tasks" / self.TASK / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.head()
        real_git = gitcmd.git

        def failing_add(*args):
            if args and args[0] == "add":
                return subprocess.CompletedProcess(list(args), 1, "", "boom")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=failing_add):
            detail = runner.commit_timeout_checkpoint(
                store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])


if __name__ == "__main__":
    unittest.main()
