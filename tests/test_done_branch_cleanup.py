"""Юнит-тесты `cleanup.drop_merged_task_branch` (tasks/T073/SPEC.md,
требование 2) — уборка ветки задачи на переходе `merge_gate -> done`.

Сквозной путь через `cmd_approve` целиком (мьютекс merge-окна, сверка
CI/свежести, реальный `--no-ff` merge, worktree первым) уже покрывают
приёмочные тесты (tasks/T073/acceptance_tests/test_ac1..test_ac3), тем
же приёмом, что и `tests/test_fsm_retro.py` для соседнего RETRO-вызова
в том же окне. Здесь — сама функция уборки в изоляции, по образцу
`tests/test_kill_cleanup.py`/`tests/test_workspace.py`.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import cleanup, config  # noqa: E402
from tests.sandbox import resilient_tmp_cleanup  # noqa: E402


class DropMergedTaskBranchTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        (self.root / "README.md").write_text("init\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        patcher = mock.patch.object(config, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    def branches(self) -> list[str]:
        return self.git(
            "branch", "--format=%(refname:short)").stdout.split()

    def test_merged_branch_is_deleted_with_safe_flag(self):
        self.git("checkout", "-q", "-b", "task/t900-x")
        (self.root / "f.txt").write_text("работа\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "T900: работа")
        self.git("checkout", "-q", config.MAIN_BRANCH)
        self.git("merge", "-q", "--no-ff", "task/t900-x", "-m", "merge")

        out = cleanup.drop_merged_task_branch("task/t900-x")

        self.assertEqual(out, "удалена ветка task/t900-x")
        self.assertNotIn("task/t900-x", self.branches())

    def test_unmerged_branch_is_refused_and_left_alone(self):
        self.git("checkout", "-q", "-b", "task/t901-x")
        (self.root / "g.txt").write_text("работа\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "T901: работа")
        self.git("checkout", "-q", config.MAIN_BRANCH)

        out = cleanup.drop_merged_task_branch("task/t901-x")

        self.assertIn("не удалена", out)
        self.assertIn("task/t901-x", self.branches())

    def test_missing_branch_is_reported_without_error(self):
        out = cleanup.drop_merged_task_branch("task/t404-nope")

        self.assertEqual(out, "локальной ветки task/t404-nope нет")

    def test_empty_branch_is_reported_without_calling_git(self):
        out = cleanup.drop_merged_task_branch("")

        self.assertEqual(out, "ветка задачи не записана — нечего удалять")


if __name__ == "__main__":
    unittest.main()
