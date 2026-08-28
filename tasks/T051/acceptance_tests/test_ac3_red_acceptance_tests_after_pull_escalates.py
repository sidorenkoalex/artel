"""AC-3 (tasks/T051/SPEC.md): приёмочные тесты после успешной подтяжки
main красные -> задача переходит в `escalated` с перечнем упавших тестов;
слияние с main при этом остаётся (откат не выполняется).
"""
import unittest

from _sandbox import FAILING_ACCEPTANCE_TEST, RealGitFreshnessTest  # noqa: E402
from orchestrator import fsm  # noqa: E402


class RedAcceptanceTestsAfterPullTest(RealGitFreshnessTest):

    def test_ac3_red_tests_after_successful_pull_escalate_but_keep_the_merge(self):
        wt = self.make_worktree()
        self.write_plan_ready(wt)
        self.write_acceptance_test(wt, FAILING_ACCEPTANCE_TEST)
        c1 = self.commit_all(wt, "T001: PLAN готов + заведомо красный тест")

        # Изменение main не пересекается с веткой задачи — слияние пройдёт
        # без конфликта, но приёмочные тесты всё равно красные.
        c2 = self.add_main_commit()

        self.set_state("in_dev")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "escalated",
                         "красные приёмочные тесты после подтяжки обязаны "
                         "эскалировать задачу")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("MARKER-AC3-RED", combined,
                     "эскалация обязана нести перечень упавших тестов")

        new_branch_head = self.branch_head()
        self.assertNotEqual(new_branch_head, c1,
                            "слияние с main обязано остаться — откат не "
                            "выполняется (требование 6)")
        self.assertTrue(self.is_ancestor(c1, new_branch_head),
                        "коммит ветки задачи остаётся предком (не rebase)")
        self.assertTrue(self.is_ancestor(c2, new_branch_head),
                        "main обязан быть подтянут и остаться в ветке")
        self.assertEqual(self.main_head(), c2, "main не должен измениться")


if __name__ == "__main__":
    unittest.main()
