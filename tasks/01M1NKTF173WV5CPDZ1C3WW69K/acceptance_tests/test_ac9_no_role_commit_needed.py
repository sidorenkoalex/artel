"""Приёмочный тест AC-9 (tasks/01M1NKTF173WV5CPDZ1C3WW69K/SPEC.md): роль,
завершившая шаг БЕЗ собственного `git commit` каталога `tasks/<id>/` в
кодовую ветку, проходит шаг штатно — автокоммит оркестратора сам
переносит написанные ролью файлы в артефактную ветку; кодовая ветка
`task/*` при этом не получает нового коммита роли по `tasks/<id>/`.

Зелёный с рождения: единая логика автокоммита для любого target
(`checkpoint._commit_external_step_artifacts`, A7, требование 2 из
«Контекста» SPEC) уже сегодня не требует собственного `git commit` роли
— плотницкая запись артефактной ветки читает файлы с ДИСКА рабочего
каталога и не зависит от истории кодовой ветки self/артели. Этот тест
закрепляет уже верное поведение регрессионным контролем на случай,
если материализация `role_cwd` (AC-1) или конфликт-гвард (AC-6) этой же
задачи случайно свяжут перенос артефактов с состоянием кодовой ветки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, checkpoint, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK = "01AC9NOCODEBRANCHCMT1"


class NoRoleCommitNeededTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        store.insert_task(store.db(), TASK, "Без коммита роли в код", "in_dev",
                          self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def test_ac9_step_lands_in_artifact_branch_without_a_role_commit_to_the_code_branch(self):
        cwd = runner.role_cwd(store.db(), TASK, config.DEFAULT_TARGET)
        code_branch_head_before = self.git("rev-parse", self.branch).strip()

        task_dir = cwd / "tasks" / TASK
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "PLAN.md").write_text(
            "PLAN без коммита роли в кодовую ветку", encoding="utf-8")
        # Роль намеренно НЕ коммитит tasks/<id>/ в СВОЮ (кодовую) ветку —
        # только пишет файл на диск, как реальный агентный шаг.

        detail = checkpoint.commit_step_artifacts(store.db(), TASK, "developer")

        self.assertIn("артефактная ветка", detail)
        artifact_branch_name = artifact_branch.branch_name(TASK)
        text, _ = gitcmd.show(artifact_branch_name, f"tasks/{TASK}/PLAN.md")
        self.assertEqual(text, "PLAN без коммита роли в кодовую ветку")

        code_branch_head_after = self.git("rev-parse", self.branch).strip()
        self.assertEqual(
            code_branch_head_before, code_branch_head_after,
            "кодовая ветка задачи не должна получить новый коммит от "
            "автокоммита артефактов — только артефактная ветка")


if __name__ == "__main__":
    unittest.main()
