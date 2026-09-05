"""Приёмочный тест AC-3 (tasks/01M1NKTF173WV5CPDZ1C3WW69K/SPEC.md): бриф
роли developer несёт актуальный текст PLAN.md и REVIEW.md артефактной
ветки, тем же способом, каким уже несёт SPEC.md (`developer_brief`/
`_manifest_component`), с sha256-фингерпринтом каждого компонента в
журнале шага.

Красен до реализации: `brief.developer_brief` сегодня собирает только
SPEC.md/карту/конвенции/ANSWER — PLAN.md и REVIEW.md артефактной ветки
в текст брифа не попадают вовсе, и журнал шага не несёт по ним записи
«бриф: компонент» — тест падает на отсутствии обоих маркеров.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import brief, config, gitcmd, store  # noqa: E402
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show, fake_git,
                           seed_developer_brief_fixtures)

TASK = "01AC3DEVBRIEFPLANREV1"


class DeveloperBriefPlanReviewTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        seed_developer_brief_fixtures(self.root)
        task_dir = config.TASKS / TASK
        task_dir.mkdir(parents=True)
        (task_dir / "SPEC.md").write_text("# SPEC\nМаркер SPEC.\n",
                                          encoding="utf-8")
        (task_dir / "PLAN.md").write_text("# PLAN\nМаркер PLAN v1.\n",
                                          encoding="utf-8")
        (task_dir / "REVIEW.md").write_text("# REVIEW\nМаркер REVIEW v1.\n",
                                            encoding="utf-8")
        store.create_schema(store.db())
        store.insert_task(store.db(), TASK, "Бриф разработчика", "in_dev",
                          f"task/{TASK.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND actor=? "
            "ORDER BY id", (TASK, "developer"))]

    def test_ac3_brief_carries_plan_and_review_text_with_sha256_fingerprint(self):
        text = brief.developer_brief(store.db(), TASK)

        self.assertIn("Маркер PLAN v1.", text,
                      "текст PLAN.md артефактной ветки не найден в брифе")
        self.assertIn("Маркер REVIEW v1.", text,
                      "текст REVIEW.md артефактной ветки не найден в брифе")

        plan_sha = brief.component_hash(
            (config.TASKS / TASK / "PLAN.md").read_text(encoding="utf-8"))
        review_sha = brief.component_hash(
            (config.TASKS / TASK / "REVIEW.md").read_text(encoding="utf-8"))
        details = self.journal_details()
        self.assertTrue(
            any(f"PLAN.md: sha256={plan_sha}" in d for d in details),
            f"нет журнальной записи sha256 компонента PLAN.md среди: {details}")
        self.assertTrue(
            any(f"REVIEW.md: sha256={review_sha}" in d for d in details),
            f"нет журнальной записи sha256 компонента REVIEW.md среди: {details}")


if __name__ == "__main__":
    unittest.main()
