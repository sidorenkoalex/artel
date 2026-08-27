"""Юнит-тесты orchestrator/lease.py (SPEC T044).

Приёмочные тесты (tasks/T044/acceptance_tests) кроют AC-1..AC-7 сквозным
путём через семь мутирующих команд; здесь — сам модуль `lease.py` в
изоляции: `resolve_session_id` и границы `acquire`/`release`, которые
критериям не нужны напрямую (форма отказа, что именно меняется в строке
БД на каждой ветке).
"""
import os
import socket
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


def _ts_ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime(
        "%Y-%m-%d %H:%M:%SZ")


class ResolveSessionIdTest(unittest.TestCase):
    """Требование 9: identity вызова — явный параметр, иначе окружение/ppid."""

    def test_explicit_argument_wins(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-sess"}):
            self.assertEqual(lease.resolve_session_id("explicit"), "explicit")

    def test_env_var_wins_over_ppid_fallback(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "env-sess"}):
            self.assertEqual(lease.resolve_session_id(None), "env-sess")

    def test_falls_back_to_parent_pid(self):
        env = dict(os.environ)
        env.pop("ARTEL_SESSION_ID", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(lease.resolve_session_id(None),
                             f"ppid-{os.getppid()}")

    def test_same_process_resolves_the_same_id_twice(self):
        """Требование 9: последовательные вызовы без явного параметра —
        одна и та же identity (без него замок блокировал бы сессию саму
        на себя)."""
        env = dict(os.environ)
        env.pop("ARTEL_SESSION_ID", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(lease.resolve_session_id(None),
                             lease.resolve_session_id(None))


class AcquireReleaseTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.lease_row(store.db(), self.TASK)

    def test_fresh_acquire_inserts_the_row_and_reports_fresh(self):
        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertTrue(fresh)
        row = self.row()
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(row["hostname"], socket.gethostname())

    def test_own_session_renews_and_is_not_fresh(self):
        lease.acquire(store.db(), self.TASK, "sess-a")

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertFalse(fresh, "продление предсуществующего lease — не "
                                "«с нуля» (см. release)")

    def test_foreign_fresh_lease_refuses_without_mutating_the_row(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", store.now()))
        conn.commit()
        before = dict(self.row())

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNotNone(refusal)
        self.assertIn("sess-holder", refusal)
        self.assertIn("holder-host", refusal)
        self.assertFalse(fresh)
        self.assertEqual(dict(self.row()), before)

    def test_foreign_stale_lease_is_taken_over_and_journalled(self):
        conn = store.db()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", stale_ts))
        conn.commit()
        journalled_before = len(store.task_steps(store.db(), self.TASK))

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNone(refusal)
        self.assertFalse(fresh, "перехват существующей строки — не «с нуля»")
        row = self.row()
        self.assertEqual(row["session_id"], "sess-caller")
        self.assertEqual(row["pid"], os.getpid())
        new_steps = store.task_steps(store.db(), self.TASK)[journalled_before:]
        self.assertTrue(any("lease" in s["action"] for s in new_steps))

    def test_release_removes_only_the_matching_session(self):
        lease.acquire(store.db(), self.TASK, "sess-a")

        lease.release(store.db(), self.TASK, "sess-b")
        self.assertIsNotNone(self.row(), "release чужой сессией снял lease")

        lease.release(store.db(), self.TASK, "sess-a")
        self.assertIsNone(self.row())


if __name__ == "__main__":
    unittest.main()
