"""Публичный дозор: уведомления, остановка, захват и отказ в песочнице.

Группа: долгоживущий
Красен до реализации: `watch` не поддерживает `--notify`/`--takeover`,
не сохраняет владельца процесса, не предупреждает о смене пина и не
отказывает в ограниченной среде.
"""

import io
import json
import os
import random
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest import mock

from orchestrator import artel, auto, config, runner, session, store, watch
from tests.sandbox import RealGitSandbox, TaskSeededTmpRootTest, capture


class WatchContractTest(TaskSeededTmpRootTest):
    def setUp(self):
        super().setUp()
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        self.seed = time.time_ns()
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def command(self, *args):
        with mock.patch.object(sys, "argv", ["artel.py", *args]):
            return capture(artel.main)

    def register(self):
        return json.loads(self.command("observe", "register", "--client", "codex",
                                       "--chat", "chat-a", "--tasks", self.TASK))["id"]

    def show(self, observation_id):
        return json.loads(self.command("observe", "show", observation_id))

    def doctor_output(self):
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "doctor"]), \
             redirect_stdout(output):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (None, 0, 1):
                    raise
        return output.getvalue().lower()

    def run_watch(self, observation_id, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            try:
                watch.cmd_watch(["--observation", observation_id,
                                 "--interval", "0.01", *args])
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise
        return output.getvalue()

    def event(self, action="state -> spec_gate", detail=None):
        marker = detail or f"event-{self.rng.randrange(10**9)}"
        store.journal(store.db(), self.TASK, "test", action, marker)
        return marker

    def test_ac5_notifications_target_gate_events_and_survive_failure(self):
        """Значимое событие вызывает уведомление, обычный отказ роли — нет.

        Ловит мутацию: сбой отправки останавливает дозор либо отказ
        «роль ещё не закончила» ошибочно уходит в уведомления.
        """
        observation_id = self.register()
        significant = self.event("state -> spec_gate")
        quiet = self.event("переход отклонён: замечания ревью не отработаны")
        calls = []
        real_run = subprocess.run

        def failed_notice(argv, *args, **kwargs):
            if argv and os.path.basename(str(argv[0])) == "osascript":
                calls.append(argv)
                raise OSError("notification unavailable")
            return real_run(argv, *args, **kwargs)

        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("subprocess.run", side_effect=failed_notice), \
             mock.patch.object(watch.time, "sleep", side_effect=SystemExit(0)):
            output = self.run_watch(observation_id, "--notify")
        self.assertIn(significant, output, self.seed)
        self.assertTrue(calls, f"зерно {self.seed}: уведомление не вызвано")
        self.assertFalse(any(quiet in " ".join(map(str, call)) for call in calls),
                         self.seed)

    def test_ac6_untrusted_text_is_escaped_and_notification_is_separate_arg(self):
        """Управляющий текст печатается безопасно, без внедрения в AppleScript.

        Ловит мутацию: ESC или OSC 52 остаётся в терминальном выводе
        либо кавычка превращает текст в часть сценария `osascript`.
        """
        observation_id = self.register()
        dangerous = 'quote " \x1b]52;c;Y2xpcA==\x07 \x1b[31m'
        self.event("state -> acceptance", dangerous)
        calls = []
        real_run = subprocess.run

        def record(argv, *args, **kwargs):
            if argv and os.path.basename(str(argv[0])) == "osascript":
                calls.append(list(argv))
                return mock.Mock(returncode=0, stdout="", stderr="")
            return real_run(argv, *args, **kwargs)

        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("subprocess.run", side_effect=record), \
             mock.patch.object(watch.time, "sleep", side_effect=SystemExit(0)):
            output = self.run_watch(observation_id, "--notify")
        self.assertNotIn("\x1b", output, self.seed)
        self.assertNotIn("\x07", output, self.seed)
        self.assertTrue(calls, self.seed)
        self.assertTrue(any(dangerous in arg for call in calls for arg in call[1:]),
                        self.seed)
        self.assertFalse(any(dangerous in str(call[1]) for call in calls
                             if len(call) > 1), self.seed)

    def test_ac6_non_macos_notification_uses_one_output_line(self):
        """Вне macOS уведомление заменяется одной читаемой строкой.

        Ловит мутацию: fallback печатает несколько строк для одного
        события или пытается вызвать `osascript` на чужой платформе.
        """
        observation_id = self.register()
        marker = self.event("state -> merge_gate")
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("subprocess.run") as process, \
             mock.patch.object(watch.time, "sleep", side_effect=SystemExit(0)):
            output = self.run_watch(observation_id, "--notify")
        notice_lines = [line for line in output.splitlines()
                        if "уведом" in line.lower()]
        self.assertEqual(len(notice_lines), 1, f"зерно {self.seed}: {output}")
        self.assertIn(marker, output, self.seed)
        self.assertFalse(any("osascript" in str(call) for call in process.call_args_list),
                         self.seed)

    def test_ac7_show_and_doctor_distinguish_process_states(self):
        """Диагностика различает живую связь и запись без живого PID.

        Ловит мутацию: мёртвый PID показывается как живой или свежая
        связь без PID ошибочно объявляется работающим процессом.
        """
        observation_id = self.register()
        store.touch_observation(store.db(), observation_id)
        fresh = json.dumps(self.show(observation_id), ensure_ascii=False).lower()
        doctor_fresh = self.doctor_output()
        conn = store.db()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(observations)")]
        pid_columns = [name for name in columns if name == "pid" or name.endswith("_pid")]
        self.assertTrue(pid_columns, f"зерно {self.seed}: наблюдение не хранит PID")
        host = next(name for name in columns if "host" in name)
        started = next(name for name in columns
                       if "start" in name and name not in ("created_at",))
        with conn:
            conn.execute(f'UPDATE observations SET "{pid_columns[0]}"=?, '
                         f'"{host}"=?, "{started}"=? WHERE id=?',
                         (os.getpid(), socket.gethostname(),
                          datetime.now(timezone.utc).isoformat(), observation_id))
        live = json.dumps(self.show(observation_id), ensure_ascii=False).lower()
        doctor_live = self.doctor_output()
        dead_pid = 1_000_000_000 + self.rng.randrange(100_000_000)
        with conn:
            conn.execute(f'UPDATE observations SET "{pid_columns[0]}"=? WHERE id=?',
                         (dead_pid, observation_id))
        dead = json.dumps(self.show(observation_id), ensure_ascii=False).lower()
        doctor_dead = self.doctor_output()
        self.assertNotEqual(fresh, live, self.seed)
        self.assertNotEqual(dead, live, self.seed)
        self.assertTrue(any(word in live for word in ("alive", "running", "жив")),
                        f"зерно {self.seed}: нет признака живого процесса")
        self.assertTrue(any(word in dead for word in ("dead", "stale", "мёртв", "мертв")),
                        f"зерно {self.seed}: нет признака мёртвого PID")
        self.assertTrue(any(word in fresh for word in ("fresh", "свеж")),
                        f"зерно {self.seed}: нет признака свежей связи")
        for label, output, words in (
                ("fresh", doctor_fresh, ("fresh", "свеж")),
                ("live", doctor_live, ("alive", "running", "жив")),
                ("dead", doctor_dead, ("dead", "мёртв", "мертв"))):
            with self.subTest(label=label):
                diagnostic = "\n".join(line for line in output.splitlines()
                                       if "наблюден" in line or "observation" in line)
                self.assertTrue(any(word in diagnostic for word in words),
                                f"зерно {self.seed}: doctor не показал {label}")

    def test_ac8_stop_exits_on_next_poll_clears_pid(self):
        """Остановка завершается кодом ноль и очищает PID.

        Ловит мутацию: `observe stop` оставляет PID или дозор продолжает
        опрос после остановки наблюдения.
        """
        observation_id = self.register()
        ticks = 0

        def on_sleep(_):
            nonlocal ticks
            ticks += 1
            if ticks == 1:
                self.command("observe", "stop", observation_id)
            elif ticks > 2:
                raise AssertionError("дозор не остановлен к следующему опросу")

        with mock.patch.object(watch.time, "sleep", side_effect=on_sleep):
            self.run_watch(observation_id)
        self.assertEqual(ticks, 1, self.seed)
        self.assertIsNone(self.show(observation_id).get("pid"), self.seed)

    def test_ac9_codex_sandbox_refuses_run_auto_and_warns_no_notification(self):
        """Ограниченная среда отказывает до запуска роли; дозор предупреждает.

        Ловит мутацию: `run` или `auto` начинают шаг из среды Codex без сети,
        либо дозор без уведомлений молчит.
        """
        env = {"CODEX_SANDBOX": "workspace-write",
               "CODEX_SANDBOX_NETWORK_DISABLED": "1",
               config.ARTEL_ROLE_ENV: ""}
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(runner, "cmd_run_and_advance") as run, \
             mock.patch.object(auto, "cmd_auto") as auto_call:
            for command in ("run", "auto"):
                with self.subTest(command=command):
                    with self.assertRaises(SystemExit) as refusal:
                        self.command(command, self.TASK, "--attach")
                    self.assertIn("песочниц", str(refusal.exception).lower(), self.seed)
            run.assert_not_called()
            auto_call.assert_not_called()
        observation_id = self.register()
        with mock.patch.object(watch.time, "sleep", side_effect=SystemExit(0)):
            output = self.run_watch(observation_id)
        self.assertIn("уведомлен", output.lower(), self.seed)

    def test_ac11_live_owner_refuses_and_takeover_finishes_old_watch(self):
        """Живой владелец блокирует второй дозор до явного перехвата.

        Ловит мутацию: второй дозор молча берёт активное наблюдение либо
        прежний продолжает двигать позицию после `--takeover`.
        """
        observation_id = self.register()
        old_waiting = threading.Event()
        new_claimed = threading.Event()
        old_done = threading.Event()
        real_pid = os.getpid()
        output = io.StringIO()
        old_polls = 0

        def process_pid():
            return getattr(threading.current_thread(), "watch_pid", real_pid)

        def no_real_sleep(_):
            nonlocal old_polls
            if process_pid() == real_pid:
                old_polls += 1
                if old_polls > 1:
                    raise AssertionError("старый дозор не завершился после перехвата")
                old_waiting.set()
                self.assertTrue(new_claimed.wait(5), f"зерно {self.seed}: нет перехвата")
            elif process_pid() == real_pid + 2:
                raise AssertionError("второй дозор не отказал живому владельцу")
            else:
                new_claimed.set()
                self.assertTrue(old_done.wait(5), f"зерно {self.seed}: старый дозор не вышел")
                raise SystemExit(0)

        def worker(takeover, pid):
            threading.current_thread().watch_pid = pid
            try:
                watch.cmd_watch(["--observation", observation_id,
                                 "--interval", "0.01", *(["--takeover"] if takeover else [])])
                return 0
            except SystemExit as exc:
                return exc.code

        with mock.patch("os.getpid", side_effect=process_pid), \
             mock.patch.object(watch.time, "sleep", side_effect=no_real_sleep), \
             redirect_stdout(output), ThreadPoolExecutor(max_workers=2) as pool:
            old = pool.submit(worker, False, real_pid)
            self.assertTrue(old_waiting.wait(5), f"зерно {self.seed}: первый дозор не начал опрос")
            threading.current_thread().watch_pid = real_pid + 2
            try:
                with self.assertRaises(SystemExit) as refusal:
                    watch.cmd_watch(["--observation", observation_id])
                self.assertIn("--takeover", str(refusal.exception), self.seed)
            finally:
                del threading.current_thread().watch_pid
            new = pool.submit(worker, True, real_pid + 1)
            self.assertTrue(new_claimed.wait(5), f"зерно {self.seed}: перехват не начат")
            try:
                self.assertEqual(old.result(timeout=5), 0, self.seed)
            finally:
                old_done.set()
            self.assertEqual(new.result(timeout=5), 0, self.seed)
        self.assertIn("дозор перехвачен", output.getvalue(), self.seed)
        self.assertIn(str(real_pid), output.getvalue(), self.seed)

    def test_ac11_dead_own_and_foreign_owner_rules(self):
        """Мёртвый и свой PID захватываются, чужой хост требует `--takeover`.

        Ловит мутацию: обычный дозор забирает запись чужого хоста либо
        отвергает безопасный перехват мёртвого или собственного PID.
        """
        observation_id = self.register()
        columns = [row[1] for row in store.db().execute(
            "PRAGMA table_info(observations)")]
        pid = next(name for name in columns if name == "pid" or name.endswith("_pid"))
        host = next(name for name in columns if "host" in name)
        started = next(name for name in columns
                       if "start" in name and name not in ("created_at",))

        def owner(pid_value, host_value):
            conn = store.db()
            with conn:
                conn.execute(f'UPDATE observations SET "{pid}"=?, "{host}"=?, '
                             f'"{started}"=? WHERE id=?',
                             (pid_value, host_value,
                              datetime.now(timezone.utc).isoformat(), observation_id))

        for pid_value in (1_000_000_000 + self.rng.randrange(100_000_000),
                          os.getpid()):
            with self.subTest(pid=pid_value):
                owner(pid_value, socket.gethostname())
                ticks = []

                def mark_poll(_):
                    ticks.append(1)
                    raise SystemExit(0)

                with mock.patch.object(watch.time, "sleep",
                                       side_effect=mark_poll):
                    self.run_watch(observation_id)
                self.assertEqual(len(ticks), 1, self.seed)

        foreign_pid = 42
        foreign_host = "remote.example.invalid"
        owner(foreign_pid, foreign_host)
        with self.assertRaises(SystemExit) as refusal:
            self.run_watch(observation_id)
        self.assertIn("--takeover", str(refusal.exception), self.seed)
        with mock.patch.object(watch.time, "sleep", side_effect=SystemExit(0)):
            output = self.run_watch(observation_id, "--takeover")
        self.assertIn(str(foreign_pid), output, self.seed)
        self.assertIn(foreign_host, output, self.seed)

    def test_ac12_empty_and_terminal_observation_runs_until_stop(self):
        """Пустой и завершённый набор не прекращают дозор сами.

        Ловит мутацию: цикл считает пустую выборку или `done` условием
        завершения и не доходит до вызова остановки.
        """
        observation_id = self.register()
        self.command("observe", "remove", observation_id, "--tasks", self.TASK)
        for state in ("empty", "terminal"):
            with self.subTest(state=state):
                if state == "terminal":
                    self.command("observe", "add", observation_id,
                                 "--tasks", self.TASK)
                    conn = store.db()
                    conn.execute("UPDATE tasks SET state='done' WHERE id=?", (self.TASK,))
                    conn.commit()
                ticks = 0

                def stop_after_first_poll(_):
                    nonlocal ticks
                    ticks += 1
                    self.command("observe", "stop", observation_id)

                with mock.patch.object(watch.time, "sleep", side_effect=stop_after_first_poll):
                    self.run_watch(observation_id)
                self.assertEqual(ticks, 1, self.seed)
                if state == "empty":
                    observation_id = self.register()


class PinChangeContractTest(RealGitSandbox):
    def test_ac8_pin_change_warns_to_restart_watch(self):
        """Смена HEAD главной копии между опросами вызывает предупреждение.

        Ловит мутацию: дозор запоминает пин только при старте и молчит,
        когда HEAD главной копии сдвинулся до следующего опроса.
        """
        seed = time.time_ns()
        print(f"зерно: {seed}")
        token = f"pin-{random.Random(seed).randrange(10**9)}"
        store.insert_task(store.db(), "T001", "Задача", "in_dev", "task/t001",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        observation_id = store.register_observation(
            store.db(), config.DEFAULT_TARGET, "codex", "chat-a",
            session.resolve_session_id(None), ["T001"])
        ticks = 0

        def move_head(_):
            nonlocal ticks
            ticks += 1
            if ticks == 1:
                (self.root / f"{token}.txt").write_text(token, encoding="utf-8")
                self.git("add", f"{token}.txt")
                self.git("commit", "-q", "-m", "pin moved")
            else:
                store.stop_observation(store.db(), observation_id)

        with mock.patch.object(watch.time, "sleep", side_effect=move_head):
            output = capture(watch.cmd_watch, ["--observation", observation_id,
                                               "--interval", "0.01"])
        self.assertEqual(ticks, 2, f"зерно {seed}")
        self.assertIn("перезапус", output.lower(), f"зерно {seed}")
