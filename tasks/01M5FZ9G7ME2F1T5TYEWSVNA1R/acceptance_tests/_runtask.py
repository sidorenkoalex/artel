"""Общий код планки: вызов подкоманды `canary run-task` и реестр живого прогона во временном каталоге.

Подкоманда вызывается тем же входом, что набирает пульт, — диспетчером
`artel.main()` с `sys.argv = ["artel.py", "canary", "run-task", …]`, в
главном потоке процесса теста. Каталог реестра —
`config.ROOT/.artel/config.CANARY_LIVE_DIRNAME`, где `config.ROOT` уведён
песочницей `tests.sandbox` во временный каталог: настоящий реестр и
настоящий каталог журналов пульта тесты не трогают.

Родитель подкоманды в процессе теста — `os.getppid()` процесса теста
(живой процесс); его метку и запись тест раскладывает файлами.
"""
import contextlib
import io
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config, doctor, gitcmd, runner, store
from tests.sandbox import ALL_CONFIG_ATTRS

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
HEX = "0123456789abcdef"
TOKEN = "abcdefghijkmnpqrstuvwxyz"
#: Корень кода пульта, из которого импортирован `orchestrator` — рабочий
#: каталог дочернего интерпретатора.
CODE_ROOT = Path(canary.__file__).resolve().parents[1]

#: Дочерний интерпретатор: подкоманда тем же входом `artel.main()` в
#: отдельном процессе; конфиг песочницы — из файла настроек. Ведение задачи
#: подменено копированием своей записи реестра в файл, после чего процесс
#: штатно завершается (его pid становится мёртвым).
CHILD = r'''
import json, os, shutil, sys
from pathlib import Path
from unittest import mock
from orchestrator import artel, canary, config, runner
settings = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for name, value in settings["config"].items():
    setattr(config, name, Path(value))
plan = canary.CanarySetPlan(settings["set"], {}, None, settings["summary"], ())
def task(*args, **kwargs):
    directory = Path(settings["registry"])
    shutil.copyfile(directory / f"{settings['stamp']}-{os.getpid()}.json",
                    settings["copy"])
with mock.patch.object(canary, "_set_plan", return_value=plan), \
        mock.patch.object(canary, "_run_one_task", side_effect=task), \
        mock.patch.object(runner, "in_role_environment", return_value=False):
    sys.argv = ["artel.py", "canary", "run-task", *settings["argv"]]
    artel.main()
'''


def plan(name: str, summary: str, codex_roles=()) -> "canary.CanarySetPlan":
    return canary.CanarySetPlan(name, {}, None, summary, tuple(codex_roles))


class Outcome:
    """Исход одного вызова: код выхода процесса, весь вывод, исключение."""

    def __init__(self, code: int, text: str, exc):
        self.code = code
        self.text = text
        self.exc = exc

    def __repr__(self):
        return f"код {self.code}; вывод:\n{self.text}"


def invoke(argv: list) -> Outcome:
    """`artel.main()` с argv; код — тот, с которым завершился бы процесс."""
    out = io.StringIO()
    code, exc = 0, None
    with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            artel.main()
        except SystemExit as error:
            exc = error
            if error.code is None:
                code = 0
            elif isinstance(error.code, int):
                code = error.code
            else:
                code = 1
                out.write(f"\n{error.code}")
        except BaseException as error:  # noqa: BLE001 — исход сценария
            exc = error
            code = 1
            out.write(f"\nисключение: {error!r}")
    return Outcome(code, out.getvalue(), exc)


class RunTaskMixin:
    """Сценарий подкоманды поверх песочницы `tests.sandbox` (пути `config` во временном каталоге)."""

    def setup_runtask(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        not_role = mock.patch.object(runner, "in_role_environment", return_value=False)
        not_role.start()
        self.addCleanup(not_role.stop)
        handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}
        self.addCleanup(lambda: [signal.signal(s, h) for s, h in handlers.items()])
        self.home = Path(tempfile.mkdtemp(prefix="run-task-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.template_name = "uchebnaya-" + self.token(6)
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        self.template = pool / f"{self.template_name}.md"
        self.template.write_text("# учебная задача\n", encoding="utf-8")
        self.sha = self.hexsha()
        self.ppid = os.getppid()
        self.replaced = []
        self.children = []
        self.addCleanup(self.stop_children)

    # ------------------------------------------------------------ значения

    def msg(self, text) -> str:
        return f"зерно: {self.seed}; {text}"

    def token(self, n: int = 8) -> str:
        return "".join(self.rng.choice(TOKEN) for _ in range(n))

    def hexsha(self) -> str:
        return "".join(self.rng.choice(HEX) for _ in range(40))

    def stamp(self) -> str:
        while True:
            moment = datetime(2031, 1, 1, tzinfo=timezone.utc) + timedelta(
                seconds=self.rng.randrange(300 * 24 * 3600))
            text = moment.strftime(STAMP_FORMAT)
            if text not in self.used:
                self.used.add(text)
                return text

    def argv(self, stamp: str, set_name: str, summary: str, sha=None,
             template=None) -> list:
        return ["canary", "run-task", "--stamp", stamp,
                "--template", str(template or self.template),
                "--sha", sha or self.sha, "--set", set_name,
                "--summary", summary]

    # ------------------------------------------------------------- реестр

    def registry(self) -> Path:
        return Path(config.ROOT) / ".artel" / config.CANARY_LIVE_DIRNAME

    def listing(self) -> list:
        directory = self.registry()
        if not directory.is_dir():
            return []
        return sorted(p.name for p in directory.iterdir())

    def snapshot(self) -> dict:
        directory = self.registry()
        if not directory.is_dir():
            return {}
        return {p.name: (p.read_bytes(), p.stat().st_ino)
                for p in sorted(directory.iterdir())}

    def put_mark(self, stamp: str, pid) -> Path:
        directory = self.registry()
        directory.mkdir(parents=True, exist_ok=True)
        mark = directory / f"{stamp}.lock"
        mark.write_text(f"{pid}\n", encoding="utf-8")
        return mark

    def put_record(self, stamp: str, pid: int, sha: str, set_name: str,
                   start_known: bool = True) -> Path:
        """Запись последовательного (родительского) прогона — поля `_live_run_record`."""
        directory = self.registry()
        directory.mkdir(parents=True, exist_ok=True)
        started = doctor.process_start_time(pid) if start_known else None
        record = directory / f"{stamp}-{pid}.json"
        record.write_text(json.dumps({
            "pid": pid,
            "process_start": None if started is None else started.isoformat(),
            "run_stamp": stamp, "sha": sha, "set_name": set_name,
            "started_at": (datetime.now(timezone.utc)
                           - timedelta(seconds=120)).isoformat(),
            "tasks": 1}), encoding="utf-8")
        return record

    def own_record_name(self, stamp: str, pid: int = None) -> str:
        return f"{stamp}-{os.getpid() if pid is None else pid}.json"

    @staticmethod
    def dead_pid() -> int:
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        return proc.pid

    # --------------------------------------------------------------- БД

    def rows(self, stamp: str = None) -> list:
        return [dict(r) for r in store.all_canary_runs(store.db())
                if stamp is None or r["run_stamp"] == stamp]

    # ----------------------------------------------------------- подмены

    def guards(self, stack: contextlib.ExitStack) -> dict:
        """Подмены, которые подкоманда звать не должна: origin, клон, профиль Codex."""
        spies = {}
        for name in ("_resolve_target_sha", "_ephemeral_clone",
                     "_locked_canary_profile", "_canary_profile_auth",
                     "_codex_clone_auth"):
            spies[name] = stack.enter_context(mock.patch.object(
                canary, name, side_effect=AssertionError(f"{name} вызван")))
        spies["fetch_ref_sha"] = stack.enter_context(mock.patch.object(
            gitcmd, "fetch_ref_sha",
            side_effect=AssertionError("gitcmd.fetch_ref_sha вызван")))
        return spies

    def spy_replace(self, stack: contextlib.ExitStack, hook=None) -> None:
        """`os.replace` со списком замен в каталог реестра; `hook(src, dst)` — до замены."""
        real = os.replace
        registry = self.registry()

        def replace(src, dst, *args, **kwargs):
            if Path(os.fsdecode(dst)).parent == registry:
                self.replaced.append((Path(os.fsdecode(src)).name,
                                      Path(os.fsdecode(dst)).name))
                if hook is not None:
                    hook(Path(os.fsdecode(src)), Path(os.fsdecode(dst)))
            return real(src, dst, *args, **kwargs)

        stack.enter_context(mock.patch.object(os, "replace", replace))

    def send_signal(self, signum: int, before) -> None:
        """Сигнал самому процессу — только если обработчик поставлен подкомандой.

        `before` — обработчик сигнала до вызова подкоманды; совпадает с
        текущим — тест падает, сигнал не отправляется."""
        current = signal.getsignal(signum)
        if current is before or current == before:
            raise AssertionError(self.msg(
                f"обработчик {signal.Signals(signum).name} не поставлен "
                f"подкомандой — сигнал не отправлен"))
        os.kill(os.getpid(), signum)

    # ------------------------------------------------- дочерний интерпретатор

    def stop_children(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
                child.wait()

    def run_child(self, stamp: str, set_name: str, summary: str) -> tuple:
        """Подкоманда в отдельном процессе; возврат после его завершения: (pid, копия записи, лог)."""
        settings = self.home / f"child-{self.token(6)}.json"
        copy = self.home / f"copy-{self.token(6)}.json"
        settings.write_text(json.dumps({
            "config": {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS},
            "registry": str(self.registry()), "stamp": stamp, "set": set_name,
            "summary": summary, "copy": str(copy),
            "argv": self.argv(stamp, set_name, summary)[2:]}), encoding="utf-8")
        log = self.home / f"child-{self.token(6)}.log"
        env = {**os.environ, config.ARTEL_ROLE_ENV: ""}
        env["PYTHONPATH"] = os.pathsep.join(
            [str(CODE_ROOT), *filter(None, [env.get("PYTHONPATH")])])
        with open(log, "wb") as out:
            child = subprocess.Popen([sys.executable, "-c", CHILD, str(settings)],
                                     cwd=CODE_ROOT, stdout=out,
                                     stderr=subprocess.STDOUT, env=env)
        self.children.append(child)
        code = child.wait()
        text = log.read_text(errors="replace")
        if code != 0 or not copy.exists():
            raise AssertionError(self.msg(
                f"дочерняя подкоманда (код {code}) не сняла копию записи: {text}"))
        return child.pid, copy.read_bytes(), text

    def capture_record(self, stamp: str, set_name: str, summary: str) -> bytes:
        """Подкоманда в процессе теста; копия её записи реестра, снятая во время подменённой задачи."""
        got = {}

        def task(*args, **kwargs):
            path = self.registry() / self.own_record_name(stamp)
            got["bytes"] = path.read_bytes()

        mark = self.put_mark(stamp, self.ppid)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(
                canary, "_set_plan", return_value=plan(set_name, summary)))
            stack.enter_context(mock.patch.object(canary, "_run_one_task",
                                                  side_effect=task))
            outcome = invoke(self.argv(stamp, set_name, summary))
        if "bytes" not in got:
            raise AssertionError(self.msg(f"подменённая задача не дошла: {outcome!r}"))
        mark.unlink(missing_ok=True)
        return got["bytes"]
