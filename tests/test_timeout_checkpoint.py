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
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = runner.commit_timeout_checkpoint(
            store.db(), self.TASK, "developer")

        # Коммит чекпоинта — в worktree задачи, не в ROOT (тот остаётся на
        # main, SPEC T048); `git log` читается там же.
        subject = self.git_in_worktree("log", "-1", "--format=%s").strip()
        self.assertEqual(subject,
                         f"{self.TASK}: WIP-чекпоинт после таймаута шага developer")
        self.assertIn(subject, detail)
        self.assertIn(self.head(), detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("таймаут", entries[0]["action"].lower())

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        runner.commit_timeout_checkpoint(store.db(), self.TASK, "developer")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def _run_with_failing_step(self, failing_subcommand: str, rc: int):
        """Заглушка `gitcmd.git`: заданный git-подкоманде отвечает `rc`,
        остальные проходят настоящим `gitcmd.git` (тот же приём, что и
        существующий `test_git_add_failure_...` — только параметризован
        по шагу, чтобы закрыть класс целиком: `add`/`diff`/`commit`)."""
        real_git = gitcmd.git

        def side_effect(*args):
            if failing_subcommand in args:
                return subprocess.CompletedProcess(list(args), rc, "", "boom")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=side_effect):
            return runner.commit_timeout_checkpoint(
                store.db(), self.TASK, "developer")

    def test_git_add_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.head()

        detail = self._run_with_failing_step("add", 1)

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_git_diff_failure_commits_nothing_and_journals_nothing(self):
        """REVIEW.md T041 итерация 1, замечание minor: тот же класс отказа
        (`git diff --cached --quiet` вне {0,1} — git не ответил), что и у
        `git add`, отдельным кейсом."""
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.head()

        detail = self._run_with_failing_step("diff", 2)

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_git_commit_failure_commits_nothing_and_journals_nothing(self):
        """REVIEW.md T041 итерация 1, замечание minor: та же деградация
        для отказа самого `git commit`."""
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.head()

        detail = self._run_with_failing_step("commit", 1)

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_non_dogfood_target_skips_checkpoint(self):
        """REVIEW.md T041 итерация 1, замечание major: для target'а,
        отличного от догфуда, чекпоинт — тихий no-op ДО первого `git
        add` (см. докстринг `commit_timeout_checkpoint` и PLAN «Риски») —
        `gitcmd.git` вообще не должен быть вызван."""
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.head()
        conn = store.db()
        store.update_task(conn, self.TASK, target="another-target")

        with mock.patch.object(gitcmd, "git") as git_mock:
            detail = runner.commit_timeout_checkpoint(
                conn, self.TASK, "developer")

        git_mock.assert_not_called()
        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])


class CommitAbnormalCheckpointTest(RealPultGitTest):
    """Юнит-тесты `runner.commit_abnormal_checkpoint` (SPEC T074, требование
    3 — расширение правила T041: чекпоинт не только на таймауте, но и на
    аварийном завершении шага, rc != 0/обрыв потока)."""

    def orchestrator_steps(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"]

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.head()

        detail = runner.commit_abnormal_checkpoint(
            store.db(), self.TASK, "developer", "rc=1")

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_with_cause_marker_in_message_and_journal(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = runner.commit_abnormal_checkpoint(
            store.db(), self.TASK, "developer", "rc=1")

        subject = self.git_in_worktree("log", "-1", "--format=%s").strip()
        self.assertIn("чекпоинт", subject.lower())
        self.assertIn("rc=1", subject)
        self.assertIn(subject, detail)
        self.assertIn(self.head(), detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("чекпоинт", entries[0]["action"].lower())

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        runner.commit_abnormal_checkpoint(
            store.db(), self.TASK, "developer", "обрыв потока")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def test_non_dogfood_target_skips_checkpoint(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.head()
        conn = store.db()
        store.update_task(conn, self.TASK, target="another-target")

        with mock.patch.object(gitcmd, "git") as git_mock:
            detail = runner.commit_abnormal_checkpoint(
                conn, self.TASK, "developer", "rc=1")

        git_mock.assert_not_called()
        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])


class CommitPauseNowCheckpointTest(RealPultGitTest):
    """Юнит-тесты `runner.commit_pause_now_checkpoint` (SPEC T074,
    требования 1, 3 — чекпоинт `pause --now`, вызванный самой командой
    `orchestrator.pause.cmd_pause_now` из ДРУГОГО процесса, не из того,
    что исполняло прерванный шаг)."""

    def orchestrator_steps(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"]

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.head()

        detail = runner.commit_pause_now_checkpoint(
            store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_with_pause_now_marker(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = runner.commit_pause_now_checkpoint(
            store.db(), self.TASK, "developer")

        subject = self.git_in_worktree("log", "-1", "--format=%s").strip()
        self.assertIn("pause --now", subject)
        self.assertIn(subject, detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("pause --now", entries[0]["action"])

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        runner.commit_pause_now_checkpoint(store.db(), self.TASK, "developer")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def test_non_dogfood_target_skips_checkpoint(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.head()
        conn = store.db()
        store.update_task(conn, self.TASK, target="another-target")

        with mock.patch.object(gitcmd, "git") as git_mock:
            detail = runner.commit_pause_now_checkpoint(
                conn, self.TASK, "developer")

        git_mock.assert_not_called()
        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])


if __name__ == "__main__":
    unittest.main()
