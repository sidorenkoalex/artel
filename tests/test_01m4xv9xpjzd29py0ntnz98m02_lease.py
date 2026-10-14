"""Матрица владения lease в изолированной SQLite.

Группа: долгоживущий
Красен до реализации: своя remote сессия с совпавшим PID ошибочно продлевает строку в AC-1, AC-2, AC-6, rollback AC-7 и run_locked/budget.

Вся строка сравнивается вместе с ненулевым pgid; часы и таблица процессов
синтетические. События проверяются только для текущего сценария lease.
"""
import itertools
import os
import random
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import budget, config, lease, liveness, store


class LeaseIdentityTest(unittest.TestCase):
    def setUp(self):
        seed = os.environ.get("LEASE_TEST_SEED")
        self.seed = int(seed) if seed is not None else random.SystemRandom().randrange(2**32)
        print(f"зерно: {self.seed}")
        rng = random.Random(self.seed)
        self.pid, self.other_pid, self.pgid = rng.sample(range(10000, 900000), 3)
        self.sid = f"caller-{rng.getrandbits(32):x}"
        self.other_sid = f"holder-{rng.getrandbits(32):x}"
        self.host = f"local-{rng.getrandbits(32):x}"
        self.remote = f"remote-{rng.getrandbits(32):x}"
        self.task = "01J00000000000000000000000"
        self.now = datetime(2035, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        self.stamp = self.now.strftime("%Y-%m-%d %H:%M:%SZ")
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        store.create_schema(self.conn)
        store.insert_task(self.conn, self.task, "Фикстура lease", "in_dev",
                          "task/lease-fixture", config.DEFAULT_TARGET, 10.0)
        for patcher in (
            mock.patch("os.getpid", return_value=self.pid),
            mock.patch("socket.gethostname", return_value=self.host),
            mock.patch.object(store, "now", return_value=self.stamp),
            mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": self.sid}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        clock = mock.patch.object(liveness, "datetime", wraps=datetime)
        clock.start().now.return_value = self.now
        self.addCleanup(clock.stop)

    @contextmanager
    def scenario(self, *, own=True, local=False, same_pid=True, age=1,
                 alive=True, conn=None):
        conn = conn if conn is not None else self.conn
        conn.execute("DELETE FROM leases WHERE task_id=?", (self.task,))
        conn.execute("DELETE FROM steps WHERE task_id=?", (self.task,))
        conn.commit()
        holder_pid = self.pid if same_pid else self.other_pid
        store.insert_lease(
            conn, self.task, self.sid if own else self.other_sid, holder_pid,
            self.host if local else self.remote,
            (self.now - timedelta(seconds=age)).strftime("%Y-%m-%d %H:%M:%SZ"))
        store.update_lease_pgid(conn, self.task, self.pgid)
        before = dict(store.lease_row(conn, self.task))

        def kill(pid, signal):
            self.assertEqual(signal, 0, f"зерно: {self.seed}")
            if not alive and pid == holder_pid:
                raise ProcessLookupError(pid)

        with mock.patch("os.kill", side_effect=kill) as probe:
            yield before, probe
        self.assertFalse(conn.in_transaction, f"зерно: {self.seed}")

    def events(self, conn=None):
        conn = conn if conn is not None else self.conn
        return [dict(s) for s in store.task_steps(conn, self.task)
                if s["actor"] == "lease" or s["action"].startswith("lease ")]

    def unchanged(self, before):
        self.assertEqual(dict(store.lease_row(self.conn, self.task)), before,
                         f"зерно: {self.seed}")
        self.assertEqual(self.events(), [], f"зерно: {self.seed}")

    def rewritten(self, before, conn=None):
        conn = conn if conn is not None else self.conn
        expected = dict(before, session_id=self.sid, hostname=self.host,
                        pid=self.pid, heartbeat_ts=self.stamp)
        self.assertEqual(dict(store.lease_row(conn, self.task)), expected,
                         f"зерно: {self.seed}")

    def test_ac1_remote_own_session_refuses_without_writes(self):
        """Коллизия номера PID не даёт владения процессом другого хоста.

        Ловит мутацию: проверка продления только по PID разрешает вызов
        и меняет remote hostname/heartbeat вместо отказа своей сессии.
        """
        for same_pid, age in itertools.product(
                (True, False), (1, config.LEASE_STALE_AFTER_SEC + 1)):
            with self.subTest(seed=self.seed, same_pid=same_pid, age=age):
                with self.scenario(same_pid=same_pid, age=age) as (before, _):
                    refusal, fresh = lease.acquire(self.conn, self.task, self.sid)
                    self.assertIsNotNone(refusal)
                    for fragment in (self.task, str(before["pid"]), "этой же сессии"):
                        self.assertIn(fragment, refusal)
                    self.assertIs(fresh, False)
                    self.unchanged(before)

    def test_ac2_remote_parallel_permission_preserves_whole_row(self):
        """Своя remote сессия допускает параллельную операцию без продления.

        Ловит мутацию: совпавший PID проходит ветку продления раньше S
        и переписывает heartbeat/hostname remote держателя.
        """
        for same_pid, age in itertools.product(
                (True, False), (1, config.LEASE_STALE_AFTER_SEC + 1)):
            with self.subTest(seed=self.seed, same_pid=same_pid, age=age):
                with self.scenario(same_pid=same_pid, age=age) as (before, _):
                    self.assertEqual(lease.acquire(self.conn, self.task, self.sid,
                                                   same_host_ok=True), (None, False))
                    self.unchanged(before)

    def test_ac3_local_renewal_live_refusal_and_dead_takeover(self):
        """Локальное продление меняет старый heartbeat, а S не крадёт живой PID.

        Ловит мутацию: пропуск записи при продлении сохраняет старый heartbeat;
        проверка S раньше смерти собственного держателя мешает перехвату.
        """
        for same_pid, alive, parallel, age in itertools.product(
                (True, False), (True, False), (False, True),
                (1, config.LEASE_STALE_AFTER_SEC + 1)):
            if same_pid and not alive:
                continue  # Свой исполняющийся процесс не бывает мёртвым.
            with self.subTest(seed=self.seed, same_pid=same_pid, alive=alive,
                              parallel=parallel, age=age):
                with self.scenario(local=True, same_pid=same_pid, alive=alive,
                                   age=age) as (before, _):
                    result = lease.acquire(self.conn, self.task, self.sid,
                                           same_host_ok=parallel)
                    if same_pid or not alive:
                        self.assertEqual(result, (None, False))
                        self.assertNotEqual(before["heartbeat_ts"], self.stamp)
                        self.rewritten(before)
                        self.assertEqual(self.events(), [])
                    else:
                        self.assertIs(result[1], False)
                        if parallel:
                            self.assertIsNone(result[0])
                        else:
                            self.assertIsNotNone(result[0])
                        self.unchanged(before)

    def test_ac4_other_session_ttl_boundary_and_liveness(self):
        """Чужой держатель защищён до порога включительно; после него важна причина.

        Ловит мутацию: замена <= на < перехватывает lease ровно на пороге;
        разрешение S на remote host либо раньше TTL даёт неправильную строку.
        """
        threshold = config.LEASE_STALE_AFTER_SEC
        for local, same_pid, alive, parallel, age in itertools.product(
                (True, False), (True, False), (True, False), (True, False),
                (max(0, threshold - 1), threshold, threshold + 1)):
            if local and same_pid and not alive:
                continue
            with self.subTest(seed=self.seed, local=local, same_pid=same_pid,
                              alive=alive, parallel=parallel, age=age):
                with self.scenario(own=False, local=local, same_pid=same_pid,
                                   alive=alive, age=age) as (before, _):
                    refusal, fresh = lease.acquire(self.conn, self.task, self.sid,
                                                   same_host_ok=parallel)
                    self.assertIs(fresh, False)
                    takeover = age > threshold or (local and not alive and not parallel)
                    if takeover:
                        self.assertIsNone(refusal)
                        self.rewritten(before)
                        events = self.events()
                        self.assertEqual(len(events), 1)
                        self.assertEqual(events[0]["action"], "lease перехвачен")
                        self.assertEqual(events[0]["session_id"], self.sid)
                        reason = "мёртв" if local and not alive else "heartbeat протух"
                        self.assertIn(reason, events[0]["detail"])
                    else:
                        self.unchanged(before)
                        if local and parallel:
                            self.assertIsNone(refusal)
                        else:
                            self.assertIsNotNone(refusal)
                            for fragment in (self.other_sid, before["hostname"], str(age)):
                                self.assertIn(fragment, refusal)

    def test_ac5_force_overrides_parallel_permission(self):
        """Force перезаписывает существующую строку и различает журнал своей/чужой сессии.

        Ловит мутацию: ранний возврат по S отменяет force; журналирование
        собственной перезаписи создаёт лишнее событие перехвата.
        """
        for own, local, same_pid, parallel, age, alive in itertools.product(
                (True, False), (True, False), (True, False), (True, False),
                (1, config.LEASE_STALE_AFTER_SEC + 1), (True, False)):
            if local and same_pid and not alive:
                continue
            with self.subTest(seed=self.seed, own=own, local=local,
                              same_pid=same_pid, parallel=parallel, age=age, alive=alive):
                with self.scenario(own=own, local=local, same_pid=same_pid,
                                   age=age, alive=alive) as (before, _):
                    self.assertEqual(lease.acquire(self.conn, self.task, self.sid,
                                                   same_host_ok=parallel, force=True),
                                     (None, False))
                    self.rewritten(before)
                    events = self.events()
                    if own:
                        self.assertEqual(events, [])
                    else:
                        self.assertEqual(len(events), 1)
                        self.assertEqual(events[0]["action"], "lease перехвачен")
                        self.assertEqual(events[0]["session_id"], self.sid)
                        reason = ("kill switch" if age <= config.LEASE_STALE_AFTER_SEC
                                  else "мёртв" if local and not alive else "heartbeat протух")
                        self.assertIn(reason, events[0]["detail"])

    def test_ac6_remote_never_probes_local_pid(self):
        """Одинаковые remote записи дают один исход при живом и мёртвом локальном номере.

        Ловит мутацию: снятие проверки hostname перед os.kill делает
        локальный зонд наблюдаемым и может разрешить remote перехват.
        """
        for own, same_pid, parallel, force, age, alive in itertools.product(
                (True, False), (True, False), (True, False), (True, False),
                (1, config.LEASE_STALE_AFTER_SEC + 1), (True, False)):
            with self.subTest(seed=self.seed, own=own, same_pid=same_pid,
                              parallel=parallel, force=force, age=age, alive=alive):
                with self.scenario(own=own, same_pid=same_pid, age=age,
                                   alive=alive) as (before, probe):
                    refusal, fresh = lease.acquire(self.conn, self.task, self.sid,
                                                   same_host_ok=parallel, force=force)
                    probe.assert_not_called()
                    self.assertIs(fresh, False)
                    takeover = force or (not own and age > config.LEASE_STALE_AFTER_SEC)
                    permitted = takeover or (own and parallel)
                    self.assertEqual(refusal is None, permitted)
                    if takeover:
                        self.rewritten(before)
                    else:
                        self.unchanged(before)

    def test_ac7_creation_transactions_and_rollback(self):
        """Свободная строка создаётся один раз; отказ/ошибка закрывают транзакцию.

        Ловит мутацию: BEGIN DEFERRED вместо IMMEDIATE виден в SQLite trace;
        пропуск rollback после ошибки оставляет открытой транзакцию.
        """
        for parallel, force in itertools.product((True, False), repeat=2):
            with self.subTest(seed=self.seed, parallel=parallel, force=force):
                self.conn.execute("DELETE FROM leases WHERE task_id=?", (self.task,))
                self.conn.execute("DELETE FROM steps WHERE task_id=?", (self.task,))
                self.conn.commit()
                trace = []
                self.conn.set_trace_callback(trace.append)
                self.assertEqual(lease.acquire(self.conn, self.task, self.sid,
                                               same_host_ok=parallel, force=force),
                                 (None, True))
                self.assertFalse(self.conn.in_transaction)
                statements = [s.upper().strip() for s in trace]
                self.assertIn("BEGIN IMMEDIATE", statements)
                self.assertIn("COMMIT", statements)
                row = dict(store.lease_row(self.conn, self.task))
                for field, value in (("session_id", self.sid), ("pid", self.pid),
                                     ("hostname", self.host), ("heartbeat_ts", self.stamp)):
                    self.assertEqual(row[field], value)
                events = self.events()
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["action"], "lease взят")
                self.assertEqual(events[0]["session_id"], self.sid)
        for same_pid in (True, False):
            with self.subTest(seed=self.seed, rollback_pid=same_pid):
                with self.scenario(same_pid=same_pid) as (before, _):
                    trace = []
                    self.conn.set_trace_callback(trace.append)
                    lease.acquire(self.conn, self.task, self.sid)
                    self.assertFalse(self.conn.in_transaction)
                    self.assertIn("ROLLBACK", [s.upper().strip() for s in trace])
                    self.unchanged(before)
        self.conn.execute("DELETE FROM leases WHERE task_id=?", (self.task,))
        self.conn.commit()
        with mock.patch.object(store, "insert_lease", side_effect=RuntimeError("write failed")):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                lease.acquire(self.conn, self.task, self.sid)
        self.assertFalse(self.conn.in_transaction)
        self.assertIsNone(store.lease_row(self.conn, self.task))

    def test_ac7_competing_sessions_have_one_winner(self):
        """Независимые SQLite-соединения одновременно захватывают одну строку.

        Ловит мутацию: чтение решения вне блокировки позволяет двум
        претендентам вернуть успех либо дублировать событие перехвата.
        """
        for initial in ("free", "stale", "dead"):
            with self.subTest(seed=self.seed, initial=initial), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "lease.db"
                master = sqlite3.connect(path)
                master.row_factory = sqlite3.Row
                try:
                    self.conn.backup(master)
                    master.execute("DELETE FROM leases WHERE task_id=?", (self.task,))
                    master.execute("DELETE FROM steps WHERE task_id=?", (self.task,))
                    master.commit()
                    if initial != "free":
                        age = config.LEASE_STALE_AFTER_SEC + 1 if initial == "stale" else 1
                        store.insert_lease(master, self.task, self.other_sid, self.other_pid,
                                           self.host, (self.now - timedelta(seconds=age)).strftime(
                                               "%Y-%m-%d %H:%M:%SZ"))
                    barrier = threading.Barrier(4, timeout=10)

                    def probe(pid, signal):
                        if initial == "dead" and pid == self.other_pid:
                            raise ProcessLookupError(pid)

                    def compete(index):
                        conn = sqlite3.connect(path, timeout=10)
                        conn.row_factory = sqlite3.Row
                        try:
                            barrier.wait()
                            sid = f"{self.sid}-{index}"
                            result = lease.acquire(conn, self.task, sid)
                            return sid, result, conn.in_transaction
                        finally:
                            conn.close()

                    with mock.patch("os.kill", side_effect=probe), ThreadPoolExecutor(4) as pool:
                        results = list(pool.map(compete, range(4)))
                    winners = [(sid, result) for sid, result, _ in results if result[0] is None]
                    self.assertEqual(len(winners), 1, (self.seed, results))
                    winner, result = winners[0]
                    self.assertEqual(result, (None, initial == "free"))
                    self.assertEqual(store.lease_row(master, self.task)["session_id"], winner)
                    self.assertTrue(all(not opened for _, _, opened in results))
                    self.assertTrue(all(not result[1] for sid, result, _ in results if sid != winner))
                    events = self.events(master)
                    self.assertEqual(len(events), 1)
                    self.assertEqual(events[0]["action"],
                                     "lease взят" if initial == "free" else "lease перехвачен")
                    self.assertEqual(events[0]["session_id"], winner)
                finally:
                    master.close()

    def test_run_locked_remote_body_permission_and_lease_retention(self):
        """Операция своей remote сессии исполняется только с S и оставляет lease.

        Ловит мутацию: remote совпадение PID запускает запрещённое тело;
        освобождение после разрешения S удаляет чужую remote строку.
        """
        for same_pid, parallel, channel in itertools.product(
                (True, False), (True, False), ("exit", "print")):
            with self.subTest(seed=self.seed, same_pid=same_pid, parallel=parallel, channel=channel):
                with self.scenario(same_pid=same_pid) as (before, _):
                    body = mock.Mock(return_value="operation result")
                    if parallel or channel == "print":
                        result = lease.run_locked(self.conn, self.task, self.sid, body,
                                                  same_host_ok=parallel, on_refusal=channel)
                        self.assertEqual(result, "operation result" if parallel else None)
                    else:
                        with self.assertRaises(SystemExit):
                            lease.run_locked(self.conn, self.task, self.sid, body)
                    if parallel:
                        body.assert_called_once_with(self.sid)
                    else:
                        body.assert_not_called()
                    self.unchanged(before)

    def test_budget_remote_permission_changes_only_allowed_ceiling(self):
        """Budget проходит через настоящий run_locked и пишет пометку активного шага.

        Ловит мутацию: снятие S блокирует свою remote сессию; расширение
        исключения на чужую remote сессию меняет запрещённый бюджет.
        """
        for own, same_pid, ceiling in itertools.product((True, False), (True, False), (20, 35)):
            with self.subTest(seed=self.seed, own=own, same_pid=same_pid, ceiling=ceiling):
                store.update_task(self.conn, self.task, budget_usd=10.0)
                with self.scenario(own=own, same_pid=same_pid) as (before, _):
                    with mock.patch.object(store, "db", return_value=self.conn):
                        if own:
                            budget.cmd_budget(self.task, str(ceiling), self.sid)
                        else:
                            with self.assertRaises(SystemExit):
                                budget.cmd_budget(self.task, str(ceiling), self.sid)
                    self.assertEqual(store.get_task(self.conn, self.task)["budget_usd"],
                                     ceiling if own else 10.0)
                    changes = [s for s in store.task_steps(self.conn, self.task)
                               if s["action"] == "бюджет изменён"]
                    self.assertEqual(len(changes), 1 if own else 0)
                    if own:
                        self.assertIn("во время шага", changes[0]["detail"])
                    self.unchanged(before)
