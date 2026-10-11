"""AC-5 (tasks/T045/SPEC.md): `kill` убирает worktree задачи.

`make_worktree` заводит worktree настоящим git напрямую (не через
команду `workspace`, чей срок реализации не влияет на этот критерий —
см. tasks/T045/acceptance_tests/_sandbox.py): важен факт «worktree
задачи существует по стандартному пути», а не то, чем он был заведён.
"""
import unittest

from orchestrator import cleanup  # noqa: E402

from _sandbox import WorktreeRepoTest  # noqa: E402


class KillRemovesWorktreeTest(WorktreeRepoTest):

    def test_ac5_kill_removes_task_worktree(self):
        path = self.make_worktree()
        self.assertTrue(path.is_dir(), "worktree не завёлся в песочнице")
        self.assertIn(str(path), self.worktree_list())

        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(self.state(), "killed")
        self.assertFalse(path.exists(),
                         "kill обязан убрать worktree задачи с диска")
        self.assertNotIn(str(path), self.worktree_list(),
                         "kill обязан убрать worktree задачи из git worktree list")


if __name__ == "__main__":
    unittest.main()
