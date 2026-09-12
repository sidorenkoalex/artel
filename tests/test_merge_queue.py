"""Юнит-тесты orchestrator/merge_queue.py (SPEC 01M291EPQ2VFGCHZTXXC81616V).

Приёмочные тесты (tasks/01M291EPQ2VFGCHZTXXC81616V/acceptance_tests) кроют
AC-1..AC-9 сквозным путём через `fsm_merge_gate._cmd_approve_merge_gate_
cycle`; здесь — сам модуль `merge_queue.py` в изоляции: границы отдельных
функций (пруна мёртвых записей, определение головы очереди, минуты
ожидания, добавка `status`, `wait_for_window` без полного цикла гейта),
тем же приёмом, что `tests/test_merge_lock.py` уже применила к
`merge_lock.py`.
"""
import socket
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, merge_lock, merge_queue, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402


class _QueueTestBase(TmpRootTest):
    TASK_A = "T001"
    TASK_B = "T002"
    TASK_C = "T003"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        for tid, branch in ((self.TASK_A, "task/t001-a"),
                            (self.TASK_B, "task/t002-b"),
                            (self.TASK_C, "task/t003-c")):
            store.insert_task(store.db(), tid, tid, "merge_gate", branch,
                              config.DEFAULT_TARGET, 25.0)

    def enqueue(self, task_id, session_id, pid, hostname, ts):
        store.enqueue_merge_wait(store.db(), task_id, session_id, pid,
                                 hostname, ts)


class PruneDeadEntriesTest(_QueueTestBase):

    def test_dead_pid_on_own_host_is_pruned(self):
        self.enqueue(self.TASK_A, "sess-a", _dead_pid(),
                    socket.gethostname(), store.now())

        merge_queue._prune_dead_entries(store.db())

        self.assertEqual(store.merge_queue_rows(store.db()), [])

    def test_stale_heartbeat_on_foreign_host_is_pruned(self):
        stale = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        self.enqueue(self.TASK_A, "sess-a", 999, "other-host", stale)

        merge_queue._prune_dead_entries(store.db())

        self.assertEqual(store.merge_queue_rows(store.db()), [])

    def test_live_entry_survives_pruning(self):
        self.enqueue(self.TASK_A, "sess-a", 999, "other-host", store.now())

        merge_queue._prune_dead_entries(store.db())

        rows = store.merge_queue_rows(store.db())
        self.assertEqual([r["task_id"] for r in rows], [self.TASK_A])

    def test_dead_entry_does_not_take_the_place_of_a_live_one_behind_it(self):
        self.enqueue(self.TASK_A, "sess-dead", _dead_pid(),
                    socket.gethostname(), _ts_ago(1))
        self.enqueue(self.TASK_B, "sess-b", 999, "other-host", store.now())

        merge_queue._prune_dead_entries(store.db())

        self.assertEqual(merge_queue._head_task_id(store.db()), self.TASK_B)


class HeadTaskIdTest(_QueueTestBase):

    def test_empty_queue_has_no_head(self):
        self.assertIsNone(merge_queue._head_task_id(store.db()))

    def test_head_is_earliest_by_enqueued_ts(self):
        self.enqueue(self.TASK_B, "sess-b", 999, "other-host", _ts_ago(5))
        self.enqueue(self.TASK_A, "sess-a", 999, "other-host", _ts_ago(10))

        self.assertEqual(merge_queue._head_task_id(store.db()), self.TASK_A)


class CurrentHolderIdTest(_QueueTestBase):

    def test_no_holder_degrades_to_placeholder(self):
        self.assertEqual(merge_queue._current_holder_id(store.db()), "?")

    def test_names_the_holder_task(self):
        store.set_merge_lock(store.db(), self.TASK_A, "sess-a", 999,
                             "holder-host", store.now())

        self.assertEqual(merge_queue._current_holder_id(store.db()),
                         self.TASK_A)


class QueueWaitMinutesAndStatusSuffixTest(_QueueTestBase):

    def test_not_queued_returns_none_and_empty_suffix(self):
        t = store.get_task(store.db(), self.TASK_B)

        self.assertIsNone(merge_queue.queue_wait_minutes(store.db(), self.TASK_B))
        self.assertEqual(merge_queue.wait_suffix(store.db(), t), "")

    def test_queued_reports_minutes_waited_and_the_current_holder(self):
        store.set_merge_lock(store.db(), self.TASK_A, "sess-a", 999,
                             "holder-host", store.now())
        self.enqueue(self.TASK_B, "sess-b", 999, "other-host", _ts_ago(180))
        t = store.get_task(store.db(), self.TASK_B)

        minutes = merge_queue.queue_wait_minutes(store.db(), self.TASK_B)
        suffix = merge_queue.wait_suffix(store.db(), t)

        self.assertEqual(minutes, 3)
        self.assertEqual(
            suffix, f"  [ждёт merge-окна: занято {self.TASK_A}, 3 мин]")


class WaitForWindowTest(_QueueTestBase):

    def test_free_mutex_registers_then_immediately_takes_the_window(self):
        conn = store.db()

        merge_queue.wait_for_window(conn, self.TASK_A, "sess-a")

        row = store.merge_lock_row(conn)
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(store.merge_queue_rows(conn), [],
                         "успешное взятие окна обязано снять регистрацию "
                         "в очереди")
        steps = store.task_steps(conn, self.TASK_A)
        self.assertTrue(
            any(s["action"] == "ждёт merge-окна: держит ?" for s in steps),
            [s["action"] for s in steps])

    def test_ceiling_expiry_dequeues_and_exits_without_touching_state(self):
        conn = store.db()
        store.set_merge_lock(conn, self.TASK_B, "sess-holder", 999,
                             "holder-host", store.now())
        clock = {"value": 0.0}

        def fake_monotonic():
            return clock["value"]

        def fake_sleep(seconds):
            clock["value"] += seconds

        with mock.patch.object(time, "monotonic", fake_monotonic), \
             mock.patch.object(time, "sleep", fake_sleep):
            with self.assertRaises(SystemExit) as ctx:
                merge_queue.wait_for_window(conn, self.TASK_A, "sess-a")

        self.assertIn(self.TASK_A, str(ctx.exception))
        self.assertGreaterEqual(clock["value"], config.MERGE_QUEUE_WAIT_CEILING_SEC)
        self.assertEqual(store.get_task(conn, self.TASK_A)["state"],
                         "merge_gate")
        self.assertEqual(store.merge_queue_rows(conn), [],
                         "истёкший потолок обязан снять регистрацию в "
                         "очереди — иначе она блокирует голову навсегда")


if __name__ == "__main__":
    unittest.main()
