"""AC-6, AC-7 (tasks/T045/SPEC.md): merge_gate, `done` и worktree.

AC-6. `done` убирает worktree задачи.
AC-7. `merge_gate` по-прежнему работает в главной копии пульта на
`main` и остаётся единственным писателем `main`.

`done` — не отдельная CLI-команда: состояние `done` наступает как исход
`approve` на гейте `merge_gate` (orchestrator/fsm.py `_cmd_approve`,
ветка `state == "merge_gate"`, финальный
`store.set_state(..., "done", ...)`), поэтому оба критерия проверяются
одним прогоном этой ветки — стенд `_sandbox.MergeGateReadyTest`.
"""
import unittest

from orchestrator import config  # noqa: E402

from _sandbox import MergeGateReadyTest  # noqa: E402


class MergeGateDoneWorktreeTest(MergeGateReadyTest):

    def test_ac6_done_removes_task_worktree(self):
        self.assertTrue(self.worktree.is_dir())

        self.approve()

        self.assertEqual(self.state(), "done",
                         "approve на merge_gate обязан завершиться done")
        self.assertFalse(self.worktree.exists(),
                         "переход в done обязан убрать worktree задачи")
        self.assertNotIn(str(self.worktree), self.worktree_list())

    def test_ac7_merge_gate_runs_in_main_copy_and_stays_sole_writer_of_main(self):
        out = self.approve()

        self.assertEqual(self.state(), "done", out)
        # Слияние происходит в ГЛАВНОЙ КОПИИ пульта, на main: рабочая
        # копия остаётся на main, а не на ветке задачи или в worktree.
        root_branch = self.git("rev-parse", "--abbrev-ref",
                               "HEAD").stdout.strip()
        self.assertEqual(root_branch, config.MAIN_BRANCH)
        log = self.git("log", "--oneline", "-n", "5",
                       config.MAIN_BRANCH).stdout
        self.assertIn(f"{self.TASK}: merge {self.branch}", log)
        # main пульта — единственный писатель: то, что уехало в origin,
        # это ровно то, что лежит в главной копии, без стороннего сдвига.
        self.assertEqual(self.origin_main_sha(), self.root_main_sha(),
                         "push обязан унести именно то состояние main, "
                         "что в главной копии")


if __name__ == "__main__":
    unittest.main()
