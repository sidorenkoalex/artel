"""Юнит-тесты `orchestrator.store.set_state` (SPEC T050).

Приёмочные тесты (tasks/T050/acceptance_tests) кроют AC-1..AC-8 сквозным
путём через реальную гонку и через `fsm.py`/`cleanup.py`; здесь — сам
CAS в изоляции: форма отказа (`CasConflict`), обязательность
`expected_state`, отсутствие следов проигравшего вызова в journal/
фиксации, атомарность самого `UPDATE`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"


class SetStateCasTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_matching_expected_state_wins_and_journals_the_transition(self):
        store.set_state(store.db(), TASK, "review", "test",
                        expected_state="in_dev")

        self.assertEqual(store.get_task(store.db(), TASK)["state"], "review")
        actions = [r["action"] for r in store.task_steps(store.db(), TASK)]
        self.assertIn("state -> review", actions)

    def test_mismatched_expected_state_raises_cas_conflict(self):
        with self.assertRaises(store.CasConflict):
            store.set_state(store.db(), TASK, "review", "test",
                            expected_state="acceptance")

    def test_cas_conflict_names_expected_and_actual(self):
        with self.assertRaises(store.CasConflict) as ctx:
            store.set_state(store.db(), TASK, "review", "test",
                            expected_state="acceptance")

        exc = ctx.exception
        self.assertEqual(exc.expected, "acceptance")
        self.assertEqual(exc.actual, "in_dev")
        self.assertEqual(exc.task_id, TASK)
        self.assertIn("acceptance", str(exc))
        self.assertIn("in_dev", str(exc))

    def test_losing_call_does_not_journal_anything(self):
        before = len(store.task_steps(store.db(), TASK))

        with self.assertRaises(store.CasConflict):
            store.set_state(store.db(), TASK, "review", "test",
                            expected_state="acceptance")

        self.assertEqual(len(store.task_steps(store.db(), TASK)), before)

    def test_losing_call_does_not_touch_fixed_sha(self):
        before = store.get_task(store.db(), TASK)["fixed_sha"]

        with self.assertRaises(store.CasConflict):
            store.set_state(store.db(), TASK, "review", "test",
                            expected_state="acceptance")

        self.assertEqual(store.get_task(store.db(), TASK)["fixed_sha"], before)

    def test_expected_state_is_mandatory(self):
        with self.assertRaises(TypeError):
            store.set_state(store.db(), TASK, "review", "test")

    def test_expected_state_is_keyword_only(self):
        with self.assertRaises(TypeError):
            store.set_state(store.db(), TASK, "review", "test", "in_dev")


if __name__ == "__main__":
    unittest.main()
