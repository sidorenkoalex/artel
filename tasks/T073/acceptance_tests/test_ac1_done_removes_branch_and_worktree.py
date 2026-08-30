"""AC-1 (tasks/T073/SPEC.md): переход задачи в состояние `done` убирает
её ветку task/* и worktree задачи.

Красен до реализации: сегодня (до T073) `fsm._cmd_approve_merge_gate`
убирает только worktree (SPEC T045) — ветку задачи после `--no-ff`
merge никто не удаляет, `git branch -D`/`-d` для неё не вызывается.
Поэтому `test_ac1_done_removes_task_branch` обязан падать на живой
ветке до появления кода этой задачи, а не на отсутствии worktree
(тот уже убирается — см. tasks/T045/acceptance_tests/test_ac6_ac7_
merge_gate.py `test_ac6_done_removes_task_worktree`, тем же стендом).
"""
import unittest

from _sandbox import DoneTaskTest  # noqa: E402


class DoneRemovesBranchAndWorktreeTest(DoneTaskTest):

    def test_ac1_done_removes_task_branch(self):
        self.assertTrue(self.branch_exists(self.branch),
                        "ветка задачи обязана существовать до approve")

        out = self.approve()

        self.assertEqual(self.state(), "done", out)
        self.assertFalse(
            self.branch_exists(self.branch),
            f"переход в done обязан убрать ветку {self.branch} задачи")

    def test_ac1_done_removes_task_worktree(self):
        self.assertTrue(self.worktree.is_dir())

        out = self.approve()

        self.assertEqual(self.state(), "done", out)
        self.assertFalse(self.worktree.exists(),
                         "переход в done обязан убрать worktree задачи")
        self.assertNotIn(str(self.worktree), self.worktree_list())


if __name__ == "__main__":
    unittest.main()
