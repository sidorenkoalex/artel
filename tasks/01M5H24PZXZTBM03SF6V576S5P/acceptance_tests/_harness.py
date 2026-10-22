"""Общий код планки: песочница прогона канарейки с подменённым дочерним процессом.

Песочница — `tests.sandbox.InitializedTmpRootTest`: БД, каталог реестра
(`config.ROOT/.artel/canary-live`) и каталог журналов (`config.LOGS`) — во
временном каталоге. Пул шаблонов, план набора и проверяемый sha подменены;
клон, профиль Codex и обращение к origin запрещены — их вызов записывается
в `self.forbidden` и роняет сценарий.

Дочерний процесс параллельного прогона перехватывается на создании процесса:
вызов `subprocess.Popen`, чей argv несёт `run-task`, запускает вместо
`artel.py` интерпретатор с `_CHILD` и ИСХОДНЫМ argv дочернего, с теми же
stdout/stderr, группой процессов и каталогом, которые передал родитель.
`_CHILD` — либо простой процесс с заданным кодом выхода (`mode: exit`),
либо настоящий `artel._cmd_canary(["run-task", …])` с подменённым
`_run_one_task` (`mode: real`); пути песочницы он берёт из файла настроек.

Ожидание — только событиями: дочерний «держится» на чтении своего FIFO;
открытие FIFO на запись координатором блокирует, пока дочерний не дошёл до
этой точки. Координатор — отдельный поток; `cmd_canary` идёт в главном
потоке, сигнал родителю — `os.kill(os.getpid(), …)` и только после проверки,
что обработчик сигнала поставлен родителем (иначе сигнал убил бы прогон
тестов). Таймауты очереди координатора — только страховка от зависания.
"""
import contextlib
import io
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config, gitcmd, store
from tests.sandbox import ALL_CONFIG_ATTRS, InitializedTmpRootTest

REPO = Path(canary.__file__).resolve().parents[1]
FULL_SHA = "3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93"
SHORT_SHA = FULL_SHA[:7]
SET_NAME = "nabor-kedr"
SUMMARY = "developer → model-pihta; источник: набор"
PARALLEL_SUFFIX = " параллельно: не более 2 процессов"
SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
SAFETY_SEC = 60
_FINISHED = object()

_CHILD = r'''
import json, os, signal, sys, time
settings = json.loads(open(sys.argv[1], encoding="utf-8").read())
sys.path.insert(0, settings["repo"])
from pathlib import Path
rescue = sys.argv[2] == "rescue"
argv = sys.argv[3:]
tpl = Path(argv[argv.index("--template") + 1]).stem
stamp = argv[argv.index("--stamp") + 1]
spec = {"mode": "exit", "hold": False} if rescue else settings["children"].get(tpl, {})
live = Path(settings["live_dir"])

def parent_files():
    return {"record": (live / f"{stamp}-{os.getppid()}.json").exists(),
            "mark": (live / f"{stamp}.lock").exists()}

def note(kind, **extra):
    line = json.dumps({"kind": kind, "template": tpl, "pid": os.getpid(),
                       "ppid": os.getppid(), **extra}, ensure_ascii=False)
    with open(settings["calls"], "a", encoding="utf-8") as out:
        out.write(line + "\n")

def wait_fifo(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.read(fd, 16)
    finally:
        os.close(fd)

def hold():
    if spec.get("ignore_term"):
        # SIGTERM учтён и проигнорирован: процесс ждёт дальше, снять его
        # может только SIGKILL. Метка времени — общие монотонные часы машины.
        def ignore(signum, frame):
            note("term", at=time.monotonic(), **parent_files())
        signal.signal(signal.SIGTERM, ignore)
    if spec.get("term_exit"):
        def leave(signum, frame):
            note("term", **parent_files())
            os._exit(128 + signum)
        signal.signal(signal.SIGTERM, leave)
    if spec.get("hold", True):
        wait_fifo(settings["fifos"][tpl])

if spec.get("term_hold"):
    def on_term(signum, frame):
        note("term", **parent_files())
        print(f"дочерний {tpl}: получен SIGTERM", flush=True)
        wait_fifo(settings["term_fifos"][tpl])
        os._exit(128 + signum)
    signal.signal(signal.SIGTERM, on_term)

note("spawned", **parent_files())
print(f"дочерний {tpl}: начало", flush=True)
if spec.get("mode", "exit") == "exit":
    hold()
    note("exit", **parent_files())
    print(f"дочерний {tpl}: конец", flush=True)
    sys.exit(spec.get("code", 0))

from unittest import mock
from orchestrator import artel, canary, config, store
for name, value in settings["config"].items():
    setattr(config, name, Path(value))
plan = canary.CanarySetPlan(settings["set_name"], {}, None, settings["summary"], ())

def drive(template_path, run_stamp, ratio, target_sha, sha_label, plan_arg, codex_auth):
    note("drive")
    if spec.get("row"):
        store.insert_canary_run(
            store.db(), run_stamp, tpl, "01FIXTURE" + tpl.upper(), 3, 1.5, 0, 0,
            "merged", None, False, False, main_sha=target_sha, verdict="green",
            set_name=plan_arg.name, models_summary=plan_arg.summary or None)
    hold()
    note("exit", **parent_files())
    print(f"дочерний {tpl}: ведение завершено", flush=True)

def clone(*args, **kwargs):
    note("clone")
    raise RuntimeError("клон в планке запрещён")

with mock.patch.object(canary, "_set_plan", return_value=plan), \
        mock.patch.object(canary, "_run_one_task", drive), \
        mock.patch.object(canary, "_ephemeral_clone", clone):
    artel._cmd_canary(argv[argv.index("run-task"):])
print(f"дочерний {tpl}: конец", flush=True)
'''


def flag_value(argv: list, flag: str):
    """Значение флага argv; флага нет — None."""
    if flag not in argv:
        return None
    index = argv.index(flag)
    return argv[index + 1] if index + 1 < len(argv) else None


def _finished(pid: int) -> bool:
    """Процесс `pid` (потомок теста) завершился — не пожиная его: WNOWAIT."""
    try:
        info = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        return True
    return info is not None


@dataclass
class Spawn:
    template: str
    argv: list
    kwargs: dict
    unfinished_before: list
    parent_record: dict | None
    pid: int | None = None
    proc: object = None


@dataclass
class Run:
    exc: BaseException | None
    stdout: str
    stderr: str
    spawns: list
    attempts: list
    errors: list
    stamp: str | None = None
    calls: list = field(default_factory=list)

    @property
    def code(self):
        """Код выхода родителя: 0, число `SystemExit` или 1 за текст отказа."""
        if self.exc is None:
            return 0
        if isinstance(self.exc, SystemExit):
            code = self.exc.code
            if code is None:
                return 0
            return code if isinstance(code, int) else 1
        return None

    def calls_of(self, kind: str, template: str | None = None) -> list:
        return [c for c in self.calls if c["kind"] == kind
                and (template is None or c["template"] == template)]

    def describe(self) -> str:
        return (f"исключение: {self.exc!r}; ошибки координатора: {self.errors};\n"
                f"stdout:\n{self.stdout}\nstderr:\n{self.stderr}")


class Coordinator:
    """Поток сценария: ждёт запусков дочерних, отпускает их, шлёт сигналы."""

    def __init__(self, harness, script):
        self.h = harness
        self.script = script
        self.events = queue.Queue()
        self.seen = []
        self.errors = []
        self.held = {}
        self.rescue = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        try:
            self.script(self)
        except _Done:
            pass
        except BaseException as exc:  # noqa: BLE001 — исход сценария
            self.errors.append(repr(exc))
            self._rescue()

    def _rescue(self):
        """Сценарий сорвался: снять всех дочерних, чтобы родитель не завис."""
        self.rescue = True
        for spawn in list(self.h.spawns):
            _kill_group(spawn.pid)

    def wait_spawns(self, count: int) -> list:
        """Блокирует, пока не запущено `count` дочерних; их шаблоны."""
        while len(self.seen) < count:
            try:
                item = self.events.get(timeout=SAFETY_SEC)
            except queue.Empty:
                raise AssertionError(
                    f"страховка: за {SAFETY_SEC} с запущено {self.seen}, "
                    f"ждали {count}") from None
            if item is _FINISHED:
                raise _Done
            self.seen.append(item)
        return list(self.seen)

    def wait_finished(self) -> None:
        """Блокирует до возврата `cmd_canary`; страховка — снять дочерних."""
        while True:
            try:
                item = self.events.get(timeout=SAFETY_SEC)
            except queue.Empty:
                raise AssertionError(
                    f"страховка: прогон не завершился за {SAFETY_SEC} с") from None
            if item is _FINISHED:
                raise _Done
            self.seen.append(item)

    def next_spawn(self):
        return self.wait_spawns(len(self.seen) + 1)[-1]

    def reach(self, template: str, term: bool = False) -> None:
        """Дочерний дошёл до своей точки ожидания (FIFO открыт им на чтение)."""
        key = (template, term)
        if key not in self.held:
            fifos = self.h.term_fifos if term else self.h.fifos
            self.held[key] = os.open(fifos[template], os.O_WRONLY)

    def release(self, template: str, term: bool = False) -> None:
        self.reach(template, term)
        fd = self.held.pop((template, term))
        try:
            os.write(fd, b"go\n")
        except BrokenPipeError:
            pass
        finally:
            os.close(fd)

    def signal_parent(self, signum: int) -> None:
        if signal.getsignal(signum) == self.h.handlers_before[signum]:
            raise AssertionError(
                f"обработчик {signal.Signals(signum).name} не поставлен "
                f"родителем — сигнал не отправлен")
        os.kill(os.getpid(), signum)

    def close(self):
        for fd in self.held.values():
            with contextlib.suppress(OSError):
                os.close(fd)
        self.held.clear()


class _Done(Exception):
    pass


def release_all(c: Coordinator) -> None:
    """Сценарий по умолчанию: каждого держащегося дочернего отпустить сразу."""
    while True:
        template = c.next_spawn()
        if c.h.children.get(template, {}).get("hold", True):
            c.release(template)


class WaitFault:
    """Подмена функции ожидания дочернего `canary._wait_child` (ANSWER-1).

    Первый вызов ждёт `ready` (координатор: дочерние дошли до точки
    ожидания), запоминает запущенные к этому моменту шаблоны, ставит
    `raised` и бросает `exc`; остальные вызовы — настоящая функция.
    Подпись функции SPEC не задаёт — аргументы передаются как есть."""

    def __init__(self, harness, exc):
        self.real = canary._wait_child
        self.h = harness
        self.exc = exc
        self.ready = threading.Event()
        self.raised = threading.Event()
        self.lock = threading.Lock()
        self.fired = False
        self.spawned_at_raise = None

    def __call__(self, *args, **kwargs):
        with self.lock:
            first, self.fired = not self.fired, True
        if not first:
            return self.real(*args, **kwargs)
        self.ready.wait(SAFETY_SEC)
        self.spawned_at_raise = [s.template for s in self.h.spawns]
        self.raised.set()
        raise self.exc


def _kill_group(pid):
    if not pid:
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


class CanaryParallelSandbox(InitializedTmpRootTest):
    """Песочница родителя прогона; `self.children` — поведение дочерних."""

    set_name = SET_NAME
    summary = SUMMARY
    codex_roles = ()

    def setUp(self):
        super().setUp()
        self.handlers_before = {s: signal.getsignal(s) for s in SIGNALS}
        self.addCleanup(lambda: [signal.signal(s, h)
                                 for s, h in self.handlers_before.items()])
        self.pool = self.root / "pool"
        self.pool.mkdir()
        for name in ("alfa", "beta", "gamma", "delta"):
            (self.pool / f"{name}.md").write_text("# учебная задача\n",
                                                  encoding="utf-8")
        self.registry = Path(config.ROOT) / ".artel" / config.CANARY_LIVE_DIRNAME
        self.fifo_dir = self.root / "fifo"
        self.fifo_dir.mkdir()
        self.children = {}
        self.spawns = []
        self.attempts = []
        self.forbidden = []
        self.resolve_calls = []
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(canary, "_pool_dir",
                                              return_value=self.pool))
        stack.enter_context(mock.patch.object(canary, "_set_plan",
                                              side_effect=self.plan))
        stack.enter_context(mock.patch.object(canary, "_resolve_target_sha",
                                              side_effect=self.resolve))
        for name in ("_ephemeral_clone", "_locked_canary_profile",
                     "_canary_profile_auth", "_codex_clone_auth"):
            stack.enter_context(mock.patch.object(
                canary, name, side_effect=self.forbid(name)))
        stack.enter_context(mock.patch.object(
            gitcmd, "fetch_ref_sha", side_effect=self.forbid("fetch_ref_sha")))
        self.parent_drive = stack.enter_context(mock.patch.object(
            canary, "_run_one_task",
            side_effect=self.forbid("_run_one_task в процессе родителя")))
        self.addCleanup(self.stop_children)

    def patch_grace(self, seconds) -> None:
        """Срок остановки дочерних (ANSWER-1: `PARALLEL_STOP_GRACE_SEC`) подменён."""
        patcher = mock.patch.object(canary, "PARALLEL_STOP_GRACE_SEC", seconds)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_wait(self, exc) -> WaitFault:
        """Функция ожидания дочернего (ANSWER-1: `_wait_child`) подменена `WaitFault`."""
        fault = WaitFault(self, exc)
        patcher = mock.patch.object(canary, "_wait_child", fault)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fault

    def record_unlinks(self) -> list:
        """Удаления файлов реестра процессом родителя: (имя, листинг перед ним)."""
        seen = []
        for name in ("unlink", "remove"):
            real = getattr(os, name)

            def spy(path, *args, _real=real, **kwargs):
                target = Path(os.fsdecode(path))
                if target.parent == self.registry and target.exists():
                    seen.append((target.name, self.listing()))
                return _real(path, *args, **kwargs)
            patcher = mock.patch.object(os, name, spy)
            patcher.start()
            self.addCleanup(patcher.stop)
        return seen

    def plan(self, name):
        return canary.CanarySetPlan(name, {}, None, self.summary,
                                    tuple(self.codex_roles))

    def resolve(self, explicit):
        self.resolve_calls.append(explicit)
        if explicit in (SHORT_SHA, FULL_SHA):
            return FULL_SHA, None
        raise AssertionError(f"_resolve_target_sha({explicit!r}) вне сценария")

    def forbid(self, name):
        def refuse(*args, **kwargs):
            self.forbidden.append(name)
            raise AssertionError(f"{name} вызван")
        return refuse

    def stop_children(self):
        for spawn in self.spawns:
            _kill_group(spawn.pid)
            with contextlib.suppress(ChildProcessError, OSError):
                spawn.proc.wait()

    @property
    def fifos(self):
        return {name: str(self.fifo_dir / name) for name in self.children}

    @property
    def term_fifos(self):
        return {name: str(self.fifo_dir / f"{name}.term") for name in self.children}

    def rows(self, stamp=None) -> list:
        return [dict(r) for r in store.all_canary_runs(store.db())
                if stamp is None or r["run_stamp"] == stamp]

    def baseline_rows(self) -> list:
        conn = store.db()
        return [tuple(r) for r in conn.execute(
            "SELECT * FROM canary_baseline ORDER BY title, set_name")]

    def listing(self) -> list:
        if not self.registry.is_dir():
            return []
        return sorted(p.name for p in self.registry.iterdir())

    def log_path(self, stamp: str, template: str) -> Path:
        return Path(config.LOGS) / "canary" / f"{stamp}-{template}.log"

    def _parent_record(self, stamp):
        path = self.registry / f"{stamp}-{os.getpid()}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _popen(self, real_popen, coord):
        def popen(args, *a, **kw):
            argv = ([os.fsdecode(x) if isinstance(x, (bytes, os.PathLike)) else str(x)
                     for x in args] if isinstance(args, (list, tuple)) else None)
            if not argv or "run-task" not in argv:
                return real_popen(args, *a, **kw)
            template = Path(flag_value(argv, "--template") or "?").stem
            spawn = Spawn(template, argv, dict(kw),
                          [s.template for s in self.spawns if not _finished(s.pid)],
                          self._parent_record(flag_value(argv, "--stamp")))
            self.attempts.append(spawn)
            error = self.children.get(template, {}).get("spawn_error")
            if error:
                raise OSError(error)
            proc = real_popen([sys.executable, "-c", _CHILD, str(self.settings_path),
                               "rescue" if coord.rescue else "-", *argv], *a, **kw)
            spawn.pid, spawn.proc = proc.pid, proc
            self.spawns.append(spawn)
            coord.events.put(template)
            return proc
        return popen

    def write_settings(self) -> None:
        for path in list(self.fifos.values()) + list(self.term_fifos.values()):
            if not os.path.exists(path):
                os.mkfifo(path)
        self.calls_path = self.root / "calls.jsonl"
        self.settings_path = self.root / "child-settings.json"
        self.settings_path.write_text(json.dumps({
            "repo": str(REPO),
            "config": {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS},
            "set_name": self.set_name, "summary": self.summary,
            "children": self.children, "fifos": self.fifos,
            "term_fifos": self.term_fifos, "calls": str(self.calls_path),
            "live_dir": str(self.registry),
        }, ensure_ascii=False), encoding="utf-8")

    def cli_argv(self, templates, sha=SHORT_SHA, extra=()):
        return ["--k", str(len(templates)), "--sha", sha, "--set", self.set_name,
                "--template", ",".join(templates), "--parallel", *extra]

    def run_cli(self, argv, script=release_all) -> Run:
        """`artel._cmd_canary(argv)` в главном потоке под координатором."""
        self.write_settings()
        coord = Coordinator(self, script)
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", write_through=True)
        err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", write_through=True)
        exc = None
        unblock = []
        with mock.patch.object(subprocess, "Popen", self._popen(subprocess.Popen, coord)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            coord.thread.start()
            try:
                artel._cmd_canary(list(argv))
            except BaseException as caught:  # noqa: BLE001 — исход сценария
                exc = caught
            finally:
                coord.events.put(_FINISHED)
                for path in list(self.fifos.values()) + list(self.term_fifos.values()):
                    with contextlib.suppress(OSError):
                        unblock.append(os.open(path, os.O_RDONLY | os.O_NONBLOCK))
                coord.thread.join(SAFETY_SEC)
                coord.close()
                for fd in unblock:
                    with contextlib.suppress(OSError):
                        os.close(fd)
        stdout = out.buffer.getvalue().decode("utf-8", "replace")
        stderr = err.buffer.getvalue().decode("utf-8", "replace")
        run = Run(exc, stdout, stderr, list(self.spawns), list(self.attempts),
                  list(coord.errors))
        match = re.search(r"\[canary\] прогон ([0-9]{8}T[0-9]{6}Z):", stdout)
        run.stamp = match.group(1) if match else None
        if self.calls_path.exists():
            run.calls = [json.loads(line) for line in
                         self.calls_path.read_text(encoding="utf-8").splitlines()
                         if line.strip()]
        return run

    def run_parallel(self, templates, script=release_all, sha=SHORT_SHA, extra=()):
        return self.run_cli(self.cli_argv(templates, sha=sha, extra=extra), script)

    def assert_clean(self, run: Run) -> None:
        """Сценарий отработал: координатор без ошибок, исход — выход, не сбой."""
        self.assertEqual(run.errors, [], run.describe())
        self.assertTrue(run.exc is None or isinstance(run.exc, SystemExit),
                        run.describe())
        self.assertEqual(self.forbidden, [], run.describe())
        self.assertIsNotNone(run.stamp, run.describe())

    def assert_red_row(self, row: dict, stamp: str, template: str) -> None:
        """Красная строка родителя по образцу `_report_drive_failure`."""
        self.assertEqual(
            {k: row[k] for k in ("run_stamp", "title", "task_id", "steps",
                                 "cost_usd", "review_iterations", "escalations",
                                 "outcome", "expected_escalation", "main_sha",
                                 "verdict", "set_name", "models_summary")},
            {"run_stamp": stamp, "title": template, "task_id": None, "steps": 0,
             "cost_usd": 0.0, "review_iterations": 0, "escalations": 0,
             "outcome": canary._DRIVE_FAILED_OUTCOME, "expected_escalation": None,
             "main_sha": None, "verdict": "red", "set_name": self.set_name,
             "models_summary": self.summary or None})
