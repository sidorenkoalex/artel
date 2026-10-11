"""AC-5 (tasks/T052/SPEC.md): при красном или неполном CI-статусе ветки
`approve` из `merge_gate` отказывает, а задача остаётся в `merge_gate` —
поведение идентично поведению до этой задачи; автоматического перехода
в `in_dev` или `escalated` по красному CI не происходит.

Песочница — `tests.test_invariants.FsmTest`, тот же приём и та же
заготовка (`GREEN_CI`/`set_ci`), что `MergeNeedsGreenCiTest` в
`tests/test_invariants.py` — эта задача не меняет гейт CI, только
проверяет, что T052 не открыл по красному CI новый путь `in_dev`/
`escalated`, которого раньше не было.
"""
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

RED_CI = json.dumps({"total_count": 1, "check_runs": [
    {"name": "python", "status": "completed", "conclusion": "failure"}]})


class RedCiKeepsTaskInMergeGateTest(FsmTest):

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

    def test_ac5_red_ci_refuses_approve_and_stays_in_merge_gate(self):
        self.set_ci(RED_CI)

        with self.assertRaises(SystemExit) as exit_:
            self.capture(fsm.cmd_approve, self.TASK)

        message = str(exit_.exception)
        self.assertIn("merge отклонён", message)
        self.assertIn("задача осталась на гейте merge", message)
        self.assertEqual(self.state(), "merge_gate",
                         "красный CI не должен сдвигать задачу с гейта")

    def test_ac5_red_ci_does_not_auto_transition_to_in_dev_or_escalated(self):
        self.set_ci(RED_CI)

        with self.assertRaises(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotIn(self.state(), ("in_dev", "escalated"),
                         "красный CI не открывает автоматический возврат "
                         "или эскалацию — это осталось за Оператором")


if __name__ == "__main__":
    unittest.main()
