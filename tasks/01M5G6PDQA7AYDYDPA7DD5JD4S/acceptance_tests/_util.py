"""Общий код планки 01M5G6PDQA7AYDYDPA7DD5JD4S: исходники кода задачи на
базе диффа и в голове, разбор `ast`, прогон pytest с зондом и прогон во
временной копии рабочей копии с текстовой мутацией."""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

ROOT = Path(CODE_ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TWO_SIDED = "tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py"
REPORT_OUTCOME = "tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py"
TIMEOUT_INTEGRATIONS = "tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py"
KILL_CLEANUP = "tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py"
STORE = "orchestrator/store.py"
SANDBOX = "tests/sandbox.py"
CONN_CLOSE_TEST = "tests/test_store_db_connection_close.py"

INNER_TIMEOUT_SEC = 100


def base_source(rel: str) -> str | None:
    """Текст `rel` на базе диффа задачи; `None` — файла там нет."""
    res = subprocess.run(["git", "-C", str(ROOT), "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else None


def head_source(rel: str) -> str | None:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.is_file() else None


def parse(source: str) -> ast.Module:
    return ast.parse(source)


def find_class(tree: ast.AST, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def class_methods(cls: ast.ClassDef) -> dict:
    return {n.name: n for n in cls.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def find_method(tree: ast.AST, name: str, cls: str | None = None):
    """(класс, метод) по имени метода; `cls` — имя класса либо любой."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and (cls is None or node.name == cls):
            found = class_methods(node).get(name)
            if found is not None:
                return node, found
    return None, None


def self_calls(func: ast.AST) -> list:
    """Имена `self.<имя>(…)`, вызванные в `func` (на любой глубине)."""
    return [n.func.attr for n in ast.walk(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"]


def assertion_texts(func: ast.AST) -> list:
    """`ast.unparse` вызовов `self.assert…(…)` в `func` по порядку."""
    calls = [n for n in ast.walk(func)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr.startswith("assert")
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"]
    calls.sort(key=lambda n: (n.lineno, n.col_offset))
    return [ast.unparse(n) for n in calls]


def missing(expected: list, found: list) -> list:
    """Элементы мультимножества `expected`, которых в `found` меньше."""
    left = list(found)
    lost = []
    for item in expected:
        if item in left:
            left.remove(item)
        else:
            lost.append(item)
    return lost


def guard_assertions(rel: str):
    """(учёт утверждений гейтом на базе, в голове, находки LOST) файла
    `rel` — `guard.test_assertions` с модулями `tests/` своей стороны и
    `guard.changed_test_assertions`, как гейт неослабления."""
    from scripts import guard
    base_mods = guard.TestModules(base_source)
    head_mods = guard.TestModules(head_source)
    base = guard.test_assertions(base_source(rel), rel, base_mods)
    head = guard.test_assertions(head_source(rel), rel, head_mods)
    return base, head, guard.changed_test_assertions(base or {}, head or {})


def qualified(table: dict, method: str, cls: str | None = None) -> str | None:
    for name in table:
        tail = name.replace("::", ".").split(".")
        if tail[-1] == method and (cls is None or cls in tail):
            return name
    return None


def new_test_paths() -> list:
    """Пути `tests/`, которых нет на базе диффа: закоммиченные задачей
    либо неотслеживаемые (`changed_paths`)."""
    return sorted(p for p in changed_paths()
                  if p.startswith("tests/") and p.endswith(".py")
                  and base_source(p) is None and (ROOT / p).is_file())


# --- прогон pytest с зондом -----------------------------------------------

PROBE = r'''
import json, os, select, selectors, sys

LOG = os.environ["ARTEL_PROBE_LOG"]
STATE = {"node": "", "wait": 0}

# Режим платформы (ANSWER-3, вариант A): `sys.platform` подменяется при
# загрузке зонда — раньше conftest и импорта тестов, — чтобы функция ожидания
# и тесты выбрали путь «Darwin» либо «вне Darwin» на любой машине.
REAL_PLATFORM = sys.platform
if os.environ.get("ARTEL_PROBE_PLATFORM"):
    sys.platform = os.environ["ARTEL_PROBE_PLATFORM"]
_real_select = select.select
_real_close = os.close


def _log(**rec):
    rec["node"] = STATE["node"]
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=repr) + "\n")


def _fd(obj):
    if isinstance(obj, bool):
        return None
    if isinstance(obj, int):
        return obj
    fileno = getattr(obj, "fileno", None)
    if callable(fileno):
        try:
            return fileno()
        except Exception:
            return None
    return None


class _SelectPoll:
    """`select.poll`, построенный на `select.select` (мутация AC-9)."""

    def __init__(self):
        self._fds = {}

    def register(self, fd, mask=select.POLLIN | select.POLLPRI | select.POLLOUT):
        self._fds[_fd(fd)] = mask

    def modify(self, fd, mask):
        self._fds[_fd(fd)] = mask

    def unregister(self, fd):
        self._fds.pop(_fd(fd), None)

    def poll(self, timeout=None):
        t = None if timeout is None or timeout < 0 else timeout / 1000
        rd = [f for f, m in self._fds.items() if m & (select.POLLIN | select.POLLPRI)]
        wr = [f for f, m in self._fds.items() if m & select.POLLOUT]
        r, w, _ = select.select(rd, wr, [], t)
        out = {}
        for f in r:
            out[f] = out.get(f, 0) | select.POLLIN
        for f in w:
            out[f] = out.get(f, 0) | select.POLLOUT
        return list(out.items())


def _logged_select(r, w, x, *timeout):
    """`select.select` с записью дескрипторов вызова внутри функции ожидания."""
    if STATE["wait"]:
        _log(kind="select", fds=[_fd(o) for o in [*r, *w, *x]])
    return _real_select(r, w, x, *timeout)


def _low_select(rd, wr, timeout):
    """Готовность `rd`/`wr` любого номера: копия каждого дескриптора на
    наименьший свободный номер (`os.dup`, то же открытое описание файла) и
    настоящий `select.select` по копиям. Так эмуляция `poll`/селекторов
    видит конец файла именованного канала и на Darwin, где `poll`/`kqueue`
    его не сообщают (эскалация AC-7, ANSWER-3)."""
    low = {}
    try:
        for f in {*rd, *wr}:
            low[f] = os.dup(f)
        r, w, _ = _real_select([low[f] for f in rd], [low[f] for f in wr], [], timeout)
    finally:
        for d in low.values():
            _real_close(d)
    back = {d: f for f, d in low.items()}
    return [back[d] for d in r], [back[d] for d in w]


class _EmuPoll(_SelectPoll):
    """`select.poll` режима «вне Darwin»: без предела номера дескриптора."""

    def poll(self, timeout=None):
        t = None if timeout is None or timeout < 0 else timeout / 1000
        rd = [f for f, m in self._fds.items() if m & (select.POLLIN | select.POLLPRI)]
        wr = [f for f, m in self._fds.items() if m & select.POLLOUT]
        if STATE["wait"]:
            _log(kind="poll", fds=sorted({*rd, *wr}))
        r, w = _low_select(rd, wr, t)
        out = {}
        for f in r:
            out[f] = out.get(f, 0) | select.POLLIN
        for f in w:
            out[f] = out.get(f, 0) | select.POLLOUT
        return list(out.items())


class _EmuSelector(selectors.SelectSelector):
    """Селектор режима «вне Darwin» (`DefaultSelector` и прочие)."""

    def _select(self, r, w, _x, timeout=None):
        if STATE["wait"]:
            _log(kind="poll", fds=sorted({*map(_fd, r), *map(_fd, w)}))
        rr, ww = _low_select(list(map(_fd, r)), list(map(_fd, w)), timeout)
        return rr, ww, []


def _replace_selectors(cls):
    for name in ("DefaultSelector", "PollSelector", "EpollSelector",
                 "KqueueSelector", "DevpollSelector"):
        if hasattr(selectors, name):
            setattr(selectors, name, cls)


def pytest_configure(config):
    import importlib, types
    if os.environ.get("ARTEL_PROBE_SELECT"):
        _replace_selectors(selectors.SelectSelector)
        select.poll = _SelectPoll
    elif os.environ.get("ARTEL_PROBE_PLATFORM") == "linux":
        _replace_selectors(_EmuSelector)
        select.poll = _EmuPoll
    select.select = _logged_select
    selectors.SelectSelector._select = staticmethod(_logged_select)
    from orchestrator import config as cfg

    class Logged(types.ModuleType):
        def __setattr__(self, name, value):
            if name == "GH_TIMEOUT_SEC":
                _log(kind="gh_timeout", value=value)
            super().__setattr__(name, value)

    _log(kind="gh_timeout_initial", value=cfg.GH_TIMEOUT_SEC)
    cfg.__class__ = Logged
    wait = os.environ.get("ARTEL_PROBE_WAIT")
    if wait:
        import fcntl
        mod_name, func_name = wait.split(":")
        mod = importlib.import_module(mod_name)
        real = getattr(mod, func_name)

        def wrapper(*args, **kwargs):
            fds = [_fd(a) for a in list(args) + list(kwargs.values())]
            _log(kind="wait", fds=[f for f in fds if f is not None])
            STATE["wait"] += 1
            try:
                return real(*args, **kwargs)
            finally:
                STATE["wait"] -= 1

        setattr(mod, func_name, wrapper)
        real_read, real_close, real_fcntl = os.read, os.close, fcntl.fcntl

        def read(fd, n):
            if STATE["node"]:
                _log(kind="read", fd=fd)
            return real_read(fd, n)

        def close(fd):
            if STATE["node"]:
                _log(kind="close", fd=fd)
            return real_close(fd)

        def fcntl_(fd, cmd, arg=0):
            res = real_fcntl(fd, cmd, arg)
            if cmd in (fcntl.F_DUPFD, getattr(fcntl, "F_DUPFD_CLOEXEC", -1)):
                _log(kind="dupfd", fd=_fd(fd), arg=arg, result=res)
            return res

        os.read, os.close, fcntl.fcntl = read, close, fcntl_


def pytest_collection_finish(session):
    clamp = os.environ.get("ARTEL_PROBE_CLAMP")
    done = set()
    for item in session.items:
        mod = getattr(item, "module", None)
        cls = getattr(mod, "Silence", None)
        if cls is None or id(cls) in done:
            continue
        done.add(id(cls))

        def setattr_(self, name, value):
            if name == "limit":
                _log(kind="silence_limit", value=value)
                if clamp and value:
                    value = min(value, float(clamp))
            object.__setattr__(self, name, value)

        cls.__setattr__ = setattr_


def pytest_runtest_setup(item):
    import resource
    STATE["node"] = item.nodeid
    _log(kind="rlimit", phase="setup",
         soft=resource.getrlimit(resource.RLIMIT_NOFILE)[0])


def pytest_runtest_teardown(item, nextitem):
    import resource
    _log(kind="rlimit", phase="teardown",
         soft=resource.getrlimit(resource.RLIMIT_NOFILE)[0])


def pytest_runtest_logfinish(nodeid, location):
    STATE["node"] = ""
'''


class Run:
    """Итог прогона pytest: код, вывод, исходы узлов, журнал зонда."""

    def __init__(self, proc, cases: dict, probe: list):
        self.code = proc.returncode
        self.out = proc.stdout + proc.stderr
        self.cases = cases
        self.probe = probe

    def failed(self, needle: str = "") -> dict:
        return {k: v for k, v in self.cases.items()
                if v[0] != "passed" and needle in k}

    def passed(self, needle: str = "") -> dict:
        return {k: v for k, v in self.cases.items()
                if v[0] == "passed" and needle in k}

    def probe_of(self, kind: str, node: str | None = None) -> list:
        return [r for r in self.probe if r.get("kind") == kind
                and (node is None or node in r.get("node", ""))]

    def tail(self, size: int = 6000) -> str:
        return self.out[-size:]


def run_pytest(nodeids: list, *, root: Path = ROOT, env: dict | None = None,
               timeout: int = INNER_TIMEOUT_SEC) -> Run:
    """pytest по узлам `nodeids` из корня `root` с зондом `PROBE`."""
    work = Path(tempfile.mkdtemp(prefix="plank-probe-"))
    try:
        (work / "_artel_probe.py").write_text(PROBE, encoding="utf-8")
        log = work / "probe.jsonl"
        log.write_text("", encoding="utf-8")
        junit = work / "junit.xml"
        full_env = dict(os.environ)
        # Только каталог зонда: корень `root` в PYTHONPATH увёл бы вложенные
        # прогоны (двусторонний прогон `two_sided`) к пакету `tests` корня.
        full_env["PYTHONPATH"] = os.pathsep.join(
            [str(work)] + [p for p in [os.environ.get("PYTHONPATH")] if p])
        full_env["ARTEL_PROBE_LOG"] = str(log)
        full_env.update(env or {})
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", *nodeids, "-p", "no:cacheprovider",
                 "-p", "timeout", "-o", f"timeout={timeout - 10}",
                 "-p", "_artel_probe", "-q", "--tb=short", "-rA",
                 f"--junitxml={junit}"],
                cwd=root, env=full_env, capture_output=True, text=True,
                timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            proc = subprocess.CompletedProcess(exc.cmd, -9, str(exc.stdout or ""),
                                               f"прогон превысил {timeout} с")
        cases = {}
        if junit.is_file() and junit.stat().st_size:
            for case in ET.parse(junit).getroot().iter("testcase"):
                key = f"{case.get('classname')}.{case.get('name')}"
                kind = "passed"
                text = ""
                for child in case:
                    if child.tag in ("failure", "error"):
                        kind = child.tag
                        text = (child.get("message") or "") + "\n" + (child.text or "")
                    elif child.tag == "skipped":
                        kind = "skipped"
                cases[key] = (kind, text)
        probe = [json.loads(line) for line in
                 log.read_text(encoding="utf-8").splitlines() if line.strip()]
        return Run(proc, cases, probe)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def mutated_copy(edits: dict) -> Path:
    """Временная копия рабочей копии кода (отслеживаемые и неотслеживаемые
    файлы вне `.gitignore`, без `tasks/`) с текстовыми правками `edits`:
    {путь: [(было, стало), …]}; каждая «было» обязана встретиться ровно один
    раз. Вызывающий удаляет копию."""
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard", "-z"],
        capture_output=True, text=True, check=True).stdout.split("\0")
    dst = Path(tempfile.mkdtemp(prefix="plank-mutant-"))
    for rel in listing:
        if not rel or rel.startswith("tasks/"):
            continue
        src = ROOT / rel
        if not src.is_file():
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    for rel, pairs in edits.items():
        path = dst / rel
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            count = text.count(old)
            if count != 1:
                shutil.rmtree(dst, ignore_errors=True)
                raise AssertionError(f"мутация {rel}: «{old}» встречается {count} раз")
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    return dst


def run_mutant(edits: dict, nodeids: list, env: dict | None = None) -> Run:
    dst = mutated_copy(edits)
    try:
        return run_pytest(nodeids, root=dst, env=env)
    finally:
        shutil.rmtree(dst, ignore_errors=True)
