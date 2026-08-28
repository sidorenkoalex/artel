"""AC-2 (tasks/T051/SPEC.md): конфликт при подтяжке main -> задача
переходит в `escalated` с диагностикой конфликта, merge-попытка отменяется
командой `git merge --abort`, ветка задачи остаётся в состоянии до
подтяжки, main не изменяется.
"""
import unittest

from _sandbox import PASSING_ACCEPTANCE_TEST, RealGitFreshnessTest  # noqa: E402
from orchestrator import fsm  # noqa: E402


class ConflictDuringPullEscalatesTest(RealGitFreshnessTest):

    def test_ac2_conflicting_pull_escalates_aborts_merge_and_leaves_branches_untouched(self):
        wt = self.make_worktree()
        self.write_plan_ready(wt)
        self.write_acceptance_test(wt, PASSING_ACCEPTANCE_TEST)
        # Ветка задачи меняет тот же файл, что и main — гарантированный
        # конфликт слияния (обе стороны правят одну и ту же строку).
        (wt / "shared.txt").write_text("task-version\n", encoding="utf-8")
        c1 = self.commit_all(wt, "T001: правка shared.txt в ветке задачи")

        (self.root / "shared.txt").write_text("main-version\n", encoding="utf-8")
        c2 = self.commit_all(self.root, "правка shared.txt в main")

        self.set_state("in_dev")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "escalated",
                         "конфликт подтяжки обязан эскалировать задачу")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower(),
                     "эскалация обязана нести диагностику конфликта")

        self.assertEqual(self.branch_head(), c1,
                         "ветка задачи обязана остаться в состоянии до "
                         "подтяжки (merge отменён)")
        self.assertEqual(self.main_head(), c2, "main не должен измениться")

        status = self.git("status", "--porcelain", cwd=wt).stdout
        self.assertNotIn("UU", status,
                         "рабочее дерево не должно остаться в конфликтном "
                         "состоянии — merge --abort обязан быть выполнен")
        content = (wt / "shared.txt").read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", content,
                         "конфликт-маркеры не должны просочиться в рабочее "
                         "дерево ветки задачи после отката")


if __name__ == "__main__":
    unittest.main()
