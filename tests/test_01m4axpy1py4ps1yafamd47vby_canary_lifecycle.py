"""Уборка процессов клона и запись исхода сигнала через публичную команду канарейки.
Группа: долгоживущий
Красен до реализации: канарейка не снимает отвязанный suite-run и не записывает исход SIGTERM/SIGHUP.
"""

import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

from orchestrator import canary, catalog, config, store
from tests.sandbox import ALL_CONFIG_ATTRS, RealGitSandbox, capture


_CHILD = r'''
import json, os, signal, subprocess, sys
from pathlib import Path
from unittest import mock
from orchestrator import artel, canary, catalog, config, runner
settings = json.loads(Path(sys.argv[1]).read_text())
for name, value in settings["config"].items():
    setattr(config, name, Path(value))
real_popen = subprocess.Popen
def launch(argv, *args, **kwargs):
    if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
        return real_popen(argv, *args, **kwargs)
    clone = Path(kwargs["cwd"])
    suite = real_popen([sys.executable, "-c", "import time; time.sleep(90)"],
                       cwd=clone, start_new_session=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run = config.LOGS / "suite-run" / "fixture" / "run.json"
    run.parent.mkdir(parents=True, exist_ok=True)
    run.write_text(json.dumps({"pid": suite.pid}))
    origin = subprocess.run(["git", "remote", "get-url", "origin"],
                            cwd=clone, capture_output=True, text=True).stdout.strip()
    drive = real_popen([sys.executable, "-c", "import time; time.sleep(90)"],
                       *args, **kwargs)
    Path(settings["observation"]).write_text(json.dumps({
        "clone": str(clone), "origin": origin, "suite_pid": suite.pid,
        "drive_pid": drive.pid}))
    return drive
with mock.patch.object(Path, "home", return_value=Path(settings["home"])), \
     mock.patch.object(catalog, "cmd_init"), \
     mock.patch.object(subprocess, "Popen", launch), \
     mock.patch.object(runner, "in_role_environment", return_value=False):
    sys.argv = ["artel.py", "canary", "--k", "1", "--sha", settings["sha"],
                "--template", "fixture"]
    artel.main()
'''


class CanaryLifecycleTest(RealGitSandbox):
    """Реальный локальный клон и подменённое ведение без ролей."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.temp_root = self.root / ".artel" / "canary-test-tmp"
        self.temp_root.mkdir(parents=True)
        temp_patch = mock.patch.object(tempfile, "tempdir", str(self.temp_root))
        temp_patch.start()
        self.addCleanup(temp_patch.stop)
        env_patch = mock.patch.dict(os.environ, {"TMPDIR": str(self.temp_root)})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        entry = self.root / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# вход заменён процессом теста\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixture drive")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.home = Path(tempfile.mkdtemp(prefix="canary-fixture-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        (pool / "fixture.md").write_text("# учебная задача\n", encoding="utf-8")
        self.suite_pids = []
        self.suite_procs = {}
        self.drive_pids = []
        self.clone_paths = []
        self.addCleanup(self.stop_suites)

    def stop_suites(self):
        for pid in self.suite_pids + self.drive_pids:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        for proc in self.suite_procs.values():
            proc.wait(timeout=5)
        for path in self.clone_paths:
            shutil.rmtree(path, ignore_errors=True)

    def alive(self, pid):
        if pid in self.suite_procs:
            return self.suite_procs[pid].poll() is None
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def launch_signalled(self, signum):
        observation = self.home / f"observation-{signum}.json"
        settings = self.home / f"settings-{signum}.json"
        settings.write_text(json.dumps({
            "config": {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS},
            "home": str(self.home), "sha": self.sha,
            "observation": str(observation),
        }))
        child = subprocess.Popen([sys.executable, "-c", _CHILD, str(settings)],
                                 cwd=Path(__file__).resolve().parents[1],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True,
                                 start_new_session=True)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        deadline = time.monotonic() + 20
        while not observation.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if not observation.exists():
            self.fail(f"зерно: {self.seed}; child: {child.communicate(timeout=2)}")
        state = json.loads(observation.read_text())
        self.suite_pids.append(state["suite_pid"])
        self.drive_pids.append(state["drive_pid"])
        self.clone_paths.extend([Path(state["clone"]), Path(state["origin"])])
        os.kill(child.pid, signum)
        stdout, stderr = child.communicate(timeout=20)
        return state, stdout, stderr

    def assert_signal_cleanup(self, signum):
        state, stdout, stderr = self.launch_signalled(signum)
        self.assertFalse(Path(state["clone"]).exists(),
                         f"зерно: {self.seed}; {stdout}; {stderr}")
        self.assertFalse(Path(state["origin"]).exists(),
                         f"зерно: {self.seed}; {stdout}; {stderr}")
        self.assertFalse(self.alive(state["suite_pid"]),
                         f"зерно: {self.seed}; suite pid={state['suite_pid']}")
        self.assertFalse(self.alive(state["drive_pid"]),
                         f"зерно: {self.seed}; drive pid={state['drive_pid']}")
        return state

    def test_ac1_sigterm_cleans_clone_origin_and_both_process_groups(self):
        """SIGTERM обрывает ожидание подменённого ведения и убирает оба каталога и оба процесса.

        Ловит мутацию: обработчик сигнала удаляет клон, но забывает группу suite-run — её pid остаётся жив.
        """
        self.assert_signal_cleanup(signal.SIGTERM)

    def test_ac2_sighup_cleans_clone_origin_and_both_process_groups(self):
        """SIGHUP во время ведения даёт ту же наблюдаемую уборку, что SIGTERM.

        Ловит мутацию: обработчик установлен только для SIGTERM — после SIGHUP остаются процессы и каталоги.
        """
        self.assert_signal_cleanup(signal.SIGHUP)

    def test_ac3_signal_records_non_green_existing_verdict(self):
        """Строка каждого оборванного прогона называет сигнал и не получает зелёный вердикт.

        Ловит мутацию: после сигнала процессы снимаются, но строка прогона не записывается в БД пульта.
        """
        existing = {"green", "red", "ceiling"}
        for signum in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signal.Signals(signum).name):
                self.launch_signalled(signum)
                rows = store.all_canary_runs(store.db())
                self.assertTrue(rows, f"зерно: {self.seed}")
                row = rows[-1]
                note = " ".join(str(row[key] or "") for key in
                                ("outcome", "kill_note") if key in row.keys())
                self.assertIn("оборвана сигналом", note, f"зерно: {self.seed}; {dict(row)}")
                self.assertIn(signal.Signals(signum).name, note,
                              f"зерно: {self.seed}; {dict(row)}")
                self.assertNotEqual(row["verdict"], "green")
                self.assertIn(row["verdict"], existing)

    def test_ac4_suite_run_stops_on_normal_timeout_and_exception(self):
        """Подменённый suite-run снимается при трёх способах окончания ведения.

        Ловит мутацию: уборка suite-run привязана только к сигналу — при штатном выходе, таймауте или исключении процесс жив.
        """
        real_popen = subprocess.Popen
        for outcome in ("normal", "timeout", "exception"):
            with self.subTest(outcome=outcome):
                seen = {}

                def launch(argv, *args, **kwargs):
                    if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                        return real_popen(argv, *args, **kwargs)
                    clone = Path(kwargs["cwd"])
                    suite = real_popen([sys.executable, "-c", "import time; time.sleep(90)"],
                                       cwd=clone, start_new_session=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.suite_pids.append(suite.pid)
                    self.suite_procs[suite.pid] = suite
                    run = config.LOGS / "suite-run" / "fixture" / "run.json"
                    run.parent.mkdir(parents=True, exist_ok=True)
                    run.write_text(json.dumps({"pid": suite.pid}))
                    seen["suite"] = suite.pid
                    if outcome == "exception":
                        raise RuntimeError("подменённое ведение оборвалось")
                    result = Path(argv[argv.index("--result") + 1])
                    result.write_text(json.dumps({
                        "task_id": "01FIXTURE", "head": self.sha,
                        "outcome": "killed", "escalated": False,
                        "metrics": {"steps": 1, "cost_usd": 0.0,
                                    "review_iterations": 0, "escalations": [],
                                    "dev_retries": 0, "outcome": "killed",
                                    "kill_note": "штатно", "test_author_visited": False,
                                    "ceiling_exhausted": False, "ceiling_raise": None},
                        "steps": [],
                    }))
                    script = "import time; time.sleep(90)" if outcome == "timeout" else "pass"
                    return real_popen([sys.executable, "-c", script], *args, **kwargs)

                with mock.patch.object(Path, "home", return_value=self.home), \
                     mock.patch.object(catalog, "cmd_init"), \
                     mock.patch.object(subprocess, "Popen", launch), \
                     mock.patch.object(canary, "CANARY_DRIVE_TIMEOUT_SEC", 0.1):
                    if outcome == "exception":
                        with self.assertRaises(RuntimeError):
                            capture(lambda: canary.cmd_canary(k=1, sha=self.sha,
                                                               templates=["fixture"]))
                    else:
                        capture(lambda: canary.cmd_canary(k=1, sha=self.sha,
                                                           templates=["fixture"]))
                self.assertIn("suite", seen, f"зерно: {self.seed}")
                self.assertFalse(self.alive(seen["suite"]),
                                 f"зерно: {self.seed}; {outcome}: {seen}")

    def test_ac5_live_clone_contains_owner_pid_marker(self):
        """Во время подменённого ведения в клоне читается маркер с pid канарейки.

        Ловит мутацию: маркер пишется после окончания ведения — во время работы pid в клоне отсутствует.
        """
        real_popen = subprocess.Popen
        seen = []

        def launch(argv, *args, **kwargs):
            if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                return real_popen(argv, *args, **kwargs)
            clone = Path(kwargs["cwd"])
            for path in clone.rglob("*"):
                if path.is_file() and ".git" not in path.parts:
                    try:
                        content = path.read_text(encoding="utf-8")
                        if len(content) < 1024 and re.search(
                                rf"(?<!\d){os.getpid()}(?!\d)", content):
                            seen.append(path)
                    except (OSError, UnicodeError):
                        pass
            raise RuntimeError("остановка после наблюдения маркера")

        with mock.patch.object(Path, "home", return_value=self.home), \
             mock.patch.object(catalog, "cmd_init"), \
             mock.patch.object(subprocess, "Popen", launch):
            with self.assertRaises(RuntimeError):
                capture(lambda: canary.cmd_canary(k=1, sha=self.sha,
                                                   templates=["fixture"]))
        self.assertTrue(seen, f"зерно: {self.seed}; pid={os.getpid()}")
