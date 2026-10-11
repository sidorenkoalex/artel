"""AC-4 (tasks/T067/SPEC.md): конфликт подтяжки, среди файлов которого
`docs/codebase-map.md` не встречается вовсе: поведение полностью
прежнее (T051), байт-в-байт.

Зелёный с рождения: сценарий «конфликт, карты не касающийся вовсе» не
задет T067 никаким новым кодом — та же ветка `_pull_main_or_escalate`,
что существует с T051, отрабатывает без единого изменения. Тест
фиксирует это как планку (ADR-0002): T067 не имеет права сузить или
изменить поведение здесь, даже случайно.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MapConflictRealGitTest, PASSING_ACCEPTANCE_TEST  # noqa: E402
from orchestrator import fsm  # noqa: E402


class ConflictWithoutMapUnchangedTest(MapConflictRealGitTest):

    def test_ac4_conflict_without_map_escalates_same_as_before(self):
        wt = self.make_worktree()
        self.advance_from_in_dev(wt)
        # Карта не тронута ни с одной стороны — не входит в список
        # конфликтующих файлов вовсе.
        self.diverge_shared_txt(wt)
        pre_branch_head = self.branch_head()
        pre_main_head = self.main_head()

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated",
                         "конфликт без карты обязан эскалировать, как и "
                         "до T067")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())

        self.assertEqual(self.branch_head(), pre_branch_head,
                         "ветка задачи обязана остаться в состоянии до "
                         "подтяжки (merge отменён)")
        self.assertEqual(self.main_head(), pre_main_head,
                         "main не должен измениться")
        self.assert_no_merge_in_progress(wt)


if __name__ == "__main__":
    import unittest
    unittest.main()
