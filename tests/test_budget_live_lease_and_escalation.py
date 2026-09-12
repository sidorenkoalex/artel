"""Юнит-тесты `orchestrator/budget.py`/`orchestrator/lease.py` (SPEC
01M1VBEDGMEXHVGWAH42FTDZ4X, требования 1 и 3): `budget` под живым lease
своего хоста и sha кода, зафиксированный `enforce_budget` при эскалации
из `review`.

Приёмочные тесты (`tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/`)
кроют AC-1..AC-4, AC-10, AC-11 (требование 1) и AC-8/AC-9/AC-14/AC-15
(требование 3) сквозным путём через `budget.cmd_budget`/`auto.cmd_auto`/
`fsm.cmd_advance`; здесь — сами примитивы в изоляции: границы
`lease.acquire`/`lease.is_live` и момент, в который `enforce_budget`
журналирует sha.
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import budget, config, gitcmd, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, _ts_ago  # noqa: E402


def _insert_lease(conn, task_id: str, session_id: str, hostname: str,
                  age_sec: float = 0.0) -> None:
    conn.execute(
        "INSERT INTO leases (task_id, session_id, pid, hostname,"
        " heartbeat_ts) VALUES (?,?,?,?,?)",
        (task_id, session_id, os.getpid(), hostname, _ts_ago(age_sec)))
    conn.commit()


class AcquireSameHostOkTest(TmpRootTest):
    """Требование 1: `lease.acquire(..., same_host_ok=True)`."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.lease_row(store.db(), self.TASK)

    def test_default_still_refuses_a_foreign_live_lease_same_host(self):
        """Дефолт (`same_host_ok=False`) не меняет поведение ни одного из
        7 прежних вызывателей `run_locked` — тот же отказ, что и раньше."""
        conn = store.db()
        _insert_lease(conn, self.TASK, "sess-holder", socket.gethostname())

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-caller")

        self.assertIsNotNone(refusal)
        self.assertFalse(fresh)

    def test_same_host_ok_passes_a_foreign_live_lease_same_host(self):
        """AC-1: живой lease чужой сессии ТОГО ЖЕ hostname — не отказ."""
        conn = store.db()
        _insert_lease(conn, self.TASK, "sess-holder", socket.gethostname())
        before = dict(self.row())

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-caller",
                                       same_host_ok=True)

        self.assertIsNone(refusal)
        self.assertFalse(fresh, "разрешение параллельной работы — не захват")
        self.assertEqual(dict(self.row()), before,
                         "чужая строка lease не должна мутироваться")

    def test_same_host_ok_still_refuses_a_different_hostname(self):
        """AC-4: другой hostname отказывает независимо от `same_host_ok`."""
        conn = store.db()
        _insert_lease(conn, self.TASK, "sess-holder", "other-host.invalid")

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-caller",
                                       same_host_ok=True)

        self.assertIsNotNone(refusal)
        self.assertIn("sess-holder", refusal)
        self.assertIn("other-host.invalid", refusal)
        self.assertFalse(fresh)

    def test_same_host_ok_does_not_change_the_stale_takeover(self):
        """Протухший чужой lease по-прежнему перехватывается (не «прошёл
        мимо» веткой same_host_ok — она применяется только к ЖИВЫМ)."""
        conn = store.db()
        _insert_lease(conn, self.TASK, "sess-holder", socket.gethostname(),
                      age_sec=config.LEASE_STALE_AFTER_SEC + 1)

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-caller",
                                       same_host_ok=True)

        self.assertIsNone(refusal)
        self.assertFalse(fresh, "перехват существующей строки — не «с нуля»")
        self.assertEqual(self.row()["session_id"], "sess-caller")


class IsLiveTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_no_lease_row_is_not_live(self):
        self.assertFalse(lease.is_live(store.db(), self.TASK))

    def test_fresh_heartbeat_is_live(self):
        conn = store.db()
        _insert_lease(conn, self.TASK, "sess-a", socket.gethostname())
        self.assertTrue(lease.is_live(conn, self.TASK))

    def test_stale_heartbeat_is_not_live(self):
        conn = store.db()
        _insert_lease(conn, self.TASK, "sess-a", socket.gethostname(),
                      age_sec=config.LEASE_STALE_AFTER_SEC + 1)
        self.assertFalse(lease.is_live(conn, self.TASK))

    def test_does_not_mutate_the_row(self):
        conn = store.db()
        _insert_lease(conn, self.TASK, "sess-a", socket.gethostname())
        before = dict(store.lease_row(conn, self.TASK))

        lease.is_live(conn, self.TASK)

        self.assertEqual(dict(store.lease_row(conn, self.TASK)), before)


class CmdBudgetMidStepMarkerTest(TmpRootTest):
    """Требование 1 (AC-2/AC-10): пометка «во время шага <роль>»."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.TASK = "T001"
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 10.0)

    def journal(self):
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT * FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]

    def test_no_live_lease_leaves_detail_unchanged(self):
        """AC-16: без активного lease detail остаётся байт-в-байт прежним
        (существующие точные сравнения `tests/test_step_cost.py` не
        задеты)."""
        budget.cmd_budget(self.TASK, "40")

        details = [d for _, a, d in self.journal() if a == "бюджет изменён"]
        self.assertEqual(details, ["$10.00 -> $40.00, израсходовано $0.00"])

    def test_live_lease_of_the_same_session_adds_the_marker(self):
        conn = store.db()
        _insert_lease(conn, self.TASK, "own-sess", socket.gethostname())

        budget.cmd_budget(self.TASK, "40", "own-sess")

        details = [d for _, a, d in self.journal() if a == "бюджет изменён"]
        self.assertEqual(len(details), 1)
        self.assertIn("во время шага", details[0])
        self.assertIn("developer", details[0])

    def test_live_foreign_lease_same_host_adds_the_marker_and_succeeds(self):
        conn = store.db()
        _insert_lease(conn, self.TASK, "other-sess", socket.gethostname())

        budget.cmd_budget(self.TASK, "40")

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], 40.0)
        details = [d for _, a, d in self.journal() if a == "бюджет изменён"]
        self.assertEqual(len(details), 1)
        self.assertIn("во время шага", details[0])

    def test_foreign_host_still_refuses_and_journals_nothing(self):
        conn = store.db()
        _insert_lease(conn, self.TASK, "other-sess", "other-host.invalid")

        with self.assertRaises(SystemExit):
            budget.cmd_budget(self.TASK, "40")

        self.assertEqual([d for _, a, d in self.journal()
                          if a == "бюджет изменён"], [])
        self.assertAlmostEqual(
            store.get_task(store.db(), self.TASK)["budget_usd"], 10.0)


class EnforceBudgetReviewEscalationShaTest(TmpRootTest):
    """Требование 3: `enforce_budget` журналирует sha кода при эскалации
    ИЗ `review`, и только тогда."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.TASK = "T001"
        store.insert_task(store.db(), self.TASK, "Задача", "review",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 5.0)
        store.update_task(store.db(), self.TASK, spent_usd=6.0)

    def journal(self):
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT * FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]

    def test_escalation_from_review_journals_the_code_sha(self):
        with mock.patch.object(gitcmd, "branch_head_sha",
                               lambda b: "a" * 40):
            escalated = budget.enforce_budget(store.db(), self.TASK, "review")

        self.assertTrue(escalated)
        details = [d for _, a, d in self.journal()
                  if a == budget.REVIEW_ESCALATION_CODE_SHA_ACTION]
        self.assertEqual(details, ["a" * 40])

    def test_escalation_from_in_dev_does_not_journal_a_code_sha(self):
        store.update_task(store.db(), self.TASK, state="in_dev")
        with mock.patch.object(gitcmd, "branch_head_sha",
                               lambda b: "a" * 40):
            budget.enforce_budget(store.db(), self.TASK, "in_dev")

        details = [d for _, a, d in self.journal()
                  if a == budget.REVIEW_ESCALATION_CODE_SHA_ACTION]
        self.assertEqual(details, [])

    def test_git_not_answering_does_not_journal_an_empty_sha(self):
        with mock.patch.object(gitcmd, "branch_head_sha", lambda b: ""):
            budget.enforce_budget(store.db(), self.TASK, "review")

        details = [d for _, a, d in self.journal()
                  if a == budget.REVIEW_ESCALATION_CODE_SHA_ACTION]
        self.assertEqual(details, [])


if __name__ == "__main__":
    unittest.main()
