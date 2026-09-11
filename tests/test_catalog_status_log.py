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

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
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


class CmdStatusZoneWaitMinutesTest(TmpRootTest):
    """SPEC 01M1VBEAWZW4EBZHKMGNBBK648, требование 4, AC-6: `status`
    добавляет минуты ожидания зоны, только пока задача реально в цикле
    `auto --wait-zone` (запись входа в ожидание уже журналирована)."""

    OTHER = "T901"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        store.update_task(store.db(), TASK, zones="a/b")
        store.insert_task(store.db(), self.OTHER, "Другая", "in_dev",
                          "task/t901-fake", config.DEFAULT_TARGET, 25.0)
        store.update_task(store.db(), self.OTHER, zones="a/b")
        store.journal(store.db(), self.OTHER, "developer",
                     "agent run started", "")

    def test_status_shows_minutes_waited_once_the_wait_cycle_entered(self):
        entry = zone_lock.wait_enter_action("a/b", self.OTHER, "in_dev")
        store.journal(store.db(), TASK, "operator", entry, "")

        out = capture(catalog.cmd_status)

        self.assertIn("ждёт", out)
        self.assertIn("мин", out)

    def test_status_does_not_show_minutes_without_the_wait_cycle_entry(self):
        """Ловит мутацию: минуты появляются в строке `status` даже без
        записи входа в ожидание — задача заблокирована зоной (`run`/`auto`
        без `--wait-zone` останавливаются немедленно), но НЕ в цикле
        ожидания, показывать «ждёт N мин» тут нечего."""
        out = capture(catalog.cmd_status)

        self.assertNotIn("мин", out)


if __name__ == "__main__":
    unittest.main()
