"""Юнит-тесты `checkpoint._commit_external_step_artifacts` (SPEC T094,
требование 8, AC-9 — REVIEW.md итерация 1, замечание 2).

До правки `checkpoint.commit_step_artifacts` безусловно пропускала любой
target, кроме self: роль внешнего target писала `tasks/<id>/` в клон
кода целевого (`runner.role_cwd`), и ни один код не переносил эти файлы
в артефактную ветку пульта — прямое нарушение требования 8 на первом же
реальном шаге роли (не только на `cmd_new`, который уже был покрыт
`tasks/T094/acceptance_tests/test_ac9_role_step_artifact_branch.py`).

Песочница — `RealGitSandbox` (пульт — реальный git-репозиторий с main),
рабочий каталог внешнего target — обычная директория на диске (клон кода
целевого не обязан быть git-репозиторием для этой проверки: функция
читает файлы с диска, коммитит их плотницки в артефактную ветку ПУЛЬТА
и убирает исходники — ни то, ни другое не требует git внутри workspace).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import checkpoint, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TARGET = "extproj"


class CommitExternalStepArtifactsTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.TASK = "01EXTTASKPREFIXSTEP01"
        conn = store.db()
        store.insert_task(conn, self.TASK, "Задача внешнего target",
                          "in_dev", f"task/{self.TASK.lower()}-x", TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, text: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list[str]:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def test_role_written_artifacts_land_in_the_pult_artifact_branch(self):
        self.write("PLAN.md", "---\ntask: x\n---\n# PLAN\n")

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertIn("артефактная ветка", detail)
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", self.artifact_branch_files())

    def test_committed_artifacts_are_removed_from_the_target_code_workspace(self):
        # Требование 8: кодовая ветка/рабочий каталог целевого свободны от
        # tasks/<id>/ после автокоммита — иначе следующий коммит роли
        # (`git add -A` в её собственном клоне) подхватил бы их в код.
        self.write("PLAN.md", "черновик")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        self.assertFalse(self.task_dir.exists(),
                         "tasks/<id>/ обязан быть убран из клона целевого")
        self.assertTrue(self.workspace_root.exists(),
                        "сам рабочий каталог роли не трогаем, только tasks/<id>/")

    def test_no_tasks_dir_written_is_not_an_error(self):
        # Роль на этом шаге правила только код, tasks/<id>/ не трогала.
        self.task_dir.rmdir()

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.artifact_branch_files(), [])

    def test_second_step_accumulates_onto_the_first_not_replaces_it(self):
        self.write("PLAN.md", "план разработчика")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        self.task_dir.mkdir(parents=True)
        self.write("REVIEW.md", "ревью")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "reviewer")

        branch = f"artifact/{self.TASK.lower()}"
        plan_text, _ = gitcmd.show(branch, f"tasks/{self.TASK}/PLAN.md")
        review_text, _ = gitcmd.show(branch, f"tasks/{self.TASK}/REVIEW.md")
        self.assertEqual(plan_text, "план разработчика")
        self.assertEqual(review_text, "ревью")

    def test_journal_records_the_autocommit(self):
        self.write("PLAN.md", "черновик")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        details = [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, "автокоммит артефактов шага (артефактная ветка)"))]
        self.assertTrue(details)
        self.assertIn(self.TASK, details[-1])


if __name__ == "__main__":
    unittest.main()
