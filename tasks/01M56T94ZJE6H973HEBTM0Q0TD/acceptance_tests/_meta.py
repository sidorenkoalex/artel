"""Общий код планки: вложенный прогон метода предела полного прогона.

Предмет критериев задачи — сам тестовый метод
`SuiteRunProfileLimitTest::test_ac5_suite_run_cuts_at_profile_limit_and_reports_it`.
Планка гоняет его отдельным процессом pytest (чёрный ящик: устройство
подмены часов в тесте не читается) и меняет только его окружение:

- `sitecustomize.py` в `PYTHONPATH` ставит прослойку над НАСТОЯЩИМИ
  `subprocess.Popen.wait` и `Popen._wait` в каждом процессе Python цепочки
  (окружение доходит до копии пульта: `cli` теста, фоновый процесс
  `suite-run` и прогон pytest пульта копируют `os.environ`). Подмена
  часов теста ставится позже, в `config.py` копии, — значит прослойка лежит
  ПОД ней, между ней и настоящим `Popen.wait`. Прослойка действует только
  в вызовах с пределом для процесса pytest из `_run_full_suite_to_log`; в
  остальных она — настоящий вызов без изменений;
- плагин pytest (`PYTEST_PLUGINS`) в прогоне ветки отмечает старт каждого
  теста и в режиме «после» держит его до первого чтения часов в
  `Popen.wait`.

Режим (`AC_META_MODE`):
- `natural` — ничего не навязано, только запись событий;
- `before` — настоящий `Popen.wait` вызывается лишь после старта всех
  тестов прогона (пробник стартовал до первого чтения часов — гонка 07.10);
- `after` — тест прогона стартует лишь после первого чтения часов в
  `Popen.wait` (потолок ожидания 3 с);
- `realtime` — обрыв возвращён к реальному отсчёту: `Popen._wait` сначала
  ждёт предел по настоящим `time.monotonic`, потом зовёт настоящий
  `_wait` (часы теста им опрашиваются);
- `noclock` — `Popen.wait` не опрашивает подменённый источник времени:
  обрыв по реальному времени вскоре после старта всех тестов прогона,
  `TimeoutExpired` бросает прослойка.

События пишутся строками JSON в `events.jsonl` каталога прогона.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

LIMIT_FILE = "tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py"
LIMIT_CLASS = "SuiteRunProfileLimitTest"
LIMIT_METHOD = "test_ac5_suite_run_cuts_at_profile_limit_and_reports_it"
LIMIT_NODE = f"{LIMIT_FILE}::{LIMIT_CLASS}::{LIMIT_METHOD}"
RUN_TIMEOUT_SEC = 112

SITECUSTOMIZE = r'''
# Планка 01M56T94ZJE6H973HEBTM0Q0TD: прослойка под подменой часов теста.
import json as _m_json
import os as _m_os
import subprocess as _m_subprocess
import sys as _m_sys
import time as _m_time

_m_dir = _m_os.environ.get("AC_META_DIR", "")
_m_mode = _m_os.environ.get("AC_META_MODE", "natural")
_m_mono = _m_time.monotonic
_m_sleep = _m_time.sleep
_m_real_wait = _m_subprocess.Popen.wait
_m_real_inner = _m_subprocess.Popen._wait


def _m_event(**fields):
    fields["pid"] = _m_os.getpid()
    fd = _m_os.open(_m_os.path.join(_m_dir, "events.jsonl"),
                    _m_os.O_WRONLY | _m_os.O_CREAT | _m_os.O_APPEND, 0o644)
    try:
        _m_os.write(fd, (_m_json.dumps(fields) + "\n").encode("utf-8"))
    finally:
        _m_os.close(fd)


def _m_cut_path(proc):
    args = proc.args if isinstance(proc.args, (list, tuple)) else [proc.args]
    if "pytest" not in [str(a) for a in args]:
        return False
    frame = _m_sys._getframe(1)
    while frame is not None:
        if frame.f_code.co_name == "_run_full_suite_to_log":
            return True
        frame = frame.f_back
    return False


def _m_all_started(pgid):
    try:
        with open(_m_os.path.join(_m_dir, f"items-{pgid}")) as fh:
            total = int(fh.read().strip() or 0)
    except (OSError, ValueError):
        return False
    calls = [n for n in _m_os.listdir(_m_dir) if n.startswith(f"call-{pgid}-")]
    return total > 0 and len(calls) >= total


def _m_until(cond, ceiling):
    deadline = _m_mono() + ceiling
    while _m_mono() < deadline:
        if cond():
            return True
        _m_sleep(0.02)
    return cond()


def _m_wait(self, timeout=None):
    if not _m_dir or timeout is None or not _m_cut_path(self):
        return _m_real_wait(self, timeout)
    pgid = self.pid
    _m_event(kind="wait_enter", pgid=pgid, timeout=timeout)
    if _m_mode == "before":
        _m_until(lambda: _m_all_started(pgid) or self.poll() is not None,
                 30.0)
        forced = _m_all_started(pgid)
        # Тело теста-пробника успевает записать свой старт.
        _m_sleep(0.5)
        _m_event(kind="order", mode="before", pgid=pgid, forced=forced,
                 exited=self.returncode is not None,
                 marks=sorted(n for n in _m_os.listdir(_m_dir)
                              if n.endswith(f"-{pgid}")
                              or n.startswith(f"call-{pgid}-")))
    if _m_mode == "noclock":
        _m_until(lambda: _m_all_started(pgid) or self.poll() is not None,
                 30.0)
        if _m_until(lambda: self.poll() is not None, 0.5):
            return self.returncode
        _m_event(kind="noclock_cut", pgid=pgid, timeout=timeout)
        raise _m_subprocess.TimeoutExpired(self.args, timeout)
    return _m_real_wait(self, timeout)


def _m_inner(self, timeout):
    if not _m_dir or timeout is None or not _m_cut_path(self):
        return _m_real_inner(self, timeout)
    pgid = self.pid
    open(_m_os.path.join(_m_dir, f"entered-{pgid}"), "w").close()
    if _m_mode == "realtime":
        deadline = _m_mono() + timeout
        while _m_mono() < deadline:
            if self.poll() is not None:
                return self.returncode
            _m_sleep(0.05)
        _m_event(kind="realtime_elapsed", pgid=pgid, timeout=timeout)
    try:
        return _m_real_inner(self, timeout)
    except _m_subprocess.TimeoutExpired:
        _m_event(kind="cut_by_real_wait", pgid=pgid, timeout=timeout)
        raise


_m_subprocess.Popen.wait = _m_wait
_m_subprocess.Popen._wait = _m_inner
'''

PLUGIN = r'''
# Планка 01M56T94ZJE6H973HEBTM0Q0TD: метки старта тестов прогона ветки.
import itertools
import os
import time

import pytest

_dir = os.environ.get("AC_META_DIR", "")
_mode = os.environ.get("AC_META_MODE", "natural")
_outer = os.environ.get("AC_META_OUTER_CWD", "")
_seq = itertools.count()


def _active():
    return bool(_dir) and os.path.realpath(os.getcwd()) != _outer


def pytest_collection_finish(session):
    if _active() and session.items:
        path = os.path.join(_dir, f"items-{os.getpgid(0)}")
        with open(path + ".tmp", "w") as fh:
            fh.write(str(len(session.items)))
        os.replace(path + ".tmp", path)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item):
    if not _active():
        return
    pgid = os.getpgid(0)
    if _mode == "after":
        flag = os.path.join(_dir, f"entered-{pgid}")
        deadline = time.monotonic() + 3.0
        while not os.path.exists(flag) and time.monotonic() < deadline:
            time.sleep(0.02)
    open(os.path.join(_dir, f"call-{pgid}-{os.getpid()}-{next(_seq)}"),
         "w").close()
'''


class NestedRun:
    """Итог вложенного прогона: исход узла, вывод pytest, события."""

    def __init__(self, outcome: str, output: str, events: list):
        self.outcome = outcome
        self.output = output
        self.events = events

    def of(self, kind: str) -> list:
        return [e for e in self.events if e.get("kind") == kind]

    def context(self) -> str:
        events = "\n".join(json.dumps(e, ensure_ascii=False)
                           for e in self.events) or "(нет)"
        return (f"исход узла: {self.outcome}\nсобытия прослойки:\n{events}\n"
                f"вывод pytest (хвост):\n{self.output[-6000:]}")


def _kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_limit_test(mode: str = "natural", root: Path | None = None,
                   node: str = LIMIT_NODE) -> NestedRun:
    """Прогоняет узел теста предела вложенным pytest из `root` (по
    умолчанию — рабочая копия кода) в режиме прослойки `mode`."""
    root = Path(root or CODE_ROOT).resolve()
    work = Path(tempfile.mkdtemp(prefix="artel-ac-meta-")).resolve()
    try:
        hooks = work / "hooks"
        events_dir = work / "events"
        hooks.mkdir()
        events_dir.mkdir()
        (hooks / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
        (hooks / "ac_meta_plugin.py").write_text(PLUGIN, encoding="utf-8")
        junit = work / "junit.xml"
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in (str(hooks), env.get("PYTHONPATH", "")) if p)
        env["PYTEST_PLUGINS"] = "ac_meta_plugin"
        env["AC_META_DIR"] = str(events_dir)
        env["AC_META_MODE"] = mode
        env["AC_META_OUTER_CWD"] = os.path.realpath(root)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.Popen(
            [sys.executable, "-m", "pytest", node, "-p", "no:cacheprovider",
             "-q", "--tb=long", f"--junitxml={junit}"],
            cwd=str(root), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True)
        try:
            raw, _ = proc.communicate(timeout=RUN_TIMEOUT_SEC)
            timed_out = False
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid)
            raw, _ = proc.communicate()
            timed_out = True
        finally:
            _kill_group(proc.pid)
        output = raw.decode("utf-8", errors="replace")
        outcome = "timeout" if timed_out else _outcome(junit)
        events = []
        path = events_dir / "events.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        return NestedRun(outcome, output, events)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _outcome(junit: Path) -> str:
    """passed / failed / error / skipped / missing — по junit-отчёту."""
    if not junit.exists():
        return "missing"
    cases = ET.parse(junit).getroot().iter("testcase")
    found = [c for c in cases if c.get("name") == LIMIT_METHOD]
    if len(found) != 1:
        return "missing"
    case = found[0]
    for tag in ("error", "failure", "skipped"):
        if case.find(tag) is not None:
            return {"failure": "failed"}.get(tag, tag)
    return "passed"


def copy_tree(dest: Path) -> Path:
    """Копия рабочей копии кода без `.git`, `tasks/`, `.artel/` и кешей —
    поле для мутаций кода пульта; тест предела копирует пульт из неё."""
    shutil.copytree(
        CODE_ROOT, dest, symlinks=True,
        ignore=lambda d, names: [
            n for n in names
            if n in {".git", "__pycache__", ".pytest_cache"}
            or (Path(d).resolve() == Path(CODE_ROOT).resolve()
                and n in {"tasks", ".artel"})])
    return dest


def mutate(root: Path, rel: str, old: str, new: str) -> None:
    """Заменяет в `root/rel` ровно одно вхождение `old` на `new`; места
    мутации нет — `AssertionError` с именем файла."""
    path = root / rel
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise AssertionError(f"место мутации не найдено однозначно в {rel}: "
                             f"{old!r} — {text.count(old)} вхождений")
    path.write_text(text.replace(old, new), encoding="utf-8")
