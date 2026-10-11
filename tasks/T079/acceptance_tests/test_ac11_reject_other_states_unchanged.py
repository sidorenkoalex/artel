"""AC-11 (tasks/T079/SPEC.md): `reject` из состояний, отличных от
`merge_gate`, `acceptance` и `verifying`, ведёт себя так же, как до этой
задачи — без изменений в поведении, доступных состояниях и лимитах.

Зелёный с рождения: до правки разработчика ЛЮБОЕ состояние, отличное от
`merge_gate`/`acceptance` (включая `verifying`, которого сегодня не
существует как рабочего состояния), уже отказывает `sys.exit` — этот
тест кодирует РЕГРЕССИЮ (T052, AC-2, `tasks/T052/acceptance_tests/
test_ac2_reject_outside_merge_gate_unchanged.py`, второй метод), а не
новое поведение: он обязан оставаться зелёным и после появления
`verifying`, поскольку явно исключает его из свипа.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from tests.test_invariants import FSM_STATES, FsmTest  # noqa: E402

# AC-11 называет ровно три состояния, которым разрешено ЧТО-ТО делать с
# reject (merge_gate/acceptance — существовавшие до этой задачи,
# verifying — новое, AC-10); остальные обязаны продолжать отказывать.
REJECT_PERMITTED_STATES = ("merge_gate", "acceptance", "verifying")


class RejectOutsideAllowedStatesStillRefusesTest(FsmTest):

    def test_ac11_every_other_known_state_still_refuses_reject(self):
        for state in set(FSM_STATES) - set(REJECT_PERMITTED_STATES):
            with self.subTest(состояние=state):
                self.set_state(state)

                with self.assertRaises(SystemExit):
                    self.capture(fsm.cmd_reject, self.TASK, "причина")

                self.assertEqual(
                    self.state(), state,
                    f"reject из {state} не должен менять состояние задачи")


if __name__ == "__main__":
    unittest.main()
