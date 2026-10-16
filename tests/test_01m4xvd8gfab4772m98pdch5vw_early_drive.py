"""Процессные сценарии канарейки и сохранения потребителей liveness.

Группа: долгоживущий
Красен до реализации: ранний drive и отдельная роль переживают удаление; ошибки уборки маскируют сигнал, второй сигнал меняет код; force-перехват kill подменяет исходный допуск.

Синхронизация происходит внутри Popen: фактический процесс уже существует,
а вызывающий код ещё не получил его объект. Наблюдатель rmtree сохраняет
снимок ДО удаления; поздняя уборка теста не может сделать его зелёным.
"""

import os
import io
import json
import random
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (canary, catalog, checkpoint, cleanup, config, doctor,
                          lease, liveness, pause, release, runner, stack, store)
from tests.sandbox import (ALL_CONFIG_ATTRS, RealGitSandbox, capture,
                          patch_pult_sleep, _stub_check_stack, _dead_pid, capture_new_task_id)


class ProcessFixture:
    def setUp(self):
        super().setUp()
        self.use_role_map()
        stack_patch = mock.patch.object(stack, "check_stack", _stub_check_stack)
        stack_patch.start()
        self.addCleanup(stack_patch.stop)
        self.seed = random.randrange(2**32)
        print(f"зерно: {self.seed}")
        self.temp_root = self.root / ".artel" / "process-fixtures"
        self.temp_root.mkdir(parents=True)
        patcher = mock.patch.object(tempfile, "tempdir", str(self.temp_root))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.home = self.temp_root / "home"
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir(parents=True)
        (pool / "fixture.md").write_text("# Локальная учебная задача\n")
        entry = self.root / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# Локальная фикстура ведения без моделей\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "local process fixture")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.processes = []
        self.waiters = {}
        self.child_pids = []
        self.monitors = {}
        self.members = {}
        self.lifelines = []
        self.dead = set()
        self.addCleanup(self.reap)

    def reap(self):
        for descriptor in self.lifelines:
            os.close(descriptor)
        for proc in self.processes:
            members = self.members.get(proc.pid, ())
            if proc.pid not in self.monitors and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.waiters.get(proc.pid, proc.wait)(timeout=5)
            for pid in members:
                if self.live(pid):
                    monitor = self.monitors[pid]
                    events = (select.select([monitor], [], [], 5)[0]
                              if isinstance(monitor, int) else monitor.control(None, 1, 5))
                    self.assertTrue(events, f"зерно: {self.seed}; cleanup pid={pid}")
                    self.dead.add(pid)
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
        for monitor in self.monitors.values():
            if isinstance(monitor, int):
                os.close(monitor)
            else:
                monitor.close()

    def live(self, pid):
        for proc in self.processes:
            if proc.pid == pid and proc.poll() is not None:
                return False
        if pid in self.dead:
            return False
        monitor = self.monitors[pid]
        if isinstance(monitor, int):
            exited = bool(select.select([monitor], [], [], 0)[0])
        else:
            exited = bool(monitor.control(None, 1, 0))
        if exited:
            self.dead.add(pid)
        return not exited

    def watch_pid(self, pid):
        # Дескриптор привязан к экземпляру процесса, а не к позднему
        # совпадению номера. Регистрация происходит до первого сигнала.
        if hasattr(os, "pidfd_open"):
            self.monitors[pid] = os.pidfd_open(pid)
        else:
            monitor = select.kqueue()
            self.monitors[pid] = monitor
            monitor.control([select.kevent(pid, filter=select.KQ_FILTER_PROC,
                                          flags=select.KQ_EV_ADD,
                                          fflags=select.KQ_NOTE_EXIT)], 0, 0)

    def await_exit(self, group):
        self.waiters.get(group["pid"], group["proc"].wait)(timeout=5)
        for pid in (group["pid"], group["child"]):
            if not pid or not self.live(pid):
                continue
            monitor = self.monitors[pid]
            if isinstance(monitor, int):
                events = select.select([monitor], [], [], 5)[0]
            else:
                events = monitor.control(None, 1, 5)
            self.assertTrue(events, f"зерно: {self.seed}; pid={pid} не завершился")
            self.dead.add(pid)

    def group(self, name, *, spawn=None, stubborn=False, with_child=True, **kwargs):
        """Handshake содержит PID, PGID и случайный nonce данного запуска."""
        read_fd, write_fd = os.pipe()
        life_read, life_write = os.pipe()
        self.lifelines.append(life_write)
        nonce = random.Random(self.seed + len(self.processes)).randrange(2**32)
        script = (
            "import json, os, signal, threading\n"
            "def parent_gone():\n"
            f"    os.read({life_read}, 1)\n"
            "    os.kill(os.getpid(), signal.SIGKILL)\n"
            + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if stubborn else "")
            + ("child = os.fork()\n"
               "if child == 0:\n"
               f"    os.close({write_fd})\n"
               "    threading.Thread(target=parent_gone, daemon=True).start()\n"
               "    while True: signal.pause()\n" if with_child else "child = 0\n")
            + "threading.Thread(target=parent_gone, daemon=True).start()\n"
            + f"os.write({write_fd}, (json.dumps([os.getpid(), os.getpgrp(), child, {nonce}])+'\\n').encode())\n"
            + f"os.close({write_fd})\n"
            + "while True: signal.pause()\n")
        kwargs.setdefault("start_new_session", True)
        kwargs.setdefault("stdout", subprocess.DEVNULL)
        kwargs.setdefault("stderr", subprocess.DEVNULL)
        try:
            proc = (spawn or subprocess.Popen)([sys.executable, "-c", script],
                                               pass_fds=(write_fd, life_read), **kwargs)
            self.processes.append(proc)
            self.waiters[proc.pid] = proc.wait
        finally:
            os.close(write_fd)
            os.close(life_read)
        with os.fdopen(read_fd) as ready:
            handshake = json.loads(ready.readline())
        self.assertEqual(handshake[0:2], [proc.pid, proc.pid], f"зерно: {self.seed}")
        self.assertEqual(handshake[3], nonce, f"зерно: {self.seed}")
        self.assertIsNone(proc.poll(), f"зерно: {self.seed}")
        self.watch_pid(proc.pid)
        if handshake[2]:
            self.child_pids.append(handshake[2])
            self.watch_pid(handshake[2])
            self.assertTrue(self.live(handshake[2]), f"зерно: {self.seed}")
            self.members[proc.pid] = (handshake[2],)
        return {"name": name, "proc": proc, "pid": proc.pid,
                "pgid": proc.pid, "child": handshake[2], "nonce": nonce}

    def scenario(self, signum=signal.SIGTERM, *, fault=None, early_role=False,
                 leader_gone=False, second_signal=False, stubborn=False, vanished=False,
                 reused=False, early_drive=False, outcome=None, repeat_cleanup=False):
        """Команда с реальными клонами, drive, suite и шагом runner.

        Drive, suite и платная команда роли заменены локальными процессами.
        Сигнал приходит из wait роли либо непосредственно из её spawn.
        """
        real_popen, real_rmtree, real_killpg = subprocess.Popen, shutil.rmtree, os.killpg
        spawn_agent = runner.spawn_agent
        state = {"groups": [], "removals": [], "signals": [], "commands": [], "fault_seen": False}
        controls = [self.group(name, spawn=real_popen) for name in
                    ("foreign", "main-line", "other-canary")]
        state["controls"] = controls
        outer_conn = store.db()
        main_task = "01" + f"{len(store.all_tasks(outer_conn)) + 1:024d}"
        store.insert_task(outer_conn, main_task, "Основная линия", "in_dev",
                          "fixture-main", config.DEFAULT_TARGET, 1)
        store.insert_lease(outer_conn, main_task, "main-line", controls[1]["pid"],
                           socket.gethostname(), store.now())
        store.update_lease_pgid(outer_conn, main_task, controls[1]["pgid"])
        other_clone = Path(tempfile.mkdtemp(prefix="artel-canary-other-"))
        (other_clone / liveness.CANARY_OWNER_MARKER).write_text(str(controls[2]["pid"]))
        other_run = other_clone / ".artel" / "logs" / "suite-run" / "other" / "run.json"
        other_run.parent.mkdir(parents=True)
        other_run.write_text(json.dumps({"pid": controls[2]["pid"]}))
        with mock.patch.object(config, "DB", other_clone / ".artel" / "state.db"):
            conn = store.db()
            store.create_schema(conn)
            store.insert_task(conn, main_task, "Другая канарейка", "in_dev",
                              "fixture-other", config.DEFAULT_TARGET, 1, is_canary=True)
            store.insert_lease(conn, main_task, "other-canary", controls[2]["pid"],
                               socket.gethostname(), store.now())
            store.update_lease_pgid(conn, main_task, controls[2]["pgid"])
        state["other_clone"] = other_clone
        class Output(io.StringIO):
            def write(stream, text):
                if (repeat_cleanup and fault and state["fault_seen"]
                        and not state.get("repeat_seen")
                        and any(str(group["pid"]) in text for group in state["groups"])):
                    state["repeat_seen"] = True
                    os.kill(os.getpid(), signal.SIGTERM)
                    os.kill(os.getpid(), signal.SIGHUP)
                return super().write(text)

        output = Output()
        task = "01" + "F" * 24
        previous_runs = len(store.all_canary_runs(store.db()))

        def snapshot():
            return [(group["name"], pid, self.live(pid))
                    for group in state["groups"]
                    for pid in (group["pid"], group["child"]) if pid]

        def remove(path, *args, **kwargs):
            path = Path(path)
            if path.parent == self.temp_root and path.name.startswith("artel-canary-"):
                if repeat_cleanup and not fault and not state.get("repeat_seen"):
                    state["repeat_seen"] = True
                    os.kill(os.getpid(), signal.SIGTERM)
                    os.kill(os.getpid(), signal.SIGHUP)
                state["removals"].append((path, snapshot()))
            return real_rmtree(path, *args, **kwargs)

        def signal_group(pgid, sig):
            state["signals"].append((pgid, sig))
            if reused and state.get("vanished_pgid") == pgid:
                # Модель повторного использования номера: ОС адресует уже
                # новый экземпляр процесса, kernel monitor старого завершён.
                return real_killpg(controls[0]["pgid"], sig)
            targets = {g["pgid"] for g in state["groups"]}
            if sig and pgid in targets:
                if second_signal and not state.get("second_sent"):
                    state["second_sent"] = True
                    os.kill(os.getpid(), signal.SIGHUP)
                if fault is not None and (early_drive or pgid != state["groups"][0]["pgid"]):
                    state["fault_seen"] = True
                    if fault == "permission":
                        raise PermissionError("fixture: signal denied")
                    if fault == "exception":
                        raise RuntimeError("fixture: cleanup failed")
                    if fault == "unconfirmed":
                        return None
            return real_killpg(pgid, sig)

        def agent(argv, **kwargs):
            group = self.group("role", spawn=spawn_agent, stubborn=stubborn, **kwargs)
            state["groups"].append(group)
            proc = group["proc"]
            state["role_pipe"] = proc.stdout
            if early_role:
                os.kill(os.getpid(), signum)
            if leader_gone:
                os.kill(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
                self.assertTrue(self.live(group["child"]), f"зерно: {self.seed}")
            original_wait = proc.wait
            first = True

            def wait(timeout=None):
                nonlocal first
                if first:
                    first = False
                    if outcome:
                        real_killpg(group["pgid"], signal.SIGKILL)
                        self.await_exit(group)
                        return original_wait(timeout=timeout)
                    if vanished:
                        real_killpg(group["pgid"], signal.SIGKILL)
                        original_wait(timeout=5)
                        self.await_exit(group)
                        state["vanished_pgid"] = group["pgid"]
                    os.kill(os.getpid(), signum)
                return original_wait(timeout=timeout)

            proc.wait = wait
            return proc

        def launch(argv, *args, **kwargs):
            state["commands"].append(list(argv))
            if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                return real_popen(argv, *args, **kwargs)
            clone = Path(kwargs["cwd"])
            state["clone"] = clone
            origin_text = (clone / ".git" / "config").read_text()
            state["origin"] = Path(re.search(r'\[remote "origin"\]\s*url\s*=\s*(\S+)',
                                               origin_text).group(1))
            drive = self.group("drive", spawn=real_popen, with_child=False, **kwargs)
            state["groups"].append(drive)
            if early_drive:
                state["early_drive_live"] = self.live(drive["pid"])
                os.kill(os.getpid(), signum)
            suite = self.group("suite-run", spawn=real_popen, cwd=clone)
            state["groups"].append(suite)
            run = config.LOGS / "suite-run" / "fixture" / "run.json"
            run.parent.mkdir(parents=True, exist_ok=True)
            run.write_text(json.dumps({"pid": suite["pid"]}))
            conn = store.db()
            store.create_schema(conn)
            store.insert_task(conn, task, "Локальная роль", "in_dev", "fixture", config.DEFAULT_TARGET, 1,
                              is_canary=True)
            store.insert_lease(conn, task, "fixture-drive", drive["pid"], socket.gethostname(), store.now())
            proc = drive["proc"]
            original_wait = proc.wait
            first = True

            def wait(timeout=None):
                nonlocal first
                if first:
                    first = False
                    with mock.patch.object(runner, "role_cwd", return_value=clone), \
                         mock.patch.object(runner, "spawn_agent", side_effect=agent):
                        runner.run_agent_once(conn, task, "developer", "Локальная фикстура", 1)
                    if outcome == "exception":
                        raise RuntimeError("fixture: drive failed")
                    if outcome in ("normal", "timeout"):
                        result = Path(argv[argv.index("--result") + 1])
                        result.write_text(json.dumps({
                            "task_id": task, "head": self.sha, "escalated": False,
                            "metrics": {"steps": 1, "cost_usd": 0.0,
                                "review_iterations": 0, "escalations": [],
                                "dev_retries": 0, "outcome": "killed", "kill_note": "штатно",
                                "test_author_visited": False, "ceiling_exhausted": False,
                                "ceiling_raise": None}, "steps": []}))
                        if outcome == "timeout":
                            raise subprocess.TimeoutExpired(argv, timeout)
                        real_killpg(drive["pgid"], signal.SIGTERM)
                        original_wait(timeout=5)
                        return 0
                    raise AssertionError("роль не дошла до доставки сигнала")
                return original_wait(timeout=timeout)

            proc.wait = wait
            return proc

        with ExitStack() as stack:
            for name in ALL_CONFIG_ATTRS:
                stack.enter_context(mock.patch.object(config, name, getattr(config, name)))
            stack.enter_context(mock.patch.object(config, "CANARY_SKIP_FULL_SUITE",
                                                   config.CANARY_SKIP_FULL_SUITE))
            stack.enter_context(mock.patch.object(Path, "home", return_value=self.home))
            stack.enter_context(mock.patch.object(catalog, "cmd_init"))
            stack.enter_context(mock.patch.object(subprocess, "Popen", launch))
            stack.enter_context(mock.patch.object(shutil, "rmtree", remove))
            stack.enter_context(mock.patch.object(os, "killpg", side_effect=signal_group))
            # Паузы не ждут стенное время: deadline продвигается каждым
            # обращением. Убийство и наблюдение процессов остаются реальными.
            ticks = iter(range(0, 1000000, 10))
            stack.enter_context(patch_pult_sleep(lambda _: None))
            stack.enter_context(mock.patch.object(liveness, "time", SimpleNamespace(
                monotonic=lambda: next(ticks), sleep=lambda _: None)))
            stack.enter_context(redirect_stdout(output))
            stack.enter_context(redirect_stderr(output))
            try:
                canary.cmd_canary(k=1, sha=self.sha, templates=["fixture"])
            except BaseException as exc:
                state["exception"] = exc
        state["output"] = output.getvalue()
        state["rows"] = [dict(row) for row in store.all_canary_runs(store.db())][previous_runs:]
        state["snapshot"] = snapshot()
        return state

    def assert_stopped(self, state, signum):
        self.assertIsInstance(state.get("exception"), SystemExit,
                              f"зерно: {self.seed}; {state.get('exception')}; {state['output']}")
        self.assertEqual(state["exception"].code, 128 + signum, f"зерно: {self.seed}")
        self.assertTrue(state["removals"], f"зерно: {self.seed}; нет удаления")
        self.assertFalse(any(alive for _, _, alive in state["removals"][0][1]),
                         f"зерно: {self.seed}; живы при первом удалении: {state['removals'][0]}")
        for path in (state["clone"], state["origin"]):
            self.assertFalse(path.exists(), f"зерно: {self.seed}; {path}")
        self.assertFalse(any(alive for _, _, alive in state["snapshot"]), f"зерно: {self.seed}")
        for group in state["controls"]:
            self.assertTrue(self.live(group["pid"]), f"зерно: {self.seed}; чужой {group['name']}")


class EarlyDriveTest(ProcessFixture, RealGitSandbox):
    def test_ac1_causal_role_leak_reproduction(self):
        """Одинаковое воздействие воспроизводителя сохраняется после исправления.

        На базе SIGTERM/SIGHUP оставляют отдельную роль с потомком при
        первом rmtree; команда и результаты записаны в записке автора.
        Здесь тот же запуск проверяет исправление через публичную канарейку,
        настоящую БД, локальный клон, роли и наблюдение ядра ОС.
        Ловит мутацию: уборка снова забывает роль вне группы drive —
        наблюдение rmtree содержит живой PID из handshake этого запуска.
        """
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(seed=self.seed, signal=sig):
                state = self.scenario(sig)
                print("воздействие:", signal.Signals(sig).name,
                      "идентичности:", [(g["name"], g["pid"], g["child"], g["nonce"])
                                        for g in state["groups"]],
                      "перед удалением:", state["removals"], "после:", state["snapshot"])
                self.assert_stopped(state, sig)

    def test_ac5_early_drive_failure_preserves_both_directories(self):
        """Ранний SIGTERM доставлен до возврата Popen; ОС отказывает drive в остановке.

        Ловит мутацию: защита раннего spawn есть, но ошибка остановки
        разрешает rmtree — clone/origin исчезают при живом drive.
        """
        for fault in ("permission", "unconfirmed"):
            with self.subTest(seed=self.seed, fault=fault):
                state = self.scenario(early_drive=True, fault=fault)
                self.assertTrue(state.get("early_drive_live"), f"зерно: {self.seed}")
                self.assertTrue(state["fault_seen"], f"зерно: {self.seed}; ранний drive потерян")
                self.assertFalse(state["removals"], f"зерно: {self.seed}")
                for path in (state["clone"], state["origin"]):
                    self.assertTrue(path.exists(), f"зерно: {self.seed}")
                self.assertIsInstance(state.get("exception"), SystemExit, f"зерно: {self.seed}")
                self.assertEqual(state["exception"].code, 143, f"зерно: {self.seed}")

    def test_ac12_real_process_matrix_exposes_each_cleanup_omission(self):
        """Каждая группа наблюдается отдельно, а отказ запрещает оба удаления.

        Сценарии с реальными процессами держат поверхности мутаций:
        роль, suite, drive, порядок rmtree, ошибка и раннее окно Popen.
        Ловит мутацию: пропущена любая группа или rmtree разрешён после
        отказа — живой член виден перед удалением либо появляется rmtree.
        """
        for sig, early, fault in ((signal.SIGTERM, False, None),
                                  (signal.SIGHUP, False, None),
                                  (signal.SIGTERM, True, None),
                                  (signal.SIGHUP, False, "exception")):
            with self.subTest(seed=self.seed, signal=sig, early=early, fault=fault):
                state = self.scenario(sig, early_drive=early, fault=fault)
                if fault:
                    self.assertTrue(state["fault_seen"], f"зерно: {self.seed}")
                    self.assertFalse(state["removals"], f"зерно: {self.seed}")
                    self.assertTrue(state["clone"].exists(), f"зерно: {self.seed}")
                    self.assertTrue(state["origin"].exists(), f"зерно: {self.seed}")
                else:
                    self.assert_stopped(state, sig)
                for control in state["controls"]:
                    self.assertTrue(self.live(control["child"]), f"зерно: {self.seed}")

    def test_ac10_non_signal_outcomes_preserve_cleanup_contract(self):
        """Normal, timeout и исключение проходят публичную команду и реальный клон.

        Ловит мутацию: уборка привязана только к сигналу или удаляет клон
        после отказа ОС — suite/потомок жив при rmtree либо каталоги потеряны.
        """
        for outcome in ("normal", "timeout", "exception"):
            for fault in (None, "permission"):
                with self.subTest(seed=self.seed, outcome=outcome, fault=fault):
                    state = self.scenario(outcome=outcome, fault=fault)
                    if outcome == "exception":
                        self.assertIsInstance(state.get("exception"), RuntimeError,
                                              f"зерно: {self.seed}")
                        self.assertIn("fixture: drive failed", str(state["exception"]))
                    elif outcome == "timeout":
                        self.assertTrue(state["rows"], f"зерно: {self.seed}")
                        self.assertEqual(state["rows"][-1]["verdict"], "red", f"зерно: {self.seed}")
                    elif fault is None:
                        self.assertNotIn("exception", state, f"зерно: {self.seed}")
                        self.assertEqual(state["rows"][-1]["outcome"], "killed", f"зерно: {self.seed}")
                    if fault:
                        self.assertTrue(state["fault_seen"], f"зерно: {self.seed}")
                        self.assertFalse(state["removals"], f"зерно: {self.seed}")
                    else:
                        self.assertTrue(state["removals"], f"зерно: {self.seed}")
                        self.assertFalse(any(alive for _, _, alive in state["removals"][0][1]),
                                         f"зерно: {self.seed}; {state['removals']}")
                    for path in (state["clone"], state["origin"]):
                        self.assertEqual(path.exists(), bool(fault), f"зерно: {self.seed}; {path}")

    def test_ac2_all_groups_finish_before_first_removal(self):
        """Оба сигнала завершают drive, suite, роль и потомков перед удалением.

        Связка команды, БД lease, runner и ОС наблюдается перед rmtree.
        Ловит мутацию: пропущена одна группа роли, suite-run или drive —
        снимок первого удаления содержит её живой PID или живого потомка.
        """
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(seed=self.seed, signal=sig):
                state = self.scenario(sig)
                self.assert_stopped(state, sig)
                self.assertTrue(state["role_pipe"].closed, f"зерно: {self.seed}; pipe роли открыт")

    def test_ac4_cleanup_failures_preserve_directories_and_signal(self):
        """Отказ ОС, исключение и успешная отправка без смерти не разрешают rmtree.

        Ловит мутацию: finally удаляет каталоги после ошибки уборки —
        в журнале наблюдателя появляется rmtree либо исчезает clone/origin.
        """
        for fault in ("permission", "exception", "unconfirmed"):
            for sig in (signal.SIGTERM, signal.SIGHUP):
                with self.subTest(seed=self.seed, fault=fault, signal=sig):
                    state = self.scenario(sig, fault=fault)
                    self.assertTrue(state["fault_seen"], f"зерно: {self.seed}; отказ не разыгран")
                    self.assertIsInstance(state.get("exception"), SystemExit,
                                          f"зерно: {self.seed}; {state.get('exception')}")
                    self.assertEqual(state["exception"].code, 128 + sig, f"зерно: {self.seed}")
                    self.assertFalse(state["removals"], f"зерно: {self.seed}; rmtree после {fault}")
                    for path in (state["clone"], state["origin"]):
                        self.assertTrue(path.exists(), f"зерно: {self.seed}; {path}")
                    self.assertRegex(state["output"].lower(), r"(ошиб|не.*заверш|отказ|не.*подтвер|не.*удал|cleanup)")
                    for _, pid, alive in state["snapshot"]:
                        if alive:
                            self.assertIn(str(pid), state["output"], f"зерно: {self.seed}; нет идентичности")

    def test_ac3_stubborn_role_requires_escalation_and_observed_death(self):
        """Роль и её потомок игнорируют мягкий сигнал; часы ожидания виртуальные.

        Ловит мутацию: после SIGTERM уборка объявляет группу завершённой
        без SIGKILL либо считает отправку SIGKILL смертью — снимок rmtree живой.
        """
        self.assertLessEqual(liveness.GROUP_TERMINATE_GRACE_SEC, 3.0,
                             f"зерно: {self.seed}; прежний grace увеличен")
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(seed=self.seed, signal=sig):
                state = self.scenario(sig, stubborn=True)
                role = next(g for g in state["groups"] if g["name"] == "role")
                delivered = [sent for pgid, sent in state["signals"] if pgid == role["pgid"] and sent]
                self.assertIn(signal.SIGTERM, delivered, f"зерно: {self.seed}")
                self.assertIn(signal.SIGKILL, delivered, f"зерно: {self.seed}")
                self.assertLess(delivered.index(signal.SIGTERM), delivered.index(signal.SIGKILL))
                self.assert_stopped(state, sig)

    def test_ac8_other_runs_and_control_processes_are_untouched(self):
        """Три независимые контрольные группы переживают уборку канарейки.

        Ловит мутацию: принадлежность ищется обзором всей машины либо
        сигнал направлен всем группам Python — появляется общий ps или умирает контроль.
        """
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(seed=self.seed, signal=sig):
                state = self.scenario(sig)
                for group in state["controls"]:
                    for pid in (group["pid"], group["child"]):
                        self.assertTrue(self.live(pid), f"зерно: {self.seed}; {group['name']}, pid={pid}")
                    self.assertFalse(any(pgid == group["pgid"] and sent
                                          for pgid, sent in state["signals"]), f"зерно: {self.seed}")
                for argv in state["commands"]:
                    if Path(str(argv[0])).name == "ps":
                        self.assertFalse(any(arg in ("-A", "-e", "aux", "-ax", "-axww")
                                             for arg in argv[1:]),
                                         f"зерно: {self.seed}; поиск по машине: {argv}")

    def test_ac7_vanished_role_and_reused_number_do_not_target_replacement(self):
        """Сохранённый номер роли больше не адресует прежний экземпляр процесса.

        Ловит мутацию: принадлежность определяется одним числом PGID —
        после исчезновения роли сигнал с этим номером попадает в живой контроль.
        """
        for reused in (False, True):
            with self.subTest(seed=self.seed, reused=reused):
                state = self.scenario(vanished=True, reused=reused, repeat_cleanup=True)
                self.assertIn("vanished_pgid", state, f"зерно: {self.seed}; окно не разыграно")
                self.assertIsInstance(state.get("exception"), SystemExit,
                                      f"зерно: {self.seed}; {state.get('exception')}")
                self.assertEqual(state["exception"].code, 143, f"зерно: {self.seed}")
                self.assertTrue(state.get("repeat_seen"), f"зерно: {self.seed}")
                if reused:
                    self.assertFalse(any(pgid == state["vanished_pgid"] and sig
                                         for pgid, sig in state["signals"]), f"зерно: {self.seed}")
                for group in state["controls"]:
                    self.assertTrue(self.live(group["pid"]), f"зерно: {self.seed}")

    def test_ac10_original_signal_record_survives_cleanup_failure(self):
        """Строка оборванного прогона сохраняет первый сигнал при исправной и сбойной уборке.

        Ловит мутацию: исключение уборки скрывает вставку строки канарейки
        или подменяет исход — нет записи red с исходным сигналом и кодом 128+signum.
        """
        for fault in (None, "permission", "exception"):
            for sig in (signal.SIGTERM, signal.SIGHUP):
                with self.subTest(seed=self.seed, fault=fault, signal=sig):
                    state = self.scenario(sig, fault=fault)
                    self.assertIsInstance(state.get("exception"), SystemExit,
                                          f"зерно: {self.seed}; {state.get('exception')}")
                    self.assertEqual(state["exception"].code, 128 + sig, f"зерно: {self.seed}")
                    self.assertTrue(state["rows"], f"зерно: {self.seed}")
                    row = state["rows"][-1]
                    self.assertEqual(row["verdict"], "red", f"зерно: {self.seed}; {row}")
                    self.assertIn(signal.Signals(sig).name, row["outcome"], f"зерно: {self.seed}; {row}")

    def test_ac5_early_role_spawn_is_not_lost(self):
        """Сигнал внутри spawn роли приходит раньше возврата объекта runner.

        Ловит мутацию: роль учитывается только после возвращения spawn —
        ранний сигнал оставляет живую группу при первом удалении клона.
        """
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(seed=self.seed, signal=sig):
                self.assert_stopped(self.scenario(sig, early_role=True), sig)

    def test_ac6_dead_leader_does_not_hide_live_child(self):
        """Лидер роли уже reaped, однако её отдельный потомок ещё работает.

        Ловит мутацию: мёртвый PID лидера считается мёртвой группой —
        потомок присутствует в живом снимке перед первым rmtree.
        """
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(seed=self.seed, signal=sig):
                self.assert_stopped(self.scenario(sig, leader_gone=True), sig)

    def test_ac9_second_signal_keeps_original_sigterm(self):
        """SIGHUP доставляется при первой попытке группового снятия после SIGTERM.

        Ловит мутацию: защищён только повтор того же сигнала — SIGHUP
        обрывает уборку, меняет код 143 или оставляет принадлежащий процесс.
        """
        state = self.scenario(second_signal=True)
        self.assertTrue(state.get("second_sent"), f"зерно: {self.seed}")
        self.assert_stopped(state, signal.SIGTERM)
        self.assertIn("SIGTERM", state["rows"][-1]["outcome"], f"зерно: {self.seed}")

    def test_ac9_repeated_stop_after_cleanup_result_is_idempotent(self):
        """Повторные stop-сигналы приходят после уборки либо после диагностики отказа.

        Ловит мутацию: обработчик повторно запускает/обрывает завершённую
        уборку — меняет 143, сигналит контролю или удаляет сохранённые каталоги.
        """
        for fault in (None, "permission", "unconfirmed"):
            with self.subTest(seed=self.seed, fault=fault):
                state = self.scenario(fault=fault, repeat_cleanup=True)
                self.assertTrue(state.get("repeat_seen"), f"зерно: {self.seed}")
                if fault is None:
                    self.assert_stopped(state, signal.SIGTERM)
                else:
                    self.assertIsInstance(state.get("exception"), SystemExit, f"зерно: {self.seed}")
                    self.assertEqual(state["exception"].code, 143, f"зерно: {self.seed}")
                    self.assertFalse(state["removals"], f"зерно: {self.seed}")
                    self.assertTrue(state["clone"].exists(), f"зерно: {self.seed}")
                    self.assertTrue(state["origin"].exists(), f"зерно: {self.seed}")
                for control in state["controls"]:
                    self.assertTrue(self.live(control["pid"]), f"зерно: {self.seed}")
                    self.assertTrue(self.live(control["child"]), f"зерно: {self.seed}")

    def test_ac5_sigterm_before_drive_popen_returns(self):
        """Два независимых прогона прерываются внутри незавершённого Popen.

        Связка команда — реальный клон — новая сессия ОС — удаление:
        ранний сигнал отправлен только после доказательства PID/PGID,
        но до возврата объекта Popen канарейке. Перед первым rmtree
        drive уже должен завершиться, а в успешном исходе исчезают оба каталога.
        Ловит мутацию: убрана защита окна spawn drive до возврата Popen —
        снимок перед первым rmtree содержит живой принадлежащий drive.
        """
        real_popen = subprocess.Popen
        real_rmtree = shutil.rmtree
        for nonce in random.Random(self.seed).sample(range(10000, 99999), 2):
            with self.subTest(seed=self.seed, nonce=nonce):
                seen = {}
                removals = []

                def launch(argv, *args, **kwargs):
                    if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                        return real_popen(argv, *args, **kwargs)
                    clone = Path(kwargs["cwd"])
                    # Переданный канал принадлежит только фикстуре; продукт
                    # сохраняет собственные stdout/stderr, переданные в Popen.
                    read_fd, write_fd = os.pipe()
                    script = ("import os, signal\n"
                              f"os.write({write_fd}, b'{nonce}\\n')\n"
                              f"os.close({write_fd})\n"
                              "signal.pause()\n")
                    try:
                        proc = real_popen([sys.executable, "-c", script],
                                          *args, pass_fds=(write_fd,), **kwargs)
                        self.processes.append(proc)
                    finally:
                        os.close(write_fd)
                    with os.fdopen(read_fd) as ready:
                        self.assertEqual(ready.readline().strip(), str(nonce),
                                         f"зерно: {self.seed}")
                    self.assertEqual(os.getpgid(proc.pid), proc.pid,
                                     f"зерно: {self.seed}")
                    self.assertIsNone(proc.poll(), f"зерно: {self.seed}")
                    seen.update(proc=proc, clone=clone, spawned=True)
                    # Выполняется до return proc: сигнал нельзя переносить
                    # в wait() либо в поток, ожидающий завершения регистрации.
                    os.kill(os.getpid(), signal.SIGTERM)
                    return proc

                def remove(path, *args, **kwargs):
                    path = Path(path)
                    if path.parent == self.temp_root and path.name.startswith("artel-canary-"):
                        removals.append((path, seen.get("proc").poll()
                                         if seen.get("proc") is not None else "not spawned"))
                    return real_rmtree(path, *args, **kwargs)

                with mock.patch.object(Path, "home", return_value=self.home), \
                     mock.patch.object(catalog, "cmd_init"), \
                     mock.patch.object(subprocess, "Popen", launch), \
                     mock.patch.object(shutil, "rmtree", remove):
                    with self.assertRaises(SystemExit) as stopped:
                        capture(lambda: canary.cmd_canary(k=1, sha=self.sha,
                                                          templates=["fixture"]))
                self.assertEqual(stopped.exception.code, 143, f"зерно: {self.seed}")
                self.assertTrue(seen.get("spawned"), f"зерно: {self.seed}")
                self.assertTrue(removals, f"зерно: {self.seed}; нет уборки")
                self.assertIsNotNone(removals[0][1],
                                     f"зерно: {self.seed}; drive={seen['proc'].pid} жив перед rmtree {removals[0][0]}")
                self.assertTrue(any(path == seen["clone"] for path, _ in removals))
                self.assertTrue(any(path.name.startswith("artel-canary-origin-")
                                    for path, _ in removals))
                for path, _ in removals:
                    self.assertFalse(path.exists(), f"зерно: {self.seed}; {path}")

    def test_ac13_owner_marker_precedes_clone(self):
        """Владелец известен уже при входе в каждую операцию клонирования.

        Ловит мутацию: запись маркера перенесена после git clone —
        наблюдение перед запуском clone не находит живого владельца.
        """
        real_run = subprocess.run
        observed = []

        def run(argv, *args, **kwargs):
            if isinstance(argv, (list, tuple)) and "clone" in argv:
                destination = Path(argv[-1])
                # Публичная схема owner marker у корня временного каталога;
                # точное имя внутреннего staging-каталога не утверждается.
                owner_root = next((p for p in (destination, *destination.parents)
                                   if p.parent == self.temp_root
                                   and p.name.startswith("artel-canary-")), None)
                if owner_root is not None:
                    observed.append((owner_root, liveness.owner_pid(owner_root),
                                     liveness.owner_alive(owner_root)))
            return real_run(argv, *args, **kwargs)

        real_popen = subprocess.Popen

        def stop_at_drive(argv, *args, **kwargs):
            if list(argv[:3]) == [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                raise RuntimeError("fixture: clone observed")
            return real_popen(argv, *args, **kwargs)

        with mock.patch.object(Path, "home", return_value=self.home), \
             mock.patch.object(catalog, "cmd_init"), \
             mock.patch.object(subprocess, "run", run), \
             mock.patch.object(subprocess, "Popen", stop_at_drive):
            with self.assertRaisesRegex(RuntimeError, "fixture: clone observed"):
                capture(lambda: canary.cmd_canary(k=1, sha=self.sha, templates=["fixture"]))
        self.assertGreaterEqual(len({p for p, _, _ in observed}), 2,
                                f"зерно: {self.seed}; оба каталога до clone")
        for path, pid, alive in observed:
            self.assertEqual(pid, os.getpid(), f"зерно: {self.seed}; {path}")
            self.assertTrue(alive, f"зерно: {self.seed}; {path}")


class ConsumerGroupsTest(ProcessFixture, RealGitSandbox):
    """Общий механизм в прежних публичных потребителях, с настоящей БД."""

    def seed_task(self, state="in_dev"):
        task = "01" + f"{len(store.all_tasks(store.db())) + 1:024d}"
        store.insert_task(store.db(), task, "Локальный шаг", state,
                          "fixture", config.DEFAULT_TARGET, 1)
        return task

    def consumer(self, path, *, holder_live=True, local=True, has_pgid=True,
                 fix=True, denied=False, terminal=True, has_lease=True,
                 race=None, holder_denied=False, repeat=False):
        conn = store.db()
        if path == "kill" and not terminal:
            if not hasattr(self, "kill_origin"):
                self.kill_origin = self.add_synced_origin()
            _, task = capture_new_task_id(catalog.cmd_new, "Локальная проверка kill")
        else:
            task = self.seed_task("killed" if path == "kill" else "in_dev")
        role, control = self.group("role"), self.group("control")
        holder = self.group("holder", with_child=False) if holder_live else None
        pid = holder["pid"] if holder else _dead_pid()
        if has_lease:
            store.insert_lease(conn, task, "fixture-session", pid,
                               socket.gethostname() if local else "foreign-host.invalid", store.now())
        if has_pgid and has_lease:
            store.update_lease_pgid(conn, task, role["pgid"])
        sent = []
        real_killpg, real_kill, real_locked = os.killpg, os.kill, lease.run_locked
        real_getpgid = os.getpgid
        raced = False
        finished = False

        def locked(*args, **kwargs):
            nonlocal raced
            if race:
                # Вход run_locked следует за исходным наблюдением cmd_kill.
                # Смена экземпляра случается раньше force-перезаписи lease.
                victim = role if race.startswith("group") else holder
                real_killpg(victim["pgid"], signal.SIGKILL)
                self.await_exit(victim)
                raced = True
            return real_locked(*args, **kwargs)

        def kill(target, sig):
            if finished and holder and target == holder["pid"]:
                return real_kill(control["pid"], sig)
            if holder_denied and holder and target == holder["pid"] and sig:
                raise PermissionError("fixture: holder denied")
            if raced and race == "holder-reused" and target == holder["pid"]:
                return real_kill(control["pid"], sig)
            if raced and race == "group-reused" and target == role["pid"]:
                return real_kill(control["pid"], sig)
            return real_kill(target, sig)

        def getpgid(target):
            if raced and race == "holder-reused" and target == holder["pid"]:
                return holder["pgid"]
            if raced and race == "group-reused" and target == role["pid"]:
                return role["pgid"]
            return real_getpgid(target)

        def killpg(pgid, sig):
            sent.append((pgid, sig))
            if finished and pgid == role["pgid"]:
                return real_killpg(control["pgid"], sig)
            if raced and race == "group-reused" and pgid == role["pgid"]:
                return real_killpg(control["pgid"], sig)
            if denied and pgid == role["pgid"] and sig:
                raise PermissionError("fixture: group denied")
            return real_killpg(pgid, sig)

        ticks = iter(range(0, 1000000, 10))
        clock = SimpleNamespace(monotonic=lambda: next(ticks), sleep=lambda _: None)
        with mock.patch.object(os, "killpg", side_effect=killpg), \
             mock.patch.object(os, "kill", side_effect=kill), \
             mock.patch.object(os, "getpgid", side_effect=getpgid), \
             mock.patch.object(lease, "run_locked", side_effect=locked), \
             patch_pult_sleep(lambda _: None), \
             mock.patch.object(liveness, "time", clock), \
             mock.patch.object(pause, "time", clock), \
             mock.patch.object(checkpoint, "commit_pause_now_checkpoint", return_value=""), \
             mock.patch.object(doctor, "all_checks", return_value=[]):
            if path == "kill":
                output = capture(lambda: cleanup.cmd_kill(task, confirmed=True))
                if repeat:
                    before = len(sent)
                    finished = True
                    output += capture(lambda: cleanup.cmd_kill(task, confirmed=True))
                    self.assertFalse(any(sig for _, sig in sent[before:]), f"зерно: {self.seed}")
            elif path == "pause":
                output = capture(pause.cmd_pause_now, task)
            elif path == "release":
                output = capture(release.cmd_release, task)
            else:
                output = capture(lambda: doctor.cmd_doctor(fix=fix))
        details = "\n".join(row["detail"] for row in store.task_steps(conn, task))
        self.assertTrue(self.live(control["pid"]), f"зерно: {self.seed}; {path}")
        self.assertTrue(self.live(control["child"]), f"зерно: {self.seed}; {path}")
        if path == "kill" and holder and race is None:
            if has_lease and local and not holder_denied:
                self.await_exit(holder)
            else:
                self.assertTrue(self.live(holder["pid"]),
                                f"зерно: {self.seed}; holder не допущен к остановке")
        if race:
            self.assertTrue(raced, f"зерно: {self.seed}; гонка не разыграна")
        if holder_denied:
            self.assertTrue(self.live(holder["pid"]), f"зерно: {self.seed}")
        return role, control, sent, output + details

    def assert_group_record(self, text, pgid):
        self.assertIn(str(pgid), text, f"зерно: {self.seed}")
        self.assertRegex(text, r"\b\d+\s+процесс", f"зерно: {self.seed}")

    def test_ac14_public_kill_uses_original_lease_for_both_states(self):
        """Force-перехват не превращает исходный запрещённый lease в допустимый.

        Настоящая БД и публичная команда проходят нетерминальный kill
        и повторный kill; каждый раз роль, потомок и контроль реальны.
        Ловит мутацию: допуск берётся из lease после force — чужой host
        или мёртвый держатель получают сигнал в группу роли.
        """
        for terminal in (False, True):
            for options in ({"local": False}, {"holder_live": False},
                            {"has_lease": False}, {"has_pgid": False}, {}):
                with self.subTest(seed=self.seed, terminal=terminal, options=options):
                    role, _, sent, text = self.consumer("kill", terminal=terminal, **options)
                    if options:
                        self.assertFalse(any(pgid == role["pgid"] and sig for pgid, sig in sent),
                                         f"зерно: {self.seed}; исходный допуск {options}")
                        self.assertTrue(self.live(role["pid"]), f"зерно: {self.seed}")
                        self.assertTrue(self.live(role["child"]), f"зерно: {self.seed}")
                    else:
                        self.await_exit(role)
                        self.assert_group_record(text, role["pgid"])

    def test_ac14_watchdog_kills_descendant_and_records_count(self):
        """Doctor --fix завершает настоящего потомка найденного зависшего прогона.

        Снимок ps/lsof ограничен фикстурами; сигналы и события смерти
        настоящие. Связка doctor — БД — группа ОС — алерт сохраняет счётчик.
        Ловит мутацию: watchdog снимает только лидера — потомок остаётся
        жив; пропуск счётчика убирает число процессов из алерта.
        """
        for denied in (False, True):
            with self.subTest(seed=self.seed, denied=denied):
                task = self.seed_task()
                role, control = self.group("watchdog"), self.group("control")
                work = self.root / ".artel" / "projects" / config.DEFAULT_TARGET / "worktrees" / task
                work.mkdir(parents=True)
                age = int(config.HUNG_TEST_RUN_AGE_SEC) + 1
                minutes, seconds = divmod(age, 60)
                hours, minutes = divmod(minutes, 60)
                real_run, real_killpg = subprocess.run, os.killpg

                def run(argv, *args, **kwargs):
                    if Path(str(argv[0])).name == "ps" and "-axww" in argv:
                        return subprocess.CompletedProcess(argv, 0,
                            f"{role['pid']} {hours}:{minutes:02}:{seconds:02} python -m unittest\n", "")
                    if Path(str(argv[0])).name == "lsof":
                        return subprocess.CompletedProcess(argv, 0, f"n{work}\n", "")
                    return real_run(argv, *args, **kwargs)

                def killpg(pgid, sig):
                    if denied and pgid == role["pgid"] and sig:
                        raise PermissionError("fixture: watchdog denied")
                    return real_killpg(pgid, sig)

                ticks = iter(range(0, 1000000, 10))
                with mock.patch.object(subprocess, "run", side_effect=run), \
                     mock.patch.object(os, "killpg", side_effect=killpg), \
                     mock.patch.object(doctor, "all_checks", return_value=[]), \
                     mock.patch.object(liveness, "time", SimpleNamespace(
                         monotonic=lambda: next(ticks), sleep=lambda _: None)):
                    capture(lambda: doctor.cmd_doctor(fix=True))
                if denied:
                    self.assertTrue(self.live(role["child"]), f"зерно: {self.seed}")
                else:
                    self.await_exit(role)
                self.assertTrue(self.live(control["child"]), f"зерно: {self.seed}")
                messages = "\n".join(row["message"] for row in store.open_alerts(store.db()))
                self.assertIn(str(role["pid"]), messages, f"зерно: {self.seed}")
                self.assertRegex(messages, r"\d+\s+процесс", f"зерно: {self.seed}")

    def test_ac14_kill_rechecks_identity_after_observation(self):
        """Исходное наблюдение устаревает перед force: экземпляр уже завершён.

        ОС возвращает адресуемый номер замены, но kernel monitor прежнего
        экземпляра уже завершён. Чужой контроль не должен получить сигнал.
        Ловит мутацию: kill сохраняет только числовой PID/PGID и проверяет
        его адресуемость — сигнал при reuse попадает в контрольный процесс.
        """
        for terminal in (False, True):
            for race in ("holder-gone", "holder-reused", "group-gone", "group-reused"):
                with self.subTest(seed=self.seed, terminal=terminal, race=race):
                    self.consumer("kill", terminal=terminal, race=race)

    def test_ac14_separate_holder_permission_error_is_contained(self):
        """Отдельный holder не входит в группу роли и может отказать в SIGKILL.

        Ловит мутацию: ошибка отдельного os.kill не перехвачена — публичный
        kill выбрасывает PermissionError вместо завершения команды.
        """
        for terminal in (False, True):
            with self.subTest(seed=self.seed, terminal=terminal):
                role, _, _, text = self.consumer("kill", terminal=terminal, holder_denied=True)
                self.await_exit(role)
                self.assert_group_record(text, role["pgid"])

    def test_ac14_repeated_kill_does_not_signal_reused_numbers(self):
        """После успешного kill старые номера адресуют уже чужую группу и holder.

        Ловит мутацию: повторный kill повторяет сохранённые PID/PGID —
        подмена адреса ОС направляет сигнал реальному контрольному процессу.
        """
        for terminal in (False, True):
            with self.subTest(seed=self.seed, terminal=terminal):
                role, _, _, text = self.consumer("kill", terminal=terminal, repeat=True)
                self.await_exit(role)
                self.assert_group_record(text, role["pgid"])

    def test_ac14_lease_paths_kill_real_group_and_child(self):
        """kill, pause, release и doctor --fix снимают группу с потомком по своему допуску.

        Связка команда — lease в БД — ОС — журнал; посторонняя группа жива.
        Ловит мутацию: один потребитель снимает только держателя/лидера —
        событие завершения потомка не приходит; пропуск записи теряет PGID/счётчик.
        """
        for path, live in (("kill", True), ("pause", True), ("release", True),
                           ("release", False), ("doctor", False)):
            with self.subTest(seed=self.seed, path=path, holder_live=live):
                role, _, _, text = self.consumer(path, holder_live=live)
                self.await_exit(role)
                self.assert_group_record(text, role["pgid"])

    def test_ac14_lease_guards_prevent_group_signals(self):
        """Чужой host, пустой PGID и недопустимая живость держателя не дают сигнал группе.

        Ловит мутацию: пропущен guard host/PGID/fix/живости — осмысленный
        сигнал появляется в перехвате ОС и затрагивает реальную группу.
        """
        cases = [(path, {"local": False}) for path in ("kill", "pause", "release", "doctor")]
        cases += [(path, {"has_pgid": False}) for path in ("kill", "pause", "release", "doctor")]
        cases += [("kill", {"holder_live": False}), ("pause", {"holder_live": False}),
                  ("doctor", {"holder_live": True}),
                  ("doctor", {"holder_live": False, "fix": False})]
        for path, options in cases:
            if path == "doctor":
                options.setdefault("holder_live", False)
            with self.subTest(seed=self.seed, path=path, options=options):
                role, _, sent, _ = self.consumer(path, **options)
                self.assertFalse(any(pgid == role["pgid"] and sig for pgid, sig in sent),
                                 f"зерно: {self.seed}")
                self.assertTrue(self.live(role["pid"]), f"зерно: {self.seed}")
                self.assertTrue(self.live(role["child"]), f"зерно: {self.seed}")

    def test_ac14_permission_error_does_not_escape_lease_consumers(self):
        """Групповой отказ ОС сохраняет прежний возврат каждой команды и запись счётчика.

        Ловит мутацию: PermissionError killpg проброшен из общего примитива —
        команда падает исключением вместо своего результата и журнала.
        """
        for path in ("kill", "pause", "release", "doctor"):
            with self.subTest(seed=self.seed, path=path):
                role, _, sent, text = self.consumer(path, holder_live=path != "doctor", denied=True)
                self.assertTrue(any(pgid == role["pgid"] and sig for pgid, sig in sent),
                                f"зерно: {self.seed}; отказ не разыгран")
                self.assertTrue(self.live(role["pid"]), f"зерно: {self.seed}")
                self.assert_group_record(text, role["pgid"])

    def test_ac14_runner_timeout_kills_group_and_closes_pipe(self):
        """Таймаут шага runner снимает настоящую группу и потомка, сохраняя контроль.

        Связка runner — lease — ОС — журнал проверяется при двух входах.
        При PermissionError фикстура одновременно завершает процесс:
        проверяется прежний возврат потребителя, а не бессрочное ожидание ОС.
        Ловит мутацию: таймаут убивает один PID вместо группы — потомок
        удерживает stdout; либо PermissionError выходит новым исключением,
        либо исчезает PGID и счётчик из журнала.
        """
        for attempt, denied in ((1, False), (max(1, config.AGENT_ATTEMPTS), True)):
            with self.subTest(seed=self.seed, attempt=attempt, denied=denied):
                task = self.seed_task()
                control = self.group("control")
                conn = store.db()
                store.insert_lease(conn, task, "fixture", os.getpid(), socket.gethostname(), store.now())
                spawned = []
                original_spawn = runner.spawn_agent
                real_killpg = os.killpg
                refused = []

                def killpg(pgid, sig):
                    if denied and spawned and pgid == spawned[0]["pgid"] and sig:
                        # Завершение фикстуры при гонке отказа ОС позволяет
                        # прежнему runner дождаться процесса, не меняя таймаут.
                        real_killpg(pgid, signal.SIGKILL)
                        refused.append((pgid, sig))
                        raise PermissionError("fixture: runner group denied")
                    return real_killpg(pgid, sig)

                def spawn(argv, **kwargs):
                    group = self.group("role", spawn=original_spawn, **kwargs)
                    spawned.append(group)
                    proc = group["proc"]
                    real_wait = proc.wait
                    first = True

                    def wait(timeout=None):
                        nonlocal first
                        if first:
                            first = False
                            raise subprocess.TimeoutExpired(argv, timeout)
                        return real_wait(timeout=timeout)

                    proc.wait = wait
                    return proc

                ticks = iter(range(0, 1000000, 10))
                with mock.patch.object(runner, "role_cwd", return_value=self.root), \
                     mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                     mock.patch.object(os, "killpg", side_effect=killpg), \
                     mock.patch.object(liveness, "time", SimpleNamespace(
                         monotonic=lambda: next(ticks), sleep=lambda _: None)):
                    result = runner.run_agent_once(conn, task, "developer", "Локальная роль", attempt)
                self.assertEqual(result[0], "timeout", f"зерно: {self.seed}")
                self.assertEqual(bool(refused), denied, f"зерно: {self.seed}")
                self.assertTrue(spawned, f"зерно: {self.seed}")
                role = spawned[0]
                self.await_exit(role)
                self.assertTrue(role["proc"].stdout.closed, f"зерно: {self.seed}")
                self.assertTrue(self.live(control["pid"]), f"зерно: {self.seed}")
                self.assertTrue(self.live(control["child"]), f"зерно: {self.seed}")
                text = "\n".join(row["detail"] for row in store.task_steps(conn, task))
                self.assert_group_record(text, role["pgid"])
