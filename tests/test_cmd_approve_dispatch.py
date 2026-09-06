"""Юнит-тесты таблицы «состояние -> обработчик» `orchestrator.fsm._cmd_
approve` (роадмап §3, фаза R, R3, требование 3): словарь заменяет цепочку
`if state == ...`; здесь — что каждое состояние `spec_gate`/`acceptance`/
`merge_gate`/`escalated` ведёт РОВНО к своему обработчику (`fsm._approve_
spec_gate`/`_approve_acceptance`/`_approve_merge_gate`/`_approve_escalated`,
подмена по имени — сама диспетчеризация, не поведение обработчиков: то
уже кроют `tests/test_zones_approve.py`/`tests/test_fsm_draft_mr_reentry.
py`/приёмочные тесты этой задачи), а состояние вне таблицы — к прежнему
тексту отказа без вызова ни одного обработчика.

Каждый сценарий — отдельный метод теста (не цикл по общей БД
`setUp`/`tearDown`): повторные `store.db()`/`insert_task`/`DELETE` на
одном файле БД в пределах одного метода периодически ловят `sqlite3.
OperationalError: database is locked` (соединения `_AutoClosingConnection`
не закрываются синхронно) — отдельный метод получает свежий временный
каталог `TmpRootTest.setUp` и не рискует этим классом флуда.
"""
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

HANDLER_NAMES = ("_approve_spec_gate", "_approve_acceptance",
                "_approve_merge_gate", "_approve_escalated")


class CmdApproveDispatchTest(TmpRootTest):

    TASK = "01CMDAPPROVEDISPATCHTST"
    BRANCH = f"task/{TASK.lower()}-x"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())

        confirm_patcher = mock.patch.object(
            fsm, "confirm_fixation", lambda *a: True)
        confirm_patcher.start()
        self.addCleanup(confirm_patcher.stop)

    def insert(self, state: str) -> None:
        store.insert_task(store.db(), self.TASK, "Тест диспетчера approve",
                          state, self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def approve(self, sha=None) -> str:
        return capture(fsm._cmd_approve, store.db(), self.TASK, sha, "sid")

    def _assert_routes_to(self, state: str, handler_name: str) -> None:
        self.insert(state)
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(mock.patch.object(fsm, name))
                for name in HANDLER_NAMES
            }
            self.approve("f" * 40)

            mocks[handler_name].assert_called_once()
            for other_name, other_mock in mocks.items():
                if other_name != handler_name:
                    other_mock.assert_not_called()

            # Аргументы обработчика — (conn, task_id, t, state, sid), тем
            # же порядком, что и до введения таблицы.
            args = mocks[handler_name].call_args[0]
            self.assertEqual(args[1], self.TASK)
            self.assertEqual(args[3], state)
            self.assertEqual(args[4], "sid")

    def test_spec_gate_routes_to_its_own_handler(self):
        self._assert_routes_to("spec_gate", "_approve_spec_gate")

    def test_acceptance_routes_to_its_own_handler(self):
        self._assert_routes_to("acceptance", "_approve_acceptance")

    def test_merge_gate_routes_to_its_own_handler(self):
        self._assert_routes_to("merge_gate", "_approve_merge_gate")

    def test_escalated_routes_to_its_own_handler(self):
        self._assert_routes_to("escalated", "_approve_escalated")

    def test_state_outside_table_calls_no_handler_and_keeps_previous_text(self):
        self.insert("review")
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(mock.patch.object(fsm, name))
                for name in HANDLER_NAMES
            }
            out = self.approve()

            for handler_mock in mocks.values():
                handler_mock.assert_not_called()

        self.assertEqual(
            out.strip(), f"[{self.TASK}] в состоянии review нечего подтверждать")
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "review")


if __name__ == "__main__":
    unittest.main()
