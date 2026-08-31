"""Юнит-тесты `store.refusal_history` / `brief.advance_refusal_history`
(SPEC T078): отказ advance доносится до следующего запуска роли.

Приёмочные тесты — `tasks/T078/acceptance_tests/`
(`test_advance_refusal_reaches_next_role_run.py`, AC-1..AC-3), сквозь
реальный `fsm.cmd_advance` и `runner.cmd_run`. Здесь — сами функции по
отдельности, тем же приёмом, что `tests/test_brief.py` уже применяет
к остальным компонентам брифа.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import brief, config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class RefusalHistorySandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), "T001", "заголовок", "tests_writing",
                          "task/t001", config.DEFAULT_TARGET, 25.0)
        store.insert_task(store.db(), "T002", "другая задача", "in_dev",
                          "task/t002", config.DEFAULT_TARGET, 25.0)


class StoreRefusalHistoryTest(RefusalHistorySandbox):

    def test_no_entries_returns_empty_list(self):
        self.assertEqual(
            store.refusal_history(store.db(), "T001", "tests_writing", 5), [])

    def test_refusal_before_any_state_marker_is_included(self):
        """Первое состояние задачи (нет записи `state -> ...`) — граница
        0, отказ виден (SPEC T078, требование 1)."""
        conn = store.db()
        store.journal(conn, "T001", "fsm",
                      "переход отклонён: трассируемость AC", "AC-2: нет теста")

        rows = store.refusal_history(conn, "T001", "tests_writing", 5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["detail"], "AC-2: нет теста")

    def test_refusal_of_a_past_visit_is_excluded_by_the_state_marker(self):
        """Запись `state -> X` — граница: отказ ДО неё принадлежит
        прошлому визиту состояния и не должен попасть в выборку
        (SPEC T078, требование 4, AC-3)."""
        conn = store.db()
        store.journal(conn, "T001", "fsm",
                      "переход отклонён: трассируемость AC", "старый отказ")
        store.journal(conn, "T001", "fsm", "state -> in_dev", "успешный переход")

        rows = store.refusal_history(conn, "T001", "in_dev", 5)

        self.assertEqual(rows, [])

    def test_refusal_after_the_state_marker_is_included(self):
        conn = store.db()
        store.journal(conn, "T001", "fsm", "state -> in_dev", "успешный переход")
        store.journal(conn, "T001", "fsm", "переход отклонён", "свежий отказ")

        rows = store.refusal_history(conn, "T001", "in_dev", 5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["detail"], "свежий отказ")

    def test_non_refusal_actions_are_not_matched(self):
        conn = store.db()
        store.journal(conn, "T001", "fsm", "приёмочные тесты пройдены", "ok")

        rows = store.refusal_history(conn, "T001", "tests_writing", 5)

        self.assertEqual(rows, [])

    def test_limit_keeps_only_the_most_recent_entries_in_order(self):
        conn = store.db()
        for n in range(1, 4):
            store.journal(conn, "T001", "fsm", "переход отклонён", f"отказ {n}")

        rows = store.refusal_history(conn, "T001", "tests_writing", 2)

        self.assertEqual([r["detail"] for r in rows], ["отказ 2", "отказ 3"])

    def test_other_task_entries_never_appear(self):
        conn = store.db()
        store.journal(conn, "T002", "fsm", "переход отклонён",
                      "T002-only-маркер")

        rows = store.refusal_history(conn, "T001", "in_dev", 5)

        self.assertEqual(rows, [])


class BriefAdvanceRefusalHistoryTest(RefusalHistorySandbox):

    def test_no_history_returns_empty_string(self):
        text = brief.advance_refusal_history(
            store.db(), "T001", "test_author", "tests_writing")

        self.assertEqual(text, "")

    def test_history_is_framed_and_carries_the_full_detail_text(self):
        conn = store.db()
        store.journal(conn, "T001", "fsm",
                      "переход отклонён: трассируемость AC",
                      "AC-2: нет теста (orchestrator/fsm.py:770)")

        text = brief.advance_refusal_history(
            conn, "T001", "test_author", "tests_writing")

        self.assertIn("отклонена вот почему — почини это", text)
        self.assertIn("AC-2: нет теста (orchestrator/fsm.py:770)", text)

    def test_component_hash_is_journaled_under_the_given_role(self):
        conn = store.db()
        store.journal(conn, "T001", "fsm", "переход отклонён", "деталь отказа")

        with mock.patch.object(brief, "component_hash", return_value="deadbeef"):
            brief.advance_refusal_history(conn, "T001", "test_author",
                                          "tests_writing")

        details = [r["detail"] for r in conn.execute(
            "SELECT detail FROM steps WHERE actor=? AND action=?",
            ("test_author", "бриф: компонент")).fetchall()]
        self.assertEqual(len(details), 1)
        self.assertIn("история отказов advance", details[0])
        self.assertIn("deadbeef", details[0])


if __name__ == "__main__":
    unittest.main()
