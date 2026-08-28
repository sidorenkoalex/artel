"""AC-5 (tasks/T053/SPEC.md): `kill` и `reject` из `merge_gate` выполняются
успешно, пока мьютекс merge занят другой сессией (не ждут его
освобождения).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import cleanup, fsm, store  # noqa: E402

from _mutex_sandbox import (CALLER_SESSION, HOLDER_HOST, HOLDER_PID,  # noqa: E402
                            HOLDER_SESSION, HOLDER_TASK, MergeLockFsmTest,
                            invoke)


class Ac5RejectBypassesMergeMutexTest(MergeLockFsmTest):

    def test_ac5_reject_succeeds_while_merge_mutex_held_by_other_session(self):
        self.seed_merge_lock(HOLDER_SESSION, HOLDER_PID, HOLDER_HOST,
                             store.now(), HOLDER_TASK)
        before_lock = self.merge_lock_rows()

        output = invoke(lambda: fsm.cmd_reject(
            self.TASK, "причина", session_id=CALLER_SESSION))

        self.assertEqual(
            self.state(), "in_dev",
            f"reject обязан пройти, не дожидаясь чужого мьютекса merge: "
            f"{output!r}")
        self.assertEqual(
            self.merge_lock_rows(), before_lock,
            "reject не имеет права брать или иначе трогать мьютекс merge")


class Ac5KillBypassesMergeMutexTest(MergeLockFsmTest):

    def test_ac5_kill_succeeds_while_merge_mutex_held_by_other_session(self):
        self.seed_merge_lock(HOLDER_SESSION, HOLDER_PID, HOLDER_HOST,
                             store.now(), HOLDER_TASK)
        before_lock = self.merge_lock_rows()

        output = invoke(lambda: cleanup.cmd_kill(
            self.TASK, session_id=CALLER_SESSION))

        self.assertEqual(
            self.state(), "killed",
            f"kill обязан пройти, не дожидаясь чужого мьютекса merge: "
            f"{output!r}")
        self.assertEqual(
            self.merge_lock_rows(), before_lock,
            "kill не имеет права брать или иначе трогать мьютекс merge")


if __name__ == "__main__":
    import unittest
    unittest.main()
