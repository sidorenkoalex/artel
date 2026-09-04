"""Юнит-тесты `doctor._fix_ignored_artifact_files`/`doctor --fix` (SPEC
01M1KVG3KSCY47HWXWF5HM0E76, требование 4, AC-5): уборка файлов,
игнорируемых `.gitignore` пульта, из артефактных веток живых задач.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, config, doctor, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

GITIGNORE_TEXT = "__pycache__/\n*.pyc\n*.log\ndropme/\n.artel/\n"
PYC_REL = "acceptance_tests/__pycache__/x.cpython-311.pyc"


class FixIgnoredArtifactFilesTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        (self.root / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "gitignore")

    def seed_task(self, task_id: str, state: str, files: dict) -> None:
        store.insert_task(store.db(), task_id, f"Задача {task_id}", state,
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        sha = artifact_branch.commit_files(
            task_id, files, f"{task_id}: артефакты шага developer "
            f"(автокоммит оркестратора)")
        self.assertTrue(sha)

    def branch_files(self, task_id: str) -> list:
        branch = artifact_branch.branch_name(task_id)
        return gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []

    def journal_entries(self, task_id: str) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id", (task_id,))]

    def test_ignored_file_removed_normal_file_kept(self):
        task_id = "01FIXTASKPYCREMOVE01"
        self.seed_task(task_id, "in_dev", {
            f"tasks/{task_id}/PLAN.md": "план\n",
            f"tasks/{task_id}/{PYC_REL}": b"\x00\x01\xff"})

        doctor._fix_ignored_artifact_files(store.db())

        files = self.branch_files(task_id)
        self.assertNotIn(f"tasks/{task_id}/{PYC_REL}", files)
        self.assertIn(f"tasks/{task_id}/PLAN.md", files)
        self.assertTrue(self.journal_entries(task_id))

    def test_task_without_ignored_files_is_not_journaled(self):
        task_id = "01FIXTASKNOJUNK00001"
        self.seed_task(task_id, "in_dev",
                       {f"tasks/{task_id}/PLAN.md": "план\n"})

        doctor._fix_ignored_artifact_files(store.db())

        self.assertIn(f"tasks/{task_id}/PLAN.md", self.branch_files(task_id))
        self.assertEqual(self.journal_entries(task_id), [])

    def test_done_task_is_not_touched(self):
        task_id = "01FIXTASKDONESKIP001"
        self.seed_task(task_id, "done", {
            f"tasks/{task_id}/PLAN.md": "план\n",
            f"tasks/{task_id}/{PYC_REL}": b"\x00"})

        doctor._fix_ignored_artifact_files(store.db())

        self.assertIn(f"tasks/{task_id}/{PYC_REL}", self.branch_files(task_id),
                      "done/killed задачи вне уборки — не 'живые'")
        self.assertEqual(self.journal_entries(task_id), [])

    def test_main_is_never_touched(self):
        task_id = "01FIXTASKMAINSAFE001"
        self.seed_task(task_id, "in_dev", {
            f"tasks/{task_id}/PLAN.md": "план\n",
            f"tasks/{task_id}/{PYC_REL}": b"\x00"})
        main_before = gitcmd.head_sha()

        doctor._fix_ignored_artifact_files(store.db())

        self.assertEqual(gitcmd.head_sha(), main_before)
        self.assertEqual(gitcmd.git("status", "--porcelain").stdout.strip(), "")

    def test_multiple_live_tasks_only_affected_ones_journaled(self):
        clean_id = "01FIXTASKMULTICLEAN1"
        dirty_id = "01FIXTASKMULTIDIRTY1"
        self.seed_task(clean_id, "in_dev",
                       {f"tasks/{clean_id}/PLAN.md": "план\n"})
        self.seed_task(dirty_id, "review", {
            f"tasks/{dirty_id}/REVIEW.md": "ревью\n",
            f"tasks/{dirty_id}/{PYC_REL}": b"\x00"})

        doctor._fix_ignored_artifact_files(store.db())

        self.assertEqual(self.journal_entries(clean_id), [])
        self.assertTrue(self.journal_entries(dirty_id))
        self.assertNotIn(f"tasks/{dirty_id}/{PYC_REL}",
                         self.branch_files(dirty_id))
        self.assertIn(f"tasks/{dirty_id}/REVIEW.md", self.branch_files(dirty_id))

if __name__ == "__main__":
    unittest.main()
