"""Сигнал остановки в раннем окне запуска процесса ведения канарейки.

Группа: долгоживущий
Красен до реализации: сигнал, пришедший до присваивания `proc` в `_drive_in_clone`, уходит наверх мимо защищённого ожидания — процесс ведения остаётся жив (AC-1, AC-2), а сигнал до создания процесса ведения обрывает команду раньше, чем ведение вообще создано (AC-3); методы AC-4, AC-5, AC-8, AC-11 держат поведение, которое на базе уже такое.

Команда канарейки запускается настоящей публичной командой `artel.py canary`
в отдельном процессе (своя сессия) на настоящем локальном клоне; процесс
ведения и suite — настоящие процессы в своих группах, подменён только
`subprocess.Popen` для argv процесса ведения. Сигнал доставляется
воздействием (`os.kill` самому командному процессу) в установленной точке
подменённого `Popen`, без пауз.
"""

import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from orchestrator import canary, catalog, config, store
from tests.sandbox import (ALL_CONFIG_ATTRS, RealGitSandbox, capture,
                           wait_processes_gone)


_EARLY_CHILD = r'''
import json, os, signal, subprocess, sys
from pathlib import Path
from unittest import mock
from orchestrator import artel, canary, catalog, config, runner
settings = json.loads(Path(sys.argv[1]).read_text())
for name, value in settings["config"].items():
    setattr(config, name, Path(value))
signal.signal(signal.SIGTERM, signal.SIG_DFL)
signal.signal(signal.SIGHUP, signal.SIG_DFL)
if settings["sigint"] == "default":
    signal.signal(signal.SIGINT, signal.default_int_handler)
elif settings["sigint"] == "ignore":
    signal.signal(signal.SIGINT, signal.SIG_IGN)
mode = settings["mode"]
signum = settings["signum"]
observation = Path(settings["observation"])
seen = {}
def note(**fields):
    seen.update(fields)
    observation.write_text(json.dumps(seen))
DRIVE = (
    "import json, os, signal, sys, time\n"
    "fd = int(sys.argv[1])\n"
    "report = {name: signal.getsignal(getattr(signal, name)) == signal.SIG_IGN\n"
    "          for name in ('SIGTERM', 'SIGHUP')}\n"
    "os.write(fd, json.dumps(report).encode())\n"
    "os.close(fd)\n"
    "if sys.argv[2] == 'long':\n"
    "    time.sleep(90)\n")
real_popen = subprocess.Popen
def group_of(pid):
    try:
        return os.getpgid(pid)
    except OSError:
        return pid
def start_suite(clone):
    suite = real_popen([sys.executable, "-c", "import time; time.sleep(90)"],
                       cwd=clone, start_new_session=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    note(suite_pid=suite.pid, suite_pgid=group_of(suite.pid))
    run = config.LOGS / "suite-run" / settings["template"] / "run.json"
    run.parent.mkdir(parents=True, exist_ok=True)
    run.write_text(json.dumps({"pid": suite.pid}))
    return suite
def start_drive(args, kwargs):
    read_end, write_end = os.pipe()
    kwargs = dict(kwargs)
    kwargs["pass_fds"] = tuple(kwargs.get("pass_fds", ())) + (write_end,)
    drive = real_popen([sys.executable, "-c", DRIVE, str(write_end), settings["drive"]],
                       *args, **kwargs)
    os.close(write_end)
    note(drive_pid=drive.pid, drive_pgid=group_of(drive.pid))
    report = b""
    while True:
        chunk = os.read(read_end, 4096)
        if not chunk:
            break
        report += chunk
    os.close(read_end)
    note(drive_ignored=json.loads(report) if report else None)
    return drive
def deliver():
    note(sigint_ignored_at_delivery=signal.getsignal(signal.SIGINT) == signal.SIG_IGN,
         delivered=True)
    os.kill(os.getpid(), signum)
def launch(argv, *args, **kwargs):
    if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
        return real_popen(argv, *args, **kwargs)
    clone = Path(kwargs["cwd"])
    origin = subprocess.run(["git", "remote", "get-url", "origin"],
                            cwd=clone, capture_output=True, text=True).stdout.strip()
    note(clone=str(clone), origin=origin)
    if mode in ("raise_oserror", "raise_runtime"):
        if signum:
            deliver()
        error = OSError if mode == "raise_oserror" else RuntimeError
        raise error(settings["error"])
    suite = start_suite(clone)
    if mode == "before_fork":
        deliver()
        return start_drive(args, kwargs)
    drive = start_drive(args, kwargs)
    if mode == "after_fork_raise":
        raise RuntimeError(settings["error"])
    note(alive_before_signal={"suite": suite.poll() is None,
                              "drive": drive.poll() is None})
    if signum:
        deliver()
    return drive
with mock.patch.object(Path, "home", return_value=Path(settings["home"])), \
     mock.patch.object(catalog, "cmd_init"), \
     mock.patch.object(subprocess, "Popen", launch), \
     mock.patch.object(runner, "in_role_environment", return_value=False):
    sys.argv = ["artel.py", "canary", "--k", "1", "--sha", settings["sha"],
                "--template", settings["template"]]
    artel.main()
'''


def living_processes() -> list[tuple[int, int]]:
    """(pid, pgid) всех живых процессов системы; зомби живыми не считаются."""
    search = os.pathsep.join([os.environ.get("PATH", ""), "/bin", "/usr/bin"])
    res = subprocess.run([shutil.which("ps", path=search) or "ps",
                          "-A", "-o", "pid=,pgid=,stat="],
                         capture_output=True, text=True, timeout=30, check=True)
    rows = []
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[2].startswith("Z"):
            continue
        rows.append((int(parts[0]), int(parts[1])))
    return rows


def pid_alive(pid: int) -> bool:
    return any(p == pid for p, _g in living_processes())


def group_alive(pgid: int) -> bool:
    return any(g == pgid for _p, g in living_processes())


class EarlySignalCanaryTest(RealGitSandbox):
    """Связка «команда canary — клон — группы процессов — БД пульта»."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.template = f"fixture{self.rng.randrange(10 ** 6)}"
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
        self.home = Path(tempfile.mkdtemp(prefix="canary-early-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        (pool / f"{self.template}.md").write_text("# учебная задача\n", encoding="utf-8")
        self.launches = 0

    def why(self, *extra) -> str:
        return "; ".join([f"зерно: {self.seed}"] + [str(e) for e in extra])

    def reap_observed(self, observation: Path) -> None:
        """Уборка теста: снять и дождаться выживших групп ведения и suite."""
        if not observation.exists():
            return
        state = json.loads(observation.read_text())
        groups = {state[key] for key in ("drive_pgid", "suite_pgid") if state.get(key)}
        for pgid in groups:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        wait_processes_gone(groups, group_alive, polls=200, pause=0.05)
        for key in ("clone", "origin"):
            if state.get(key):
                shutil.rmtree(state[key], ignore_errors=True)

    def run_early(self, mode, signum=None, *, sigint="default", drive="long",
                  error="подменённый Popen"):
        """Команда canary в своём процессе; возвращает (код, наблюдение, stdout, stderr)."""
        self.launches += 1
        observation = self.home / f"observation-{self.launches}.json"
        settings = self.home / f"settings-{self.launches}.json"
        settings.write_text(json.dumps({
            "config": {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS},
            "home": str(self.home), "sha": self.sha, "template": self.template,
            "observation": str(observation), "mode": mode,
            "signum": int(signum) if signum else None,
            "sigint": sigint, "drive": drive, "error": error,
        }))
        self.addCleanup(self.reap_observed, observation)
        child = subprocess.Popen([sys.executable, "-c", _EARLY_CHILD, str(settings)],
                                 cwd=Path(__file__).resolve().parents[1],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, start_new_session=True)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        stdout, stderr = child.communicate(timeout=60)
        state = json.loads(observation.read_text()) if observation.exists() else {}
        print(f"наблюдение: {json.dumps(state)}")
        return child.returncode, state, stdout, stderr

    def rows(self):
        return list(store.all_canary_runs(store.db()))

    def assert_dirs_removed(self, state, stdout, stderr):
        self.assertTrue(state.get("clone"), self.why(state, stdout, stderr))
        self.assertFalse(Path(state["clone"]).exists(),
                         self.why("клон не удалён", state, stdout, stderr))
        self.assertTrue(state.get("origin"), self.why(state, stdout, stderr))
        self.assertFalse(Path(state["origin"]).exists(),
                         self.why("origin не удалён", state, stdout, stderr))

    def assert_signal_row(self, signum, before, stdout, stderr):
        rows = self.rows()
        self.assertGreater(len(rows), before, self.why("строки прогона нет", stdout, stderr))
        row = rows[-1]
        name = signal.Signals(signum).name
        self.assertIn(f"оборвана сигналом {name}", str(row["outcome"] or ""),
                      self.why(dict(row), stdout, stderr))
        self.assertNotEqual(row["verdict"], "green", self.why(dict(row)))

    def test_ac1_sigterm_sighup_in_early_window_stop_drive_and_record_signal(self):
        """SIGTERM и SIGHUP, пришедшие после создания ведения до возврата `Popen`.

        Подменённый `Popen` создаёт suite и настоящий долгоживущий процесс
        ведения в своей группе, убеждается, что оба живы, и посылает сигнал
        командному процессу до `return`. После исхода процесс ведения не жив,
        клон и origin удалены, последняя строка прогона — «оборвана сигналом
        <имя>» с вердиктом не `green`, код выхода `128 + номер`.

        Ловит мутацию: откладывающий обработчик не ставится (или отложенный сигнал поднимается уже после выхода из защищённого ожидания) — исключение уходит мимо `terminate_process_group`, и pid ведения после выхода команды остаётся жив.
        """
        signums = [signal.SIGTERM, signal.SIGHUP]
        self.rng.shuffle(signums)
        for signum in signums:
            with self.subTest(signal=signal.Signals(signum).name):
                before = len(self.rows())
                code, state, stdout, stderr = self.run_early("after_fork", signum)
                name = signal.Signals(signum).name
                self.assertIn("drive_pid", state, self.why(name, stdout, stderr))
                self.assertFalse(pid_alive(state["drive_pid"]),
                                 self.why(f"{name}: процесс ведения жив",
                                          f"drive pid={state['drive_pid']}", stderr))
                self.assertEqual(state.get("alive_before_signal"),
                                 {"suite": True, "drive": True},
                                 self.why(name, "до сигнала ведение и suite обязаны жить", state))
                self.assert_dirs_removed(state, stdout, stderr)
                self.assert_signal_row(signum, before, stdout, stderr)
                self.assertEqual(code, 128 + int(signum), self.why(name, stdout, stderr))

    def test_ac2_sigint_in_early_window_stops_drive_without_run_row(self):
        """SIGINT с восстановленным `default_int_handler` в той же точке окна.

        Дочерний процесс теста до запуска команды ставит обработчик SIGINT по
        умолчанию; подменённый `Popen` посылает SIGINT после создания ведения.
        После исхода процесс ведения не жив, клон и origin удалены, новой
        строки прогона нет.

        Ловит мутацию: откладывание охватывает только SIGTERM/SIGHUP — `KeyboardInterrupt` вылетает из `Popen` мимо защищённого ожидания, и pid ведения остаётся жив.
        """
        before = len(self.rows())
        _code, state, stdout, stderr = self.run_early("after_fork", signal.SIGINT,
                                                      sigint="default")
        self.assertIn("drive_pid", state, self.why(stdout, stderr))
        self.assertFalse(pid_alive(state["drive_pid"]),
                         self.why("SIGINT: процесс ведения жив",
                                  f"drive pid={state['drive_pid']}", stderr))
        self.assertEqual(state.get("alive_before_signal"), {"suite": True, "drive": True},
                         self.why("до сигнала ведение и suite обязаны жить", state))
        self.assert_dirs_removed(state, stdout, stderr)
        self.assertEqual(len(self.rows()), before,
                         self.why("SIGINT не пишет строку прогона",
                                  [dict(r) for r in self.rows()]))

    def test_ac3_signal_before_drive_creation_does_not_leave_ignored_signals(self):
        """SIGTERM до создания процесса ведения внутри подменённого `Popen`.

        Подменённый `Popen` посылает SIGTERM и только потом создаёт ведение;
        ведение само сообщает через канал, игнорирует ли оно SIGTERM/SIGHUP.
        Ожидается: ни один не `SIG_IGN`, после исхода ведение не живо, клон и
        origin удалены, строка «оборвана сигналом SIGTERM», не `green`, код 143.

        Ловит мутацию: на участке откладывания SIGTERM переводится в `SIG_IGN` (по образцу действующего обработчика) — ведение стартует, игнорируя SIGTERM, и его отчёт показывает `SIGTERM: true`.
        """
        before = len(self.rows())
        code, state, stdout, stderr = self.run_early("before_fork", signal.SIGTERM)
        self.assertIn("drive_pid", state,
                      self.why("ведение после сигнала не создано", stdout, stderr))
        self.assertEqual(state.get("drive_ignored"), {"SIGTERM": False, "SIGHUP": False},
                         self.why("ведение стартовало с игнорируемым сигналом", state))
        self.assertFalse(pid_alive(state["drive_pid"]),
                         self.why("SIGTERM: процесс ведения жив", state, stderr))
        self.assert_dirs_removed(state, stdout, stderr)
        self.assert_signal_row(signal.SIGTERM, before, stdout, stderr)
        self.assertEqual(code, 128 + int(signal.SIGTERM), self.why(stdout, stderr))

    def test_ac4_signal_wins_over_exception_from_popen(self):
        """SIGTERM в подменённом `Popen`, который затем бросает `OSError` или `RuntimeError`.

        Исход — исход сигнала: код 143, строка «оборвана сигналом SIGTERM» с
        вердиктом не `green`; ни кода 127 и текста «процесс клона не запущен»,
        ни вылетевшего `RuntimeError` с его текстом.

        Ловит мутацию: при исключении из `Popen` отложенный сигнал сбрасывается — `OSError` даёт строку сбоя ведения «завершился с кодом 127» и код выхода 0, `RuntimeError` уходит наверх трассировкой с кодом 1.
        """
        for mode in ("raise_oserror", "raise_runtime"):
            with self.subTest(mode=mode):
                error = f"подменённый Popen {self.rng.randrange(10 ** 9)}"
                before = len(self.rows())
                code, state, stdout, stderr = self.run_early(mode, signal.SIGTERM,
                                                             error=error)
                self.assertTrue(state.get("delivered"), self.why(mode, stdout, stderr))
                self.assertEqual(code, 128 + int(signal.SIGTERM),
                                 self.why(mode, stdout, stderr))
                self.assert_signal_row(signal.SIGTERM, before, stdout, stderr)
                self.assertNotIn("процесс клона не запущен", stdout + stderr,
                                 self.why(mode))
                self.assertNotIn("кодом 127", stdout + stderr, self.why(mode))
                self.assertNotIn(error, stderr, self.why(mode, stderr))
                self.assert_dirs_removed(state, stdout, stderr)

    def test_ac5_popen_exception_without_signal_keeps_old_outcome(self):
        """Без сигнала `OSError` из `Popen` даёт код 127 с прежним текстом, `RuntimeError` уходит наверх.

        Публичная команда `canary.cmd_canary` в процессе теста: сбой ведения с
        `OSError` печатает «завершился с кодом 127», а вывод ведения в каталоге
        диагностики несёт «canary: процесс клона не запущен: <исключение>».

        Ловит мутацию: правка участка `Popen` ловит `BaseException` вместо `OSError` — `RuntimeError` превращается в код 127 и `assertRaises` не срабатывает; либо меняется текст «процесс клона не запущен».
        """
        real_popen = subprocess.Popen
        message = f"нет интерпретатора {self.rng.randrange(10 ** 9)}"
        for error in (OSError, RuntimeError):
            with self.subTest(error=error.__name__):
                def launch(argv, *args, **kwargs):
                    if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                        return real_popen(argv, *args, **kwargs)
                    raise error(message)

                with mock.patch.object(Path, "home", return_value=self.home), \
                     mock.patch.object(catalog, "cmd_init"), \
                     mock.patch.object(subprocess, "Popen", launch):
                    if error is RuntimeError:
                        with self.assertRaises(RuntimeError) as caught:
                            capture(lambda: canary.cmd_canary(
                                k=1, sha=self.sha, templates=[self.template]))
                        self.assertIn(message, str(caught.exception), self.why())
                        continue
                    out = capture(lambda: canary.cmd_canary(
                        k=1, sha=self.sha, templates=[self.template]))
                self.assertIn("завершился с кодом 127", out, self.why(out))
                diag = [line.split(":", 1)[1].strip() for line in out.splitlines()
                        if line.strip().startswith("диагностика:")]
                self.assertTrue(diag, self.why(out))
                texts = [p.read_text(encoding="utf-8", errors="replace")
                         for p in Path(diag[-1]).rglob("*") if p.is_file()]
                self.assertTrue(any(f"canary: процесс клона не запущен: {message}" in t
                                    for t in texts), self.why(out, texts))

    def test_ac8_test_cleanup_leaves_no_living_recorded_groups(self):
        """Уборка теста раннего окна снимает выживших из записанных групп.

        Подменённый `Popen` создаёт suite и долгоживущее ведение и бросает
        `RuntimeError` без сигнала — процесс ведения команде не достаётся и
        переживает её (это прежний исход требования 5). После уборки теста
        (`doCleanups`) ни в группе ведения, ни в группе suite, записанных в
        файле наблюдения, нет живых процессов.

        Ловит мутацию: уборка теста снимает только suite или шлёт сигнал pid без ожидания — группа ведения после `doCleanups` ещё жива.
        """
        _code, state, stdout, stderr = self.run_early("after_fork_raise", None)
        self.assertIn("drive_pgid", state, self.why(stdout, stderr))
        groups = [state["drive_pgid"], state["suite_pgid"]]
        self.doCleanups()
        alive = [g for g in groups if group_alive(g)]
        self.assertEqual(alive, [], self.why("живые группы после уборки", state))

    def test_ac11_ignored_sigint_does_not_interrupt_run(self):
        """SIGINT при унаследованном `SIG_IGN` в точке раннего окна прогон не обрывает.

        Короткое самозавершающееся ведение (только в этом тесте) без файла
        результата. Прогон без сигнала и прогон с SIGINT в точке окна дают
        одинаковые код выхода, исход и вердикт строки; `KeyboardInterrupt` нет;
        в точке доставки обработчик SIGINT — `SIG_IGN`; после исхода ведение
        не живо, клон и origin удалены.

        Ловит мутацию: откладывающий обработчик ставится и на игнорируемый SIGINT — в точке доставки `getsignal(SIGINT)` уже не `SIG_IGN`, а после `Popen` поднимается `KeyboardInterrupt`.
        """
        outcomes = []
        for signum in (None, signal.SIGINT):
            before = len(self.rows())
            code, state, stdout, stderr = self.run_early("after_fork", signum,
                                                         sigint="ignore", drive="short")
            self.assertNotIn("KeyboardInterrupt", stderr, self.why(stderr))
            rows = self.rows()
            self.assertGreater(len(rows), before, self.why(stdout, stderr))
            outcomes.append((code, rows[-1]["outcome"], rows[-1]["verdict"]))
            self.assertIn("drive_pid", state, self.why(stdout, stderr))
            self.assertFalse(pid_alive(state["drive_pid"]), self.why(state))
            self.assert_dirs_removed(state, stdout, stderr)
            if signum is not None:
                self.assertTrue(state.get("sigint_ignored_at_delivery"), self.why(state))
        self.assertEqual(outcomes[0], outcomes[1], self.why(outcomes))
