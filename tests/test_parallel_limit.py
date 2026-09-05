"""Юнит-тесты orchestrator/parallel_limit.py (SPEC T060).

Приёмочные тесты (tasks/T060/acceptance_tests) кроют AC-1..AC-7 сквозным
путём через `run`/`auto`; здесь — сам модуль `parallel_limit.py` в
изоляции: подсчёт занятых задач и форма отказа, без прогона команд CLI.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, parallel_limit, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402

# Граница свежести heartbeat (01M1R5B570KMS26NQ6J2G2WXZB): запас ровно в
# 1 секунду до/после `LEASE_STALE_AFTER_SEC` делал тест зависимым от
# скорости прогона — просадка CI-раннера съедала секунду между посевом
# lease и вызовом проверяемой функции быстрее, чем тест успевал
# отработать (наблюдение 05.09, push-прогон ветки регрессии №10).
# Запас в половину порога на порядки больше любой реалистичной просадки
# и не завязан на конкретное числовое значение порога — переживёт его
# будущую правку Оператором без изменений здесь.
_MARGIN_SEC = config.LEASE_STALE_AFTER_SEC // 2


def _fresh_edge_ts() -> str:
    """Heartbeat моложе порога на `_MARGIN_SEC` — задача ещё занята."""
    return _ts_ago(config.LEASE_STALE_AFTER_SEC - _MARGIN_SEC)


def _stale_edge_ts() -> str:
    """Heartbeat старше порога на `_MARGIN_SEC` — задача уже не занята."""
    return _ts_ago(config.LEASE_STALE_AFTER_SEC + _MARGIN_SEC)


class ParallelLimitTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def seed_lease(self, task_id: str, session_id: str, pid: int,
                   hostname: str, heartbeat_ts: str) -> None:
        if task_id != self.TASK:
            store.insert_task(store.db(), task_id, f"Другая {task_id}",
                              "in_dev", f"task/{task_id.lower()}-fake",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    # ------------------------------------------------------- busy_other_tasks

    def test_no_leases_at_all_means_no_busy_tasks(self):
        self.assertEqual(parallel_limit.busy_other_tasks(store.db(), self.TASK), [])

    def test_own_lease_is_excluded_regardless_of_session(self):
        self.seed_lease(self.TASK, "any-session", os.getpid(),
                        socket.gethostname(), store.now())

        self.assertEqual(parallel_limit.busy_other_tasks(store.db(), self.TASK), [])

    def test_foreign_fresh_live_lease_counts(self):
        self.seed_lease("T901", "sess-1", os.getpid(), socket.gethostname(),
                        store.now())

        busy = parallel_limit.busy_other_tasks(store.db(), self.TASK)

        self.assertEqual([r["task_id"] for r in busy], ["T901"])

    def test_stale_heartbeat_is_excluded(self):
        stale = _stale_edge_ts()
        self.seed_lease("T901", "sess-1", os.getpid(), socket.gethostname(),
                        stale)

        self.assertEqual(parallel_limit.busy_other_tasks(store.db(), self.TASK), [])

    def test_heartbeat_just_under_the_threshold_still_counts(self):
        edge = _fresh_edge_ts()
        self.seed_lease("T901", "sess-1", os.getpid(), socket.gethostname(),
                        edge)

        busy = parallel_limit.busy_other_tasks(store.db(), self.TASK)

        self.assertEqual([r["task_id"] for r in busy], ["T901"])

    def test_dead_pid_is_excluded(self):
        self.seed_lease("T901", "sess-1", _dead_pid(), socket.gethostname(),
                        store.now())

        self.assertEqual(parallel_limit.busy_other_tasks(store.db(), self.TASK), [])

    def test_foreign_host_counts_even_with_locally_dead_pid(self):
        self.seed_lease("T901", "sess-1", _dead_pid(), "other-host",
                        store.now())

        busy = parallel_limit.busy_other_tasks(store.db(), self.TASK)

        self.assertEqual([r["task_id"] for r in busy], ["T901"])

    def test_foreign_host_with_stale_heartbeat_is_still_excluded(self):
        stale = _stale_edge_ts()
        self.seed_lease("T901", "sess-1", _dead_pid(), "other-host", stale)

        self.assertEqual(parallel_limit.busy_other_tasks(store.db(), self.TASK), [])

    def test_several_foreign_tasks_all_count(self):
        self.seed_lease("T901", "sess-1", os.getpid(), socket.gethostname(),
                        store.now())
        self.seed_lease("T902", "sess-2", os.getpid(), socket.gethostname(),
                        store.now())

        busy = parallel_limit.busy_other_tasks(store.db(), self.TASK)

        self.assertEqual({r["task_id"] for r in busy}, {"T901", "T902"})

    # -------------------------------------------------------------- refusal

    def test_refusal_is_none_below_the_ceiling(self):
        for i in range(config.MAX_PARALLEL_TASKS - 1):
            self.seed_lease(f"T90{i}", f"sess-{i}", os.getpid(),
                            socket.gethostname(), store.now())

        self.assertIsNone(parallel_limit.refusal(store.db(), self.TASK))

    def test_refusal_names_every_busy_task_session_and_ceiling(self):
        for i in range(config.MAX_PARALLEL_TASKS):
            self.seed_lease(f"T90{i}", f"sess-busy-{i}", os.getpid(),
                            socket.gethostname(), store.now())

        text = parallel_limit.refusal(store.db(), self.TASK)

        self.assertIsNotNone(text)
        for i in range(config.MAX_PARALLEL_TASKS):
            self.assertIn(f"T90{i}", text)
            self.assertIn(f"sess-busy-{i}", text)
        self.assertIn(str(config.MAX_PARALLEL_TASKS), text)

    def test_refusal_is_none_when_ceiling_only_reached_by_stale_or_dead(self):
        stale = _stale_edge_ts()
        self.seed_lease("T901", "sess-stale", os.getpid(),
                        socket.gethostname(), stale)
        self.seed_lease("T902", "sess-dead", _dead_pid(),
                        socket.gethostname(), store.now())

        self.assertIsNone(parallel_limit.refusal(store.db(), self.TASK))


if __name__ == "__main__":
    unittest.main()
