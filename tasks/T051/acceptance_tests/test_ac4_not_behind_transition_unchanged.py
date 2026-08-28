"""AC-4 (tasks/T051/SPEC.md): ветка задачи не отстала от main -> переход
выполняется в точности как до этой задачи (никакой подтяжки, никакого
дополнительного merge-коммита).
"""
import unittest

from _sandbox import PASSING_ACCEPTANCE_TEST, RealGitFreshnessTest  # noqa: E402
from orchestrator import fsm  # noqa: E402


class NotBehindTransitionUnchangedTest(RealGitFreshnessTest):

    def test_ac4_branch_even_with_main_advances_without_extra_merge_commit(self):
        wt = self.make_worktree()
        self.write_plan_ready(wt)
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        c1 = self.commit_all(wt, "T001: PLAN готов, ветка не отстаёт от main")

        main_before = self.main_head()
        self.set_state("in_dev")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "review",
                         "переход обязан состояться, как и до этой задачи")
        self.assertEqual(self.branch_head(), c1,
                         "не отставшая ветка не должна получать коммит "
                         "подтяжки")
        self.assertEqual(self.parent_count(wt), 1,
                         "не должно появиться merge-коммита — ровно один "
                         "родитель у HEAD")
        self.assertEqual(self.main_head(), main_before,
                         "main не должен измениться")


if __name__ == "__main__":
    unittest.main()
