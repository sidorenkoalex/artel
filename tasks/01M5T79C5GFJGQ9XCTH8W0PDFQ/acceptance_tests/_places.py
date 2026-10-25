"""Общий код планки: репозиторий-фикстура, шпион запусков `subprocess.Popen`,
поддельный процесс git и вызовы семи мест «Контекста» SPEC.

Шпион ставится на `subprocess.Popen` модуля `subprocess`: через него проходят
и прямые `subprocess.Popen(...)`, и `subprocess.run(...)` (тот зовёт
`Popen` своего модуля). Для каждого запуска запоминаются argv, ключевые
аргументы (`cwd`, `env`, `text`, `stdin`), сроки, переданные `communicate`/
`wait`, и «запускатель» — файл первого кадра стека вне `subprocess.py` и
этого модуля: так видно, из какого модуля пульта пришёл запуск git, без
знания имён новых функций `gitcmd`.
"""
import contextlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, brief, gitcmd, reference_cache, tz_check
from orchestrator.advance_gates import outcome_integrity

REAL_POPEN = subprocess.Popen
REAL_RUN = subprocess.run

GITCMD_FILE = os.path.realpath(gitcmd.__file__)
_SKIP_FILES = {os.path.realpath(subprocess.__file__), os.path.realpath(__file__)}

PLACE_MODULE_FILES = {
    1: os.path.realpath(acceptance.__file__),
    2: os.path.realpath(brief.__file__),
    3: os.path.realpath(reference_cache.__file__),
    4: os.path.realpath(reference_cache.__file__),
    5: os.path.realpath(reference_cache.__file__),
    6: os.path.realpath(tz_check.__file__),
    7: os.path.realpath(outcome_integrity.__file__),
}


def _launcher() -> str:
    frame = sys._getframe(2)
    while frame is not None:
        path = os.path.realpath(frame.f_code.co_filename)
        if path not in _SKIP_FILES:
            return path
        frame = frame.f_back
    return ""


class Launch:
    """Один запуск процесса под шпионом."""

    def __init__(self, args, kwargs):
        self.argv = [args] if isinstance(args, (str, bytes)) else list(args)
        self.kwargs = dict(kwargs)
        self.launcher = _launcher()
        self.events: list = []
        self.inputs: list = []
        self.proc = None

    @property
    def is_git(self) -> bool:
        return bool(self.argv) and os.path.basename(str(self.argv[0])) == "git"

    @property
    def wants_text(self) -> bool:
        kw = self.kwargs
        return bool(kw.get("text") or kw.get("universal_newlines")
                    or kw.get("encoding") or kw.get("errors"))

    @property
    def timeouts(self) -> list:
        """Сроки верхнего уровня: `communicate(timeout=)` и `wait(timeout=)`,
        позванные не изнутри `communicate`."""
        return [e[1] for e in self.events if e[0] in ("communicate", "wait")]

    def first_timeout(self):
        timed = [t for t in self.timeouts if t is not None]
        return timed[0] if timed else None


class _SpyPopen(REAL_POPEN):
    """Настоящий процесс; запоминает сроки и вход."""

    def __init__(self, rec, args, *a, **kw):
        self.spy_rec = rec
        self.spy_in_communicate = False
        rec.proc = self
        super().__init__(args, *a, **kw)

    def communicate(self, input=None, timeout=None):
        self.spy_rec.events.append(("communicate", timeout))
        if input is not None:
            self.spy_rec.inputs.append(input)
        self.spy_in_communicate = True
        try:
            return super().communicate(input, timeout)
        finally:
            self.spy_in_communicate = False

    def wait(self, timeout=None):
        if not self.spy_in_communicate:
            self.spy_rec.events.append(("wait", timeout))
        return super().wait(timeout)

    def kill(self):
        self.spy_rec.events.append(("kill",))
        return super().kill()


class FakeProc:
    """Поддельный процесс git: первый вызов `communicate`/`wait` со сроком
    отвечает `TimeoutExpired`; после `kill`/`terminate` — немедленно."""

    pid = 4194301

    def __init__(self, rec):
        self.rec = rec
        self.args = rec.argv
        self.returncode = None
        self.killed = False
        empty = "" if rec.wants_text else b""
        self.empty = empty
        self.stdin = None
        self.stdout = None
        self.stderr = None
        rec.proc = self

    def _expire(self, timeout):
        if timeout is not None and not self.killed:
            raise subprocess.TimeoutExpired(self.args, timeout)

    def communicate(self, input=None, timeout=None):
        self.rec.events.append(("communicate", timeout))
        if input is not None:
            self.rec.inputs.append(input)
        self._expire(timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.empty, self.empty

    def wait(self, timeout=None):
        self.rec.events.append(("wait", timeout))
        self._expire(timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.rec.events.append(("kill",))
        self.killed = True
        self.returncode = -9

    def terminate(self):
        self.rec.events.append(("terminate",))
        self.killed = True
        self.returncode = -15

    def send_signal(self, sig):
        self.rec.events.append(("signal", sig))
        self.killed = True
        self.returncode = -int(sig)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@contextlib.contextmanager
def spy_popen(select=None, behave=None):
    """Шпион `subprocess.Popen`; запуск, для которого `select(argv)` истинно,
    отдаётся `behave(rec)` (поддельный процесс или исключение запуска)."""
    log: list = []

    def factory(args, *a, **kw):
        rec = Launch(args, kw)
        log.append(rec)
        if select is not None and select(rec.argv):
            return behave(rec)
        return _SpyPopen(rec, args, *a, **kw)

    with mock.patch.object(subprocess, "Popen", factory):
        yield log


def raising(exc):
    """Поведение `behave`: запуск процесса падает исключением `exc`."""
    def behave(rec):
        raise exc
    return behave


def git_launches(log) -> list:
    return [rec for rec in log if rec.is_git]


# --- репозиторий-фикстура -------------------------------------------------

_GIT_ID = ("-c", "user.name=planka", "-c", "user.email=planka@example.invalid",
           "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null")


def raw_git(repo: Path, *args: str, env: dict | None = None) -> str:
    res = REAL_RUN(["git", "-C", str(repo), *_GIT_ID, *args],
                   capture_output=True, text=True, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"git {args}: {res.stderr}")
    return res.stdout.strip()


class Repo:
    """Клон-фикстура: два коммита, `.py` и не-`.py`, ветка main."""

    def __init__(self, root: Path):
        self.path = root / "clone"
        self.path.mkdir(parents=True)
        p = self.path
        raw_git(p, "init", "-q", "-b", "main")
        (p / "a.py").write_text("x = 1\n", encoding="utf-8")
        (p / "sub").mkdir()
        (p / "sub" / "b.py").write_text("y = 2\n", encoding="utf-8")
        (p / "notes.txt").write_text("заметка\n", encoding="utf-8")
        raw_git(p, "add", "-A")
        raw_git(p, "commit", "-q", "-m", "первый")
        self.base = raw_git(p, "rev-parse", "HEAD")
        (p / "a.py").write_text("x = 1\nz = 3\n", encoding="utf-8")
        raw_git(p, "commit", "-q", "-am", "второй")
        self.head = raw_git(p, "rev-parse", "HEAD")
        self.tree = raw_git(p, "rev-parse", "HEAD^{tree}")
        self.blob_a = raw_git(p, "rev-parse", "HEAD:a.py")
        self.blob_b = raw_git(p, "rev-parse", "HEAD:sub/b.py")

    def worktree_tree(self) -> str:
        """Дерево рабочей копии (отслеживаемые файлы) через отдельный индекс."""
        with tempfile.TemporaryDirectory() as holder:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(holder) / "i")}
            raw_git(self.path, "read-tree", "HEAD", env=env)
            raw_git(self.path, "add", "-u", "--", ".", env=env)
            return raw_git(self.path, "write-tree", env=env)


def fake_git_dir(root: Path, script: str) -> Path:
    """Каталог с исполняемым `git` — shell-скриптом `script`."""
    bindir = root / "fakebin"
    bindir.mkdir(exist_ok=True)
    exe = bindir / "git"
    exe.write_text("#!/bin/sh\n" + script + "\n", encoding="utf-8")
    exe.chmod(0o755)
    return bindir


@contextlib.contextmanager
def exceptions_in(files):
    """Исключения, прошедшие через кадры функций из файлов `files`:
    [(файл, имя класса исключения)] по событиям `exception` трассировки."""
    files = {os.path.realpath(f) for f in files}
    seen: list = []

    def local(frame, event, arg):
        if event == "exception":
            seen.append((os.path.realpath(frame.f_code.co_filename),
                         arg[0].__name__))
        return local

    def global_trace(frame, event, arg):
        if os.path.realpath(frame.f_code.co_filename) in files:
            return local
        return None

    old = sys.gettrace()
    sys.settrace(global_trace)
    try:
        yield seen
    finally:
        sys.settrace(old)


def deadline_in(seconds: float) -> float:
    return time.monotonic() + seconds
