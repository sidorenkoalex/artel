"""Юнит-тесты подтипа не-зелёного статуса CI на гейте `merge_gate`
(SPEC T082, ревью итерации 2, замечание major 1).

`tasks/T082/acceptance_tests/test_ci_flake_rerun.py` (AC-14..17) кроет
только сценарий, где `ci.branch_status` возвращает РЕАЛЬНО красный статус
(«не зелёный: python=failure») — ре-ран и flake-rate там уместны. Этот
модуль кроет случаи, которые до итерации 2 попадали в ту же ветку кода
ошибочно: «CI ещё идёт» и «статус неизвестен» — для них нет что
подтверждать ре-раном, гейт обязан отказать как раньше, БЕЗ вызова
`ci.trigger_rerun` и БЕЗ записи «подтверждённый красный» в flake-rate.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import ci, fsm, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

RUNNING = (False, "CI коммита abc12345 ещё идёт: guard")
UNKNOWN = (False, "статус CI коммита abc12345 неизвестен: gh не ответил")


class NonRedStatusSkipsRerunTest(FsmTest):

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

    def journal_blob(self) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
        return "\n".join(f"{r['action']} | {r['detail']}" for r in rows).lower()

    def approve_with(self, status: tuple) -> mock.Mock:
        mocked = mock.Mock(return_value=status)
        status_patcher = mock.patch.object(ci, "branch_status", mocked)
        status_patcher.start()
        self.addCleanup(status_patcher.stop)
        rerun_patcher = mock.patch.object(
            ci, "trigger_rerun",
            mock.Mock(side_effect=AssertionError(
                "ci.trigger_rerun не должен звонить для не-красного "
                "статуса (running/unknown) — там нечего подтверждать")))
        rerun_patcher.start()
        self.addCleanup(rerun_patcher.stop)
        with self.assertRaises(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)
        return mocked

    def test_still_running_does_not_trigger_a_rerun(self):
        mocked = self.approve_with(RUNNING)

        self.assertEqual(
            mocked.call_count, 1,
            "«CI ещё идёт» не подлежит ре-рану — branch_status обязан "
            "быть спрошен ровно один раз, как до T082")
        self.assertEqual(self.state(), "merge_gate")
        self.assertNotIn("flake-rate", self.journal_blob())

    def test_unknown_status_does_not_trigger_a_rerun(self):
        mocked = self.approve_with(UNKNOWN)

        self.assertEqual(
            mocked.call_count, 1,
            "статус «неизвестен» не подлежит ре-рану — branch_status "
            "обязан быть спрошен ровно один раз, как до T082")
        self.assertEqual(self.state(), "merge_gate")
        self.assertNotIn("flake-rate", self.journal_blob())


if __name__ == "__main__":
    unittest.main()
