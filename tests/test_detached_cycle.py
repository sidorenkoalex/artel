"""Юнит-тесты отвязки `run`/`auto` от процесса сессии Оператора (SPEC
01M1NWCHVTYQ0M8PCJ1YJ2N78P): разбор argv, запуск отвязанного процесса,
`stop`, `force` у lease и точечный SIGKILL держателя при `kill`.

Приёмочные тесты (tasks/01M1TNMBY8G3AH3MYCB07RW14N/acceptance_tests)
кроют AC-1..AC-13 сквозным путём (реальный `python3 orchestrator/artel.py
...` отдельным процессом ОС) — здесь те же модули в изоляции, теми же
мок-приёмами, что уже используют `tests/test_lease.py`/`tests/
test_kill_cleanup.py` (эти два файла не правятся: AC-13 требует их
зелёными БЕЗ изменений, новое покрытие — отдельным файлом).
"""
import os
import signal
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel, catalog, cleanup, config, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402
from tests.test_kill_cleanup import TmpRepoTest  # noqa: E402

_REAL_OS_KILL = os.kill


def _signal_only_kill(mod):
    """`mock.patch.object(mod.os, "kill", side_effect=...)` — `os` один и
    тот же объект модуля для ЛЮБОГО импортёра (`cleanup.os`/`artel.os`/
    `liveness.os`): подмена без разбора перехватила бы и `liveness.
    _pid_alive`'s собственный `os.kill(pid, 0)`, ломая живость проверяемого
    pid внутри самого теста. Сигнал 0 идёт настоящим `os.kill` (только он
    отвечает правду о живости), остальные сигналы — молча записываются
    моком, не долетая до реального процесса."""
    def fake(pid, sig):
        if sig == 0:
            return _REAL_OS_KILL(pid, sig)
        return None
    return mock.patch.object(mod.os, "kill", side_effect=fake)


def _terminating_calls(kill_mock) -> list:
    """Вызовы `kill_mock`, кроме сигнала 0 (проверка живости `liveness`,
    не намеренная отправка сигнала самим тестируемым кодом)."""
    return [c for c in kill_mock.call_args_list if c.args[1] != 0]


class TaskIdAndAttachTest(unittest.TestCase):

    def test_bare_task_id_is_not_attach(self):
        self.assertEqual(artel._task_id_and_attach(["T001"], "usage"),
                         ("T001", False))

    def test_trailing_attach_flag_is_detected(self):
        self.assertEqual(
            artel._task_id_and_attach(["T001", "--attach"], "usage"),
            ("T001", True))

    def test_leading_attach_flag_is_detected(self):
        self.assertEqual(
            artel._task_id_and_attach(["--attach", "T001"], "usage"),
            ("T001", True))

    def test_missing_task_id_exits_with_usage(self):
        with self.assertRaises(SystemExit) as ctx:
            artel._task_id_and_attach([], "auto <id> [--attach]")
        self.assertIn("auto <id> [--attach]", str(ctx.exception))

    def test_bare_attach_flag_without_task_id_exits(self):
        with self.assertRaises(SystemExit):
            artel._task_id_and_attach(["--attach"], "usage")


class LaunchDetachedTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def _popen_mock(self, pid: int = 4242):
        proc = mock.Mock()
        proc.pid = pid
        return mock.patch.object(artel.subprocess, "Popen", return_value=proc)

    def test_spawns_itself_with_attach_and_detached_session(self):
        with self._popen_mock(pid=4242) as popen:
            out = capture(artel._launch_detached, "auto", self.TASK)

        popen.assert_called_once()
        args, kwargs = popen.call_args
        argv = args[0]
        self.assertEqual(argv[0], sys.executable)
        self.assertIn("-u", argv)
        self.assertEqual(argv[-3:], ["auto", self.TASK, "--attach"])
        self.assertTrue(kwargs["start_new_session"],
                        "не отвязан от группы/сессии — переживёт SIGHUP "
                        "родителя (AC-5)")
        self.assertEqual(kwargs["stderr"], artel.subprocess.STDOUT)
        self.assertEqual(kwargs["stdin"], artel.subprocess.DEVNULL)

        self.assertIn("pid 4242", out)
        self.assertIn(f"artel.py log {self.TASK}", out)

    def test_log_path_follows_task_cmd_n_pattern_and_is_created(self):
        with self._popen_mock():
            out = capture(artel._launch_detached, "auto", self.TASK)

        expected = config.LOGS / f"{self.TASK}-auto-1.log"
        self.assertIn(str(expected), out)
        self.assertTrue(expected.exists(),
                        "лог обязан быть создан ДО возврата команды, не "
                        "лениво отвязанным процессом")

    def test_second_launch_increments_the_log_number(self):
        with self._popen_mock():
            capture(artel._launch_detached, "auto", self.TASK)
        with self._popen_mock():
            out2 = capture(artel._launch_detached, "auto", self.TASK)

        self.assertIn(str(config.LOGS / f"{self.TASK}-auto-2.log"), out2)

    def test_run_and_auto_logs_do_not_collide(self):
        with self._popen_mock():
            out_run = capture(artel._launch_detached, "run", self.TASK)
        with self._popen_mock():
            out_auto = capture(artel._launch_detached, "auto", self.TASK)

        self.assertIn(str(config.LOGS / f"{self.TASK}-run-1.log"), out_run)
        self.assertIn(str(config.LOGS / f"{self.TASK}-auto-1.log"), out_auto)

    def test_task_id_prefix_is_resolved_to_full_id_before_spawning(self):
        prefix = self.TASK[:4]
        with self._popen_mock() as popen:
            capture(artel._launch_detached, "auto", prefix)

        args, _ = popen.call_args
        self.assertEqual(args[0][-2], self.TASK,
                         "дочерний процесс обязан получить полный id, не "
                         "префикс — иначе гонка с новой задачей того же "
                         "префикса адресует не ту задачу")


class CmdStopTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def _seed_lease(self, pid: int, hostname: str) -> None:
        store.insert_lease(store.db(), self.TASK, "cycle-session", pid,
                           hostname, store.now())

    def test_sends_sigterm_to_the_lease_holder_pid(self):
        self._seed_lease(os.getpid(), socket.gethostname())

        with _signal_only_kill(artel) as kill:
            out = capture(artel._cmd_stop, self.TASK)

        self.assertEqual(_terminating_calls(kill),
                         [mock.call(os.getpid(), signal.SIGTERM)])
        self.assertIn(str(os.getpid()), out)

    def test_no_lease_exits_without_signalling(self):
        with _signal_only_kill(artel) as kill:
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_stop(self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertIn("нечего останавливать", str(ctx.exception))

    def test_foreign_host_holder_is_refused_without_signalling(self):
        self._seed_lease(4242, "other-host.invalid")

        with _signal_only_kill(artel) as kill:
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_stop(self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertIn("other-host.invalid", str(ctx.exception))

    def test_already_dead_holder_pid_is_reported_without_signalling(self):
        self._seed_lease(_dead_pid(), socket.gethostname())

        with _signal_only_kill(artel) as kill:
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_stop(self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertIn("уже не существует", str(ctx.exception))

    def test_process_lookup_error_race_is_reported_not_raised(self):
        """Pid жив по проверке `liveness`, но успевает умереть между ней и
        самим `os.kill` — гонка, а не отказ, репортится тем же текстом."""
        self._seed_lease(os.getpid(), socket.gethostname())

        def fake(pid, sig):
            if sig == 0:
                return _REAL_OS_KILL(pid, sig)
            raise ProcessLookupError

        with mock.patch.object(artel.os, "kill", side_effect=fake):
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_stop(self.TASK)

        self.assertIn("уже не существует", str(ctx.exception))


class LeaseForceTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def _seed_foreign_fresh_lease(self) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, socket.gethostname(), store.now()))
        conn.commit()

    def test_without_force_a_fresh_foreign_lease_refuses(self):
        self._seed_foreign_fresh_lease()

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-kill")

        self.assertIsNotNone(refusal)
        self.assertFalse(fresh)

    def test_force_overrides_a_fresh_foreign_lease(self):
        """AC-10: `kill` обязан прервать задачу немедленно, даже если lease
        держит живой отвязанный цикл со свежим heartbeat."""
        self._seed_foreign_fresh_lease()

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-kill",
                                       force=True)

        self.assertIsNone(refusal)
        row = store.lease_row(store.db(), self.TASK)
        self.assertEqual(row["session_id"], "sess-kill")

    def test_force_intercept_names_kill_switch_in_the_journal(self):
        self._seed_foreign_fresh_lease()

        lease.acquire(store.db(), self.TASK, "sess-kill", force=True)

        detail = store.task_steps(store.db(), self.TASK)[-1]["detail"]
        self.assertIn("kill switch", detail)

    def test_force_on_a_stale_lease_keeps_the_pid_dead_cause(self):
        """`force=True` не подменяет причину, когда перехват и без него
        законен (протухший/мёртвый держатель) — специальная причина
        «kill switch» только для СВЕЖЕГО lease (требование 6)."""
        conn = store.db()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", _dead_pid(), socket.gethostname(),
             stale_ts))
        conn.commit()

        lease.acquire(store.db(), self.TASK, "sess-kill", force=True)

        detail = store.task_steps(store.db(), self.TASK)[-1]["detail"]
        self.assertNotIn("kill switch", detail)
        self.assertIn("мёртв", detail)


class KillSignalsDetachedHolderTest(TmpRepoTest):
    """`cleanup.cmd_kill` (AC-10): SIGKILL держателя lease, снятого ДО
    `force=True` перезаписи (`holder_before`), если он живой и на этом
    host."""

    def _seed_lease(self, pid: int, hostname: str) -> None:
        store.insert_lease(store.db(), self.TASK, "cycle-session", pid,
                           hostname, store.now())

    def test_kill_sends_sigkill_to_the_live_same_host_holder(self):
        self._seed_lease(os.getpid(), socket.gethostname())

        with _signal_only_kill(cleanup) as kill:
            self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(_terminating_calls(kill),
                         [mock.call(os.getpid(), signal.SIGKILL)])
        self.assertEqual(self.task_row()["state"], "killed")

    def test_kill_does_not_signal_a_foreign_host_holder(self):
        self._seed_lease(4242, "other-host.invalid")

        with _signal_only_kill(cleanup) as kill:
            self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertEqual(self.task_row()["state"], "killed")

    def test_kill_does_not_signal_an_already_dead_holder(self):
        self._seed_lease(_dead_pid(), socket.gethostname())

        with _signal_only_kill(cleanup) as kill:
            self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertEqual(self.task_row()["state"], "killed")

    def test_kill_completes_even_if_the_signal_itself_fails(self):
        self._seed_lease(os.getpid(), socket.gethostname())

        def fake(pid, sig):
            if sig == 0:
                return _REAL_OS_KILL(pid, sig)
            raise OSError

        with mock.patch.object(cleanup.os, "kill", side_effect=fake):
            self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(self.task_row()["state"], "killed")

    def test_kill_without_any_lease_does_not_crash(self):
        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(self.task_row()["state"], "killed")


if __name__ == "__main__":
    unittest.main()
