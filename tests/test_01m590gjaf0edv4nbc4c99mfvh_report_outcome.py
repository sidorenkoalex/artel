"""Итог тестов компонента из отчёта: `junit-xml`, отчётчик пульта `pult-vitest`, окружение и установка пультом, сторож зависших тестов; прежний разбор у артели.

Группа: долгоживущий
Красен до реализации: пульт читает итог любого прогона из кода возврата и текста pytest — у компонента с отчётом зелёный код без отчёта даёт зелёный итог, `FullSuiteRun` не несёт поля `tests`, `pult-vitest` не получает ни флагов пульта, ни отчётчика, ни установки, `project_profile.VITEST_VERSION_FLAGS` нет, ключ итога не видит имени компонента, сторож зависших тестов узнаёт только pytest/unittest; тесты прежнего поведения артели (AC-4 п. 3, AC-6 п. 1–2, AC-12 п. 2, AC-20) зелены с рождения.

Песочница — `tests.sandbox.RealGitSandbox`: пути `config` во временном
каталоге, `config.TARGETS` — временный файл, сценарий пишет в него запись
артели песочницы (`artel_target_entry`) и учебные записи проектов; клон
проекта — `make_project_repo` по адресу `repo_context` (настоящий git).
Профиль компонента берётся публичным входом гейтов
`project_profile.decide(<проект>).profile` записи с одним компонентом и
передаётся местам прогона прежним каналом (`command=` у `acceptance.run`,
`collect`, `run_repeat`, `full_suite`; `profile=` у `run_plank` и
`two_sided.run`). Узел полного прогона — `acceptance.full_suite(root,
task_id, command=<профиль>, fresh=True)`; итог по каждому тесту — поле
`FullSuiteRun.tests` (ANSWER-2, В3): записи с атрибутами (или ключами)
`id`, `outcome`, `failure`, `skip_reason`, `time`, у `pult-vitest` ещё
`mode`, `fails`, `retries`.

Подменённый раннер — исполняемая обёртка `/bin/sh` вне дерева прогона,
которая зовёт драйвер на Python интерпретатором пульта. Драйвер пишет в
каталог зонда свой argv (с `argv[0]`, каким его запустили), `cwd`,
окружение, группу процессов и путь `node_modules`, затем по сценарию
(JSON рядом с ним) пишет заранее заданный отчёт по пути после флага
отчёта, печатает заданный вывод и выходит с заданным кодом. Для
`pult-vitest` раннер ставит поддельная установка (`install` компонента —
исполняемый файл на Python): как `npm ci`, она кладёт
`node_modules/.bin/vitest` (ту же обёртку) в свой рабочий каталог и
записывает в журнал установок свой `cwd` и сумму `package-lock.json`.
Отчёт `pult-vitest` — форма ANSWER-2, В2: `{"tests": [{"file", "name",
"state", "mode", "fails", "retry_count", "error_name", "timeout", "hook",
"duration_ms"}]}`. Версия Vitest — из таблицы
`project_profile.VITEST_VERSION_FLAGS` (ANSWER-2, В1): положительные
сценарии берут главную версию таблицы, принимающую
`--expect.requireAssertions`; отказ — версию вне таблицы. Форма записи
таблицы не навязывается: флаг кэша — её строковое значение, начинающееся с
`--`, «принимает» — её булево значение.

В окружении пульта на время теста — случайная переменная `ARTEL_LEAK_*`;
имена проектов, компонентов, каталогов, файлов, тестов и значения — из
`random`, зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (модуль в `orchestrator/`,
удалён, не закоммичен): профиль компонента из `decide` с `report_args`/
`select`/`failure_errors`/`checks_local`, разбор JUnit и JSON отчётчика в
`FullSuiteRun.tests`, таблица версий Vitest с записью для Vitest 4,
установка в каталог пульта по сумме файла блокировки со ссылкой только для
чтения, ключ итога с именем компонента и `report_args`, сторож по `command`
записей — все методы файла зелёные. Сценарий AC-15 после смены файла
блокировки застаёт в рабочей копии ссылку `node_modules` на прежнюю
установку пульта: подменой она не считается (подмена — свой каталог или
ссылка мимо каталога пульта, AC-16).
"""
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


# ------------------------------------------------------------ junit-xml

class JunitReportOutcomeTest(ReportSandbox):

    def test_ac1_outcome_follows_report_not_runner_output(self):
        """Компонент `junit-xml`: исход полного прогона — по отчёту, а не по тексту вывода раннера.

        Сценарий: учебный компонент `junit-xml` (имена от зерна), раннер
        всегда выходит с кодом 0. Для каждого из двух текстов вывода
        («N passed …» и «N failed …») раннер пишет по очереди: зелёный
        отчёт — итог зелёный; отчёт с проваленным тестом — итог красный, и
        деталь называет упавший тест; отчёта нет — исход «неизвестно», не
        зелёный. Тот же вывод с другим отчётом даёт другой исход.

        Ловит мутацию: итог компонента по-прежнему читается из кода
        возврата и итоговой строки pytest — зелёный код без отчёта и с
        проваленным отчётом даёт «зелёный прогон», а вывод «N failed» при
        зелёном отчёте — «красный прогон».
        """
        case = self.junit_component()
        bad = f"test_{self.word()}"
        green = junit([("src/x.test.jsx", f"test_{self.word()}", "passed",
                        "", "", "0.1")])
        failed = junit([("src/x.test.jsx", f"test_{self.word()}", "passed",
                         "", "", "0.1"),
                        ("src/x.test.jsx", bad, "failed", "AssertionError",
                         "boom", "0.2")])
        n = self.rng.randint(2, 9)
        for stdout in (f"{n} passed in 0.1s\n", f"{n} failed in 0.1s\n"):
            seen = {}
            for label, report in (("зелёный", green), ("красный", failed),
                                  ("нет", None)):
                with self.subTest(stdout=stdout, report=label):
                    case["fake"].scenario(stdout=stdout, report=report)
                    run, out = self.full(case["clone"], case["task"],
                                         case["profile"])
                    seen[label] = run.outcome
                    context = f"вывод {stdout!r}, отчёт {label}: {out}"
                    if label == "зелёный":
                        self.assertTrue(run.green, self.note(f"{context}\n{run}"))
                        self.assertEqual(run.outcome, acceptance.FULL_SUITE_GREEN,
                                         self.note(context))
                    elif label == "красный":
                        self.assertFalse(run.green, self.note(f"{context}\n{run}"))
                        self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED,
                                         self.note(f"{context}\n{run}"))
                        self.assertIn(bad, run.detail, self.note(run.detail))
                    else:
                        self.assert_unknown(run, context)
            self.assertEqual(len(set(seen.values())), 3, self.note(
                f"вывод {stdout!r}: исходы не различаются отчётом: {seen}"))

    def test_ac2_empty_or_unreadable_report_is_unknown(self):
        """Ненулевой код при отчёте без тестов и неразборчивый отчёт — исход «неизвестно», не зелёный.

        Сценарий: учебный компонент `junit-xml`. (а) Раннер выходит с
        ненулевым кодом и пишет отчёт без единого testcase. (б) Раннер
        пишет обрезанный XML — с кодом 0 и с ненулевым кодом. В каждом
        случае `full_suite` даёт `FULL_SUITE_NOT_STARTED` с деталью
        «итог неизвестен: …».

        Ловит мутацию: пустой отчёт читается как «тестов нет — зелено», а
        неразобранный отчёт — как красный прогон по коду возврата (или
        зелёный при коде 0); исход «неизвестно» не наступает.
        """
        case = self.junit_component()
        code = self.rng.randint(1, 3)
        empty = junit([])
        broken = junit([("src/x.test.jsx", "test_a", "passed", "", "", "0.1")])
        broken = broken[:self.rng.randint(40, len(broken) - 20)]
        for label, report, rc in (("пустой", empty, code),
                                  ("обрезанный, код 0", broken, 0),
                                  ("обрезанный, ненулевой код", broken, code)):
            with self.subTest(report=label):
                case["fake"].scenario(stdout="1 passed in 0.1s\n",
                                      report=report, code=rc)
                run, out = self.full(case["clone"], case["task"], case["profile"])
                self.assert_unknown(run, f"отчёт {label}: {out}")

    def test_ac2_per_test_record_id_from_repo_root_outcome_kind_reason_time(self):
        """Итог по каждому тесту: идентификатор от корня репозитория с `workdir`, исход, вид падения, причина пропуска, время.

        Сценарий: компонент `junit-xml` с `workdir` (имя от зерна); отчёт
        с четырьмя тестами файла `src/x.test.jsx` (путь от `workdir`):
        прошедший, проваленный (`AssertionError`), ошибка
        (`RuntimeError`), пропущенный с причиной. У каждого — время.
        Записи `FullSuiteRun.tests` найдены по
        `project_profile.test_id(компонент, "<workdir>/src/x.test.jsx",
        имя)` — путь содержит `workdir`; исходы `passed`/`failed`/`error`/
        `skipped`; вид падения называет тип ошибки; причина пропуска — текст
        `skipped`; время — значение отчёта.

        Ловит мутацию: идентификатор строится от `workdir` (`src/x…`), а не
        от корня репозитория, — записи по ожидаемому id не находятся; либо
        ошибка схлопнута в провал (`failed`), либо причина пропуска и тип
        ошибки не переносятся в запись.
        """
        case = self.junit_component()
        names = {k: f"test_{self.word()}" for k in
                 ("passed", "failed", "error", "skipped")}
        reason = f"нужна сеть {self.word()}"
        seconds = {k: round(self.rng.uniform(0.01, 2.0), 3) for k in names}
        cases = [("src/x.test.jsx", names["passed"], "passed", "", "",
                  seconds["passed"]),
                 ("src/x.test.jsx", names["failed"], "failed", "AssertionError",
                  "boom", seconds["failed"]),
                 ("src/x.test.jsx", names["error"], "error", "RuntimeError",
                  "bad", seconds["error"]),
                 ("src/x.test.jsx", names["skipped"], "skipped", "", reason,
                  seconds["skipped"])]
        case["fake"].scenario(stdout="", report=junit(cases), code=1)
        run, out = self.full(case["clone"], case["task"], case["profile"])
        path = f"{case['wd']}/src/x.test.jsx"
        for kind, name in names.items():
            record = self.by_id(run, project_profile.test_id(case["comp"],
                                                             path, name))
            context = self.note(f"{kind}: {record}")
            self.assertEqual(fld(record, "outcome"), kind, context)
            got = fld(record, "time")
            self.assertIsNotNone(got, context)
            self.assertTrue(abs(float(got) - seconds[kind]) < 1e-6
                            or abs(float(got) - seconds[kind] * 1000) < 1e-3,
                            context)
            if kind == "failed":
                self.assertIn("AssertionError", str(fld(record, "failure")),
                              context)
            if kind == "error":
                self.assertIn("RuntimeError", str(fld(record, "failure")),
                              context)
            if kind == "skipped":
                self.assertIn(reason, str(fld(record, "skip_reason")), context)
        ids = [fld(r, "id") for r in self.records_of(run)]
        self.assertFalse(any(str(i).startswith(f"{case['comp']}:src/")
                             for i in ids), self.note(f"id от workdir: {ids}"))

    def test_ac3_report_path_outside_tree_workdir_and_clean_env(self):
        """Команда компонента получает `report_args` с `{path}` вне рабочей копии, идёт в `workdir` с окружением компонента.

        Сценарий: компонент `junit-xml` с явными `report_args`
        `[--report-to, {path}]`, `workdir` и переменной `env` (имена и
        значения от зерна); в окружении пульта — случайная переменная
        `ARTEL_LEAK_*`. Раннер пишет зелёный отчёт по пути после
        `--report-to`. Прогон зелёный (отчёт прочитан по этому пути); argv
        несёт `--report-to <путь>`, путь — вне клона; `cwd` — `workdir` в
        клоне; окружение несёт переменную компонента и не несёт переменной
        пульта.

        Ловит мутацию: `{path}` подставляется путём внутри рабочей копии
        (например, `workdir/report.xml`) либо команда идёт с копией
        окружения пульта из корня клона.
        """
        case = self.junit_component(report_args=["--report-to", "{path}"])
        case["fake"].scenario(report=junit([("src/x.test.jsx", "test_ok",
                                             "passed", "", "", "0.1")]))
        run, out = self.full(case["clone"], case["task"], case["profile"])
        self.assertTrue(run.green, self.note(f"{run}\n{out}"))
        runs = case["fake"].runs()
        self.assertTrue(runs, self.note("раннер не запускался"))
        record = runs[-1]
        path = report_arg(record["args"], "--report-to")
        self.assertIsNotNone(path, self.note(f"нет --report-to: {record['args']}"))
        self.assertFalse(under(path, case["clone"]),
                         self.note(f"отчёт внутри рабочей копии: {path}"))
        self.assertEqual(os.path.realpath(record["cwd"]),
                         os.path.realpath(case["clone"] / case["wd"]),
                         self.note("cwd не workdir"))
        env_name, env_value = case["env"]
        self.assertEqual(record["env"].get(env_name), env_value,
                         self.note("нет переменной env компонента"))
        self.assertNotIn(self.leak, record["env"],
                         self.note("окружение пульта в прогоне"))

    def test_ac4_explicit_report_args_win_over_default(self):
        """Компонент с явными `report_args` запускается с ними, а не с умолчанием `--junitxml`.

        Сценарий: компонент `junit-xml` с `report_args` `[--report-to,
        {path}]`. argv прогона несёт `--report-to` и не несёт ни одного
        аргумента `--junitxml`.

        Ловит мутацию: умолчание `[--junitxml, {path}]` подставляется
        всегда, поверх явных `report_args` компонента.
        """
        case = self.junit_component(report_args=["--report-to", "{path}"])
        case["fake"].scenario(report=junit([("src/x.test.jsx", "test_ok",
                                             "passed", "", "", "0.1")]))
        self.full(case["clone"], case["task"], case["profile"])
        args = case["fake"].runs()[-1]["args"]
        self.assertIsNotNone(report_arg(args, "--report-to"), self.note(str(args)))
        self.assertFalse(any(a.startswith("--junitxml") for a in args),
                         self.note(f"умолчание поверх явных: {args}"))

    def test_ac4_ac6_sled_record_default_report_args_outcome_from_report(self):
        """Запись `test_profile` с `report: junit-xml` и `runner: pytest-own` без `report_args` идёт с `--junitxml <путь вне клона>` и судится отчётом.

        Сценарий: запись `test_profile` (не `components:`) с
        `runner: pytest-own`, `workdir`, `report: junit-xml`, командой —
        подменённым раннером. Раннер выходит с кодом 0: с зелёным отчётом
        и выводом «N failed» — итог зелёный; с проваленным отчётом и
        выводом «N passed» — красный; без отчёта — «неизвестно». argv несёт
        `--junitxml` с путём вне клона.

        Ловит мутацию: умолчание `report_args` подставляется только
        компонентам записи `components:` — у записи `test_profile`
        `pytest-own` итог по-прежнему по коду возврата (зелёный без отчёта).
        """
        fake = Fake(self, "sled")
        wd = f"be{self.word(5)}"
        name, clone = self.project(self.junit_fields(fake, wd),
                                   {f"{wd}/src/x.test.jsx": "// тест\n"})
        task, profile = self.task(name), self.profile(name)
        green = junit([("src/x.test.jsx", "test_ok", "passed", "", "", "0.1")])
        failed = junit([("src/x.test.jsx", "test_bad", "failed",
                         "AssertionError", "boom", "0.1")])
        for label, report, stdout in (("зелёный", green, "3 failed in 0.1s\n"),
                                      ("красный", failed, "3 passed in 0.1s\n"),
                                      ("нет", None, "3 passed in 0.1s\n")):
            with self.subTest(report=label):
                fake.scenario(report=report, stdout=stdout)
                run, out = self.full(clone, task, profile)
                if label == "зелёный":
                    self.assertTrue(run.green, self.note(f"{run}\n{out}"))
                elif label == "красный":
                    self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED,
                                     self.note(f"{run}\n{out}"))
                else:
                    self.assert_unknown(run, out)
                args = fake.runs()[-1]["args"]
                path = report_arg(args, "--junitxml")
                self.assertIsNotNone(path, self.note(f"нет --junitxml: {args}"))
                self.assertFalse(under(path, clone), self.note(path))

    def test_ac5_unknown_outcome_form_and_log(self):
        """Исход «неизвестно»: константа «прогон не начат», деталь «итог неизвестен: …», лог записан и назван, вывод называет «неизвестно».

        Сценарий: компонент `junit-xml`, раннер выходит с кодом 0 и
        отчёта не пишет. `full_suite`: `outcome` —
        `acceptance.FULL_SUITE_NOT_STARTED`, `green` ложно, `detail`
        начинается с «итог неизвестен: », `log_path` — существующий файл, и
        его путь назван в `detail`; слово «неизвестно» есть в тексте узла
        (деталь, выжимка или вывод).

        Ловит мутацию: исход «неизвестно» возвращается веткой «прогон не
        начат» без лога (`log_path` — `None`, путь в детали не назван) или
        выдаётся красным прогоном.
        """
        case = self.junit_component()
        case["fake"].scenario(stdout=f"{self.rng.randint(1, 9)} passed in 0.1s\n")
        run, out = self.full(case["clone"], case["task"], case["profile"])
        self.assert_unknown(run, out)
        self.assertIsNotNone(run.log_path, self.note(str(run)))
        self.assertTrue(Path(run.log_path).is_file(), self.note(str(run)))
        self.assertIn(str(run.log_path), run.detail, self.note(run.detail))
        self.assertIn("неизвестно", f"{run.detail}\n{run.digest}\n{out}",
                      self.note(f"{run}\n{out}"))

    def test_ac6_pult_pytest_and_no_report_records_by_code_and_text(self):
        """Запись `test_profile` с `runner: pult-pytest` (с `report: junit-xml` и без `report`) судится кодом возврата и текстом pytest.

        Сценарий: две записи `test_profile` без `runner` (раннер пульта) —
        с `report: junit-xml`, как у артели, и без `report`; команда —
        подменённый раннер. Раннер отчёта не пишет: с кодом 0 и выводом
        «N passed» итог зелёный, с ненулевым кодом и «N failed» — красный.
        Исхода «неизвестно» нет.

        Ловит мутацию: различитель «итог из отчёта» смотрит на одно поле
        `report` — запись артели (`pult-pytest`, `report: junit-xml`)
        переходит на отчёт и без отчёта получает «неизвестно».
        """
        for with_report in (True, False):
            fake = Fake(self, "pult")
            fields = {"command": [str(fake.wrapper)], "long_lived_dir": "tests",
                      "long_lived_name": "test_<id>_<name>.py",
                      "weakening_scope": ["tests/**"],
                      "mutation_claim_scope": ["tests/**"]}
            if with_report:
                fields["report"] = "junit-xml"
            name, clone = self.project(fields, {"tests/test_x.py": "# тест\n"})
            task, profile = self.task(name), self.profile(name)
            n = self.rng.randint(1, 9)
            for code, stdout, outcome in (
                    (0, f"{n} passed in 0.1s\n", acceptance.FULL_SUITE_GREEN),
                    (1, f"{n} failed in 0.1s\n", acceptance.FULL_SUITE_RED)):
                with self.subTest(report=with_report, code=code):
                    fake.scenario(code=code, stdout=stdout)
                    run, out = self.full(clone, task, profile)
                    self.assertEqual(run.outcome, outcome,
                                     self.note(f"{run}\n{out}"))
                    self.assertIn(stdout.strip(), run.detail, self.note(run.detail))

    def test_ac11_unknown_is_never_green_at_any_place(self):
        """Компонент `junit-xml` с исходом «неизвестно» не даёт зелёного итога ни в одном месте прогона пульта.

        Сценарий: компонент `junit-xml` записи `components:` без `runner`
        (в корне); раннер выходит с кодом 0, печатает «1 passed» и отчёта
        не пишет. Места: `acceptance.run` (рубеж, подтяжка main,
        `amend-tests`), `acceptance.collect` (сухой сбор),
        `acceptance.run_repeat` (повтор красных), `acceptance.run_plank`
        (`plank-run`), `acceptance.full_suite`, `two_sided.run`
        (двусторонний прогон на ветке клона). Ни одно не зелёное: `run` и
        `collect` — ложь, `run_repeat` — непустой список, `run_plank` —
        ненулевой код, `full_suite` — не зелёный, у `two_sided.run` есть
        отказы.

        Ловит мутацию: разбор отчёта есть только в полном прогоне, а
        точечные места (`run`, `collect`, `run_repeat`, `run_plank`) у
        компонента с отчётом по-прежнему судят по коду 0 — «зелено».
        """
        fake = Fake(self, "places")
        comp = f"c{self.word(5)}"
        rel = f"src/test_{self.word()}.py"
        name, clone = self.project(
            self.junit_fields(fake, "", report_args=["--junitxml", "{path}"]),
            {rel: "import unittest\n"}, comp=comp)
        task, profile = self.task(name), self.profile(name)
        fake.scenario(stdout="1 passed in 0.01s\n")
        tdir = self.plank_dir()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            green, tail = acceptance.run(tdir, cwd=clone, command=profile)
            self.assertFalse(green, self.note(f"run: {tail}"))
            ok, tail = acceptance.collect(tdir, cwd=clone, command=profile)
            self.assertFalse(ok, self.note(f"collect: {tail}"))
            reds = acceptance.run_repeat([rel], clone, command=profile)
            self.assertTrue(reds, self.note("run_repeat: зелёный повтор"))
            code, output = acceptance.run_plank([rel], clone, profile=profile)
            self.assertNotEqual(code, 0, self.note(f"run_plank: {output}"))
            run = acceptance.full_suite(clone, task, command=profile, fresh=True)
            self.assertFalse(run.green, self.note(f"full_suite: {run}"))
        base = self.git("-C", str(clone), "rev-parse", "HEAD").strip()
        branch = f"task/{self.word()}"
        self.git("-C", str(clone), "checkout", "-q", "-b", branch)
        self.commit(clone, {rel: "import unittest\n# ветка\n"})
        self.git("-C", str(clone), "checkout", "-q", config.MAIN_BRANCH)
        method = two_sided.Method(rel, rel, "T::test_a",
                                  "import unittest\n", "import unittest\n")
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            outcome = two_sided.run(clone, branch, base, [method],
                                    profile=profile)
        self.assertTrue(outcome.refusals, self.note(
            f"двусторонний прогон доказан без отчёта: {outcome}"))


class ResultKeyTest(ReportSandbox):

    def key_case(self, tools: str, lock: str, extra_arg: str = "",
                 report_args=("--junitxml", "{path}"), comp: str | None = None,
                 project: str | None = None, clone: Path | None = None):
        """Ключ итога компонента `junit-xml` с `tools` `tools`, игнорируемым
        `package-lock.json` с текстом `lock` и (опционально) добавочным
        аргументом команды."""
        command = [str(self.fake.wrapper)] + ([extra_arg] if extra_arg else [])
        fields = self.junit_fields(self.fake, self.wd, command=command,
                                   report_args=list(report_args),
                                   tools={"node": tools})
        project = project or self.name
        self.entries = [e for e in self.entries
                        if not e.startswith(f"  {project}:\n")]
        self.entries.append(entry(project, fields, comp or self.comp))
        self.write_targets()
        clone = clone or self.clone
        (clone / self.wd / "package-lock.json").write_text(lock, encoding="utf-8")
        tree = acceptance.suite_tree_hash(clone)
        self.assertIsNotNone(tree, self.note("дерево клона не снято"))
        return tree, acceptance.suite_result_key(tree, self.profile(project),
                                                 root=clone)

    def test_ac18_component_key_follows_tools_lock_command_name_and_artel_key_is_main(self):
        """Ключ итога компонента с отчётом меняется с `tools`, файлом блокировки, командой, `report_args`, различен у двух компонентов; ключ артели — формулы main.

        Сценарий: компонент `junit-xml` с `workdir`, `tools` и
        `package-lock.json`, игнорируемым git (дерево клона от его
        содержимого не меняется); ключ — `acceptance.suite_result_key(
        дерево, decide(<проект>).profile, root=клон)`. Смена версии в
        `tools`, текста файла блокировки, добавочного аргумента команды,
        `report_args` — каждая даёт другой ключ. Второй проект с теми же
        полями и другим именем компонента на том же дереве — другой ключ.
        Ключ артели (`command=None` и список команды её профиля) равен
        ключу, посчитанному формулой main: sha256 JSON дерева, Python,
        пакетов и argv полного прогона пульта.

        Ловит мутацию: ключ компонента с отчётом считается прежней формой
        `pytest-own` — без имени компонента (ключи двух компонентов
        совпадают) и без `report_args`; либо ключ артели получает новые
        поля и перестаёт совпадать с сохранёнными итогами main.
        """
        self.fake = Fake(self, "key")
        self.wd = f"fe{self.word(5)}"
        self.comp = f"c{self.word(5)}"
        self.name, self.clone = self.project(
            self.junit_fields(self.fake, self.wd), {
                f"{self.wd}/src/x.test.jsx": "// тест\n",
                ".gitignore": "package-lock.json\nnode_modules/\n"},
            comp=self.comp)
        v1, v2 = self.version(1), self.version(2)
        tree, base = self.key_case(v1, "lock-a\n")
        self.assertIsNotNone(base, self.note("ключа нет"))
        for label, kwargs in (("tools", {"tools": v2, "lock": "lock-a\n"}),
                              ("файл блокировки", {"tools": v1, "lock": "lock-b\n"}),
                              ("команда", {"tools": v1, "lock": "lock-a\n",
                                           "extra_arg": f"--x{self.word(4)}"}),
                              ("report_args", {"tools": v1, "lock": "lock-a\n",
                                               "report_args": ("--report-to",
                                                               "{path}")})):
            with self.subTest(change=label):
                tree2, key = self.key_case(**kwargs)
                self.assertEqual(tree2, tree, self.note("дерево сменилось"))
                self.assertNotEqual(key, base, self.note(f"ключ не видит {label}"))
        _tree, same = self.key_case(v1, "lock-a\n")
        self.assertEqual(same, base, self.note("ключ не воспроизводится"))
        other = f"p{self.word()}"
        _tree, key_other = self.key_case(v1, "lock-a\n", comp=f"d{self.word(5)}",
                                         project=other)
        self.assertNotEqual(key_other, base,
                            self.note("ключи двух компонентов совпали"))

        artel_tree = "0123456789abcdef0123456789abcdef01234567"
        python = stack.pytest_python_executable()
        argv = [python, "-m", "pytest", "tests", "-p", "no:cacheprovider",
                "-p", "timeout", "-o", f"timeout={stack.PER_TEST_TIMEOUT_SEC}",
                "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"]
        packages = sorted((d.metadata["Name"].lower(), d.version)
                          for d in importlib.metadata.distributions())
        main_key = hashlib.sha256(json.dumps(
            {"tree": artel_tree, "python": sys.version, "packages": packages,
             "command": argv}, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        artel = list(self.profile(config.DEFAULT_TARGET).command)
        self.assertEqual(acceptance.suite_result_key(artel_tree, None), main_key,
                         self.note("ключ артели (команда пульта)"))
        self.assertEqual(acceptance.suite_result_key(artel_tree, artel), main_key,
                         self.note("ключ артели (список команды профиля)"))


# ------------------------------------------------------------ pult-vitest

class VitestReporterTest(ReportSandbox):

    def full_vitest(self, case: dict, tests=None, **scenario) -> tuple:
        if tests is not None:
            scenario["report"] = vitest_report(tests)
        case["fake"].scenario(
            version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
            **scenario)
        return self.full(case["clone"], case["task"], case["profile"])

    def test_ac6_vitest_component_without_runner_outcome_from_report(self):
        """Компонент `pult-vitest` записи `components:` без поля `runner` судится отчётом.

        Сценарий: компонент `pult-vitest` в корне клона без `runner`. Раннер
        выходит с кодом 0: с зелёным отчётом — итог зелёный; без отчёта —
        «неизвестно»; с отчётом, где тест упал `AssertionError`, — красный.

        Ловит мутацию: различитель читает `runner` компонента — компонент
        без `runner` (умолчание `pult-pytest`) идёт прежним разбором по
        коду возврата и без отчёта получает зелёный итог.
        """
        case = self.vitest_component(workdir=False)
        run, out = self.full_vitest(case, [vitest_test("src/a.test.js", "ok")])
        self.assertTrue(run.green, self.note(f"{run}\n{out}"))
        run, out = self.full_vitest(case, None, report=None)
        self.assert_unknown(run, out)
        run, out = self.full_vitest(case, [vitest_test(
            "src/a.test.js", "bad", state="fail", error_name="AssertionError")])
        self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED,
                         self.note(f"{run}\n{out}"))

    def test_ac7_failure_kinds_assertion_type_timeout_hook(self):
        """`TypeError` — ошибка, `AssertionError` (из `failure_errors`) — провал проверки, таймаут и хук — ошибки с признаком.

        Сценарий: компонент `pult-vitest` с `failure_errors:
        [AssertionError]`; отчёт с четырьмя упавшими тестами: `TypeError`;
        `AssertionError`; таймаут (`timeout: true`); падение хука
        `beforeEach` (имя хука — случайное из четырёх). Итог красный;
        записи: `TypeError` — `error`; `AssertionError` — `failed`;
        таймаут — `error`, вид падения называет таймаут; хук — `error`,
        вид падения называет хук.

        Ловит мутацию: любое падение считается провалом проверки (`TypeError`
        — `failed`), либо признаки таймаута и хука теряются при разборе.
        """
        case = self.vitest_component()
        hook = self.rng.choice(["beforeAll", "beforeEach", "afterEach",
                                "afterAll"])
        names = {k: f"t {self.word()}" for k in ("type", "assert", "timeout",
                                                   "hook")}
        tests = [vitest_test("src/a.test.js", names["type"], state="fail",
                             error_name="TypeError"),
                 vitest_test("src/a.test.js", names["assert"], state="fail",
                             error_name="AssertionError"),
                 vitest_test("src/a.test.js", names["timeout"], state="fail",
                             error_name="Error", timeout=True),
                 vitest_test("src/a.test.js", names["hook"], state="fail",
                             error_name="Error", hook=hook)]
        run, out = self.full_vitest(case, tests)
        self.assertFalse(run.green, self.note(f"{run}\n{out}"))
        rec = {k: self.by_id(run, self.vid(case, "src/a.test.js", n))
               for k, n in names.items()}
        self.assertEqual(fld(rec["type"], "outcome"), "error", self.note(str(rec)))
        self.assertEqual(fld(rec["assert"], "outcome"), "failed", self.note(str(rec)))
        self.assertEqual(fld(rec["timeout"], "outcome"), "error", self.note(str(rec)))
        self.assertIn("timeout", str(fld(rec["timeout"], "failure")).lower(),
                      self.note(str(rec["timeout"])))
        self.assertEqual(fld(rec["hook"], "outcome"), "error", self.note(str(rec)))
        self.assertIn(hook, str(fld(rec["hook"], "failure")),
                      self.note(str(rec["hook"])))

    def test_ac8_modes_fails_todo_skip_only_and_retries(self):
        """`it.fails`, `todo`, `skip`, `only` различимы в итоге; число повторов видно; повтор при зелёном — красный итог «повтор».

        Сценарий: компонент `pult-vitest`; отчёт с тестами: зелёный,
        `it.fails` (состояние `pass`, `fails: true`), `todo`, `skip`,
        `only` и зелёный с `retry_count` от зерна (1–4). Тройки (исход,
        `mode`, `fails`) записей `fails`/`todo`/зелёного/`skip` попарно
        различны, `skip` и `only` различны; у теста с повтором `retries` —
        число отчёта. Отдельный прогон из одного зелёного теста с повтором
        больше 0 — `FULL_SUITE_RED`, деталь называет «повтор»; тот же тест
        без повтора — зелёный.

        Ловит мутацию: повтор внутри прогона не учитывается — зелёный тест
        с `retry_count > 0` даёт зелёный итог; либо `mode`/`fails` не
        переносятся из отчёта, и `it.fails` неотличим от зелёного.
        """
        case = self.vitest_component()
        retries = self.rng.randint(1, 4)
        names = {k: f"t {self.word()}" for k in
                 ("pass", "fails", "todo", "skip", "only", "retry")}
        tests = [vitest_test("src/a.test.js", names["pass"]),
                 vitest_test("src/a.test.js", names["fails"], fails=True),
                 vitest_test("src/a.test.js", names["todo"], state="todo",
                             mode="todo"),
                 vitest_test("src/a.test.js", names["skip"], state="skip",
                             mode="skip"),
                 vitest_test("src/a.test.js", names["only"], mode="only"),
                 vitest_test("src/a.test.js", names["retry"],
                             retry_count=retries)]
        run, out = self.full_vitest(case, tests)
        rec = {k: self.by_id(run, self.vid(case, "src/a.test.js", n))
               for k, n in names.items()}

        def shape(key):
            return (fld(rec[key], "outcome"), fld(rec[key], "mode"),
                    bool(fld(rec[key], "fails")))

        group = ["fails", "todo", "pass", "skip"]
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                self.assertNotEqual(shape(a), shape(b), self.note(
                    f"{a} и {b} неразличимы: {shape(a)}"))
        self.assertNotEqual(shape("skip"), shape("only"),
                            self.note(f"skip и only: {shape('skip')}"))
        self.assertEqual(int(fld(rec["retry"], "retries")), retries,
                         self.note(str(rec["retry"])))
        self.assertFalse(run.green, self.note(f"повтор внутри прогона: {run}"))

        run, out = self.full_vitest(case, [vitest_test(
            "src/a.test.js", names["retry"], retry_count=retries)])
        self.assertEqual(run.outcome, acceptance.FULL_SUITE_RED,
                         self.note(f"{run}\n{out}"))
        self.assertIn("повтор", run.detail, self.note(run.detail))
        run, out = self.full_vitest(case, [vitest_test(
            "src/a.test.js", names["retry"])])
        self.assertTrue(run.green, self.note(f"без повтора: {run}\n{out}"))

    def test_ac9_run_conditions_argv_env_cache_and_flags(self):
        """Прогон `pult-vitest`: `workdir`, окружение компонента с `CI=true`, своя группа, базовый argv, отчётчик пульта, `--expect.requireAssertions`, флаг кэша вне дерева.

        Сценарий: компонент `pult-vitest` с `workdir`, переменной `env` и
        версией Vitest из таблицы, принимающей `--expect.requireAssertions`.
        Прогон зелёный; вызов `run` раннера: `cwd` — `workdir`; окружение
        несёт переменную компонента и `CI=true`, не несёт переменной
        пульта; группа процессов раннера — не группа процесса теста; argv
        начинается с базового (`argv[0]` — `node_modules/.bin/vitest`),
        несёт `--reporter=<файл каталога orchestrator/reporters/>` (файл
        есть), `--expect.requireAssertions` и флаг кэша таблицы с путём вне
        клона и вне `node_modules`.

        Ловит мутацию: пульт не добавляет флаги — нет
        `--expect.requireAssertions` или флага кэша; `{pult_reporter}`
        подставляется путём вне `orchestrator/reporters/`; прогон идёт с
        окружением пульта без `CI=true`.
        """
        case = self.vitest_component()
        run, out = self.full_vitest(case, [vitest_test("src/a.test.js", "ok")])
        self.assertTrue(run.green, self.note(f"{run}\n{out}"))
        runs = case["fake"].runs()
        self.assertTrue(runs, self.note("раннер не запускался"))
        record = runs[-1]
        self.assertEqual(os.path.realpath(record["cwd"]),
                         os.path.realpath(self.wd_path(case)), self.note("cwd"))
        env = record["env"]
        self.assertEqual(env.get("CI"), "true", self.note(f"окружение: {env}"))
        self.assertEqual(env.get(case["env"][0]), case["env"][1], self.note("env"))
        self.assertNotIn(self.leak, env, self.note("окружение пульта"))
        self.assertNotEqual(record["pgid"], os.getpgrp(),
                            self.note("раннер в группе процесса пульта"))
        argv = [record["argv0"], *record["args"]]
        self.assertTrue(argv[0].endswith("node_modules/.bin/vitest"),
                        self.note(str(argv)))
        self.assertEqual(argv[1:len(VITEST_BASE)], VITEST_BASE[1:],
                         self.note(f"argv не начинается с базового: {argv}"))
        reporters = Path(inspect.getfile(acceptance)).resolve().parent / "reporters"
        reporter = [a.split("=", 1)[1] for a in argv
                    if a.startswith("--reporter=") and a != "--reporter=default"]
        self.assertTrue(reporter, self.note(f"нет --reporter=<путь>: {argv}"))
        self.assertTrue(under(reporter[0], reporters) and
                        Path(reporter[0]).is_file(),
                        self.note(f"отчётчик не из {reporters}: {reporter}"))
        self.assertTrue(any(a.startswith(REQUIRE_ASSERTIONS) for a in argv),
                        self.note(f"нет {REQUIRE_ASSERTIONS}: {argv}"))
        flag = self.cache_flag(self.accepted_major()[1])
        cache = report_arg(argv, flag)
        self.assertIsNotNone(cache, self.note(f"нет флага кэша {flag}: {argv}"))
        self.assertFalse(under(cache, case["clone"]), self.note(cache))
        self.assertNotIn("node_modules", Path(cache).parts, self.note(cache))

    def test_ac9_timeout_kills_group_not_green(self):
        """Раннер `pult-vitest`, превысивший предел компонента, снимается вместе с группой; итог не зелёный.

        Сценарий: компонент `pult-vitest` с `full_suite_timeout_sec: 1`;
        раннер держит конец записи именованного канала в дочернем процессе
        и спит дольше предела. `full_suite` не зелёный; после него читатель
        канала получает конец файла — раннер и его потомок мертвы (событие,
        предел ожидания — страховка).

        Ловит мутацию: прогон `pult-vitest` идёт без своей группы процессов
        и по таймауту убивается только главный процесс — потомок держит
        канал открытым.
        """
        case = self.vitest_component(timeout=1)
        fifo = case["fake"].dir / "fifo"
        os.mkfifo(fifo)
        reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        if not select_limited():
            # Номер выше FD_SETSIZE в каждом прогоне: ожидание держится и
            # там, где исполнитель xdist уже занял тысячу дескрипторов.
            reader = high_fd(self, reader)
        self.addCleanup(os.close, reader)
        run, out = self.full_vitest(case, [vitest_test("src/a.test.js", "ok")],
                                    fifo=str(fifo), sleep=120)
        self.assertFalse(run.green, self.note(f"{run}\n{out}"))
        self.assertTrue(case["fake"].runs(), self.note("раннер не запускался"))
        gone = False
        while True:
            ready = wait_readable(reader, CHILD_GUARD_SEC)
            if not ready:
                break
            try:
                if os.read(reader, 4096) == b"":
                    gone = True
                    break
            except BlockingIOError:
                continue
        self.assertTrue(gone, self.note("потомок раннера пережил таймаут"))

    def test_ac9_version_refusals_require_assertions_and_unconfirmed_cache(self):
        """Версия Vitest, не принимающая `--expect.requireAssertions`, и версия вне таблицы — отказ подготовки с текстом, не зелёный.

        Сценарий: (а) таблица `VITEST_VERSION_FLAGS` подменена копией с
        новой главной версией, у записи которой булевы значения ложны;
        компонент объявляет эту версию в `tools`, раннер отвечает ею на
        `--version`. (б) Компонент с главной версией, которой в таблице нет.
        В обоих случаях итог не зелёный, деталь непуста, раннер не
        запускался с `run`; в (а) деталь называет `--expect.requireAssertions`.

        Ловит мутацию: подготовка не сверяет версию с таблицей — флаги
        подставляются по умолчанию, и прогон неподтверждённой версии идёт
        и даёт зелёный итог.
        """
        key, value = self.accepted_major()
        new_major = self.absent_major()
        new_key = new_major if isinstance(key, int) else str(new_major)
        patched = dict(self.table())
        patched[new_key] = flipped(value)
        with mock.patch.object(project_profile, "VITEST_VERSION_FLAGS", patched):
            case = self.vitest_component(version=self.version(new_major))
            run, out = self.full_vitest(case, [vitest_test("src/a.test.js", "ok")])
        self.assertFalse(run.green, self.note(f"{run}\n{out}"))
        self.assertIn(REQUIRE_ASSERTIONS, run.detail, self.note(run.detail))
        self.assertEqual(case["fake"].runs(), [], self.note("прогон шёл"))

        case = self.vitest_component(version=self.version(self.absent_major()))
        run, out = self.full_vitest(case, [vitest_test("src/a.test.js", "ok")])
        self.assertFalse(run.green, self.note(f"{run}\n{out}"))
        self.assertTrue(run.detail.strip(), self.note(str(run)))
        self.assertEqual(case["fake"].runs(), [], self.note("прогон шёл"))

    def test_ac10_preparation_refusals_command_and_report_args(self):
        """Чужой `command` и `report_args` без `{pult_reporter}` или `{path}` — отказ подготовки с текстом, не зелёный.

        Сценарий: компонент `pult-vitest`, у которого по очереди: `command`
        `[npx, vitest, run]`; базовый argv с чужим `--config`; с
        `--retry=1`; с `--expect.requireAssertions` внутри `command`;
        `report_args` без `{pult_reporter}`; `report_args` без `{path}`.
        Каждый — итог не зелёный, деталь непуста, раннер не запускался с
        `run`.

        Ловит мутацию: сверка `command` с базовым argv требования 7 снята
        (или сравнивает только начало), и прогон с `--retry=1` или без
        отчётчика пульта идёт и даёт зелёный итог.
        """
        other_config = list(VITEST_BASE)
        other_config[3] = f"{self.word()}.config.js"
        retry = VITEST_BASE[:-1] + ["--retry=1"]
        variants = {
            "npx vitest run": {"command": ["npx", "vitest", "run"]},
            "чужой --config": {"command": other_config},
            "--retry=1": {"command": retry},
            "--expect.requireAssertions в command": {
                "command": VITEST_BASE + [REQUIRE_ASSERTIONS]},
            "без {pult_reporter}": {"report_args": ["--outputFile={path}"]},
            "без {path}": {"report_args": ["--reporter={pult_reporter}"]},
        }
        for label, extra in variants.items():
            with self.subTest(variant=label):
                case = self.vitest_component(**extra)
                run, out = self.full_vitest(case, [vitest_test("src/a.test.js",
                                                               "ok")])
                self.assertFalse(run.green, self.note(f"{label}: {run}\n{out}"))
                self.assertTrue(run.detail.strip(), self.note(str(run)))
                self.assertEqual(case["fake"].runs(), [],
                                 self.note(f"{label}: прогон шёл"))

    def test_ac10_subset_by_select_and_refusal_without_select(self):
        """Подмножество тестов идёт подстановкой `{tests}` в `select`; без `select` подмножество отказывает, полный прогон идёт.

        Сценарий: компонент `pult-vitest` с `select: ["{tests}"]` —
        `acceptance.run_repeat` двух файлов компонента (имена от зерна)
        зелёный, argv вызова `run` называет оба файла. Компонент без
        `select` — `run_repeat` красный (непустой список с текстом), раннер
        с `run` не запускался; полный прогон того же компонента зелёный.

        Ловит мутацию: без `select` пульт молча гонит полный набор вместо
        подмножества (повтор «зелёный»), либо `{tests}` не подставляется, и
        файлы подмножества не доходят до раннера.
        """
        case = self.vitest_component()
        files = [f"src/{self.word()}.test.js", f"src/{self.word()}.test.js"]
        prefix = f"{case['wd']}/"
        report = [vitest_test(f, "ok") for f in files]
        case["fake"].scenario(
            version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
            report=vitest_report(report))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            reds = acceptance.run_repeat([prefix + f for f in files],
                                         case["clone"], command=case["profile"])
        self.assertEqual(reds, [], self.note(f"повтор подмножества: {reds}\n"
                                             f"{buf.getvalue()}"))
        runs = case["fake"].runs()
        self.assertTrue(runs, self.note("раннер не запускался"))
        args = " ".join(runs[-1]["args"])
        for f in files:
            self.assertIn(Path(f).name, args, self.note(f"нет {f}: {args}"))

        case = self.vitest_component(select=None)
        case["fake"].scenario(
            version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
            report=vitest_report(report))
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            reds = acceptance.run_repeat([f"{case['wd']}/{f}" for f in files],
                                         case["clone"], command=case["profile"])
        self.assertTrue(reds, self.note("подмножество без select не отказало"))
        self.assertTrue(any(red.note for red in reds), self.note(str(reds)))
        self.assertEqual(case["fake"].runs(), [], self.note("прогон шёл"))
        run, out = self.full_vitest(case, report)
        self.assertTrue(run.green, self.note(f"полный прогон без select: {run}"))


class InstallAndDepsTest(ReportSandbox):

    def full_vitest(self, case: dict) -> tuple:
        case["fake"].scenario(
            version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
            report=vitest_report([vitest_test("src/a.test.js", "ok")]))
        return self.full(case["clone"], case["task"], case["profile"])

    def test_ac15_install_once_per_lock_content_from_task_branch(self):
        """Установка исполняется пультом один раз на содержимое `package-lock.json` рабочей копии ветки задачи.

        Сценарий: компонент `pult-vitest` с поддельной `install`. Два
        полных прогона — оба зелёные, раннер с `run` запускался дважды,
        установка — один раз. В клоне — ветка задачи с правкой
        `package-lock.json` (main не меняется); прогон на ней — вторая
        установка, и её сумма — сумма нового содержимого.

        Ловит мутацию: установка ключуется суммой файла блокировки main
        (или не ключуется вовсе) — правка в ветке установку не повторяет,
        либо установка идёт на каждом прогоне.
        """
        case = self.vitest_component()
        for _ in range(2):
            run, out = self.full_vitest(case)
            self.assertTrue(run.green, self.note(f"{run}\n{out}"))
        self.assertEqual(len(case["fake"].runs()), 2, self.note("прогонов не два"))
        self.assertEqual(len(case["fake"].installs()), 1,
                         self.note(f"установки: {case['fake'].installs()}"))
        self.git("-C", str(case["clone"]), "checkout", "-q", "-b",
                 f"task/{self.word()}")
        lock_rel = f"{case['wd']}/package-lock.json"
        text = json.dumps({"lockfileVersion": 3, "seed": self.word()}) + "\n"
        self.commit(case["clone"], {lock_rel: text}, "правка блокировки")
        run, out = self.full_vitest(case)
        self.assertTrue(run.green, self.note(f"{run}\n{out}"))
        installs = case["fake"].installs()
        self.assertEqual(len(installs), 2, self.note(f"установки: {installs}"))
        self.assertEqual(installs[-1]["lock"],
                         hashlib.sha256(text.encode()).hexdigest(),
                         self.note("установка не по файлу блокировки ветки"))

    def test_ac15_install_without_lock_and_failed_install_refuse(self):
        """`install` без файла блокировки в `workdir` (npm и `uv sync`) не исполняется; сбой установки — отказ, не зелёный.

        Сценарий: (а) компонент `pult-vitest` без `package-lock.json`; (б)
        компонент `junit-xml` с `install: [<…>/uv, sync]` и без файлов
        блокировки в `workdir`. В обоих итог не зелёный, деталь несёт
        «install без файла блокировки не исполняется», установка не
        запускалась. (в) Компонент `pult-vitest`, установка выходит с
        ненулевым кодом: итог не зелёный, деталь непуста, раннер не
        запускался.

        Ловит мутацию: `install` без файла блокировки исполняется как есть
        (или пропускается молча, и прогон идёт); сбой установки не
        останавливает прогон.
        """
        case = self.vitest_component(lock=False)
        run, out = self.full_vitest(case)
        self.assertFalse(run.green, self.note(f"{run}\n{out}"))
        self.assertIn(INSTALL_WITHOUT_LOCK, run.detail, self.note(run.detail))
        self.assertEqual(case["fake"].installs(), [], self.note("установка шла"))

        fake = Fake(self, "uv")
        uv = fake.tool("uv")
        junit_case = self.junit_component(install=[str(uv), "sync"])
        junit_case["fake"].scenario(report=junit([("src/x.test.jsx", "test_ok",
                                                   "passed", "", "", "0.1")]))
        run, out = self.full(junit_case["clone"], junit_case["task"],
                             junit_case["profile"])
        self.assertFalse(run.green, self.note(f"{run}\n{out}"))
        self.assertIn(INSTALL_WITHOUT_LOCK, run.detail, self.note(run.detail))
        self.assertEqual(fake.installs(), [], self.note("uv sync исполнялся"))

        case = self.vitest_component()
        case["fake"].fail_install()
        run, out = self.full_vitest(case)
        self.assertFalse(run.green, self.note(f"{run}\n{out}"))
        self.assertTrue(run.detail.strip(), self.note(str(run)))
        self.assertTrue(case["fake"].installs(), self.note("установка не шла"))
        self.assertEqual(case["fake"].runs(), [], self.note("прогон после сбоя"))

    def test_ac16_node_modules_read_only_shared_and_substitution_refused(self):
        """`node_modules` рабочей копии — подключение каталога пульта только для чтения, общее у мест прогона; подмена — отказ.

        Сценарий: компонент `pult-vitest`. После полного прогона
        `node_modules` в `workdir` ведёт в каталог вне клона; запись файла в
        него отказывает (`OSError`). Прогон планки `acceptance.run` и
        полный прогон видят один и тот же каталог `node_modules`. Затем
        `node_modules` заменён собственным каталогом с копией раннера —
        полный прогон не зелёный, раннер не запускался; затем ссылкой на
        копию каталога пульта в другом месте — так же.

        Ловит мутацию: пульт доверяет каталогу дерева — подменённый
        `node_modules` с чужим раннером исполняется, либо каталог пульта
        подключён с правом записи.
        """
        case = self.vitest_component()
        run, out = self.full_vitest(case)
        self.assertTrue(run.green, self.note(f"{run}\n{out}"))
        nm = self.wd_path(case) / "node_modules"
        self.assertTrue(os.path.lexists(nm), self.note("node_modules не подключён"))
        pult_dir = os.path.realpath(nm)
        self.assertFalse(under(pult_dir, case["clone"]),
                         self.note(f"node_modules — каталог дерева: {pult_dir}"))
        with self.assertRaises(OSError, msg=self.note("запись в node_modules")):
            (nm / f"probe-{self.word()}.txt").write_text("x", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            acceptance.run(self.plank_dir(), cwd=case["clone"],
                           command=case["profile"])
        seen = {r["node_modules"] for r in case["fake"].runs()}
        self.assertEqual(seen, {pult_dir}, self.note(f"каталоги прогонов: {seen}"))

        before = len(case["fake"].runs())
        os.unlink(nm) if os.path.islink(nm) else shutil.rmtree(nm)
        (nm / ".bin").mkdir(parents=True)
        shutil.copyfile(case["fake"].wrapper, nm / ".bin" / "vitest")
        (nm / ".bin" / "vitest").chmod(0o755)
        run, out = self.full_vitest(case)
        self.assertFalse(run.green, self.note(f"свой каталог: {run}\n{out}"))
        self.assertEqual(len(case["fake"].runs()), before,
                         self.note("исполнен раннер из подменённого каталога"))

        shutil.rmtree(nm)
        copy = Path(tempfile.mkdtemp(prefix="artel-nm-copy-")).resolve()
        self.addCleanup(shutil.rmtree, copy, True)
        self.addCleanup(writable, copy)
        shutil.copytree(pult_dir, copy / "node_modules")
        os.symlink(copy / "node_modules", nm)
        run, out = self.full_vitest(case)
        self.assertFalse(run.green, self.note(f"чужая ссылка: {run}\n{out}"))
        self.assertEqual(len(case["fake"].runs()), before,
                         self.note("исполнен раннер по чужой ссылке"))


# ------------------------------------------------------------ сторож

class HungComponentWatchdogTest(ReportSandbox):

    def test_ac19_watchdog_knows_component_commands_only(self):
        """Сторож признаёт зависшим процесс с командой компонента проекта и не признаёт процесс с чужой командой.

        Сценарий: две записи проектов — компонент `pult-vitest` (базовый
        argv) и компонент `junit-xml` с командой из исполняемого файла и
        флага от зерна; у каждой задача без lease, `cwd` процессов — в
        рабочей копии задачи. `ps` (подменён) называет три процесса старше
        `config.HUNG_TEST_RUN_AGE_SEC`: команда Vitest с флагами пульта,
        команда второго компонента с аргументами и `node server.js`. Находки
        `doctor.check_hung_test_runs` — первые два pid, третьего нет.

        Ловит мутацию: сторож по-прежнему узнаёт только `pytest`/`unittest`
        — процессы компонентов не находятся; либо узнаёт любой процесс в
        рабочей копии задачи — `node server.js` тоже находка.
        """
        vitest = self.vitest_component()
        fake = Fake(self, "hung")
        flag = f"--{self.word(5)}"
        junit_case = self.junit_component(command=[str(fake.wrapper), flag])
        age = int(config.HUNG_TEST_RUN_AGE_SEC) + self.rng.randint(10, 500)
        etime = f"{age // 3600}:{age // 60 % 60:02}:{age % 60:02}"
        pids = {}
        cwds = {}
        rows = []
        for label, case, command in (
                ("vitest", vitest,
                 f"node {' '.join(VITEST_BASE)} {REQUIRE_ASSERTIONS} "
                 f"--reporter=/x/r.js"),
                ("junit", junit_case,
                 f"{fake.wrapper} {flag} --junitxml /tmp/r.xml"),
                ("чужой", vitest, "node server.js --port 3000")):
            pid = self.rng.randint(400_000, 900_000)
            while pid in pids.values():
                pid += 1
            cwd = (config.PROJECTS / case["name"] / "worktrees" / case["task"]
                   / (case["wd"] or "."))
            cwd.mkdir(parents=True, exist_ok=True)
            pids[label], cwds[pid] = pid, cwd
            rows.append(f"{pid} {etime} {command}")

        def run(argv, *args, **kwargs):
            argv = [str(a) for a in argv]
            if argv[:2] == ["ps", "-axww"]:
                return subprocess.CompletedProcess(argv, 0, "\n".join(rows) + "\n", "")
            if argv[:1] == ["lsof"]:
                pid = int(argv[argv.index("-p") + 1])
                cwd = cwds.get(pid)
                if cwd is None:
                    return subprocess.CompletedProcess(argv, 1, "", "")
                return subprocess.CompletedProcess(argv, 0, f"p{pid}\nn{cwd}\n", "")
            return REAL_RUN(argv, *args, **kwargs)

        with mock.patch.object(subprocess, "run", run):
            checks = doctor.check_hung_test_runs(store.db())
        found = " ".join(c.detail for c in checks if c.status == "fail")
        self.assertIn(f"pid {pids['vitest']}", found, self.note(str(checks)))
        self.assertIn(f"pid {pids['junit']}", found, self.note(str(checks)))
        self.assertNotIn(f"pid {pids['чужой']}", found, self.note(str(checks)))


# ------------------------------------------------------------ артель

class PytestSpy:
    """Замена модуля `subprocess` у `acceptance`: вызов pytest запоминает
    argv и отвечает заданным кодом и выводом (или таймаутом); прочие
    вызовы идут настоящим `subprocess`."""

    def __init__(self, code: int = 0, stdout: str = "1 passed in 0.01s\n",
                 timeout: bool = False):
        self.calls: list = []
        self.code, self.stdout, self.timeout = code, stdout, timeout

    def __getattr__(self, name):
        return getattr(subprocess, name)

    @staticmethod
    def is_pytest(argv) -> bool:
        parts = [str(a) for a in argv]
        return any(a == "-m" and b == "pytest" for a, b in zip(parts, parts[1:]))

    def run(self, argv, *args, **kwargs):
        if not self.is_pytest(argv):
            return REAL_RUN(argv, *args, **kwargs)
        self.calls.append([str(a) for a in argv])
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"),
                                            output="частичный вывод\n", stderr="")
        return subprocess.CompletedProcess(argv, self.code, self.stdout, "")

    def Popen(self, argv, *args, **kwargs):
        if not self.is_pytest(argv):
            return REAL_POPEN(argv, *args, **kwargs)
        self.calls.append([str(a) for a in argv])
        spy = self
        out = kwargs.get("stdout")
        if hasattr(out, "write"):
            out.write(self.stdout.encode() if "b" in getattr(out, "mode", "")
                      else self.stdout)
            out.flush()

        class Proc:
            pid = 2_000_000_000
            returncode = spy.code
            stdin = stdout = stderr = None

            def communicate(self, input=None, timeout=None):
                if spy.timeout and timeout is not None:
                    raise subprocess.TimeoutExpired(argv, timeout,
                                                    output="частичный вывод\n")
                return spy.stdout, ""

            def wait(self, timeout=None):
                if spy.timeout and timeout is not None:
                    raise subprocess.TimeoutExpired(argv, timeout)
                return spy.code

            def poll(self):
                return spy.code

            def kill(self):
                pass

            terminate = kill

        return Proc()


def pytest_output(rng: random.Random, word) -> tuple:
    """(вывод pytest с упавшими, ожидаемые пары `failed_entries`, единица
    подтеста и её родитель, итоговая строка)."""
    mod = f"tests/test_{word()}.py"
    c, d, e, b = (f"{mod}::T::test_{word()}" for _ in range(4))
    msgs = [f"AssertionError: {word()}", f"RuntimeError: {word()}",
            f"AssertionError: {word()}"]
    label = f"(i={rng.randint(1, 9)})"
    summary = f"1 failed, 1 passed, 1 error in {rng.randint(1, 99)}.{rng.randint(10, 99)}s"
    out = ("============================= test session starts =====\n"
           f"{b} PASSED\n{c} FAILED\n"
           "=================================== FAILURES ===========\n"
           "____ T.test ____\nAssertionError: traceback text\n"
           "=========================== short test summary info ====\n"
           f"FAILED {c} - {msgs[0]}\nERROR {d} - {msgs[1]}\n"
           f"SUBFAILED{label} {e} - {msgs[2]}\n"
           f"=================== {summary} ===================\n")
    entries = [(c, msgs[0]), (d, msgs[1]), (f"{e} {label}", msgs[2])]
    lines = [f"FAILED {c} - {msgs[0]}", f"ERROR {d} - {msgs[1]}",
             f"SUBFAILED{label} {e} - {msgs[2]}"]
    return out, entries, (f"{e} {label}", e), summary, lines


class ArtelUnchangedTest(ReportSandbox):

    def main_head(self, command) -> list:
        head = list(command) if command else ["python3", "-m", "pytest"]
        if head[0] == "python3":
            head[0] = stack.pytest_python_executable()
        return head

    FLAGS = ["-p", "no:cacheprovider", "-p", "timeout", "-o",
             f"timeout={stack.PER_TEST_TIMEOUT_SEC}"]

    def channels(self):
        """(метка, канал команды, начало команды на main): артель — без
        команды, её профиль и его список; запись `test_profile` без
        `report` — профиль и список."""
        fields = {"command": ["python3", "-m", "pytest", "-rN"],
                  "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": ["tests/**"],
                  "mutation_claim_scope": ["tests/**"]}
        name, clone = self.project(fields, {"tests/test_x.py": "# тест\n"})
        artel = self.profile(config.DEFAULT_TARGET)
        plain = self.profile(name)
        return clone, [("артель без команды", None, None),
                       ("профиль артели", artel, artel.command),
                       ("список артели", list(artel.command), artel.command),
                       ("профиль без report", plain, plain.command),
                       ("список без report", list(plain.command), plain.command)]

    def test_ac4_ac6_pult_pytest_argv_and_outcome_as_main(self):
        """У артели и у записи `test_profile` без `report` argv полного прогона и прогона планки — как на main, итог — по коду и тексту.

        Сценарий: учебная запись `test_profile` без `report` и запись
        артели песочницы (`report: junit-xml`, `runner` — пульта); каналы
        команды — без команды, профиль `decide(...)`, список его команды.
        Вызов pytest подменён (`acceptance.subprocess`). argv
        `run_full_suite` равен argv main (интерпретатор пульта, `tests`,
        флаги пульта, `-n`, `-p xdist`); argv `acceptance.run` — начало
        команды, путь планки, флаги пульта, без `--junitxml`. Код 1 с
        выводом «N failed» — красный прогон полного набора, код 0 — зелёный.

        Ловит мутацию: умолчание `[--junitxml, {path}]` добавляется к
        записи с `report: junit-xml` без различителя — argv артели получает
        `--junitxml`, итог артели читается из отчёта.
        """
        clone, channels = self.channels()
        tdir = self.plank_dir()
        for label, command, head_src in channels:
            with self.subTest(channel=label):
                head = self.main_head(head_src)
                spy = PytestSpy()
                with mock.patch.object(acceptance, "subprocess", spy), \
                        contextlib.redirect_stdout(io.StringIO()):
                    green, _out = (acceptance.run_full_suite(clone)
                                   if command is None else
                                   acceptance.run_full_suite(clone, command=command))
                    ok, _tail = (acceptance.run(tdir, cwd=clone) if command is None
                                 else acceptance.run(tdir, cwd=clone, command=command))
                self.assertTrue(green and ok, self.note(label))
                full, plank = spy.calls
                self.assertEqual(full, head + ["tests", *self.FLAGS, "-n",
                                               str(config.FULL_SUITE_WORKERS),
                                               "-p", "xdist"],
                                 self.note(f"{label}: {full}"))
                self.assertEqual(len(plank), len(head) + 1 + len(self.FLAGS),
                                 self.note(f"{label}: {plank}"))
                self.assertEqual(plank[:len(head)], head, self.note(str(plank)))
                self.assertTrue(plank[len(head)].endswith("acceptance_tests"),
                                self.note(str(plank)))
                self.assertEqual(plank[len(head) + 1:], self.FLAGS,
                                 self.note(str(plank)))
                n = self.rng.randint(1, 9)
                spy = PytestSpy(1, f"{n} failed in 0.1s\n")
                with mock.patch.object(acceptance, "subprocess", spy), \
                        contextlib.redirect_stdout(io.StringIO()):
                    green, out = (acceptance.run_full_suite(clone)
                                  if command is None else
                                  acceptance.run_full_suite(clone, command=command))
                self.assertFalse(green, self.note(f"{label}: {out}"))
                self.assertEqual(suite_run.parse(green, out).outcome,
                                 acceptance.FULL_SUITE_RED, self.note(out))

    def test_ac20_constants_and_texts_as_main(self):
        """Константы исходов, тексты отказа и сводки — значения main.

        Сценарий: сверка значений `acceptance.FULL_SUITE_*`,
        `WORKDIR_REFUSAL`, `REFUSED_EXIT_CODE`, текста сводки без планки и
        текстов отказа `suite-run` записи `test_profile` без `report`:
        не-pytest команда (команда от зерна) и запись без профиля.

        Ловит мутацию: исход «неизвестно» заведён новой константой взамен
        `FULL_SUITE_NOT_STARTED` либо меняет её текст; отказ «не запуск
        pytest» снят и для записи без `report`.
        """
        self.assertEqual(acceptance.FULL_SUITE_GREEN, "зелёный прогон")
        self.assertEqual(acceptance.FULL_SUITE_RED, "красный прогон")
        self.assertEqual(acceptance.FULL_SUITE_TIMEOUT, "таймаут прогона")
        self.assertEqual(acceptance.FULL_SUITE_NO_TESTS, "tests/ нет в worktree")
        self.assertEqual(acceptance.FULL_SUITE_NOT_STARTED, "прогон не начат")
        self.assertEqual(acceptance.FULL_SUITE_NO_TESTS_NOTE,
                         "tests/ нет в worktree — полный набор не проверен")
        self.assertEqual(acceptance.WORKDIR_REFUSAL,
                         "отказ запуска pytest-own: workdir профиля")
        self.assertEqual(acceptance.REFUSED_EXIT_CODE, 4)
        empty = Path(tempfile.mkdtemp(prefix="artel-empty-"))
        self.addCleanup(shutil.rmtree, empty, True)
        self.assertEqual(acceptance.summary(empty),
                         "acceptance_tests/ нет — приёмочные тесты не заведены")
        command = [f"./run-{self.word()}", f"--{self.word(4)}"]
        fields = {"command": command, "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": ["tests/**"],
                  "mutation_claim_scope": ["tests/**"]}
        name, _clone = self.project(fields, {"tests/test_x.py": "# тест\n"})
        bare = f"p{self.word()}"
        self.entries.append(ENTRY_HEAD.format(name=bare))
        self.write_targets()
        make_project_repo(bare, origin=False)
        expected = {
            name: (f"команда профиля тестов проекта «{name}» "
                   f"({' '.join(command)}) — не запуск pytest: флаги "
                   f"параллели pytest (-n) к ней неприменимы"),
            bare: (f"у проекта «{bare}» нет профиля тестов (test_profile в "
                   f"targets.yaml) — команде прогона неоткуда взять команду")}
        for project, refusal in expected.items():
            with self.subTest(project=project):
                task = self.task(project)
                with self.assertRaises(SystemExit) as raised, \
                        contextlib.redirect_stdout(io.StringIO()):
                    suite_run.cmd_suite_run([task])
                self.assertEqual(str(raised.exception.code),
                                 f"[{task}] suite-run: отказ — {refusal}; "
                                 f"прогон не запускался", self.note(project))

    def test_ac12_suite_run_no_report_non_pytest_refusal_as_main(self):
        """`suite-run` записи `test_profile` без `report` с не-pytest командой отказывает прежним текстом.

        Сценарий: запись `test_profile` без `report` с командой из
        исполняемого файла `./tool-<зерно>` и флага; `suite_run.cmd_suite_run`
        завершается `SystemExit` с текстом «… — не запуск pytest: флаги
        параллели pytest (-n) к ней неприменимы; прогон не запускался».

        Ловит мутацию: признак «итог из отчёта» смотрит на команду, а не на
        `report`, — запись без `report` с не-pytest командой больше не
        отказывает и уходит в прогон.
        """
        command = [f"./tool-{self.word()}", "--ci"]
        fields = {"command": command, "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": ["tests/**"],
                  "mutation_claim_scope": ["tests/**"]}
        name, _clone = self.project(fields, {"tests/test_x.py": "# тест\n"})
        task = self.task(name)
        with self.assertRaises(SystemExit) as raised, \
                contextlib.redirect_stdout(io.StringIO()):
            suite_run.cmd_suite_run([task])
        self.assertIn("— не запуск pytest: флаги параллели pytest (-n) к ней "
                      "неприменимы; прогон не запускался",
                      str(raised.exception.code), self.note())

    def test_ac20_parsing_digest_journal_and_suite_run_lines_as_main(self):
        """Разбор вывода pytest, выжимка, строки журнала полного набора и строки `suite-run` артели — как на main.

        Сценарий: вывод pytest с упавшим, ошибкой и подтестом (имена и
        сообщения от зерна). `run_summary_line`, `failed_test_lines`,
        `failed_entries`, `short_summary_block`, `subtest_parents`,
        `run_digest` — значения разбора main; без итоговой строки выжимка —
        хвост вывода. `full_suite` задачи артели (вызов pytest подменён):
        зелёный, красный и таймаут — строки журнала «полный набор tests/
        зелёный|красный: <выжимка> (лог прогона: <путь>)» и «прогон
        полного набора tests/ превысил {N}с — … (источник: …)».
        `suite_run.parse` и `render` — строки «[<id>] suite-run №<n>
        (полный набор): красный прогон», «прошло: N, упало: M, пропущено:
        K», «полный лог: <путь>».

        Ловит мутацию: разбор итога артели переведён на отчёт —
        `full_suite` артели теряет итоговую строку pytest в выжимке, а
        `suite-run` считает «прошло/упало» не по итоговой строке.
        """
        out, entries, (unit, parent), summary, lines = pytest_output(
            self.rng, self.word)
        self.assertEqual(acceptance.run_summary_line(out), summary)
        self.assertEqual(acceptance.failed_test_lines(out), lines)
        self.assertEqual(acceptance.failed_entries(out), entries)
        self.assertEqual(acceptance.subtest_parents(out), {unit: parent})
        block_text = acceptance.short_summary_block(out)
        self.assertTrue(block_text.strip().startswith(lines[0]), block_text)
        self.assertNotIn(summary, block_text)
        self.assertEqual(acceptance.run_digest(out), "\n".join(lines + [summary]))
        tail = f"ошибка сбора {self.word()}\nImportError: x"
        self.assertEqual(acceptance.run_digest(tail), tail)

        (self.root / "tests").mkdir(exist_ok=True)
        task = self.task(config.DEFAULT_TARGET)
        green_out = f"{self.rng.randint(2, 9)} passed in 0.5s\n"
        for label, spy, head in (
                ("зелёный", PytestSpy(0, green_out), "полный набор tests/ зелёный"),
                ("красный", PytestSpy(1, out), "полный набор tests/ красный")):
            with self.subTest(outcome=label):
                with mock.patch.object(acceptance, "subprocess", spy), \
                        contextlib.redirect_stdout(io.StringIO()):
                    run = acceptance.full_suite(self.root, task, fresh=True)
                text = green_out if label == "зелёный" else out
                self.assertEqual(run.detail,
                                 f"{head}: {acceptance.run_digest(text)} "
                                 f"(лог прогона: {run.log_path})", self.note(label))
        seconds, source = project_profile.full_suite_limit(config.DEFAULT_TARGET)
        with mock.patch.object(acceptance, "subprocess", PytestSpy(timeout=True)), \
                contextlib.redirect_stdout(io.StringIO()):
            run = acceptance.full_suite(self.root, task, fresh=True)
        self.assertEqual(run.outcome, acceptance.FULL_SUITE_TIMEOUT, str(run))
        self.assertTrue(run.detail.startswith(
            f"прогон полного набора tests/ превысил {seconds}с — завис или "
            f"ждёт сетевой ответ (источник: {source})"), run.detail)

        parsed = suite_run.parse(False, out)
        self.assertEqual((parsed.outcome, parsed.passed, parsed.failed,
                          parsed.skipped),
                         (acceptance.FULL_SUITE_RED, 1, 2, 0))
        log = self.root / "suite.log"
        report = suite_run.render(task, 3, suite_run.MODE_FULL, parsed, None,
                                  "база не нужна", log).splitlines()
        self.assertEqual(report[0], f"[{task}] suite-run №3 (полный набор): "
                                    f"красный прогон")
        self.assertEqual(report[1], "прошло: 1, упало: 2, пропущено: 0")
        self.assertEqual(report[-1], f"полный лог: {log}")


if __name__ == "__main__":
    unittest.main()
