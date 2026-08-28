"""AC-8 (tasks/T050/SPEC.md): `kill` переводит задачу в `killed` из
любого нетерминального состояния даже при параллельном переходе
состояния между чтением и вызовом `kill` (инвариант №14 «kill срабатывает
всегда», docs/design.md §6 — тот же инвариант, что кодирует
tests/test_kill_cleanup.py::KillCleanupTest, здесь под гонкой).

`_race.single_shot_state_race` имитирует конкурентный переход,
случившийся между чтением состояния командой `kill` и её CAS-попыткой —
инвариант обязан устоять независимо от того, из какого состояния и в
какое (иное) состояние успела вклиниться гонка.

Песочница — `tests.test_invariants.FsmTest`, тем же приёмом, что
`tasks/T044/acceptance_tests/test_lease_enforcement.py`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import cleanup  # noqa: E402
from tests.test_invariants import FSM_STATES, FsmTest  # noqa: E402

from _race import single_shot_state_race  # noqa: E402

NON_TERMINAL_STATES = tuple(s for s in FSM_STATES if s not in ("done", "killed"))


class KillAlwaysReachesKilledTest(FsmTest):
    """НЕОСЛАБЛЯЕМЫЙ: инвариант №14, tasks/T050/SPEC.md требования 7-8."""

    def test_ac8_kill_reaches_killed_from_any_nonterminal_state_under_a_race(self):
        for state in NON_TERMINAL_STATES:
            with self.subTest(состояние=state):
                self.set_state(state, reviewed_iter=0, escalated_from=None,
                               review_iters=0, accept_rejects=0)
                decoy = "review" if state != "review" else "tests_writing"

                with single_shot_state_race(self.TASK, decoy):
                    # Исключение здесь = провал теста: инвариант №14 не
                    # допускает ни отказа, ни зависания kill под гонкой.
                    cleanup.cmd_kill(self.TASK)

                self.assertEqual(
                    self.state(), "killed",
                    f"kill не добил задачу из {state} при параллельном "
                    f"переходе в {decoy}")


if __name__ == "__main__":
    unittest.main()
