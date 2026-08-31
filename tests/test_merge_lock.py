"""Юнит-тесты orchestrator/merge_lock.py (SPEC T053).

Приёмочные тесты (tasks/T053/acceptance_tests) кроют AC-1..AC-6 сквозным
путём через `fsm.cmd_approve`/`cmd_reject`/`cleanup.cmd_kill`; здесь — сам
модуль `merge_lock.py` в изоляции: границы `acquire`/`release` (что именно
меняется в строке БД на каждой ветке), тем же приёмом, что
`tests/test_lease.py` уже применила к `lease.py`.
"""
import os
import socket
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, merge_lock, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402


class AcquireReleaseTest(TmpRootTest):
    TASK = "T001"
    HOLDER_TASK = "T999"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача",
                          "merge_gate", "task/t001-zadacha",
                          config.DEFAULT_TARGET, 25.0)
        store.insert_task(store.db(), self.HOLDER_TASK, "Держит окно",
                          "merge_gate", "task/t999-holder",
                          config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.merge_lock_row(store.db())

    def seed(self, session_id, pid, hostname, heartbeat_ts, task_id) -> None:
        store.set_merge_lock(store.db(), task_id, session_id, pid, hostname,
                             heartbeat_ts)

    def test_fresh_acquire_on_empty_table_takes_the_lock(self):
        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        row = self.row()
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["task_id"], self.TASK)
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(row["hostname"], socket.gethostname())

    def test_own_session_re_enters_without_refusal(self):
        merge_lock.acquire(store.db(), self.TASK, "sess-a")

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertEqual(self.row()["session_id"], "sess-a")

    def test_foreign_fresh_lock_refuses_and_names_holder_and_task(self):
        self.seed("sess-holder", 999, "holder-host", store.now(),
                  self.HOLDER_TASK)
        before = dict(self.row())

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNotNone(refusal)
        self.assertIn("sess-holder", refusal)
        self.assertIn(self.HOLDER_TASK, refusal)
        self.assertEqual(dict(self.row()), before,
                         "отказанное взятие не имеет права тронуть чужой "
                         "мьютекс")

    def test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled(self):
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        self.seed("sess-holder", 999, "holder-host", stale_ts,
                  self.HOLDER_TASK)
        before = len(store.task_steps(store.db(), self.TASK))

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNone(refusal)
        row = self.row()
        self.assertEqual(row["session_id"], "sess-caller")
        self.assertEqual(row["task_id"], self.TASK)
        new_steps = store.task_steps(store.db(), self.TASK)[before:]
        self.assertTrue(any("мьютекс" in s["action"] for s in new_steps),
                        new_steps)

    def test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat(self):
        self.seed("sess-holder", _dead_pid(), socket.gethostname(),
                  store.now(), self.HOLDER_TASK)

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNone(
            refusal, "мёртвый pid держателя обязан перешагиваться даже при "
                    "свежем heartbeat (требование 4)")
        self.assertEqual(self.row()["session_id"], "sess-caller")

    def test_foreign_dead_pid_on_a_different_host_is_not_taken_over(self):
        """Чужой host — pid чужой процессной таблицы нельзя ни
        подтвердить, ни опровергнуть; решает только heartbeat (тот же
        приём, что `doctor.check_leases`/`check_merge_lock`)."""
        self.seed("sess-holder", 999999, "other-host", store.now(),
                  self.HOLDER_TASK)

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNotNone(refusal)

    def test_release_removes_only_the_matching_session(self):
        merge_lock.acquire(store.db(), self.TASK, "sess-a")

        merge_lock.release(store.db(), "sess-b")
        self.assertIsNotNone(self.row(), "release чужой сессией снял мьютекс")

        merge_lock.release(store.db(), "sess-a")
        self.assertIsNone(self.row())


class RunWindowTest(TmpRootTest):
    """SPEC T057, требование 2 rev. AC-3: общая точка окна merge-мьютекса —
    `acquire` -> отказ (`sys.exit`) -> `body()` -> `release` безусловно."""

    TASK = "T001"
    HOLDER_TASK = "T999"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        store.insert_task(store.db(), self.HOLDER_TASK, "Держит окно",
                          "merge_gate", "task/t999-holder",
                          config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.merge_lock_row(store.db())

    def test_success_runs_body_and_releases_the_mutex_afterwards(self):
        conn = store.db()
        seen = []

        result = merge_lock.run_window(conn, self.TASK, "sess-a",
                                       lambda: seen.append("done") or "ok")

        self.assertEqual(result, "ok")
        self.assertEqual(seen, ["done"])
        self.assertIsNone(self.row(), "мьютекс обязан быть отпущен после "
                                      "тела окна")

    def test_refusal_exits_without_running_the_body(self):
        conn = store.db()
        store.set_merge_lock(conn, self.HOLDER_TASK, "sess-holder", 999,
                             "holder-host", store.now())
        called = []

        with self.assertRaises(SystemExit) as ctx:
            merge_lock.run_window(conn, self.TASK, "sess-caller",
                                  lambda: called.append("ran"))

        self.assertIn("sess-holder", str(ctx.exception))
        self.assertEqual(called, [])
        self.assertEqual(self.row()["session_id"], "sess-holder",
                         "отказанное взятие не имеет права тронуть чужой "
                         "мьютекс")

    def test_mutex_is_released_even_when_the_body_raises(self):
        conn = store.db()

        with self.assertRaises(ValueError):
            merge_lock.run_window(
                conn, self.TASK, "sess-a",
                lambda: (_ for _ in ()).throw(ValueError))

        self.assertIsNone(self.row(), "тело упало — мьютекс всё равно "
                                      "обязан быть отпущен")


class ConcurrentAcquireTest(TmpRootTest):
    """Read-then-write в `acquire()` (`merge_lock_row` -> `set_merge_lock`)
    обязан быть атомарным под конкурентным доступом (SPEC T053, требование
    1 — `BEGIN IMMEDIATE` по образцу `lease.acquire`, ревью T044 итерация
    1 замечание 1). Каждый поток открывает своё собственное подключение
    (`store.db()`), как и делают отдельные процессы CLI, — общий только
    файл БД."""

    TASK = "T001"
    THREADS = 8

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        # Догоняет migrate()/seed_task_counters ПОСЛЕ вставки T001, пока
        # тест ещё однопоточный — тот же приём, что
        # `tests/test_lease.py::ConcurrentAcquireTest.setUp`.
        store.db()

    def test_concurrent_acquire_on_free_lock_exactly_one_wins(self):
        barrier = threading.Barrier(self.THREADS)
        results = [None] * self.THREADS
        errors = []

        def worker(i):
            try:
                conn = store.db()
                barrier.wait(timeout=5)
                results[i] = merge_lock.acquire(conn, self.TASK, f"sess-{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,))
                  for i in range(self.THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [], "acquire() не должна падать под гонкой")
        wins = [r for r in results if r is None]
        self.assertEqual(len(wins), 1, results)
        row = store.merge_lock_row(store.db())
        self.assertTrue(row["session_id"].startswith("sess-"))


if __name__ == "__main__":
    unittest.main()
