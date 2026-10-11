"""AC-4 (tasks/T053/SPEC.md): задача не отстала от main -> переход
`acceptance -> merge_gate` и сам merge выполняются в точности как до этой
задачи (байт-в-байт прежнее поведение).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

from _sandbox import (MergeQueueRealGitTest, PASSING_ACCEPTANCE_TEST,  # noqa: E402
                      TASK)


class Ac4NotBehindTransitionAndMergeUnchangedTest(MergeQueueRealGitTest):

    def test_ac4_acceptance_to_merge_gate_and_merge_are_byte_for_byte_unchanged(self):
        wt = self.make_worktree()
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        pre_sha = self.commit_all(wt, f"{TASK}: приёмочные тесты")

        self.approve()  # acceptance -> merge_gate, ветка не отстала

        self.assertEqual(
            self.state(), "merge_gate",
            "вход на гейт обязан пройти, когда ветка не отстала от main")
        self.assertEqual(
            self.branch_head(), pre_sha,
            "сверка свежести не имеет права коснуться ветки, когда она "
            "не отстала от main (никакого коммита подтяжки)")

        self.approve()  # merge_gate -> done: мьютекс свободен, не отстала

        self.assertEqual(
            self.state(), "done",
            "merge обязан пройти байт-в-байт как до T053, когда ветка не "
            "отстала от main на входе в окно")
        log = self.git("log", "--oneline", "-n", "5",
                       config.MAIN_BRANCH).stdout
        self.assertIn(f"{TASK}: merge {self.branch}", log)
        self.assertEqual(
            self.origin_main_sha(), self.main_head(),
            "push обязан унести именно то, что смержено в главной копии "
            "— тот же инвариант, что tasks/T045 AC-7")


if __name__ == "__main__":
    import unittest
    unittest.main()
