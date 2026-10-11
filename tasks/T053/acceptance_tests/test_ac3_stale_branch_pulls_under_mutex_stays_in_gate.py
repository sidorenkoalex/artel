"""AC-3 (tasks/T053/SPEC.md): задача отстала от main на входе в
merge-окно -> под мьютексом выполняется подтяжка (merge main в ветку
задачи + прогон приёмочных) и merge в main НЕ выполняется; задача
остаётся в `merge_gate`; сообщение команды содержит новый head ветки;
после зелёного CI нового head повторный `approve` выполняет merge.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (MergeQueueRealGitTest, PASSING_ACCEPTANCE_TEST,  # noqa: E402
                      TASK)


class Ac3PullUnderMutexKeepsTaskInGateTest(MergeQueueRealGitTest):

    def setUp(self):
        super().setUp()
        wt = self.make_worktree()
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        self.pre_sha = self.commit_all(wt, f"{TASK}: приёмочные тесты")
        # acceptance -> merge_gate: ветка ещё не отстала на этом шаге,
        # T051-сверка на входе в гейт — no-op (не предмет этих тестов).
        self.approve()
        self.assertEqual(self.state(), "merge_gate",
                         "предпосылка теста: вход на гейт обязан пройти")

    def test_ac3_behind_branch_pulls_and_stays_in_merge_gate(self):
        # main уходит вперёд, ПОКА задача стоит на гейте merge_gate —
        # ровно дыра №2 из «Контекста» SPEC.
        c2 = self.add_main_commit()

        out = self.approve()

        self.assertEqual(
            self.state(), "merge_gate",
            "подтяжка внутри окна не имеет права мержить в main в этом же "
            "вызове — задача обязана остаться на гейте")
        new_head = self.branch_head()
        self.assertNotEqual(
            new_head, self.pre_sha,
            "ветка задачи обязана получить коммит подтяжки main")
        self.assertTrue(
            self.is_ancestor(self.pre_sha, new_head),
            "существующий коммит ветки обязан остаться валидным предком "
            "(не rebase)")
        self.assertTrue(self.is_ancestor(c2, new_head),
                        "main обязан быть подтянут в ветку задачи")
        self.assertEqual(
            self.main_head(), c2,
            "merge в main НЕ должен произойти в этом же вызове approve")
        self.assertIn(
            new_head, out,
            f"сообщение approve обязано назвать новый head ветки: {out!r}")

    def test_ac3_second_approve_after_pull_merges_into_main(self):
        self.add_main_commit()
        self.approve()
        self.assertEqual(
            self.state(), "merge_gate",
            "предпосылка теста: подтяжка обязана оставить задачу на гейте")

        # CI нового head — зелёный (замокан по branch, не по sha) — SPEC
        # требование 6: повторный approve после подтяжки и зелёного CI
        # нового head выполняет merge.
        self.approve()

        self.assertEqual(
            self.state(), "done",
            "после подтяжки и зелёного CI нового head повторный approve "
            "обязан выполнить merge-окно")


if __name__ == "__main__":
    import unittest
    unittest.main()
