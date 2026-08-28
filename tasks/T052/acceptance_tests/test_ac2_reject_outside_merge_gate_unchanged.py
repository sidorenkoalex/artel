"""AC-2 (tasks/T052/SPEC.md): `reject` из любого состояния, отличного от
`merge_gate` (в частности, из `acceptance`), ведёт себя так же, как до
этой задачи — без изменений в поведении, доступных состояниях и лимитах.

Две стороны того же критерия: `acceptance` — единственное состояние, из
которого `reject` уже работал до T052, и обязано продолжать работать
ровно так же (переход в `in_dev`, счёт `accept_rejects`); любое другое
состояние (не `merge_gate` и не `acceptance`) до T052 отказывало
`sys.exit`, и обязано продолжать отказывать — тем же исходом (отказ,
состояние не меняется), не обязательно тем же текстом сообщения (текст
теперь легитимно упоминает и `merge_gate` как разрешённое состояние).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402


class RejectOutsideMergeGateUnchangedTest(FsmTest):

    def test_ac2_reject_from_acceptance_still_transitions_to_in_dev(self):
        self.set_state("acceptance", accept_rejects=0)

        self.capture(fsm.cmd_reject, self.TASK, "приёмка не пройдена")

        self.assertEqual(self.state(), "in_dev",
                         "reject из acceptance обязан по-прежнему вести в in_dev")
        self.assertEqual(
            self.task_row()["accept_rejects"], 1,
            "reject из acceptance обязан по-прежнему считать попытки приёмки")

    def test_ac2_reject_from_other_states_still_refuses(self):
        for state in ("spec_writing", "spec_gate", "tests_writing", "in_dev",
                      "review", "escalated", "done", "killed"):
            with self.subTest(состояние=state):
                self.set_state(state)

                with self.assertRaises(SystemExit):
                    self.capture(fsm.cmd_reject, self.TASK, "причина")

                self.assertEqual(
                    self.state(), state,
                    f"reject из {state} не должен менять состояние задачи")


if __name__ == "__main__":
    unittest.main()
