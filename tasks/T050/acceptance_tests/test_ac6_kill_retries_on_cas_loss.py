"""AC-6 (tasks/T050/SPEC.md): `kill`, проиграв первую попытку CAS,
перечитывает состояние и повторяет попытку с новым `expected_state` — не
завершается с ошибкой (в отличие от advance/approve/reject/merge, для
которых проигрыш CAS — именованный отказ, требование 4).

`_race.single_shot_state_race` имитирует конкурентный переход, который
успел вклиниться между чтением состояния командой `kill` и её первой
CAS-попыткой (тот же приём, что в test_ac5_*.py и test_ac8_*.py) — если
`kill` не перечитывает и не повторяет, эта единственная попытка проиграет
CAS и (по общему правилу требования 4) должна была бы упасть отказом;
здесь она не имеет права упасть вовсе.

Песочница — `tests.test_invariants.FsmTest`, тем же приёмом, что
`tasks/T044/acceptance_tests/test_lease_enforcement.py`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import cleanup  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

from _race import single_shot_state_race  # noqa: E402


class KillRetriesAfterLosingTheFirstCasTest(FsmTest):

    def test_ac6_kill_survives_a_concurrent_transition_before_its_first_cas(self):
        self.set_state("in_dev")

        with single_shot_state_race(self.TASK, "review"):
            # Исключение/sys.exit здесь = провал теста: kill обязан
            # перечитать состояние и повторить CAS, не отказывать.
            cleanup.cmd_kill(self.TASK)

        self.assertEqual(self.state(), "killed")


if __name__ == "__main__":
    unittest.main()
