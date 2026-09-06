"""Юнит-тесты каркаса гейтов `orchestrator.fsm_advance._run_gates`/
`GateRefusal` (SPEC 01M1TKNXX5YN5KT4WHG4T44JWV, требования 1-4, AC-1..
AC-4, AC-8): свойства каркаса на СИНТЕТИЧЕСКИХ гейтах, не привязанных к
реальным проверкам `in_dev`/`review` — те закрыты отдельно
(`tests/test_capacity_gate.py`, `tests/test_zones_gate.py`,
`tests/test_fsm_review_rework_gate.py`, `tests/test_fsm_advance_gate_
smoke.py`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fsm_advance, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class RunGatesFrameworkTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        store.insert_task(self.conn, self.task_id, "Тест каркаса",
                          "in_dev", "task/t001-x", "artel", 25.0)

    def journal_rows(self):
        return self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,)).fetchall()

    def test_all_gates_pass_returns_false_without_journal_or_print(self):
        """AC-4: все гейты списка пройдены — `False`, без единой записи
        в журнал (и без печати)."""
        calls = []

        def passing(name):
            def gate():
                calls.append(name)
                return None
            return gate

        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            refused = fsm_advance._run_gates(
                self.conn, self.task_id,
                [passing("a"), passing("b"), passing("c")])

        self.assertFalse(refused)
        self.assertEqual(calls, ["a", "b", "c"])
        self.assertEqual(self.journal_rows(), [])
        self.assertEqual(buf.getvalue(), "")

    def test_order_is_respected(self):
        """Требование 3/AC-3: гейты применяются в порядке списка."""
        calls = []

        def passing(name):
            def gate():
                calls.append(name)
                return None
            return gate

        fsm_advance._run_gates(
            self.conn, self.task_id,
            [passing("first"), passing("second"), passing("third")])

        self.assertEqual(calls, ["first", "second", "third"])

    def test_stops_on_first_refusal_later_gates_not_called(self):
        """AC-3: гейты ПОСЛЕ отказавшего не вызываются."""
        calls = []

        def passing(name):
            def gate():
                calls.append(name)
                return None
            return gate

        def refusing(name):
            def gate():
                calls.append(name)
                return fsm_advance.GateRefusal(
                    "переход отклонён: тест", "деталь отказа", "подсказка")
            return gate

        refused = fsm_advance._run_gates(
            self.conn, self.task_id,
            [passing("a"), refusing("b"), passing("c")])

        self.assertTrue(refused)
        self.assertEqual(calls, ["a", "b"],
                         "гейт «c», идущий после отказавшего «b», не "
                         "имеет права быть вызванным")

    def test_refusal_journals_exactly_once(self):
        """AC-4: на отказе — ровно один вызов `store.journal`, с текстом
        `action`/`detail` из `GateRefusal`."""
        def refusing():
            return fsm_advance.GateRefusal(
                "переход отклонён: тест", "деталь отказа", "подсказка")

        refused = fsm_advance._run_gates(self.conn, self.task_id, [refusing])

        self.assertTrue(refused)
        rows = self.journal_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "переход отклонён: тест")
        self.assertEqual(rows[0]["detail"], "деталь отказа")

    def test_refusal_prints_message_and_hint(self):
        import io
        import contextlib

        def refusing():
            return fsm_advance.GateRefusal(
                "переход отклонён: тест", "деталь отказа", "подсказка тут")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fsm_advance._run_gates(self.conn, self.task_id, [refusing])

        out = buf.getvalue()
        self.assertIn(f"[{self.task_id}] переход отклонён: деталь отказа", out)
        self.assertIn("  дальше: подсказка тут", out)

    def test_empty_hint_is_not_printed(self):
        """`hint` пустой — вторая строка подсказки не печатается вовсе."""
        import io
        import contextlib

        def refusing():
            return fsm_advance.GateRefusal(
                "переход отклонён: тест", "деталь отказа", "")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fsm_advance._run_gates(self.conn, self.task_id, [refusing])

        self.assertNotIn("дальше:", buf.getvalue())

    def test_empty_gate_list_passes(self):
        self.assertFalse(fsm_advance._run_gates(self.conn, self.task_id, []))
        self.assertEqual(self.journal_rows(), [])


if __name__ == "__main__":
    unittest.main()
