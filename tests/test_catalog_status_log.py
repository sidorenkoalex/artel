"""Юнит-тесты `orchestrator.catalog.cmd_log`/`cmd_status` (SPEC
01M1GCHKG8DDK4DCZWCE3DYKWC, требования 2, 6, AC-3/AC-11): видимость
identity сессии в журнале и держателя lease в статусе задачи.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

TASK = "T001"


class CmdLogSessionIdTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_log_shows_the_session_id_on_one_readable_line(self):
        store.journal(store.db(), TASK, "operator", "событие", "деталь",
                      session_id="sess-log-unit")

        out = capture(catalog.cmd_log, TASK)

        lines = [ln for ln in out.splitlines() if "sess-log-unit" in ln]
        self.assertTrue(lines, out)
        for ln in lines:
            self.assertNotIn("{'", ln)
            self.assertNotIn("Row(", ln)

    def test_log_degrades_silently_for_legacy_rows_without_session_id(self):
        """Записи, заведённые до миграции колонки, — `session_id` NULL:
        строка `log` не падает и не печатает «None»."""
        conn = store.db()
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail,"
            " session_id) VALUES (?,?,?,?,?,?,?)",
            (TASK, config.DEFAULT_TARGET, store.now(), "operator",
             "легаси-событие", "", None))
        conn.commit()

        out = capture(catalog.cmd_log, TASK)

        self.assertIn("легаси-событие", out)
        self.assertNotIn("None", out)


class CmdStatusLeaseHolderTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_no_lease_adds_no_holder_suffix(self):
        out = capture(catalog.cmd_status)

        self.assertNotIn("lease", out)

    def test_shows_holder_and_liveness_on_this_host(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (TASK, "sess-status-unit", os.getpid(), socket.gethostname(),
             store.now()))
        conn.commit()

        out = capture(catalog.cmd_status)

        self.assertIn("sess-status-unit", out)
        self.assertIn("жив", out)


if __name__ == "__main__":
    unittest.main()
