"""AC-7 (tasks/T052/SPEC.md): счётчики итераций задачи (`review_iters`,
`accept_rejects`) не сбрасываются переходом `merge_gate -> in_dev`,
выполненным ни через `reject`, ни через автоматический возврат по
конфликту.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from _sandbox import MergeGateRealGitTest  # noqa: E402
from orchestrator import fsm  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402


class CountersSurviveRejectFromMergeGateTest(FsmTest):

    def test_ac7_reject_from_merge_gate_does_not_reset_counters(self):
        self.set_state("merge_gate", review_iters=2, accept_rejects=1)

        self.capture(fsm.cmd_reject, self.TASK, "main ушёл вперёд")

        self.assertEqual(self.state(), "in_dev")
        row = self.task_row()
        self.assertEqual(row["review_iters"], 2,
                         "review_iters не должен сбрасываться reject'ом из merge_gate")
        self.assertEqual(row["accept_rejects"], 1,
                         "accept_rejects не должен сбрасываться reject'ом из merge_gate")


class CountersSurviveAutomaticConflictReturnTest(MergeGateRealGitTest):

    def test_ac7_automatic_conflict_return_does_not_reset_counters(self):
        self.make_conflicting_branch(
            "shared.txt", "правка ветки задачи\n", "правка main\n")
        self.set_state("merge_gate", review_iters=2, accept_rejects=1)

        self.approve()

        self.assertEqual(self.state(), "in_dev")
        row = self.task_row()
        self.assertEqual(
            row["review_iters"], 2,
            "review_iters не должен сбрасываться автоматическим возвратом "
            "по конфликту")
        self.assertEqual(
            row["accept_rejects"], 1,
            "accept_rejects не должен сбрасываться автоматическим "
            "возвратом по конфликту")


if __name__ == "__main__":
    unittest.main()
