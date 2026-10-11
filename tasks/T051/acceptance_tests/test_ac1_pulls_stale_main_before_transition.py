"""AC-1 (tasks/T051/SPEC.md): ветка задачи отстала от main -> на входе в
`in_dev -> review` и в `acceptance -> merge_gate` оркестратор подтягивает
main в ветку задачи merge-коммитом (не rebase) и прогоняет приёмочные
тесты задачи в worktree ветки; переход выполняется только после успеха
обоих шагов.
"""
import unittest

from _sandbox import (PASSING_ACCEPTANCE_TEST, RealGitFreshnessTest,  # noqa: E402
                      TASK)
from orchestrator import fsm  # noqa: E402


class InDevToReviewPullsStaleMainTest(RealGitFreshnessTest):

    def test_ac1_indev_to_review_merges_main_and_runs_acceptance_before_advancing(self):
        wt = self.make_worktree()
        self.write_plan_ready(wt)
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        c1 = self.commit_all(wt, f"{TASK}: PLAN готов + приёмочные тесты")

        # main уходит вперёд, пока задача едет по конвейеру — ветка задачи
        # отстаёт (SPEC, «Контекст»).
        c2 = self.add_main_commit()

        self.set_state("in_dev")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "review",
                         "переход обязан состояться после успешной подтяжки")
        new_head = self.branch_head()
        self.assertNotEqual(new_head, c1,
                            "ветка задачи обязана получить коммит подтяжки main")
        self.assertTrue(
            self.is_ancestor(c1, new_head),
            "существующий коммит ветки задачи обязан остаться валидным "
            "предком (не rebase, требование 3)")
        self.assertTrue(
            self.is_ancestor(c2, new_head),
            "main обязан быть подтянут в ветку задачи")
        self.assertEqual(self.main_head(), c2,
                         "main не должен измениться самой сверкой "
                         "(требование 10)")


class AcceptanceToMergeGatePullsStaleMainTest(RealGitFreshnessTest):

    def test_ac1_acceptance_to_merge_gate_merges_main_before_approving(self):
        self.set_state("acceptance")
        wt = self.make_worktree()
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        pre_sha = self.commit_all(wt, f"{TASK}: приёмочные тесты")

        c2 = self.add_main_commit()

        self.capture(fsm.cmd_approve, self.TASK, pre_sha)

        self.assertEqual(self.task_row()["state"], "merge_gate",
                         "approve обязан продвинуть задачу после успешной "
                         "подтяжки и зелёных приёмочных тестов")
        new_head = self.branch_head()
        self.assertNotEqual(new_head, pre_sha,
                            "ветка задачи обязана получить коммит подтяжки main")
        self.assertTrue(self.is_ancestor(pre_sha, new_head),
                        "существующий коммит ветки задачи остаётся валидным")
        self.assertTrue(self.is_ancestor(c2, new_head),
                        "main обязан быть подтянут в ветку задачи")
        self.assertEqual(self.main_head(), c2, "main не должен измениться")


if __name__ == "__main__":
    unittest.main()
