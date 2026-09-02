"""AC-4: захват свободного (ранее не существовавшего) lease
журналируется отдельной записью, называющей взявшую сессию.

Красный до реализации: `orchestrator.lease.acquire`, ветка `row is
None` (свободный lease), сегодня только вставляет строку `leases` —
`store.journal` в этой ветке не зовётся вовсе (см. `orchestrator/
lease.py`, "if row is None: store.insert_lease(...); return None,
True" — ни одного вызова журнала). Перехват протухшего чужого lease
УЖЕ журналируется (это существующее поведение, покрытое
`tests/test_lease.py::AcquireReleaseTest::
test_foreign_stale_lease_is_taken_over_and_journalled`), но свежий
захват — нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import lease, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, any_step_carries  # noqa: E402


class FreshAcquireJournaledTest(LeaseTaskTest):

    def test_ac4_fresh_acquire_journals_the_taking_session(self):
        self.assertIsNone(self.lease_row(), "предпосылка: lease ещё "
                          "не заведён — захват должен быть «с нуля»")
        before = len(self.steps())

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-ac4-taker")

        self.assertIsNone(refusal)
        self.assertTrue(fresh, "взятие свободного lease обязано быть "
                        "«с нуля» — это существующее поведение")
        new_steps = self.steps()[before:]
        self.assertTrue(
            any_step_carries(new_steps, "sess-ac4-taker"),
            f"захват свободного lease не журналирован именем взявшей "
            f"сессии (AC-4): {new_steps}")


if __name__ == "__main__":
    unittest.main()
