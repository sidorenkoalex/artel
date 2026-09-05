"""Юнит-тесты `orchestrator.store.update_lease_pgid` (SPEC
01M1PNBSHR2PMFECMP7C204MF1, AC-2): pgid агентного шага пишется рядом с
существующим `pid` держателя lease, не трогая его.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"


class UpdateLeasePgidTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Задача", "in_dev",
                          "task/t001-x", config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.lease_row(store.db(), TASK)

    def test_records_pgid_on_an_existing_lease(self):
        """Ловит мутацию: `update_lease_pgid` не выполняет UPDATE вовсе
        (пустое тело/опечатка в имени колонки) — значение останется
        `None`."""
        store.insert_lease(self.conn, TASK, "sess-a", 4242,
                           "host.invalid", store.now())

        store.update_lease_pgid(self.conn, TASK, 5000)

        self.assertEqual(self.row()["pgid"], 5000)

    def test_does_not_touch_the_existing_pid(self):
        """Ловит мутацию: `update_lease_pgid` по ошибке (копипаста
        `update_lease`) перезаписывает `pid` вместо `pgid` — держатель
        lease потерял бы адрес, по которому его находят kill/pause_now/
        release (AC-2, `_sandbox.AgentStepSandbox.
        assert_lease_pid_unchanged`)."""
        store.insert_lease(self.conn, TASK, "sess-a", 4242,
                           "host.invalid", store.now())

        store.update_lease_pgid(self.conn, TASK, 5000)

        row = self.row()
        self.assertEqual(row["pid"], 4242)
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["hostname"], "host.invalid")

    def test_missing_lease_row_is_a_silent_no_op(self):
        """Ловит мутацию: функция падает (или заводит строку) на
        отсутствующей лизе — шаг, запущенный в обход `lease.acquire`
        (юнит-тесты `run_agent_once`), не имеет lease вовсе, и запись
        pgid обязана тихо ничего не менять."""
        self.assertIsNone(self.row())

        store.update_lease_pgid(self.conn, TASK, 5000)

        self.assertIsNone(self.row())

    def test_does_not_touch_pgid_of_another_task(self):
        store.insert_task(self.conn, "T002", "Другая", "in_dev",
                          "task/t002-x", config.DEFAULT_TARGET, 25.0)
        store.insert_lease(self.conn, TASK, "sess-a", 1, "h", store.now())
        store.insert_lease(self.conn, "T002", "sess-b", 2, "h", store.now())

        store.update_lease_pgid(self.conn, TASK, 5000)

        self.assertIsNone(store.lease_row(store.db(), "T002")["pgid"])


if __name__ == "__main__":
    unittest.main()
