"""Юнит-тесты `checkpoint.commit_step_artifacts` (tasks/T059/SPEC.md;
перенесено из runner.py в T091 — декомпозиция диспетчеров fsm/runner).

Приёмочные тесты (tasks/T059/acceptance_tests) проверяют критерии
приёмки целиком через `cmd_run` с подложным процессом агента; здесь —
изолированные случаи самой функции автокоммита: пустое дерево, отказ
git на любом из шагов, повторная фиксация sha (`store.record_fixation`)
и отказ для не-догфуд target. Тот же приём, что `tests/
test_timeout_checkpoint.py` — общая обвязка (`_commit_worktree_change`)
у обеих функций одна и та же, поэтому и структура тестов зеркальна.

Песочница — `RealPultGitTest` (tests/test_git_fixation.py): автокоммит —
это реальные `git add`/`git diff`/`git commit`, заглушкой `gitcmd.git`
эту механику не проверить (тот же довод, что в acceptance_tests T059).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import checkpoint, fixation, gitcmd, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class CommitStepArtifactsTest(RealPultGitTest):

    def orchestrator_steps(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"]

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.head()

        detail = checkpoint.commit_step_artifacts(
            store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_with_message_sha_and_journal_entry(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")

        detail = checkpoint.commit_step_artifacts(
            store.db(), self.TASK, "developer")

        # Коммит автокоммита — в worktree задачи, не в ROOT (тот
        # остаётся на main, тот же адрес, что у чекпоинта T041/T048).
        subject = self.git_in_worktree("log", "-1", "--format=%s").strip()
        self.assertEqual(
            subject,
            f"{self.TASK}: артефакты шага developer (автокоммит оркестратора)")
        self.assertIn(subject, detail)
        self.assertIn(self.head(), detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("автокоммит", entries[0]["action"].lower())

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def _run_with_failing_step(self, failing_subcommand: str, rc: int):
        """Заглушка `gitcmd.git`: заданный git-подкоманде отвечает `rc`,
        остальные проходят настоящим `gitcmd.git` — тот же приём, что
        `tests/test_timeout_checkpoint.py::CommitTimeoutCheckpointTest.
        _run_with_failing_step`."""
        real_git = gitcmd.git

        def side_effect(*args):
            if failing_subcommand in args:
                return subprocess.CompletedProcess(list(args), rc, "", "boom")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=side_effect):
            return checkpoint.commit_step_artifacts(
                store.db(), self.TASK, "developer")

    def test_git_add_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")
        before = self.head()

        detail = self._run_with_failing_step("add", 1)

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_git_diff_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")
        before = self.head()

        detail = self._run_with_failing_step("diff", 2)

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_git_commit_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")
        before = self.head()

        detail = self._run_with_failing_step("commit", 1)

        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_non_dogfood_target_skips_autocommit(self):
        """Тот же довод, что у `commit_timeout_checkpoint` (REVIEW.md
        T041 итерация 1, замечание major): для target'а, отличного от
        догфуда, автокоммит — тихий no-op ДО первого `git add` (см.
        докстринг `commit_step_artifacts` и PLAN «Подход») — `gitcmd.git`
        вообще не должен быть вызван."""
        self.enter_in_dev()
        (self.task_dir() / "wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")
        before = self.head()
        conn = store.db()
        store.update_task(conn, self.TASK, target="another-target")

        with mock.patch.object(gitcmd, "git") as git_mock:
            detail = checkpoint.commit_step_artifacts(
                conn, self.TASK, "developer")

        git_mock.assert_not_called()
        self.assertEqual(detail, "")
        self.assertEqual(self.head(), before)
        self.assertEqual(self.orchestrator_steps(), [])


if __name__ == "__main__":
    unittest.main()
