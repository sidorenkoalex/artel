"""Песочница отчётов исходов компонента: сценарии подменённого раннера, установки и учебные записи проектов для тестов `orchestrator/reporters/outcome.py`."""
import contextlib
import dataclasses
import hashlib
import importlib.metadata
import inspect
import io
import json
import os
import random
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, config, doctor, idgen, project_profile,
                          stack, store, suite_run)
from orchestrator.advance_gates import two_sided
from tests.fd_wait import high_fd, select_limited, wait_readable
from tests.sandbox import RealGitSandbox, artel_target_entry, make_project_repo

LETTERS = "abcdefghijkmnpqrstuvwxyz"
REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
VITEST_BASE = ["node_modules/.bin/vitest", "run", "--config", "vitest.config.js",
               "--allowOnly=false", "--update=false", "--retry=0"]
REQUIRE_ASSERTIONS = "--expect.requireAssertions"
VITEST_REPORT_ARGS = ["--reporter=default", "--reporter={pult_reporter}",
                      "--outputFile={path}"]
UNKNOWN_PREFIX = "итог неизвестен: "
INSTALL_WITHOUT_LOCK = "install без файла блокировки не исполняется"
CHILD_GUARD_SEC = 30
PATH_FLAGS = ["--junitxml", "--outputFile", "--report-to"]

DRIVER = r'''import hashlib, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
argv0, args = sys.argv[1], sys.argv[2:]
with open(os.path.join(HERE, "scenario.json"), encoding="utf-8") as fh:
    scen = json.load(fh)
if args[:1] == ["--version"]:
    print(scen.get("version_out", ""))
    sys.exit(0)
nm = os.path.join(os.getcwd(), "node_modules")
record = {"argv0": argv0, "args": args, "cwd": os.getcwd(),
          "env": dict(os.environ), "pid": os.getpid(),
          "pgid": os.getpgid(0),
          "node_modules": os.path.realpath(nm) if os.path.exists(nm) else None}
with open(os.path.join(HERE, "probe.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\n")
report = None
for i, arg in enumerate(args):
    for flag in scen.get("path_flags", []):
        if arg == flag and i + 1 < len(args):
            report = args[i + 1]
        elif arg.startswith(flag + "="):
            report = arg[len(flag) + 1:]
if scen.get("fifo"):
    fd = os.open(scen["fifo"], os.O_WRONLY)
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(600)"],
        pass_fds=(fd,), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    with open(os.path.join(HERE, "pids"), "a", encoding="utf-8") as fh:
        fh.write(f"{child.pid}\n{os.getpid()}\n")
if scen.get("sleep"):
    time.sleep(scen["sleep"])
    with open(os.path.join(HERE, "slept"), "a", encoding="utf-8") as fh:
        fh.write("1\n")
if report is not None and scen.get("report") is not None:
    folder = os.path.dirname(report)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(report, "w", encoding="utf-8") as fh:
        fh.write(scen["report"])
sys.stdout.write(scen.get("stdout", ""))
sys.stdout.flush()
sys.exit(scen.get("code", 0))
'''

INSTALLER = r'''import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
lock = os.path.join(os.getcwd(), "package-lock.json")
digest = None
if os.path.isfile(lock):
    with open(lock, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
with open(os.path.join(HERE, "installs.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"cwd": os.getcwd(), "argv": sys.argv,
                         "lock": digest}) + "\n")
if os.path.exists(os.path.join(HERE, "install_fails")):
    sys.stderr.write("поддельная установка: сбой npm ci\n")
    sys.exit(1)
os.makedirs(os.path.join("node_modules", ".bin"), exist_ok=True)
target = os.path.join("node_modules", ".bin", "vitest")
with open(os.path.join(HERE, "run"), encoding="utf-8") as src, \
        open(target, "w", encoding="utf-8") as dst:
    dst.write(src.read())
os.chmod(target, 0o755)
'''

ENTRY_HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def quoted(items) -> str:
    """Потоковый список `yamlmini` — без кавычек: кавычки в нём не
    разбираются."""
    return "[" + ", ".join(str(item) for item in items) + "]"


def block(fields: dict, indent: str) -> str:
    """Поля для `targets.yaml`: отображение — блоком (значения в
    кавычках), список — потоковым списком, прочее — как есть."""
    out = []
    for key, value in fields.items():
        if isinstance(value, dict):
            out.append(f"{indent}{key}:\n")
            out.extend(f'{indent}  {k}: "{v}"\n' for k, v in value.items())
        elif isinstance(value, (list, tuple)):
            out.append(f"{indent}{key}: {quoted(value)}\n")
        else:
            out.append(f"{indent}{key}: {value}\n")
    return "".join(out)


def entry(project: str, fields: dict, comp: str | None = None) -> str:
    """Запись проекта: `test_profile` (`comp` не назван) либо
    `components:` с одним компонентом `comp`."""
    if comp is None:
        return ENTRY_HEAD.format(name=project) + "    test_profile:\n" + \
            block(fields, "      ")
    return (ENTRY_HEAD.format(name=project) + "    components:\n"
            + f"      {comp}:\n" + block(fields, "        "))


def fld(record, name: str):
    """Поле записи итога теста — атрибут или ключ."""
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


def junit(cases) -> str:
    """Отчёт JUnit: `cases` — (файл от workdir, имя, исход, тип, сообщение,
    время)."""
    body = []
    for file, name, kind, etype, message, seconds in cases:
        attrs = (f'classname="{file}" file="{file}" name="{name}" '
                 f'time="{seconds}"')
        inner = {
            "passed": "",
            "failed": f'<failure type="{etype}" message="{message}">'
                      f'{etype}: {message}</failure>',
            "error": f'<error type="{etype}" message="{message}">'
                     f'{etype}: {message}</error>',
            "skipped": f'<skipped type="pytest.skip" message="{message}"/>',
        }[kind]
        body.append(f"<testcase {attrs}>{inner}</testcase>")
    counts = {k: sum(1 for c in cases if c[2] == k)
              for k in ("failed", "error", "skipped")}
    return ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
            f'<testsuite name="pytest" errors="{counts["error"]}" '
            f'failures="{counts["failed"]}" skipped="{counts["skipped"]}" '
            f'tests="{len(cases)}">' + "".join(body)
            + "</testsuite></testsuites>")


def vitest_test(file: str, name: str, state: str = "pass", mode: str = "run",
                fails: bool = False, retry_count: int = 0,
                error_name: str | None = None, timeout: bool = False,
                hook: str | None = None, duration_ms: int = 5) -> dict:
    return {"file": file, "name": name, "state": state, "mode": mode,
            "fails": fails, "retry_count": retry_count,
            "error_name": error_name, "timeout": timeout, "hook": hook,
            "duration_ms": duration_ms}


def vitest_report(tests) -> str:
    return json.dumps({"tests": list(tests)})


def entry_values(entry_value) -> list:
    """Значения записи таблицы версий Vitest любой формы."""
    if isinstance(entry_value, Mapping):
        return list(entry_value.values())
    if dataclasses.is_dataclass(entry_value):
        return [getattr(entry_value, f.name)
                for f in dataclasses.fields(entry_value)]
    if isinstance(entry_value, (tuple, list)):
        return list(entry_value)
    return [entry_value]


def flipped(entry_value):
    """Та же запись таблицы версий, но булевы значения — `False`
    («флаг `--expect.requireAssertions` не принимается»)."""
    if isinstance(entry_value, Mapping):
        return {k: (False if isinstance(v, bool) else v)
                for k, v in entry_value.items()}
    if dataclasses.is_dataclass(entry_value):
        return dataclasses.replace(entry_value, **{
            f.name: False for f in dataclasses.fields(entry_value)
            if isinstance(getattr(entry_value, f.name), bool)})
    values = [False if isinstance(v, bool) else v
              for v in entry_values(entry_value)]
    if isinstance(entry_value, tuple) and type(entry_value) is not tuple:
        return type(entry_value)(*values)  # именованный кортеж
    return tuple(values)


def under(path, folder) -> bool:
    real, base = os.path.realpath(str(path)), os.path.realpath(str(folder))
    return real == base or real.startswith(base.rstrip(os.sep) + os.sep)


def report_arg(args: list, flag: str) -> str | None:
    """Значение флага `flag` в argv: `flag значение` или `flag=значение`."""
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


class Fake:
    """Подменённый раннер и поддельная установка в своём каталоге вне
    дерева прогона: сценарий, зонд, журнал установок."""

    def __init__(self, case: unittest.TestCase, label: str):
        self.dir = Path(tempfile.mkdtemp(prefix=f"artel-fake-{label}-")).resolve()
        case.addCleanup(shutil.rmtree, self.dir, True)
        case.addCleanup(self.kill_all)
        python = stack.pytest_python_executable()
        (self.dir / "driver.py").write_text(DRIVER, encoding="utf-8")
        self.wrapper = self.dir / "run"
        self.wrapper.write_text(
            f"#!/bin/sh\nexec '{python}' '{self.dir / 'driver.py'}' "
            f'"$0" "$@"\n', encoding="utf-8")
        self.installer = self.dir / "install"
        self.installer.write_text(f"#!{python}\n{INSTALLER}", encoding="utf-8")
        for path in (self.wrapper, self.installer):
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        self.scenario()

    def tool(self, name: str) -> Path:
        """Копия поддельной установки под именем `name` (`uv` и т. п.)."""
        path = self.dir / name
        shutil.copyfile(self.installer, path)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def scenario(self, **values) -> None:
        data = {"path_flags": PATH_FLAGS, "code": 0, "stdout": "",
                "report": None}
        data.update(values)
        (self.dir / "scenario.json").write_text(json.dumps(data),
                                                encoding="utf-8")

    def lines(self, name: str) -> list:
        path = self.dir / name
        if not path.is_file():
            return []
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line]

    def records(self) -> list:
        return self.lines("probe.jsonl")

    def runs(self) -> list:
        """Вызовы прогона (у Vitest — подкоманда `run`)."""
        return [r for r in self.records() if r["args"][:1] == ["run"]
                or not r["argv0"].endswith("node_modules/.bin/vitest")]

    def installs(self) -> list:
        return self.lines("installs.jsonl")

    def slept(self) -> int:
        """Сколько раз раннер доспал сценарную паузу до конца."""
        path = self.dir / "slept"
        return len(path.read_text(encoding="utf-8").split()) \
            if path.is_file() else 0

    def fail_install(self) -> None:
        (self.dir / "install_fails").write_text("1", encoding="utf-8")

    def kill_all(self) -> None:
        path = self.dir / "pids"
        if not path.is_file():
            return
        for line in path.read_text(encoding="utf-8").split():
            with contextlib.suppress(ProcessLookupError, PermissionError,
                                     ValueError):
                os.kill(int(line), signal.SIGKILL)


def writable(root: Path) -> None:
    """Права записи всему дереву `root` и каталогам, на которые ведут
    ссылки `node_modules`: каталог пульта только для чтения иначе не
    убрать."""
    seen = set()
    stack_ = [Path(root)]
    while stack_:
        top = stack_.pop()
        real = os.path.realpath(top)
        if real in seen or not os.path.isdir(real):
            continue
        seen.add(real)
        for dirpath, dirnames, _files in os.walk(real):
            with contextlib.suppress(OSError):
                os.chmod(dirpath, 0o755)
            for name in dirnames:
                full = os.path.join(dirpath, name)
                if os.path.islink(full):
                    stack_.append(Path(full))
                with contextlib.suppress(OSError):
                    os.chmod(full, 0o755)


class ReportSandbox(RealGitSandbox):
    """Учебные проекты с компонентами и подменённым раннером."""

    def setUp(self):
        super().setUp()
        self.addCleanup(writable, self.root)
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        self.leak = f"ARTEL_LEAK_{self.word().upper()}"
        patcher = mock.patch.dict(os.environ, {self.leak: self.word(10)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.entries: list = []

    def word(self, size: int = 7) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    # ------------------------------------------------------------ записи

    def write_targets(self) -> str:
        text = "targets:\n" + artel_target_entry() + "".join(self.entries)
        config.TARGETS.write_text(text, encoding="utf-8")
        return text

    def project(self, fields: dict, files: dict, comp: str | None = None,
                name: str | None = None) -> tuple:
        """(имя проекта, клон): запись — в `targets.yaml`, файлы — первым
        коммитом проекта после пустого."""
        name = name or f"p{self.word()}"
        self.entries.append(entry(name, fields, comp))
        self.write_targets()
        clone = make_project_repo(name, origin=False)
        self.commit(clone, files)
        return name, clone

    def commit(self, clone: Path, files: dict, message: str = "файлы") -> None:
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "--", *files)
        self.git("-C", str(clone), "commit", "-q", "-m", message)

    def task(self, project: str) -> str:
        task_id = idgen.new_task_id()
        store.insert_task(store.db(), task_id, f"Задача {self.word()}",
                          "in_dev", f"task/{task_id.lower()}-{self.word()}",
                          project, 25.0)
        return task_id

    def profile(self, project: str):
        decision = project_profile.decide(project)
        self.assertIsNotNone(decision.profile, self.note(
            f"профиль проекта {project} не получен: {decision.refusal}\n"
            f"{config.TARGETS.read_text(encoding='utf-8')}"))
        return decision.profile

    def full(self, root: Path, task_id: str, profile) -> tuple:
        """(итог `full_suite`, вывод узла)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            run = acceptance.full_suite(root, task_id, command=profile,
                                        fresh=True)
        return run, buf.getvalue()

    def records_of(self, run) -> list:
        tests = getattr(run, "tests", None)
        self.assertIsNotNone(tests, self.note(
            f"у итога полного прогона нет поля tests: {run}"))
        return list(tests)

    def by_id(self, run, test_id: str):
        found = [r for r in self.records_of(run) if fld(r, "id") == test_id]
        self.assertEqual(len(found), 1, self.note(
            f"итога теста {test_id} нет (или не один): "
            f"{[fld(r, 'id') for r in self.records_of(run)]}"))
        return found[0]

    def assert_unknown(self, run, context: str) -> None:
        self.assertFalse(run.green, self.note(f"{context}: {run}"))
        self.assertEqual(run.outcome, acceptance.FULL_SUITE_NOT_STARTED,
                         self.note(f"{context}: {run}"))
        self.assertTrue(run.detail.startswith(UNKNOWN_PREFIX),
                        self.note(f"{context}: {run.detail}"))

    def plank_dir(self) -> Path:
        """Каталог задачи с планкой из одного файла — вне дерева прогона."""
        tdir = Path(tempfile.mkdtemp(prefix="artel-plank-")).resolve()
        self.addCleanup(shutil.rmtree, tdir, True)
        task_dir = tdir / f"T{self.word()}"
        (task_dir / "acceptance_tests").mkdir(parents=True)
        (task_dir / "acceptance_tests" / f"test_{self.word()}.py").write_text(
            "import unittest\n\n\nclass P(unittest.TestCase):\n"
            "    def test_p(self):\n        self.assertTrue(True)\n",
            encoding="utf-8")
        return task_dir

    # ---------------------------------------------------- junit-xml

    def junit_fields(self, fake: Fake, workdir: str, **extra) -> dict:
        fields = {"command": [str(fake.wrapper)],
                  "long_lived_dir": f"{workdir}/src" if workdir else "src",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": [f"{workdir or 'src'}/**"],
                  "mutation_claim_scope": [f"{workdir or 'src'}/**"],
                  "report": "junit-xml"}
        if workdir:
            fields.update(runner="pytest-own", workdir=workdir)
        fields.update(extra)
        return fields

    def junit_component(self, **extra) -> dict:
        """Проект с одним компонентом `junit-xml` в `workdir`: словарь
        сценария (проект, клон, компонент, workdir, переменная `env`,
        подменённый раннер, задача, профиль)."""
        fake = Fake(self, "junit")
        workdir = f"fe{self.word(5)}"
        comp = f"c{self.word(5)}"
        env_name = f"PROBE_ENV_{self.word().upper()}"
        env_value = self.word(12)
        fields = self.junit_fields(fake, workdir, env={env_name: env_value},
                                   report_args=["--junitxml", "{path}"])
        fields.update(extra)
        name, clone = self.project(fields, {
            f"{workdir}/src/x.test.jsx": "// тест\n"}, comp=comp)
        return {"name": name, "clone": clone, "comp": comp, "wd": workdir,
                "env": (env_name, env_value), "fake": fake,
                "task": self.task(name), "profile": self.profile(name)}

    # ---------------------------------------------------- pult-vitest

    def table(self) -> Mapping:
        table = getattr(project_profile, "VITEST_VERSION_FLAGS", None)
        self.assertIsInstance(table, Mapping, self.note(
            "нет таблицы project_profile.VITEST_VERSION_FLAGS"))
        self.assertTrue(table, self.note("таблица версий Vitest пуста"))
        return table

    def accepted_major(self):
        """(ключ, запись) версии таблицы, принимающей
        `--expect.requireAssertions`."""
        for key, value in self.table().items():
            if True in [v for v in entry_values(value) if isinstance(v, bool)]:
                return key, value
        self.fail(self.note(f"в таблице нет версии, принимающей "
                            f"{REQUIRE_ASSERTIONS}: {dict(self.table())}"))

    def cache_flag(self, value) -> str:
        flags = [v for v in entry_values(value)
                 if isinstance(v, str) and v.startswith("--")]
        self.assertTrue(flags, self.note(f"у записи таблицы нет флага кэша: "
                                         f"{value!r}"))
        return flags[0]

    def absent_major(self) -> int:
        majors = [int(str(k)) for k in self.table() if str(k).isdigit()]
        return max(majors + [0]) + self.rng.randint(5, 50)

    def version(self, major) -> str:
        return f"{major}.{self.rng.randint(0, 9)}.{self.rng.randint(0, 20)}"

    def vitest_component(self, *, workdir: bool = True, version=None,
                         lock: bool = True, timeout: int = 60,
                         **extra) -> dict:
        """Проект с одним компонентом `pult-vitest`: с `workdir` (и тогда
        `runner: pytest-own` — правило записи с одним компонентом) либо в
        корне без поля `runner`."""
        fake = Fake(self, "vitest")
        wd = f"web{self.word(5)}" if workdir else ""
        comp = f"v{self.word(5)}"
        if version is None:
            version = self.version(self.accepted_major()[0])
        prefix = f"{wd}/" if wd else ""
        fields = {"command": VITEST_BASE,
                  "long_lived_dir": f"{prefix}src",
                  "long_lived_name": "<id>_<name>.test.js",
                  "weakening_scope": [f"{prefix}src/**"],
                  "mutation_claim_scope": [f"{prefix}src/**"],
                  "report": "pult-vitest",
                  "report_args": VITEST_REPORT_ARGS,
                  "failure_errors": ["AssertionError"],
                  "select": ["{tests}"],
                  "install": [str(fake.installer)],
                  "full_suite_timeout_sec": timeout,
                  "tools": {"vitest": version}}
        env = None
        if wd:
            env = (f"PROBE_ENV_{self.word().upper()}", self.word(12))
            fields.update(runner="pytest-own", workdir=wd,
                          env={env[0]: env[1]})
        fields.update(extra)
        fields = {k: v for k, v in fields.items() if v is not None}
        files = {f"{prefix}package.json": '{"name": "web"}\n',
                 f"{prefix}vitest.config.js": "export default {}\n",
                 f"{prefix}src/a.test.js": "// тест\n"}
        if lock:
            files[f"{prefix}package-lock.json"] = json.dumps(
                {"lockfileVersion": 3, "seed": self.word()}) + "\n"
        fake.scenario(version_out=f"vitest/{version} linux-x64 node-v22.11.0",
                      report=vitest_report([vitest_test("src/a.test.js", "ok")]))
        name, clone = self.project(fields, files, comp=comp)
        return {"name": name, "clone": clone, "comp": comp, "wd": wd,
                "env": env, "fake": fake, "version": version,
                "task": self.task(name), "profile": self.profile(name)}

    def wd_path(self, case: dict) -> Path:
        return case["clone"] / case["wd"] if case["wd"] else case["clone"]

    def vid(self, case: dict, file: str, name: str) -> str:
        path = f"{case['wd']}/{file}" if case["wd"] else file
        return project_profile.test_id(case["comp"], path, name)
