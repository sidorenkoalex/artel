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
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, _ts_ago, capture  # noqa: E402


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


class RunLockedTest(TmpRootTest):
    """SPEC T057, требование 2: общая точка обвязки — `resolve_session_id`
    -> `acquire` -> отказ -> `body(sid)` -> `release`-если-`fresh`."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.lease_row(store.db(), self.TASK)

    def test_fresh_acquire_runs_body_and_releases_afterwards(self):
        conn = store.db()
        seen = []

        result = lease.run_locked(conn, self.TASK, "sess-a",
                                  lambda sid: seen.append(sid) or "ok")

        self.assertEqual(result, "ok")
        self.assertEqual(seen, ["sess-a"])
        self.assertIsNone(self.row(), "lease, взятый с нуля, обязан быть "
                                      "отпущен после тела")

    def test_renewed_own_lease_runs_body_and_is_not_released(self):
        conn = store.db()
        lease.acquire(conn, self.TASK, "sess-a")

        lease.run_locked(conn, self.TASK, "sess-a", lambda sid: None)

        self.assertIsNotNone(self.row(), "lease, продлённый (не с нуля), "
                                        "не имеет права быть отпущенным")

    def test_refusal_defaults_to_sys_exit_and_does_not_run_body(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", store.now()))
        conn.commit()
        called = []

        with self.assertRaises(SystemExit) as ctx:
            lease.run_locked(conn, self.TASK, "sess-caller",
                             lambda sid: called.append(sid))

        self.assertIn("sess-holder", str(ctx.exception))
        self.assertEqual(called, [])

    def test_refusal_with_print_channel_prints_and_returns_none_without_body(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", store.now()))
        conn.commit()
        called = []
        result = {}

        def call():
            result["value"] = lease.run_locked(
                conn, self.TASK, "sess-caller", lambda sid: called.append(sid),
                on_refusal="print")

        out = capture(call)

        self.assertIsNone(result["value"])
        self.assertEqual(called, [])
        self.assertIn("sess-holder", out)

    def test_body_result_is_released_even_when_body_raises(self):
        conn = store.db()

        with self.assertRaises(ValueError):
            lease.run_locked(conn, self.TASK, "sess-a",
                             lambda sid: (_ for _ in ()).throw(ValueError))

        self.assertIsNone(self.row(), "тело упало — lease, взятый с нуля, "
                                      "всё равно обязан быть отпущен")


class ConcurrentAcquireTest(TmpRootTest):
    """Ревью T044 (итерация 1), Замечание 1: read-then-write в `acquire()`
    (`lease_row` -> `insert_lease`/`update_lease`) должен быть атомарным
    под конкурентным доступом двух и более сессий к одной задаче — не
    только в однопоточных прогонах остальных тестов этого файла. Каждый
    поток открывает своё собственное подключение (`store.db()`), как и
    делают отдельные процессы CLI, — общий только файл БД."""

    TASK = "T001"
    THREADS = 8

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        # Догоняет migrate()/seed_task_counters ПОСЛЕ вставки T001, пока
        # тест ещё однопоточный: без этого первый же `store.db()` каждого
        # потока ниже гонится за посевом task_counters.artel — отдельный,
        # не связанный с T044 дефект (check-then-insert без транзакции в
        # `store.seed_task_counters`), который иначе маскирует проверяемую
        # здесь гонку `lease.acquire()`.
        store.db()

    def _run_concurrently(self, session_ids):
        """Каждая сессия — своё подключение, как у реального CLI-процесса.
        sqlite3 запрещает использовать Connection не из того потока, где
        она создана, поэтому каждый поток открывает её сам — но ДО
        барьера, который синхронизирует только сам вызов `acquire()`.
        Иначе тест ловит не гонку `acquire()`, а несвязанную с T044 гонку
        на посев `task_counters` внутри `store.migrate()`, который зовёт
        каждый `store.db()` (эта гонка уже закрыта разово в `setUp()`,
        до которого сюда никакой поток не доходит)."""
        barrier = threading.Barrier(len(session_ids))
        results = [None] * len(session_ids)
        errors = []

        def worker(i, sid):
            try:
                conn = store.db()
                barrier.wait(timeout=5)
                results[i] = lease.acquire(conn, self.TASK, sid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i, sid))
                  for i, sid in enumerate(session_ids)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        return results, errors

    def test_concurrent_acquire_on_free_lease_exactly_one_wins(self):
        """Случай 1 из Замечания 1: гонка на INSERT при свободном lease —
        раньше вторая сессия получала необработанный
        `sqlite3.IntegrityError` вместо именованного отказа."""
        session_ids = [f"sess-{i}" for i in range(self.THREADS)]

        results, errors = self._run_concurrently(session_ids)

        self.assertEqual(errors, [], "acquire() не должна падать под гонкой")
        fresh_wins = [r for r in results if r[1]]
        refusals = [r for r in results if r[0] is not None]
        self.assertEqual(len(fresh_wins), 1, results)
        self.assertEqual(len(refusals), self.THREADS - 1, results)

    def test_concurrent_acquire_on_stale_lease_exactly_one_intercepts(self):
        """Случай 2 из Замечания 1: гонка на UPDATE протухшего чужого
        lease — раньше обе сессии молча считали лизинг своим и обе шли
        выполнять тело мутирующей команды параллельно."""
        conn = store.db()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", stale_ts))
        conn.commit()
        journalled_before = len(store.task_steps(store.db(), self.TASK))
        session_ids = [f"sess-{i}" for i in range(self.THREADS)]

        results, errors = self._run_concurrently(session_ids)

        self.assertEqual(errors, [], "acquire() не должна падать под гонкой")
        wins = [r for r in results if r[0] is None]
        self.assertEqual(len(wins), 1, results)
        row = store.lease_row(store.db(), self.TASK)
        self.assertIn(row["session_id"], session_ids)
        new_steps = store.task_steps(store.db(), self.TASK)[journalled_before:]
        intercept_steps = [s for s in new_steps if "lease" in s["action"]]
        self.assertEqual(len(intercept_steps), 1, new_steps)


if __name__ == "__main__":
    unittest.main()
