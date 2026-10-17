"""Общий код планки: прогон целевого теста предела полного прогона во
временной копии рабочей копии кода — с разметкой обрыва либо с мутацией
пульта.

Целевой тест — `SuiteRunProfileLimitTest::test_ac5_…` долгоживущего файла
задачи 01M48WRE8BHFDY011Q0HQGQ91B. Он сам копирует `orchestrator/` из корня
своего кода (`CODE_ROOT` теста — от `acceptance.__file__`) в песочницу, поэтому
правка `orchestrator/` во временной копии доходит до фонового `suite-run`
песочницы. Рабочая копия кода задачи не меняется.

Разметка обрыва — строки вокруг `proc.wait(timeout=limit[0])` в
`_run_full_suite_to_log` копии: файл-метка «до» вызова, «вернулся» после него
и «обрыв» первой строкой ветки `except subprocess.TimeoutExpired`. Реальное
время между метками — по `st_mtime_ns` файлов (часы ядра, а не `time` пульта,
который тест вправе подменять). Сама строка вызова не меняется.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pult  # noqa: E402

TARGET_REL = "tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py"
TARGET_MODULE = "tests.test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs"
TARGET_CLASS = "SuiteRunProfileLimitTest"
TARGET_METHOD = "test_ac5_suite_run_cuts_at_profile_limit_and_reports_it"
NODE = f"{TARGET_REL}::{TARGET_CLASS}::{TARGET_METHOD}"

ACCEPTANCE_REL = "orchestrator/acceptance.py"
SUITE_RUN_REL = "orchestrator/suite_run.py"
WAIT_CALL = "proc.wait(timeout=limit[0])"
TIMEOUT_EXCEPT = "except subprocess.TimeoutExpired"

# Страховочные потолки вложенного прогона: исход планки они не держат.
INNER_TIMEOUT = 80
RUN_TIMEOUT = 95

_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
             "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
             "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX",
             "PYTEST_CURRENT_TEST", "PYTEST_ADDOPTS", "PYTHONPATH")

MARK_CODE = '''

# --- разметка планки 01M55VG9Q5A5341ZED8NRJKVTC (только во временной копии) ---
import itertools as _plank_itertools

_PLANK_ORDER = _plank_itertools.count()


def _plank_mark(event, limit, pid, token=None):
    import json as _json
    import os as _os
    import signal as _signal
    import threading as _threading
    order = next(_PLANK_ORDER)
    if token is None:
        token = f"{{_os.getpid()}}-{{order}}"
    with open(_os.path.join({marks!r}, f"{{token}}-{{event}}.json"), "w",
              encoding="utf-8") as fh:
        fh.write(_json.dumps({{"event": event, "limit": limit,
                               "token": token, "pid": pid}}))
    if event == "before" and {freeze!r} and order == 0:
        hold = min(float(limit) + 3, 40)

        def _plank_hold():
            try:
                _os.killpg(pid, _signal.SIGSTOP)
            except OSError:
                return
            with open(_os.path.join({marks!r}, f"{{token}}-frozen.json"),
                      "w", encoding="utf-8") as fh:
                fh.write(_json.dumps({{"event": "frozen", "hold": hold,
                                       "token": token, "pid": pid}}))
            try:
                _threading.Event().wait(hold)
            finally:
                try:
                    _os.killpg(pid, _signal.SIGCONT)
                except OSError:
                    pass

        _threading.Thread(target=_plank_hold, daemon=True).start()
    return token
'''


class SiteMissing(AssertionError):
    """Место правки копии не найдено — код пульта сдвинулся."""


@dataclass
class Call:
    token: str
    limit: float
    before_ns: int
    end: str = ""
    end_ns: int = 0
    frozen: bool = False

    @property
    def elapsed(self) -> float:
        return (self.end_ns - self.before_ns) / 1e9


@dataclass
class Run:
    code: int | None
    output: str
    calls: list = field(default_factory=list)
    marked: bool = False

    @property
    def green(self) -> bool:
        return self.code == 0

    def context(self, what: str) -> str:
        calls = "\n".join(
            f"  вызов {c.token}: предел {c.limit}, исход {c.end or '—'}, "
            f"{c.elapsed if c.end else float('nan'):.2f} с реального времени"
            f"{', группа пробника заморожена' if c.frozen else ''}"
            for c in self.calls) or "  (разметка вызовов пуста)"
        marked = (f"вызовы proc.wait(timeout=limit[0]) копии:\n{calls}\n"
                  if self.marked else "")
        return (f"{what}: pytest {NODE} — код {self.code}\n{marked}"
                f"вывод (хвост):\n{self.output[-6000:]}")


def code_root() -> Path:
    if _pult.CODE_ROOT:
        return Path(_pult.CODE_ROOT).resolve()
    return Path(__file__).resolve().parents[3]


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _ENV_DROP}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def copy_code(dest: Path) -> None:
    """Файлы рабочей копии кода (отслеживаемые и новые неигнорируемые, без
    `tasks/`) — в `dest`."""
    root = code_root()
    res = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
         "--exclude-standard"], capture_output=True, env=_env(), check=True)
    for rel in res.stdout.decode("utf-8").split("\0"):
        if not rel or rel.startswith(("tasks/", ".artel/")):
            continue
        src = root / rel
        if not os.path.lexists(src) or src.is_dir():
            continue
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst, follow_symlinks=False)


def replace_once(copy: Path, rel: str, old: str, new: str) -> None:
    path = copy / rel
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SiteMissing(f"в {rel} копии «{old}» встречается "
                          f"{text.count(old)} раз, а не один")
    path.write_text(text.replace(old, new), encoding="utf-8")


def instrument(copy: Path, marks: Path, freeze: bool) -> None:
    """Разметка вызова `proc.wait(timeout=limit[0])` копии; `freeze` —
    первый такой вызов фонового процесса (прогон ветки) замораживает группу
    процессов прогона SIGSTOP на «предел + 3 с» реального времени."""
    path = copy / ACCEPTANCE_REL
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if WAIT_CALL in line]
    if len(hits) != 1:
        raise SiteMissing(f"в {ACCEPTANCE_REL} копии строк с «{WAIT_CALL}» "
                          f"{len(hits)}, а не одна")
    i = hits[0]
    pad = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    j = next((k for k in range(i + 1, min(i + 6, len(lines)))
              if TIMEOUT_EXCEPT in lines[k]), None)
    if j is None:
        raise SiteMissing(f"за «{WAIT_CALL}» в {ACCEPTANCE_REL} копии нет "
                          f"ветки «{TIMEOUT_EXCEPT}»")
    inner = lines[j + 1][:len(lines[j + 1]) - len(lines[j + 1].lstrip())]
    out = (lines[:i]
           + [f"{pad}_plank_token = _plank_mark('before', limit[0], "
              f"proc.pid)\n",
              lines[i],
              f"{pad}_plank_mark('returned', limit[0], proc.pid, "
              f"_plank_token)\n"]
           + lines[i + 1:j + 1]
           + [f"{inner}_plank_mark('timeout', limit[0], proc.pid, "
              f"_plank_token)\n"]
           + lines[j + 1:])
    text = "".join(out) + MARK_CODE.format(marks=str(marks), freeze=freeze)
    path.write_text(text, encoding="utf-8")


def read_calls(marks: Path) -> list:
    calls: dict = {}
    for path in sorted(marks.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        at = path.stat().st_mtime_ns
        if rec["event"] == "before":
            calls.setdefault(rec["token"], Call(rec["token"], 0.0, 0))
            calls[rec["token"]].limit = float(rec["limit"])
            calls[rec["token"]].before_ns = at
    for path in sorted(marks.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        call = calls.get(rec["token"])
        if call is None:
            continue
        if rec["event"] in ("returned", "timeout"):
            call.end, call.end_ns = rec["event"], path.stat().st_mtime_ns
        elif rec["event"] == "frozen":
            call.frozen = True
    return sorted(calls.values(), key=lambda c: c.before_ns)


def run_target(copy: Path) -> tuple:
    """(код, вывод) вложенного pytest целевого nodeid в копии; `None` —
    не вернулся за потолок."""
    env = _env()
    env["PYTHONPATH"] = str(copy)
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", NODE, "-p", "no:cacheprovider",
         "-p", "timeout", "-o", f"timeout={INNER_TIMEOUT}", "-q"],
        cwd=str(copy), env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True)
    try:
        raw, _ = proc.communicate(timeout=RUN_TIMEOUT)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        _kill(proc.pid)
        raw, _ = proc.communicate()
        code = None
    finally:
        _kill(proc.pid)
    return code, raw.decode("utf-8", errors="replace")


def _kill(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


_CACHE: dict = {}


def instrumented_run(freeze: bool = False) -> Run:
    """Целевой тест в копии с разметкой обрыва (результат кэшируется на
    процесс: разметка поведения не меняет)."""
    if freeze not in _CACHE:
        holder = Path(tempfile.mkdtemp(prefix="artel-plank-01m55vg9-"))
        try:
            copy, marks = holder / "code", holder / "marks"
            marks.mkdir()
            copy_code(copy)
            instrument(copy, marks, freeze)
            code, output = run_target(copy)
            _CACHE[freeze] = Run(code, output, read_calls(marks), marked=True)
        finally:
            shutil.rmtree(holder, ignore_errors=True)
    return _CACHE[freeze]


def mutated_run(*edits: tuple) -> Run:
    """Целевой тест в копии с мутацией: `edits` — (путь, было, стало)."""
    holder = Path(tempfile.mkdtemp(prefix="artel-plank-01m55vg9-"))
    try:
        copy = holder / "code"
        copy_code(copy)
        for rel, old, new in edits:
            replace_once(copy, rel, old, new)
        code, output = run_target(copy)
        return Run(code, output)
    finally:
        shutil.rmtree(holder, ignore_errors=True)
