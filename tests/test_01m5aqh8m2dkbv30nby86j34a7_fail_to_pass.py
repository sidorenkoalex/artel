"""Честный `FAIL_TO_PASS` на выходе из `tests_writing` у компонента с отчётом, наличие тестов критериев на ветке, запреты в тексте планки и переносы G2а/G2б-1.

Группа: долгоживущий
Красен до реализации: гейта честного FAIL_TO_PASS нет — планка компонента `pult-vitest`/`junit-xml` после сухого сбора уходит в `in_dev` при любом исходе тестов критериев на базе (прошёл, пропуск, TypeError, таймаут, нет записи, ошибка уровня файла, повтор имени), без отказа «список «провал проверки» не задан», без сверки опоры SPEC, без прогона с `--continue-on-collection-errors` и без записи «критериев с тестом нет»; у `acceptance.run` нет параметра `records`; приёмка ветки не сверяет наличие тестов критериев в отчёте; функции запретов нет — `it.only`, `{ retry }`, числа первого уровня, две метки проходят гейт групп, гейт долгоживущих и предпроверку; разбор скобок `.each` спотыкается об апостроф комментария; чекпоинт пишет «правило планки: взято умолчание» на каждом шаге, а гейт посторонних не пропускает эту запись; методы прежнего поведения и переносов-закреплений (AC-1, AC-7, AC-17, AC-22, AC-24, AC-25, AC-26, AC-27, проходящие ветви AC-14, AC-15 и AC-28) зелены и на базе ветки.

Стенд — настоящий git (`tests.sandbox.GitignoreCommittedRealGitSandbox`):
клон артели — корень песочницы с bare `origin`; учебный внешний проект —
`tests.sandbox.make_project_repo` со своим `origin` и записью `components:`
в `targets.yaml` песочницы (один компонент `pult-vitest` либо один
`junit-xml` на pytest). Задача заводится в `spec_gate`, SPEC.md ложится в
ссылку документов чекпоинтом шага, затем — настоящий переход
`store.set_state(… "tests_writing" …)` с деталью гейта SPEC: он пишет
запись перехода, паспорт и фиксацию «sha зафиксирован» — опору перечня
«Зелёный с рождения». Черновик планки — в каталоге документов, переход —
штатные чекпоинты шага (`checkpoint.commit_step_artifacts`,
`checkpoint.commit_success_checkpoint`) и `fsm.cmd_advance`; исход —
состояние задачи и записи журнала (действие и деталь).

Раннеры подменены без Node и без сети шпионом `subprocess.Popen`: запуск
`node_modules/.bin/vitest` (и `--version`), поддельного исполняемого файла
`pytest` вне дерева и установки `install` записывает argv и рабочий каталог
и пишет отчёт сценария: JSON отчётчика пульта по `--outputFile` либо JUnit
по `--junitxml`. Записи отчёта строятся по тестам, которые лежат в
переданных раннеру файлах (`it('AC-<n>: …')` у Vitest, `def test_ac<n>_…`
у pytest), с исходом, заданным сценарием для номера критерия. Прочие
вызовы (git) — настоящий `subprocess`.

Связка «запись проекта — профиль — правило планки — журнал — ссылка
документов — FSM».

Защитная ветка проверки ветки (запись с повтором при зелёном прогоне)
достигается подменой публичного `outcome.verdict` зелёным вердиктом.
Части AC-9 (проект из двух компонентов) и AC-12 (правило планки не
построено), требующие прямого вызова закрытой функции гейта (ответ
Оператора на вопрос планки), — в разовом файле планки задачи
`test_direct_gate_two_components.py`: долгоживущему файлу такой импорт
запрещён.

Имена проектов, компонентов, каталогов, файлов, номера критериев и
тексты — из `random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`acceptance.run(records=…, continue_on_collection_errors=…)`, гейт после
сухого сбора (опора SPEC, пустой `failure_errors`, подготовка, находки в
порядке требования 4, «Зелёный с рождения»), проверка ветки после
зелёного прогона, `guard`-функция запретов в гейте групп, гейте
долгоживущих и предпроверке, комментарии в разборе скобок `.each`, запись
умолчания правила один раз на визит и её пропуск гейтом посторонних,
текст автогейта и шесть классов отказов — все методы файла зелёные.
"""
import contextlib
import dataclasses
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (acceptance, checkpoint, config, fsm, github_adapter,
                          project_profile, store, workspace)
from orchestrator.reporters import outcome
from tests.sandbox import GitignoreCommittedRealGitSandbox, make_project_repo

REAL_POPEN = subprocess.Popen
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
VITEST_BIN = project_profile.VITEST_BASE_ARGV[0]
VITEST_REPORT_ARGS = ["--reporter=default", "--reporter={pult_reporter}",
                      "--outputFile={path}"]
LONG_TEMPLATE = "frontend/src/<dir>/<name>.<id>.test.jsx"

APPROVED_DETAIL = "гейт SPEC пройден — приёмочные тесты до кода"
F2P_ACTION = "переход отклонён: честный FAIL_TO_PASS"
NO_FAILURE_ERRORS_ACTION = ("переход отклонён: честный FAIL_TO_PASS — список "
                            "«провал проверки» не задан")
PREPARE_ACTION = "переход отклонён: честный FAIL_TO_PASS — отказ подготовки"
ANCHOR_ACTION = "переход отклонён: честный FAIL_TO_PASS — опора SPEC не найдена"
SPEC_CHANGED_ACTION = "переход отклонён: SPEC изменён после гейта SPEC"
NO_TESTED_NOTE = "честный FAIL_TO_PASS: критериев с тестом нет"
NO_RECORD = "теста нет в отчёте"
FILE_LEVEL = "ошибка уровня файла — тесты файла не исполнены"
REPEAT = "повтор имени теста в файле: "
ANCHOR_TEXT = "опора SPEC для перечня «Зелёный с рождения» не найдена: "
SPEC_CHANGED_TEXT = ("SPEC.md изменён после одобрения на гейте SPEC — верни "
                     "его к версии ")
NO_LIST_TEXT = "список «провал проверки» не задан у компонента "
PREPARE_TEXT = "отказ подготовки: "
CONTINUE_FLAG = "--continue-on-collection-errors"
DRY_COLLECT_ACTION = "переход отклонён: планка не собирается"
MANIFEST_NOTE = "перечень долгоживущих тестов записан"
GREEN_MARK = "Зелёный с рождения:"
# Пустое дерево git — встроенный объект любого репозитория.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: фикстура

## Подход
Правка кода фикстуры.

## Шаги
1. Правка кода.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Только код фикстуры.

## Риски
Нет.
"""

VITEST_LABEL = re.compile(
    r"\b(?:it|test)(?:\.[A-Za-z]+)*\(\s*'((AC-(\d+)): [^']*)'")
VITEST_ANY = re.compile(r"\b(?:it|test)(?:\.[A-Za-z]+)*\(\s*'([^']*)'")
AC_HEAD = re.compile(r"^AC-(\d+): ")
PYTEST_LABEL = re.compile(r"^\s*def (test_ac(\d+)_\w+)\(", re.MULTILINE)


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def spec_text(task_id: str, numbers, green=()) -> str:
    """SPEC фикстуры: критерии `numbers`; `green` — номера раздела
    «## Зелёный с рождения» (пусто — раздела нет)."""
    items = "\n\n".join(f"AC-{n}. Критерий фикстуры номер {n}." for n in
                        sorted(numbers))
    section = ""
    if green:
        section = "## Зелёный с рождения\n\n" + "".join(
            f"- AC-{n}\n" for n in sorted(green)) + "\n"
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура честного FAIL_TO_PASS\n\n## Контекст\n\n"
            f"## Требования\n\n## Критерии приёмки\n\n{items}\n\n"
            f"{section}## Не входит\n")


def arg_value(args: list, flag: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


class TimeoutProc:
    """Процесс раннера, «превысивший предел»: первый `communicate` с
    пределом бросает `TimeoutExpired` сразу, без ожидания; дальше — ответ
    настоящего короткого процесса, чья группа и снимается пультом."""

    def __init__(self, real):
        self.real = real
        self.pid = real.pid
        self.fired = False

    def communicate(self, *args, timeout=None, **kwargs):
        if not self.fired and timeout is not None:
            self.fired = True
            raise subprocess.TimeoutExpired("runner", timeout)
        return self.real.communicate(*args, **kwargs)

    def wait(self, timeout=None):
        if not self.fired and timeout is not None:
            self.fired = True
            raise subprocess.TimeoutExpired("runner", timeout)
        return self.real.wait()

    def kill(self):
        with contextlib.suppress(OSError):
            self.real.kill()

    @property
    def returncode(self):
        return self.real.returncode

    def __getattr__(self, name):
        return getattr(self.real, name)


class FailToPassSandbox(GitignoreCommittedRealGitSandbox):
    """Клон артели с `origin`; учебные проекты с компонентом и задачи с
    опорой SPEC заводит сценарий; раннеры — шпион `subprocess.Popen`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        fake = Path(tempfile.mkdtemp(prefix="artel-fake-")).resolve()
        self.addCleanup(shutil.rmtree, fake, True)
        self.installer = fake / f"install{self.word()}"
        self.pytest_cmd = fake / "pytest"
        for path in (self.installer, self.pytest_cmd):
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        self.vitest_version = next(
            f"{major}.0.0" for major, flags in
            project_profile.VITEST_VERSION_FLAGS.items()
            if flags.require_assertions)
        # Сценарий отчёта: номер критерия -> поля записи (Vitest) или
        # (вид, текст) (JUnit); метки без записи; файлы без записей.
        self.vitest_case: dict = {}
        self.junit_case: dict = {}
        self.vitest_default: dict = {}
        self.junit_default = ("failure", "assert 1 == 2")
        self.drop_numbers: set = set()
        self.drop_files: set = set()
        self.duplicate_numbers: set = set()
        self.collection_error_files: set = set()
        self.timeout_when = None
        self.no_report_when = None
        self.broken_report_when = None
        self.on_run = None
        self.runs: list = []
        for patcher in (
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda *args, **kwargs: (True, "")),
                mock.patch.object(subprocess, "Popen", self.spy_popen)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.clones = {config.DEFAULT_TARGET: self.root}
        self.conn = store.db()

    # --- входы ----------------------------------------------------------

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def numbers(self, count: int) -> list:
        return sorted(self.rng.sample(range(1, 60), count))

    # --- шпион раннеров -------------------------------------------------

    def answer(self, code: int, out: str, args, kwargs):
        script = f"import sys; sys.stdout.write({out!r}); sys.exit({code})"
        return REAL_POPEN([sys.executable, "-c", script], *args, **kwargs)

    def spy_popen(self, argv, *args, **kwargs):
        if not isinstance(argv, (list, tuple)) or not argv:
            return REAL_POPEN(argv, *args, **kwargs)
        parts = [str(a) for a in argv]
        cwd = Path(str(kwargs.get("cwd") or os.getcwd()))
        if parts[0] == str(self.installer):
            (cwd / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
            return self.answer(0, "", args, kwargs)
        if parts[0] == VITEST_BIN:
            if parts[1:2] == ["--version"]:
                return self.answer(0, f"vitest/{self.vitest_version}\n",
                                   args, kwargs)
            return self.vitest_run(parts, cwd, args, kwargs)
        if parts[0] == str(self.pytest_cmd):
            return self.junit_run(parts, cwd, args, kwargs)
        return REAL_POPEN(argv, *args, **kwargs)

    def runner_files(self, parts: list, cwd: Path, suffixes) -> list:
        """(путь от `cwd`, текст) файлов тестов, переданных раннеру: файлы
        по пути и файлы каталогов-целей."""
        found = []
        for part in parts:
            path = Path(part) if os.path.isabs(part) else cwd / part
            if path.is_dir():
                found += [p for p in sorted(path.rglob("*"))
                          if p.is_file() and p.name.endswith(suffixes)]
            elif path.is_file() and path.name.endswith(suffixes):
                found.append(path)
        return [(os.path.relpath(p, cwd).replace(os.sep, "/"),
                 p.read_text(encoding="utf-8")) for p in found]

    def record_run(self, kind: str, parts: list, cwd: Path) -> dict:
        run = {"kind": kind, "argv": parts, "cwd": cwd, "index": len(self.runs)}
        self.runs.append(run)
        if self.on_run is not None:
            self.on_run(run)
        return run

    @staticmethod
    def when(predicate, run: dict) -> bool:
        return predicate is not None and bool(predicate(run))

    def finish(self, run: dict, out: str, args, kwargs, red: bool = True):
        proc = self.answer(1 if red else 0, out, args, kwargs)
        if self.when(self.timeout_when, run):
            return TimeoutProc(proc)
        return proc

    def vitest_items(self, files: list) -> list:
        items = []
        for rel, text in files:
            if rel in self.drop_files or Path(rel).name in self.drop_files:
                continue
            for match in VITEST_ANY.finditer(text):
                head = AC_HEAD.match(match.group(1))
                n = int(head.group(1)) if head else None
                if n is not None and n in self.drop_numbers:
                    continue
                item = {"file": rel, "name": match.group(1), "state": "fail",
                        "mode": "run", "fails": False, "retry_count": 0,
                        "error_name": "AssertionError", "timeout": False,
                        "hook": None, "duration_ms": 3}
                item.update(self.vitest_default)
                item.update(self.vitest_case.get(n, {}))
                items.append(item)
                if n in self.duplicate_numbers:
                    items.append(dict(item))
        return items

    def vitest_run(self, parts: list, cwd: Path, args, kwargs):
        run = self.record_run("vitest", parts, cwd)
        files = self.runner_files(parts[1:], cwd, (".test.jsx",))
        items = self.vitest_items(files)
        run["items"] = items
        path = arg_value(parts, "--outputFile")
        if path and not self.when(self.no_report_when, run):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps({"tests": items})
            if self.when(self.broken_report_when, run):
                text = "{не json"
            Path(path).write_text(text, encoding="utf-8")
        red = any(item["state"] not in ("pass", "skip", "todo") for item in items)
        return self.finish(run, f"{len(items)} tests\n", args, kwargs, red)

    def junit_xml(self, files: list) -> str:
        cases = []
        for rel, text in files:
            if rel in self.drop_files or Path(rel).name in self.drop_files:
                continue
            if Path(rel).name in self.collection_error_files:
                dotted = rel[:-3].replace("/", ".")
                cases.append(f'<testcase classname="" name="{dotted}" '
                             f'time="0.000"><error message="collection '
                             f'failure">ImportError: no module</error>'
                             f'</testcase>')
                continue
            for match in PYTEST_LABEL.finditer(text):
                n = int(match.group(2))
                if n in self.drop_numbers:
                    continue
                kind, message = self.junit_case.get(n, self.junit_default)
                body = ("" if kind == "passed" else
                        f'<{kind} message="{message}">{message}</{kind}>')
                cases.append(f'<testcase file="{rel}" classname="" '
                             f'name="{match.group(1)}" time="0.01">{body}'
                             f'</testcase>')
        return ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
                '<testsuite name="pytest">' + "".join(cases)
                + "</testsuite></testsuites>")

    def junit_run(self, parts: list, cwd: Path, args, kwargs):
        run = self.record_run("pytest", parts, cwd)
        files = self.runner_files(parts[1:], cwd, (".py",))
        files = [(rel, text) for rel, text in files
                 if Path(rel).name.startswith("test_")]
        run["files"] = [rel for rel, _ in files]
        path = arg_value(parts, "--junitxml")
        if path and not self.when(self.no_report_when, run):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            text = self.junit_xml(files)
            if self.when(self.broken_report_when, run):
                text = "<не xml"
            Path(path).write_text(text, encoding="utf-8")
        red = "<failure" in self.junit_xml(files) or "<error" in self.junit_xml(files)
        return self.finish(run, "pytest\n", args, kwargs, red)

    def base_runs(self) -> list:
        """Запуски раннера компонента (без `--version` и установки)."""
        return list(self.runs)

    # --- проекты --------------------------------------------------------

    def append_entry(self, text: str) -> None:
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + text,
                                  encoding="utf-8")

    def commit_project(self, clone: Path, files: dict) -> None:
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def vitest_project(self, failure_errors=("AssertionError",)) -> SimpleNamespace:
        """Учебный проект с единственным компонентом `pult-vitest` (шаблон
        `long_lived`, маска `tests`, `plank_layout`)."""
        name, comp = f"v{self.word()}", f"c{self.word()}"
        layout = f"frontend/src/.pv{self.word(5)}/<id>"
        fields = {"command": flow(project_profile.VITEST_BASE_ARGV),
                  "report": "pult-vitest",
                  "report_args": flow(VITEST_REPORT_ARGS),
                  "select": flow([f"--sel{self.word()}", "{tests}"]),
                  "install": flow([str(self.installer)]),
                  "tests": flow(["frontend/src/**/*.test.jsx"]),
                  "plank_layout": layout,
                  "long_lived": LONG_TEMPLATE,
                  "weakening_scope": flow(["frontend/src/**"]),
                  "mutation_claim_scope": flow(["frontend/src/**"])}
        if failure_errors:
            fields["failure_errors"] = flow(failure_errors)
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        for key, value in fields.items():
            lines.append(f"        {key}: {value}\n")
        lines.append("        tools:\n")
        lines.append(f'          vitest: "{self.vitest_version}"\n')
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        self.commit_project(clone, {
            "package.json": '{"name": "web"}\n',
            "vitest.config.js": "export default {}\n",
            "package-lock.json": json.dumps({"lockfileVersion": 3}) + "\n",
            "frontend/src/app.jsx": "export const app = 1;\n",
            "lib/app.js": "export const lib = 1;\n"})
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, layout=layout,
                               kind="vitest", code="lib/app.js")

    def junit_project(self, failure_errors=("AssertionError",)) -> SimpleNamespace:
        """Учебный проект с единственным компонентом `junit-xml` на pytest
        (поддельный исполняемый файл `pytest`), `plank_layout` в корне."""
        name, comp = f"j{self.word()}", f"c{self.word()}"
        layout = f".pj{self.word(5)}/<id>"
        fields = {"command": flow([str(self.pytest_cmd)]),
                  "report": "junit-xml",
                  "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "plank_layout": layout,
                  "weakening_scope": flow(["tests/**"]),
                  "mutation_claim_scope": flow(["tests/**"])}
        if failure_errors:
            fields["failure_errors"] = flow(failure_errors)
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        for key, value in fields.items():
            lines.append(f"        {key}: {value}\n")
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        self.commit_project(clone, {"tests/test_base.py":
                                    "def test_base():\n    pass\n",
                                    "app.py": "APP = 1\n"})
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, layout=layout,
                               kind="junit", code="app.py")

    def own_profile_project(self) -> SimpleNamespace:
        """Учебный проект с записью `test_profile`: `runner: pytest-own`,
        `report: junit-xml`, поддельный `pytest` — вне границы задачи."""
        name = f"o{self.word()}"
        fields = {"command": flow([str(self.pytest_cmd)]),
                  "runner": "pytest-own",
                  "report": "junit-xml",
                  "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": flow(["tests/**"]),
                  "mutation_claim_scope": flow(["tests/**"])}
        lines = [ENTRY_HEAD.format(name=name), "    test_profile:\n"]
        for key, value in fields.items():
            lines.append(f"      {key}: {value}\n")
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        self.commit_project(clone, {"tests/test_base.py":
                                    "def test_base():\n    pass\n",
                                    "app.py": "APP = 1\n"})
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=project_profile.DEFAULT_COMPONENT,
                               layout="", kind="own", code="app.py")

    # --- задачи ---------------------------------------------------------

    def new_task(self, project, numbers, green=(), approve: bool = True,
                 ensure: bool = True):
        """Задача проекта: SPEC в ссылке документов и (при `approve`)
        настоящий переход `spec_gate -> tests_writing` гейта SPEC;
        `ensure=False` — рабочей копии и кодовой ветки ещё нет."""
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        state = "spec_gate" if approve else "tests_writing"
        store.insert_task(self.conn, tid, "Фикстура FAIL_TO_PASS", state,
                          branch, project.name, 25.0)
        if ensure:
            wt, error = workspace.ensure(tid, branch)
            self.assertIsNone(error, self.note(
                f"рабочая копия не заведена: {error}"))
        else:
            wt = workspace.path(tid, project.name)
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=project.name, wt=Path(wt), project=project)
        t.docs = config.PROJECTS / project.name / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        t.spec = spec_text(tid, numbers, green)
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, tid, "analyst")
        if approve:
            store.set_state(self.conn, tid, "tests_writing", "operator",
                            expected_state="spec_gate", detail=APPROVED_DETAIL)
        # Чекпоинт уносит SPEC.md в ссылку и чистит каталог; на старте шага
        # роли пульт материализует его снова — то же делает сценарий.
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        return t

    def docs_head(self, t) -> str:
        return self.git("-C", str(self.clones[t.target]), "for-each-ref",
                        "--format=%(objectname)",
                        "refs/artifacts/" + t.id).strip()

    def anchor_sha(self, t) -> str:
        """`артефакты=` первой фиксации после перехода гейта SPEC."""
        rows = store.task_steps(self.conn, t.id)
        since = max(i for i, r in enumerate(rows)
                    if r["action"] == "state -> tests_writing")
        for row in rows[since:]:
            if row["action"] == "sha зафиксирован":
                return re.search(r"артефакты=(\S+)", row["detail"]).group(1)
        self.fail(self.note("фиксации после перехода нет"))

    def edit_spec(self, t, green: int | None = None) -> None:
        """Правка SPEC.md в каталоге документов (чекпоинт шага уносит файл
        в ссылку и чистит каталог — текст пишется заново): раздел «## Зелёный
        с рождения» с критерием `green` либо лишняя строка."""
        if green is None:
            t.spec += f"\nПравка роли {self.word()}.\n"
        else:
            t.spec = t.spec.replace(
                "## Не входит",
                f"## Зелёный с рождения\n\n- AC-{green}\n\n## Не входит")
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")

    def write_plank(self, t, files: dict) -> None:
        t.plank.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (t.plank / name).write_text(text, encoding="utf-8")

    def write_code(self, t, rel: str, text: str) -> None:
        path = t.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def long_rel(self, t) -> str:
        return f"frontend/src/{self.word(5)}/{self.word()}.{t.low}.test.jsx"

    def layout_rel(self, t, name: str) -> str:
        return t.project.layout.replace("<id>", t.id) + "/" + name

    def case_id(self, t, rel: str, name: str, n: int | None = None) -> str:
        return project_profile.test_id(t.project.comp, rel, name, n)

    # --- тексты фикстур -------------------------------------------------

    def jsx(self, labels, head: str | None = None) -> str:
        """Файл планки с меткой: строка группы «разовый», маркер красноты
        (или `head`), по `it('<метка>', …)` на элемент `labels` — номер
        критерия либо готовая метка."""
        if head is None:
            head = f"// Красен до реализации: фикстура {self.word()}.\n"
        body = ""
        for label in labels:
            if isinstance(label, int):
                label = f"AC-{label}: кнопка {self.word()}"
            body += (f"it('{label}', () => {{ expect(1).toBe(2); }});\n")
        return ("// Группа: разовый\n" + head
                + "import { expect, it } from 'vitest';\n\n" + body)

    def long_jsx(self, numbers) -> str:
        body = ""
        for n in numbers:
            body += (f"// Ловит мутацию: фикстура {self.word()} — сумма другая.\n"
                     f"it('AC-{n}: модуль {self.word()}', () => "
                     f"{{ expect({n}).toBe({n + 1}); }});\n\n")
        return ("// Группа: долгоживущий\n"
                f"// Красен до реализации: фикстура {self.word()}.\n"
                "import { expect, it } from 'vitest';\n\n" + body)

    def py_plank(self, numbers, marker: str | None = None) -> str:
        name = self.word()
        if marker is None:
            marker = "Красен " + "до реализации: фикстура " + name + " ждёт кода."
        lines = ['"""Разовая фикстура ' + name + ".", "",
                 "Группа: разовый", marker, '"""', "import unittest", "", "",
                 "class FixturePlankTest(unittest.TestCase):", ""]
        for n in numbers:
            lines += [f"    def test_ac{n}_{self.word()}(self):",
                      '        """Фикстурный метод."""',
                      "        self.assertEqual(2 + 2, 5)", ""]
        return "\n".join(lines)

    def labels_of(self, text: str) -> dict:
        """{номер: метка} тестов `it('AC-<n>: …')` текста."""
        return {int(m.group(3)): m.group(1) for m in VITEST_LABEL.finditer(text)}

    # --- места ----------------------------------------------------------

    def advance(self, t, checkpoint_code: bool = True,
                before_advance=None) -> tuple:
        """Шаг test_author (запись «agent run started», чекпоинты шага:
        черновик — в ссылку документов, долгоживущие файлы — в кодовую
        ветку), затем `advance`: (новые записи журнала, вывод).
        `before_advance` — правка сценария между чекпоинтом и `advance`."""
        store.journal(self.conn, t.id, "test_author", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        if checkpoint_code and t.wt.is_dir():
            checkpoint.commit_success_checkpoint(self.conn, t.id, "test_author")
        if before_advance is not None:
            before_advance()
        before = len(store.task_steps(self.conn, t.id))
        self.runs.clear()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, buf.getvalue()

    def state(self, t) -> str:
        return store.get_task(self.conn, t.id)["state"]

    def explain(self, rows: list, output: str) -> str:
        runs = "\n".join(f"{r['kind']}: {r['argv']}" for r in self.runs)
        return self.note(
            f"записи: {[(r['action'], r['detail']) for r in rows]}\n"
            f"вывод: {output[-3000:]}\nзапуски:\n{runs}")

    def details(self, rows: list, action: str) -> list:
        return [r["detail"] or "" for r in rows if r["action"] == action]

    def refusal(self, t, action: str, **kwargs) -> tuple:
        """(деталь записи отказа `action`, записи, вывод); провал — записи
        нет либо задача ушла из `tests_writing`."""
        rows, output = self.advance(t, **kwargs)
        found = self.details(rows, action)
        self.assertTrue(found, f"advance не записал «{action}»:\n"
                        + self.explain(rows, output) + "\nжурнал: " + str(
                            [(r["actor"], r["action"]) for r in
                             store.task_steps(self.conn, t.id)]))
        self.assertEqual(self.state(t), "tests_writing",
                         self.explain(rows, output))
        return found[-1], rows, output

    def passes(self, t) -> tuple:
        rows, output = self.advance(t)
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        return rows, output

    def gate_runs(self) -> list:
        """Запуски раннера компонента после сухого сбора (первого)."""
        return self.runs[1:]

    def developer_advance(self, t) -> tuple:
        """Шаг developer: правка кода в зонах задачи коммитом, PLAN.md
        `ready` чекпоинтом шага, затем `advance` из `in_dev`."""
        store.update_task(self.conn, t.id, zones=t.project.code)
        self.write_code(t, t.project.code, f"// код {self.word()}\n")
        self.git("-C", str(t.wt), "add", "--", t.project.code)
        self.git("-C", str(t.wt), "commit", "-q", "-m", "код разработчика")
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "PLAN.md").write_text(PLAN_READY.format(task=t.id),
                                        encoding="utf-8")
        store.journal(self.conn, t.id, "developer", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        before = len(store.task_steps(self.conn, t.id))
        self.runs.clear()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, buf.getvalue()

    def branch_phase(self, base: bool = False) -> None:
        """Отчёты прогонов ветки: тесты по умолчанию проходят; `base` —
        прежний сценарий базы (провал проверки)."""
        self.vitest_case.clear()
        self.junit_case.clear()
        self.drop_numbers.clear()
        self.drop_files.clear()
        if base:
            self.vitest_default = {}
            self.junit_default = ("failure", "assert 1 == 2")
        else:
            self.vitest_default = {"state": "pass", "error_name": None}
            self.junit_default = ("passed", "")


# ---------------------------------------------------------------- AC-1

class Ac1AssertionOnBaseTest(FailToPassSandbox):

    def test_ac1_assertion_failures_on_base_go_to_in_dev(self):
        """Тесты `AC-<n>` планки `pult-vitest`, упавшие на базе с `AssertionError`, — выход в `in_dev`.

        Сценарий: SPEC с двумя–тремя критериями (номера от зерна), планка —
        один-два файла `.test.jsx` с тестами всех критериев; отчёт базы
        несёт по записи на тест, исход `fail`, `error_name` —
        `AssertionError` (имя из `failure_errors` компонента). `advance`
        переводит задачу в `in_dev`, записи «переход отклонён: честный
        FAIL_TO_PASS» нет.

        Ловит мутацию: «провал проверки» у `pult-vitest` сверяется по
        исходу без имени ошибки из `failure_errors` наоборот (имя из
        списка считается ошибкой) — отказ вместо перехода; гейт требует
        `passed` вместо провала — отказ «прошёл» не нужен, но запись
        `failed` объявлена находкой.
        """
        nums = self.numbers(self.rng.randint(2, 3))
        project = self.vitest_project()
        t = self.new_task(project, nums)
        split = self.rng.randint(1, len(nums))
        files = {f"a{self.word()}.test.jsx": self.jsx(nums[:split])}
        if nums[split:]:
            files[f"b{self.word()}.test.jsx"] = self.jsx(nums[split:])
        self.write_plank(t, files)
        rows, output = self.passes(t)
        self.assertFalse(self.details(rows, F2P_ACTION),
                         self.explain(rows, output))


# ---------------------------------------------------------------- AC-2

class Ac2PassedOnBaseTest(FailToPassSandbox):

    def test_ac2_passed_on_base_refused_with_id_and_kind(self):
        """Тест `AC-<n>`, прошедший на базе, — отказ «переход отклонён: честный FAIL_TO_PASS» с идентификатором теста и видом «прошёл».

        Сценарий: два критерия; отчёт базы: тест первого — `pass`, второго —
        `AssertionError`. Отказ гейта; деталь несёт идентификатор теста
        первого критерия `<компонент>:<путь выкладки>::<полное имя>` и слово
        «прошёл», идентификатора теста второго критерия в ней нет; задача
        остаётся в `tests_writing`.

        Ловит мутацию: гейт проверяет только наличие записи критерия, не её
        исход — прошедший тест принят, задача в `in_dev`; идентификатор
        строится по пути каталога планки, а не выкладки — в детали нет
        идентификатора отчёта.
        """
        a, b = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (a, b))
        name = f"a{self.word()}.test.jsx"
        text = self.jsx((a, b))
        self.write_plank(t, {name: text})
        self.vitest_case[a] = {"state": "pass", "error_name": None}
        detail, rows, output = self.refusal(t, F2P_ACTION)
        labels = self.labels_of(text)
        rel = self.layout_rel(t, name)
        self.assertIn(self.case_id(t, rel, labels[a]), detail,
                      self.explain(rows, output))
        self.assertIn("прошёл", detail, self.explain(rows, output))
        self.assertNotIn(self.case_id(t, rel, labels[b]), detail,
                         self.explain(rows, output))


# ---------------------------------------------------------- AC-3, AC-4

class KindOfRecordTest(FailToPassSandbox):

    def assert_kind(self, case: dict, words) -> None:
        """Тест одного из двух критериев с полями записи `case` — отказ
        гейта с идентификатором этого теста и словами вида `words`."""
        self.vitest_case.clear()
        a, b = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (a, b))
        name = f"k{self.word()}.test.jsx"
        text = self.jsx((a, b))
        self.write_plank(t, {name: text})
        self.vitest_case[a] = case
        detail, rows, output = self.refusal(t, F2P_ACTION)
        label = self.labels_of(text)[a]
        self.assertIn(self.case_id(t, self.layout_rel(t, name), label), detail,
                      self.explain(rows, output))
        for word in words:
            self.assertIn(word, detail, self.explain(rows, output))

    def test_ac3_error_name_timeout_and_hook_refused_with_kind(self):
        """Тест `AC-<n>`, упавший на базе с `TypeError`, по таймауту или в хуке, — отказ с идентификатором и видом.

        Сценарий (подслучай — свежая задача): у теста первого критерия
        запись `fail` с (а) `error_name: TypeError` — имя вне
        `failure_errors`; (б) `timeout: true`; (в) `hook: beforeEach` при
        `error_name: AssertionError`. Отказ «переход отклонён: честный
        FAIL_TO_PASS»; деталь несёт идентификатор теста и вид: имя ошибки
        «TypeError», «таймаут», «хук» соответственно.

        Ловит мутацию: «провал проверки» — любой `failed`/`error` отчёта
        (без сверки с `failure_errors`) — `TypeError` принят; поле
        `timeout`/`hook` не читается при имени `AssertionError` — тест,
        упавший в хуке, принят как провал проверки; вид в детали не назван.
        """
        cases = [("TypeError", {"error_name": "TypeError"}, ("TypeError",)),
                 ("таймаут", {"error_name": "Error", "timeout": True},
                  ("таймаут",)),
                 ("хук", {"error_name": "AssertionError",
                          "hook": "beforeEach"}, ("хук",))]
        for label, case, words in cases:
            with self.subTest(case=label, seed=self.seed):
                self.assert_kind(case, words)

    def test_ac4_skip_todo_and_fails_refused_with_kind(self):
        """Тест `AC-<n>` пропущенный, `todo` или с `fails` — отказ с идентификатором и видом.

        Сценарий (подслучай — свежая задача): запись теста первого критерия
        (а) `state: skip`, `mode: skip`; (б) `state: todo`, `mode: todo`;
        (в) `state: fail`, `error_name: AssertionError`, `fails: true` — по
        исходу и имени запись выглядит провалом проверки, отличает её
        только `fails`. Отказ гейта; деталь несёт идентификатор теста и вид
        («пропуск» с `mode` — «skip»; «todo»; «fails»).

        Ловит мутацию: пропуск засчитан как «не прошёл» и принят; поле
        `fails` не читается — `it.fails` с `AssertionError` принят как
        провал проверки; вид пропуска назван без `mode`.
        """
        cases = [("skip", {"state": "skip", "mode": "skip", "error_name": None},
                  ("пропуск", "skip")),
                 ("todo", {"state": "todo", "mode": "todo", "error_name": None},
                  ("todo",)),
                 ("fails", {"error_name": "AssertionError", "fails": True},
                  ("fails",))]
        for label, case, words in cases:
            with self.subTest(case=label, seed=self.seed):
                self.assert_kind(case, words)


# ---------------------------------------------------------------- AC-5

class Ac5NoRecordTest(FailToPassSandbox):

    def test_ac5_covered_criterion_without_records_refused(self):
        """Покрытый критерий без записей в отчёте базы — находка «AC-n: теста нет в отчёте».

        Сценарий: один файл планки с тестами двух критериев; отчёт базы
        несёт запись только первого (`AssertionError`). Отказ «переход
        отклонён: честный FAIL_TO_PASS» с находкой «AC-<второй>: теста нет
        в отчёте»; первый критерий находкой «нет в отчёте» не назван.

        Ловит мутацию: гейт перебирает записи отчёта, а не покрытые
        критерии — отсутствие записи не замечено, задача в `in_dev`.
        """
        a, b = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (a, b))
        self.write_plank(t, {f"n{self.word()}.test.jsx": self.jsx((a, b))})
        self.drop_numbers.add(b)
        detail, rows, output = self.refusal(t, F2P_ACTION)
        self.assertIn(f"AC-{b}: {NO_RECORD}", detail, self.explain(rows, output))
        self.assertNotIn(f"AC-{a}: {NO_RECORD}", detail,
                         self.explain(rows, output))


# ---------------------------------------------------------------- AC-6

class Ac6FileLevelVitestTest(FailToPassSandbox):

    def test_ac6_plank_file_without_records_is_file_level_error(self):
        """Тестовый файл планки `pult-vitest` без записей в отчёте базы — находка «<файл>: ошибка уровня файла — тесты файла не исполнены».

        Сценарий: два файла планки; второй импортирует несуществующий
        модуль, и отчёт базы не несёт ни одной его записи; первый — с
        записью `AssertionError`. Отказ гейта с находкой «<второй файл>:
        ошибка уровня файла — тесты файла не исполнены»; первый файл этой
        находкой не назван.

        Ловит мутацию: файлы планки без записей не ищутся — отказ называет
        только «теста нет в отчёте»; файл сопоставляется с записями по пути
        каталога планки, а не выкладки — и первый файл объявлен без записей.
        """
        a, b = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (a, b))
        first, second = f"f{self.word()}.test.jsx", f"g{self.word()}.test.jsx"
        broken = self.jsx((b,)).replace(
            "import { expect, it } from 'vitest';",
            "import { expect, it } from 'vitest';\n"
            f"import {{ nope }} from './{self.word()}.js';")
        self.write_plank(t, {first: self.jsx((a,)), second: broken})
        self.drop_files.add(second)
        detail, rows, output = self.refusal(t, F2P_ACTION)
        self.assertIn(f"{second}: {FILE_LEVEL}", detail,
                      self.explain(rows, output))
        self.assertNotIn(f"{first}: {FILE_LEVEL}", detail,
                         self.explain(rows, output))


# ---------------------------------------------------------- AC-7, AC-8

class JunitBaseTest(FailToPassSandbox):

    def test_ac7_junit_assert_failure_passes_gate(self):
        """Компонент `junit-xml` на pytest: тест `test_ac<n>_…`, падающий на `assert`, проходит гейт честного `FAIL_TO_PASS`.

        Сценарий: учебный проект с одним компонентом `junit-xml` (поддельный
        `pytest`, `failure_errors: [AssertionError]`), SPEC с одним–двумя
        критериями, планка — `test_*.py` с методом `test_ac<n>_…` на
        критерий; JUnit базы: у каждого `<failure message="assert 1 == 2">`.
        `advance` переводит задачу в `in_dev`, отказа «честный FAIL_TO_PASS»
        нет.

        Ловит мутацию: у `junit-xml` вид падения сверяется только с
        `failure_errors` (без «assert ») — запись «assert 1 == 2» объявлена
        находкой, задача остаётся в `tests_writing`.
        """
        nums = self.numbers(self.rng.randint(1, 2))
        project = self.junit_project()
        t = self.new_task(project, nums)
        self.write_plank(t, {f"test_{self.word()}.py": self.py_plank(nums)})
        rows, output = self.passes(t)
        self.assertFalse(self.details(rows, F2P_ACTION),
                         self.explain(rows, output))

    def test_ac8_junit_collection_error_is_file_level_by_record_name(self):
        """Компонент `junit-xml`: запись `error` с видом «collection failure» — находка об ошибке уровня файла с файлом по имени записи.

        Сценарий: планка из двух `test_*.py`; JUnit базы несёт у второго
        файла одну запись `<error message="collection failure">` с именем —
        точечным путём модуля выкладки, у первого — `assert`. Отказ
        «переход отклонён: честный FAIL_TO_PASS»; находка «… ошибка уровня
        файла — тесты файла не исполнены» называет второй файл (имя модуля
        из имени записи), первый файл в находке об ошибке уровня файла не
        назван.

        Ловит мутацию: запись `error` «collection failure» разбирается как
        тест критерия — находки ошибки уровня файла нет; файл находки
        берётся из пустого classname — имя файла не названо.
        """
        a, b = self.numbers(2)
        project = self.junit_project()
        t = self.new_task(project, (a, b))
        first, second = f"test_{self.word()}.py", f"test_{self.word()}.py"
        self.write_plank(t, {first: self.py_plank((a,)),
                             second: self.py_plank((b,))})
        self.collection_error_files.add(second)
        detail, rows, output = self.refusal(t, F2P_ACTION)
        found = [part for part in re.split(r"; |\n", detail)
                 if FILE_LEVEL in part]
        self.assertTrue(found, self.explain(rows, output))
        self.assertTrue(any(second[:-3] in part for part in found),
                        self.explain(rows, output))
        self.assertFalse(any(first[:-3] in part for part in found),
                         self.explain(rows, output))


# ---------------------------------------------------------------- AC-9

# Часть критерия о проекте из двух компонентов (прямой вызов гейта) — в
# разовом файле планки задачи; здесь — один компонент каждого вида.

class Ac9NoFailureErrorsTest(FailToPassSandbox):

    def test_ac9_empty_failure_errors_refused_before_run(self):
        """Пустой `failure_errors` у `junit-xml` и у `pult-vitest` — отказ «список «провал проверки» не задан у компонента <имя>» без прогона, своим действием.

        Сценарий (подслучай — свой проект с одним компонентом без поля
        `failure_errors`): планка с тестом критерия, падающим провалом
        проверки. Отказ — действие «переход отклонён: честный FAIL_TO_PASS
        — список «провал проверки» не задан», деталь «список «провал
        проверки» не задан у компонента <имя компонента>»; записи
        «переход отклонён: честный FAIL_TO_PASS» нет; раннер компонента
        запущен только сухим сбором (у pytest — ни одного запуска с
        `--continue-on-collection-errors`).

        Ловит мутацию: пустой список проверяется после прогона на базе —
        второй запуск раннера есть; отказ идёт находкой общего отказа
        «честный FAIL_TO_PASS»; у `junit-xml` пустой список не проверяется
        (там есть «assert ») — задача в `in_dev`.
        """
        for kind in ("vitest", "junit"):
            with self.subTest(kind=kind, seed=self.seed):
                if kind == "vitest":
                    project = self.vitest_project(failure_errors=())
                else:
                    project = self.junit_project(failure_errors=())
                n = self.numbers(1)[0]
                t = self.new_task(project, (n,))
                files = ({f"e{self.word()}.test.jsx": self.jsx((n,))}
                         if kind == "vitest" else
                         {f"test_{self.word()}.py": self.py_plank((n,))})
                self.write_plank(t, files)
                detail, rows, output = self.refusal(t, NO_FAILURE_ERRORS_ACTION)
                self.assertIn(NO_LIST_TEXT + project.comp, detail,
                              self.explain(rows, output))
                self.assertFalse(self.details(rows, F2P_ACTION),
                                 self.explain(rows, output))
                self.assertEqual(len(self.runs), 1, self.explain(rows, output))
                self.assertFalse(any(CONTINUE_FLAG in r["argv"]
                                     for r in self.runs),
                                 self.explain(rows, output))


# --------------------------------------------------------------- AC-10

class Ac10RepeatTest(FailToPassSandbox):

    def test_ac10_repeated_name_in_plank_and_long_lived_file(self):
        """Повтор имени теста в файле планки или своём долгоживущем файле (идентификатор с `#<n>`) — находка «повтор имени теста в файле: <идентификатор>».

        Сценарий (подслучай — свежая задача): (а) отчёт базы несёт тест
        критерия файла планки дважды под одним именем; (б) так же — тест
        критерия долгоживущего файла задачи по шаблону `long_lived`. Обе
        записи — `AssertionError`. Отказ «переход отклонён: честный
        FAIL_TO_PASS» с находкой «повтор имени теста в файле:
        <компонент>:<путь>::<имя>#2».

        Ловит мутацию: повторы ищутся только в файлах планки — повтор
        долгоживущего файла не замечен; запись `#2` проверяется как
        обычный провал проверки — задача в `in_dev`.
        """
        for where in ("планка", "долгоживущий"):
            with self.subTest(where=where, seed=self.seed):
                a, b = self.numbers(2)
                project = self.vitest_project()
                t = self.new_task(project, (a, b))
                plank_name = f"r{self.word()}.test.jsx"
                plank_text = self.jsx((a,))
                long_rel = self.long_rel(t)
                long_text = self.long_jsx((b,))
                self.write_plank(t, {plank_name: plank_text})
                self.write_code(t, long_rel, long_text)
                if where == "планка":
                    self.duplicate_numbers.add(a)
                    rel, label = (self.layout_rel(t, plank_name),
                                  self.labels_of(plank_text)[a])
                else:
                    self.duplicate_numbers.add(b)
                    rel, label = long_rel, self.labels_of(long_text)[b]
                detail, rows, output = self.refusal(t, F2P_ACTION)
                self.assertIn(REPEAT + self.case_id(t, rel, label, 2), detail,
                              self.explain(rows, output))
                self.duplicate_numbers.clear()


# --------------------------------------------------------------- AC-11

class Ac11OrderTest(FailToPassSandbox):

    def test_ac11_findings_order_in_one_refusal(self):
        """Находки — одним отказом в порядке: повторы `#<n>` → по критериям → ошибки уровня файла.

        Сценарий: файл планки A — тест первого критерия дважды под одним
        именем (`AssertionError`), тест второго — `pass`; файл B — тест
        третьего критерия, отчёт базы не несёт ни одной записи файла B.
        Одна запись «переход отклонён: честный FAIL_TO_PASS»: в её детали
        находка повтора стоит раньше находки «прошёл» второго критерия, а
        та — раньше находки ошибки уровня файла B.

        Ловит мутацию: находки выдаются в порядке файлов/записей отчёта —
        ошибка уровня файла или находка критерия впереди повтора; каждая
        группа находок пишется отдельной записью отказа.
        """
        a, b, c = self.numbers(3)
        project = self.vitest_project()
        t = self.new_task(project, (a, b, c))
        fa, fb = f"a{self.word()}.test.jsx", f"b{self.word()}.test.jsx"
        text_a = self.jsx((a, b))
        self.write_plank(t, {fa: text_a, fb: self.jsx((c,))})
        self.duplicate_numbers.add(a)
        self.vitest_case[b] = {"state": "pass", "error_name": None}
        self.drop_files.add(fb)
        detail, rows, output = self.refusal(t, F2P_ACTION)
        self.assertEqual(len(self.details(rows, F2P_ACTION)), 1,
                         self.explain(rows, output))
        labels = self.labels_of(text_a)
        rel = self.layout_rel(t, fa)
        repeat = detail.find(REPEAT + self.case_id(t, rel, labels[a], 2))
        passed = detail.find(self.case_id(t, rel, labels[b]))
        file_level = detail.find(f"{fb}: {FILE_LEVEL}")
        self.assertTrue(min(repeat, passed, file_level) >= 0,
                        self.explain(rows, output))
        self.assertLess(repeat, passed, self.explain(rows, output))
        self.assertLess(passed, file_level, self.explain(rows, output))

    def test_ac11_run_timeout_first_finding(self):
        """Таймаут прогона на базе — первая находка общего отказа, раньше находок по критериям.

        Сценарий: компонент `junit-xml`; прогон гейта (запуск с
        `--continue-on-collection-errors`) превышает предел — процесс
        раннера бросает `TimeoutExpired` на первом ожидании, без реального
        ожидания. Отказ «переход отклонён: честный FAIL_TO_PASS»: в детали
        есть находка таймаута («таймаут»/«превысил») и находка «AC-<n>:
        теста нет в отчёте», таймаут — раньше.

        Ловит мутацию: таймаут прогона уходит в «отказ подготовки» (другое
        действие) или теряется — находка таймаута отсутствует; таймаут
        дописывается в конец после находок критериев.
        """
        n = self.numbers(1)[0]
        project = self.junit_project()
        t = self.new_task(project, (n,))
        self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
        self.timeout_when = lambda run: CONTINUE_FLAG in run["argv"]
        detail, rows, output = self.refusal(t, F2P_ACTION)
        timeout = re.search(r"таймаут|превысил", detail)
        missing = detail.find(f"AC-{n}: {NO_RECORD}")
        self.assertIsNotNone(timeout, self.explain(rows, output))
        self.assertGreaterEqual(missing, 0, self.explain(rows, output))
        self.assertLess(timeout.start(), missing, self.explain(rows, output))

    def test_ac11_separate_refusals_order(self):
        """Отдельные отказы по старшинству: SPEC изменён → пустой `failure_errors` → отказ подготовки → находки; каждый — своим действием, без общего отказа.

        Сценарий (подслучай — свежая задача): (а) test_author правит SPEC.md
        после гейта SPEC, у компонента нет `failure_errors`, есть тест
        «прошёл» — только отказ «SPEC.md изменён после одобрения на гейте
        SPEC — верни его к версии <sha опоры>», без записи пустого списка
        и находок, раннер запущен только сухим сбором; (б) нет
        `failure_errors`, а отчёт прогона гейта не создаётся — только отказ
        пустого списка; (в) `failure_errors` есть, тест «прошёл», отчёт
        прогона гейта не разобран — только «отказ подготовки», без записи
        «переход отклонён: честный FAIL_TO_PASS».

        Ловит мутацию: пустой список проверяется раньше опоры SPEC — в (а)
        отказ пустого списка; подготовка проверяется раньше пустого списка
        — в (б) «отказ подготовки»; отказ подготовки дописан к находкам — в
        (в) есть общий отказ «прошёл».
        """
        def case_spec_changed():
            n = self.numbers(1)[0]
            project = self.vitest_project(failure_errors=())
            t = self.new_task(project, (n,))
            anchor = self.anchor_sha(t)
            self.edit_spec(t)
            self.write_plank(t, {f"s{self.word()}.test.jsx": self.jsx((n,))})
            self.vitest_case[n] = {"state": "pass", "error_name": None}
            detail, rows, output = self.refusal(t, SPEC_CHANGED_ACTION)
            match = re.search(re.escape(SPEC_CHANGED_TEXT) + r"([0-9a-f]{7,40})",
                              detail)
            self.assertIsNotNone(match, self.explain(rows, output))
            self.assertTrue(anchor.startswith(match.group(1)),
                            self.explain(rows, output))
            for action in (NO_FAILURE_ERRORS_ACTION, F2P_ACTION, PREPARE_ACTION):
                self.assertFalse(self.details(rows, action),
                                 self.explain(rows, output))
            self.assertEqual(len(self.runs), 1, self.explain(rows, output))

        def case_list_before_prepare():
            n = self.numbers(1)[0]
            project = self.vitest_project(failure_errors=())
            t = self.new_task(project, (n,))
            self.write_plank(t, {f"l{self.word()}.test.jsx": self.jsx((n,))})
            self.no_report_when = lambda run: run["index"] >= 1
            _detail, rows, output = self.refusal(t, NO_FAILURE_ERRORS_ACTION)
            for action in (PREPARE_ACTION, F2P_ACTION):
                self.assertFalse(self.details(rows, action),
                                 self.explain(rows, output))

        def case_prepare_before_findings():
            n = self.numbers(1)[0]
            project = self.vitest_project()
            t = self.new_task(project, (n,))
            self.write_plank(t, {f"p{self.word()}.test.jsx": self.jsx((n,))})
            self.vitest_case[n] = {"state": "pass", "error_name": None}
            self.broken_report_when = lambda run: run["index"] >= 1
            detail, rows, output = self.refusal(t, PREPARE_ACTION)
            self.assertIn(PREPARE_TEXT, detail, self.explain(rows, output))
            self.assertFalse(self.details(rows, F2P_ACTION),
                             self.explain(rows, output))

        for label, case in (("SPEC изменён", case_spec_changed),
                            ("пустой список", case_list_before_prepare),
                            ("подготовка", case_prepare_before_findings)):
            with self.subTest(case=label, seed=self.seed):
                self.vitest_case.clear()
                self.no_report_when = self.broken_report_when = None
                case()


# --------------------------------------------------------------- AC-12

# Защитная ветка «правило планки не построено» (прямой вызов гейта) — в
# разовом файле планки задачи; здесь — остальные выключенные случаи.

class Ac12DisabledCasesTest(FailToPassSandbox):

    def manual_only_plank(self, n: int) -> str:
        """Файл планки без тестов критериев: пометка `manual` и
        вспомогательный тест без метки."""
        return ("// Группа: разовый\n"
                f"// Красен до реализации: фикстура {self.word()}.\n"
                f"// AC-{n}: manual — внешняя система {self.word()} без "
                f"тестового контура\n"
                "import { expect, it } from 'vitest';\n\n"
                f"it('вспомогательный {self.word()}', () => "
                "{ expect(1).toBe(2); });\n")

    def test_ac12_no_tested_criteria_journal_and_no_run(self):
        """Ни одного критерия, покрытого тестом, — прогона нет, в журнале «честный FAIL_TO_PASS: критериев с тестом нет».

        Сценарий: единственный критерий помечен `// AC-<n>: manual — …`,
        файл планки несёт только тест без метки. После `advance` в журнале
        есть запись «честный FAIL_TO_PASS: критериев с тестом нет», раннер
        компонента запущен только сухим сбором, отказа «переход отклонён:
        честный FAIL_TO_PASS» нет.

        Ловит мутацию: выключенный случай не распознан — гейт гонит планку
        на базе (второй запуск раннера) или молча проходит без записи
        журнала.
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,))
        self.write_plank(t, {f"m{self.word()}.test.jsx": self.manual_only_plank(n)})
        rows, output = self.advance(t)
        noted = [r for r in rows if NO_TESTED_NOTE in (r["action"] or "")
                 or NO_TESTED_NOTE in (r["detail"] or "")]
        self.assertTrue(noted, self.explain(rows, output))
        self.assertEqual(len(self.runs), 1, self.explain(rows, output))
        self.assertFalse(self.details(rows, F2P_ACTION),
                         self.explain(rows, output))

    def test_ac12_spec_changed_checked_first_when_no_tested_criteria(self):
        """Критериев с тестом нет, а SPEC.md изменён после одобрения, — отказ «SPEC.md изменён…», записи «критериев с тестом нет» нет.

        Сценарий: как в выключенном случае, но test_author дописал строку в
        SPEC.md после перехода гейта SPEC. Отказ «переход отклонён: SPEC
        изменён после гейта SPEC» с текстом «SPEC.md изменён после одобрения
        на гейте SPEC — верни его к версии <sha опоры>»; записи «честный
        FAIL_TO_PASS: критериев с тестом нет» нет, задача в `tests_writing`.

        Ловит мутацию: выключенный случай «критериев с тестом нет»
        возвращает раньше сверки опоры — задача в `in_dev` с изменённым
        SPEC.
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,))
        anchor = self.anchor_sha(t)
        self.edit_spec(t)
        self.write_plank(t, {f"m{self.word()}.test.jsx": self.manual_only_plank(n)})
        detail, rows, output = self.refusal(t, SPEC_CHANGED_ACTION)
        self.assertIn(SPEC_CHANGED_TEXT + anchor[:7], detail,
                      self.explain(rows, output))
        self.assertFalse([r for r in rows
                          if NO_TESTED_NOTE in (r["action"] or "")
                          or NO_TESTED_NOTE in (r["detail"] or "")],
                         self.explain(rows, output))

    def test_ac12_no_code_branch_runs_plank_in_dry_collect_copy(self):
        """Кодовой ветки ещё нет (`code_diff` — `None`) — гейт гонит одну планку в той же рабочей копии, что сухой сбор.

        Сценарий: задача без рабочей копии и кодовой ветки до `advance`
        (их заводит гейт рабочей копии перехода); тест критерия на базе
        «прошёл». Отказ «переход отклонён: честный FAIL_TO_PASS»; раннер
        запущен дважды (сухой сбор и гейт) в одном рабочем каталоге, и
        прогон гейта получил файл планки.

        Ловит мутацию: без `code_diff` гейт пропускается — задача в
        `in_dev`; прогон гейта идёт в другом каталоге (главная копия
        клона) — каталоги запусков различаются.
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,), ensure=False)
        name = f"c{self.word()}.test.jsx"
        self.write_plank(t, {name: self.jsx((n,))})
        self.vitest_case[n] = {"state": "pass", "error_name": None}
        _detail, rows, output = self.refusal(t, F2P_ACTION)
        self.assertGreaterEqual(len(self.runs), 2, self.explain(rows, output))
        self.assertEqual(self.runs[1]["cwd"], self.runs[0]["cwd"],
                         self.explain(rows, output))
        self.assertTrue(any(a.endswith(name) for a in self.runs[1]["argv"]),
                        self.explain(rows, output))

    def test_ac12_preparation_refusals_have_own_action(self):
        """Отказ выкладки, отсутствие и неразбор отчёта прогона гейта — «отказ подготовки: <причина>» своим действием, а не «теста нет в отчёте».

        Сценарий (подслучай — свежая задача, тест критерия на базе падает
        провалом проверки): (а) во время сухого сбора в каталог-родитель
        `plank_layout` рабочей копии кладётся отслеживаемый git файл —
        выкладка прогона гейта отказывает; (б) прогон гейта не создаёт
        отчёт; (в) отчёт прогона гейта не разобран. Отказ — действие
        «переход отклонён: честный FAIL_TO_PASS — отказ подготовки», деталь
        начинается причиной «отказ подготовки: …»; записи «переход
        отклонён: честный FAIL_TO_PASS» и находки «теста нет в отчёте» нет.

        Ловит мутацию: отказ выкладки или «неизвестно» отчёта читается как
        пустой список записей — находка «AC-n: теста нет в отчёте» общим
        отказом.
        """
        def tracked_in_layout(t):
            def hook(run):
                if run["index"] != 0:
                    return
                parent = t.wt / t.project.layout.rsplit("/", 1)[0]
                parent.mkdir(parents=True, exist_ok=True)
                keep = parent / f"keep{self.word()}.txt"
                keep.write_text("отслеживаемый\n", encoding="utf-8")
                self.git("-C", str(t.wt), "add", "-f", "--", str(keep))
                self.git("-C", str(t.wt), "commit", "-q", "-m", "файл в выкладке")
            self.on_run = hook

        def no_report(t):
            self.no_report_when = lambda run: run["index"] >= 1

        def broken_report(t):
            self.broken_report_when = lambda run: run["index"] >= 1

        for label, arrange in (("выкладка", tracked_in_layout),
                               ("отчёта нет", no_report),
                               ("отчёт не разобран", broken_report)):
            with self.subTest(case=label, seed=self.seed):
                self.on_run = self.no_report_when = None
                self.broken_report_when = None
                n = self.numbers(1)[0]
                project = self.vitest_project()
                t = self.new_task(project, (n,))
                self.write_plank(t, {f"q{self.word()}.test.jsx": self.jsx((n,))})
                arrange(t)
                detail, rows, output = self.refusal(t, PREPARE_ACTION)
                self.assertIn(PREPARE_TEXT, detail, self.explain(rows, output))
                self.assertNotIn(NO_RECORD, detail, self.explain(rows, output))
                self.assertFalse(self.details(rows, F2P_ACTION),
                                 self.explain(rows, output))

    def test_ac12_run_timeout_is_finding_of_common_refusal(self):
        """Таймаут прогона гейта — находка отказа «переход отклонён: честный FAIL_TO_PASS», а не отказ подготовки.

        Сценарий: компонент `pult-vitest`; второй запуск раннера (прогон
        гейта после сухого сбора) бросает `TimeoutExpired` на первом
        ожидании. Есть запись «переход отклонён: честный FAIL_TO_PASS» с
        находкой таймаута («таймаут»/«превысил»), записи «отказ
        подготовки» нет.

        Ловит мутацию: `timed_out` прогона пишется отказом подготовки.
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,))
        self.write_plank(t, {f"t{self.word()}.test.jsx": self.jsx((n,))})
        self.timeout_when = lambda run: run["index"] >= 1
        detail, rows, output = self.refusal(t, F2P_ACTION)
        self.assertRegex(detail, r"таймаут|превысил", self.explain(rows, output))
        self.assertFalse(self.details(rows, PREPARE_ACTION),
                         self.explain(rows, output))


# --------------------------------------------------------------- AC-13

class Ac13PlaceTest(FailToPassSandbox):

    def layout_root(self, t) -> Path:
        return t.wt / t.project.layout.replace("<id>", t.id)

    def assert_plank_dropped(self, t, rows, output) -> None:
        self.assertFalse(self.layout_root(t).exists(), self.explain(rows, output))
        self.assertFalse((t.wt / TASKS_DIR / t.id).exists(),
                         self.explain(rows, output))

    def test_ac13_after_dry_collect_before_manifest_and_dropped(self):
        """Гейт — после сухого сбора и до перечня сумм; планка убрана из рабочей копии кода при любом исходе.

        Сценарий (подслучай — свежая задача): (а) отчёт любого запуска без
        записей — сухой сбор отказывает «планка не собирается», раннер
        запущен один раз (гейта не было); (б) тест критерия «прошёл» —
        отказ гейта, записи «перечень долгоживущих тестов записан» нет и в
        ссылке документов нет перечня сумм; (в) провал проверки — переход
        в `in_dev`, а в момент прогона гейта записи о перечне в журнале ещё
        не было. Во всех случаях после `advance` ни выкладки
        `plank_layout`, ни каталога задачи в рабочей копии нет.

        Ловит мутацию: гейт поставлен до сухого сбора — в (а) раннер запущен
        дважды; гейт поставлен после перечня — в (б) перечень записан, в
        (в) запись о перечне уже есть в момент прогона гейта; гейт вне
        `try/finally` уборки — выкладка остаётся после отказа.
        """
        def manifest_rows(t) -> list:
            return [r for r in store.task_steps(self.conn, t.id)
                    if r["action"] == MANIFEST_NOTE]

        with self.subTest(case="сухой сбор", seed=self.seed):
            n = self.numbers(1)[0]
            project = self.vitest_project()
            t = self.new_task(project, (n,))
            name = f"d{self.word()}.test.jsx"
            self.write_plank(t, {name: self.jsx((n,))})
            self.drop_files.add(name)
            _detail, rows, output = self.refusal(t, DRY_COLLECT_ACTION)
            self.assertEqual(len(self.runs), 1, self.explain(rows, output))
            self.assert_plank_dropped(t, rows, output)
            self.drop_files.clear()

        with self.subTest(case="отказ гейта", seed=self.seed):
            n = self.numbers(1)[0]
            project = self.vitest_project()
            t = self.new_task(project, (n,))
            self.write_plank(t, {f"g{self.word()}.test.jsx": self.jsx((n,))})
            self.vitest_case[n] = {"state": "pass", "error_name": None}
            _detail, rows, output = self.refusal(t, F2P_ACTION)
            self.assertFalse(manifest_rows(t), self.explain(rows, output))
            tree = self.git("-C", str(self.clones[t.target]), "ls-tree", "-r",
                            "--name-only", "refs/artifacts/" + t.id)
            self.assertNotIn("long_lived.sha256.txt", tree,
                             self.explain(rows, output))
            self.assert_plank_dropped(t, rows, output)
            self.vitest_case.clear()

        with self.subTest(case="гейт пройден", seed=self.seed):
            n = self.numbers(1)[0]
            project = self.vitest_project()
            t = self.new_task(project, (n,))
            self.write_plank(t, {f"p{self.word()}.test.jsx": self.jsx((n,))})
            seen = []
            self.on_run = lambda run: seen.append(
                (run["index"], len(manifest_rows(t)),
                 self.layout_root(t).is_dir()))
            rows, output = self.passes(t)
            self.on_run = None
            self.assertTrue(manifest_rows(t), self.explain(rows, output))
            gate = [s for s in seen if s[0] >= 1]
            self.assertTrue(gate, self.explain(rows, output))
            self.assertEqual(gate[0][1], 0, self.explain(rows, output))
            self.assertTrue(gate[0][2], self.explain(rows, output))
            self.assert_plank_dropped(t, rows, output)


# --------------------------------------------------------------- AC-14

class Ac14GreenFromBirthTest(FailToPassSandbox):

    def green_head(self) -> str:
        return f"// {GREEN_MARK} фикстура {self.word()} держит поведение.\n"

    def test_ac14_green_marker_file_of_listed_criteria_passes(self):
        """Файл с маркером «Зелёный с рождения:», все тесты `AC-<n>` которого — из перечня SPEC и прошли на базе, — гейт пройден.

        Сценарий: SPEC (опорная версия) с двумя критериями и разделом
        «## Зелёный с рождения» с первым; файл A с маркером «Зелёный с
        рождения:» и тестом первого критерия (`pass`), файл B с маркером
        красноты и тестом второго (`AssertionError`). `advance` — `in_dev`.

        Ловит мутацию: маркер не учитывается — прошедший тест файла A
        объявлен находкой «прошёл»; перечень читается с головы ссылки, а
        не из опоры, — здесь они равны, и мутация видна в AC-28.
        """
        g, r = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (g, r), green=(g,))
        self.write_plank(t, {
            f"a{self.word()}.test.jsx": self.jsx((g,), head=self.green_head()),
            f"b{self.word()}.test.jsx": self.jsx((r,))})
        self.vitest_case[g] = {"state": "pass", "error_name": None}
        rows, output = self.passes(t)
        self.assertFalse(self.details(rows, F2P_ACTION), self.explain(rows, output))

    def test_ac14_green_marker_refusals(self):
        """Маркер «Зелёный с рождения:» у файла с тестом критерия вне перечня, с тестом перечня, не прошедшим на базе, или отсутствующим в отчёте, — отказ гейта.

        Сценарий (подслучай — свежая задача; перечень SPEC — первый
        критерий): (а) файл с маркером несёт тесты первого (`pass`) и
        второго (`pass`) критериев; (б) файл с маркером — тест первого
        критерия упал с `AssertionError`; (в) тест первого критерия файла с
        маркером отсутствует в отчёте. Отказ «переход отклонён: честный
        FAIL_TO_PASS», задача в `tests_writing`.

        Ловит мутацию: маркер допускается по любому критерию файла, а не по
        всем — (а) проходит; для файла с маркером провал проверки
        засчитывается как норма — (б) проходит; отсутствие записи у файла с
        маркером не проверяется — (в) проходит.
        """
        cases = (("критерий вне перечня", "extra"),
                 ("не прошёл", "failed"), ("нет в отчёте", "missing"))
        for label, kind in cases:
            with self.subTest(case=label, seed=self.seed):
                self.vitest_case.clear()
                self.drop_numbers.clear()
                g, r = self.numbers(2)
                project = self.vitest_project()
                t = self.new_task(project, (g, r), green=(g,))
                if kind == "extra":
                    files = {f"a{self.word()}.test.jsx":
                             self.jsx((g, r), head=self.green_head())}
                    self.vitest_case[g] = {"state": "pass", "error_name": None}
                    self.vitest_case[r] = {"state": "pass", "error_name": None}
                else:
                    files = {f"a{self.word()}.test.jsx":
                             self.jsx((g,), head=self.green_head()),
                             f"b{self.word()}.test.jsx": self.jsx((r,))}
                    if kind == "missing":
                        self.drop_numbers.add(g)
                self.write_plank(t, files)
                self.refusal(t, F2P_ACTION)


# --------------------------------------------------------------- AC-28

class Ac28SpecAnchorTest(FailToPassSandbox):

    def add_green_section(self, t, n: int) -> None:
        self.edit_spec(t, green=n)

    def green_plank(self, t, g: int, r: int) -> None:
        self.write_plank(t, {
            f"a{self.word()}.test.jsx": self.jsx(
                (g,), head=f"// {GREEN_MARK} фикстура {self.word()}.\n"),
            f"b{self.word()}.test.jsx": self.jsx((r,))})
        self.vitest_case[g] = {"state": "pass", "error_name": None}

    def test_ac28_role_added_green_list_after_gate_refused(self):
        """test_author дописал «## Зелёный с рождения» в SPEC.md после гейта SPEC — отказ «SPEC.md изменён после одобрения на гейте SPEC — верни его к версии <sha>», тест под маркером не принят.

        Сценарий: опора — SPEC без раздела; test_author дописывает раздел
        с первым критерием и кладёт файл с маркером «Зелёный с рождения:»
        и прошедшим тестом первого критерия. Отказ — действие «переход
        отклонён: SPEC изменён после гейта SPEC», текст с sha опоры —
        `артефакты=` первой фиксации после перехода гейта SPEC; задача в
        `tests_writing`.

        Ловит мутацию: перечень читается с головы ссылки документов — тест
        под маркером принят, задача в `in_dev`; сверка головы с опорой не
        делается.
        """
        g, r = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (g, r))
        anchor = self.anchor_sha(t)
        self.add_green_section(t, g)
        self.green_plank(t, g, r)
        detail, rows, output = self.refusal(t, SPEC_CHANGED_ACTION)
        self.assertIn(SPEC_CHANGED_TEXT + anchor[:7], detail,
                      self.explain(rows, output))

    def test_ac28_operator_edit_on_gate_is_anchor(self):
        """SPEC, поправленный Оператором на гейте SPEC до перехода, — опорная версия: выход этим отказом не отклоняется.

        Сценарий: в `spec_gate` SPEC.md правится (добавлен раздел «## Зелёный
        с рождения» с первым критерием) и уходит в ссылку документов, затем
        переход гейта SPEC; файл с маркером и прошедшим тестом первого
        критерия. `advance` — `in_dev`, записи «SPEC изменён после гейта
        SPEC» нет.

        Ловит мутацию: опорой берётся первая версия SPEC в ссылке (от
        аналитика), а не зафиксированная на переходе, — отказ «SPEC
        изменён».
        """
        g, r = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (g, r), approve=False)
        store.update_task(self.conn, t.id, state="spec_gate")
        self.add_green_section(t, g)
        checkpoint.commit_step_artifacts(self.conn, t.id, "operator")
        store.set_state(self.conn, t.id, "tests_writing", "operator",
                        expected_state="spec_gate", detail=APPROVED_DETAIL)
        self.green_plank(t, g, r)
        rows, output = self.passes(t)
        self.assertFalse(self.details(rows, SPEC_CHANGED_ACTION),
                         self.explain(rows, output))

    def test_ac28_return_from_escalation_keeps_anchor(self):
        """Возврат в `tests_writing` из эскалации опору не меняет: правка SPEC ролью до эскалации — отказ «SPEC изменён».

        Сценарий: опора — SPEC без раздела; test_author дописывает раздел
        «## Зелёный с рождения», правка уходит в ссылку документов; задача
        уходит в `escalated` и возвращается в `tests_writing` переходом с
        иной деталью (его фиксация — уже с правкой). Отказ «SPEC изменён
        после гейта SPEC» с sha первой опоры.

        Ловит мутацию: опорой берётся фиксация последнего входа в
        `tests_writing` любой деталью — правка узаконена, задача в
        `in_dev`.
        """
        g, r = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (g, r))
        anchor = self.anchor_sha(t)
        self.add_green_section(t, g)
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        store.set_state(self.conn, t.id, "escalated", "fsm",
                        expected_state="tests_writing",
                        detail=f"эскалация {self.word()}")
        store.set_state(self.conn, t.id, "tests_writing", "operator",
                        expected_state="escalated",
                        detail=f"ответ Оператора {self.word()}")
        self.green_plank(t, g, r)
        detail, rows, output = self.refusal(t, SPEC_CHANGED_ACTION)
        self.assertIn(SPEC_CHANGED_TEXT + anchor[:7], detail,
                      self.explain(rows, output))


# ----------------------------------------------------- AC-30, AC-31, AC-32

class AnchorNotFoundTest(FailToPassSandbox):

    def assert_anchor_refusal(self, t, **kwargs) -> None:
        detail, rows, output = self.refusal(t, ANCHOR_ACTION, **kwargs)
        self.assertIn(ANCHOR_TEXT, detail, self.explain(rows, output))
        self.assertEqual(len(self.runs), 1, self.explain(rows, output))
        self.assertFalse(self.details(rows, F2P_ACTION), self.explain(rows, output))

    def plain_task(self):
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,), approve=False)
        self.write_plank(t, {f"o{self.word()}.test.jsx": self.jsx((n,))})
        return t

    def transition(self, t) -> None:
        store.journal(self.conn, t.id, "operator", "state -> tests_writing",
                      APPROVED_DETAIL)

    def fixation(self, t, artifacts: str) -> None:
        store.journal(self.conn, t.id, "fsm", "sha зафиксирован",
                      f"target={t.target}, sha={artifacts}, чисто=True, "
                      f"код=—, артефакты={artifacts}")

    def test_ac30_anchor_not_found_cases(self):
        """Опора SPEC не найдена — отказ «опора SPEC для перечня «Зелёный с рождения» не найдена: <причина>» своим действием, без прогона.

        Сценарий (подслучай — свежая задача, тест критерия падает
        провалом проверки, иначе выход прошёл бы): (а) записи «state ->
        tests_writing» с деталью гейта SPEC нет вовсе; (б) запись перехода
        есть, после неё нет «sha зафиксирован»; (в) первая «sha
        зафиксирован» после перехода — фиксация чекпоинта, идущая после
        «agent run started»; (г) между переходом и фиксацией — запись с
        деталью «переход в tests_writing без паспорта и фиксации». Отказ —
        действие «переход отклонён: честный FAIL_TO_PASS — опора SPEC не
        найдена», раннер запущен только сухим сбором.

        Ловит мутацию: опора не найдена — проверка пропускается и гейт
        гонит планку (второй запуск, задача в `in_dev`); опорой становится
        фиксация чекпоинта шага роли; запись «без паспорта и фиксации» не
        учитывается.
        """
        def none(t):
            return {}

        def no_fixation(t):
            return {"before_advance": lambda: self.transition(t)}

        def checkpoint_fixation(t):
            self.transition(t)
            return {}

        def drift(t):
            self.transition(t)
            store.journal(self.conn, t.id, "fsm",
                          "фиксация не обновлена: голова ссылки документов "
                          "не прочитана",
                          "переход в tests_writing без паспорта и фиксации")
            store.record_fixation(self.conn, t.id)
            return {}

        for label, arrange in (("нет перехода", none),
                               ("нет фиксации", no_fixation),
                               ("фиксация чекпоинта", checkpoint_fixation),
                               ("без паспорта и фиксации", drift)):
            with self.subTest(case=label, seed=self.seed):
                t = self.plain_task()
                self.assert_anchor_refusal(t, **arrange(t))

    def test_ac30_unfixed_transition_then_role_spec_edit(self):
        """Переход гейта SPEC без фиксации, затем test_author правит SPEC.md и пульт фиксирует чекпоинт — отказ «опора не найдена», тест под маркером не принят.

        Сценарий: запись перехода с деталью гейта SPEC и запись «переход в
        tests_writing без паспорта и фиксации»; шаг test_author дописывает
        «## Зелёный с рождения» с критерием и кладёт файл с маркером
        «Зелёный с рождения:» и прошедшим тестом; чекпоинт шага фиксирует
        голову. Отказ «переход отклонён: честный FAIL_TO_PASS — опора SPEC
        не найдена», задача в `tests_writing`.

        Ловит мутацию: опорой становится фиксация чекпоинта роли — перечень
        с правкой роли принят, задача в `in_dev`.
        """
        g, r = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (g, r), approve=False)
        self.transition(t)
        store.journal(self.conn, t.id, "fsm",
                      "фиксация не обновлена: голова ссылки документов не "
                      "прочитана",
                      "переход в tests_writing без паспорта и фиксации")
        self.edit_spec(t, green=g)
        self.write_plank(t, {
            f"a{self.word()}.test.jsx": self.jsx(
                (g,), head=f"// {GREEN_MARK} фикстура {self.word()}.\n"),
            f"b{self.word()}.test.jsx": self.jsx((r,))})
        self.vitest_case[g] = {"state": "pass", "error_name": None}
        self.assert_anchor_refusal(t)

    def test_ac31_anchor_without_artifacts_sha(self):
        """В опорной записи «sha зафиксирован» `артефакты=—` — отказ «опора SPEC … не найдена: <причина>» тем же действием, без прогона.

        Сценарий: запись перехода гейта SPEC и сразу за ней (до «agent run
        started») запись «sha зафиксирован» с `артефакты=—`. Отказ
        «переход отклонён: честный FAIL_TO_PASS — опора SPEC не найдена».

        Ловит мутацию: `—` читается как «опоры нет — проверку пропустить» —
        гейт гонит планку, задача в `in_dev`.
        """
        t = self.plain_task()
        self.transition(t)
        self.fixation(t, "—")
        self.assert_anchor_refusal(t)

    def test_ac32_spec_unread_in_anchor_commit(self):
        """SPEC.md в опорном коммите не прочитан (файла нет в коммите или git не ответил) — отказ «опора SPEC … не найдена: <причина>», без прогона.

        Сценарий (подслучай — свежая задача): опорная запись несёт
        `артефакты=` (а) коммита клона с пустым деревом — SPEC.md в нём
        нет; (б) несуществующего sha — git не отвечает. Отказ «переход
        отклонён: честный FAIL_TO_PASS — опора SPEC не найдена».

        Ловит мутацию: непрочитанный SPEC опоры читается как пустой перечень
        — проверка идёт дальше, задача в `in_dev`.
        """
        for label in ("нет SPEC.md", "git не ответил"):
            with self.subTest(case=label, seed=self.seed):
                t = self.plain_task()
                clone = str(self.clones[t.target])
                if label == "нет SPEC.md":
                    sha = self.git("-C", clone, "commit-tree", EMPTY_TREE, "-m",
                                   f"пусто {self.word()}").strip()
                else:
                    sha = "".join(self.rng.choice("0123456789abcdef")
                                  for _ in range(40))
                self.transition(t)
                self.fixation(t, sha)
                self.assert_anchor_refusal(t)


# --------------------------------------------------------------- AC-15

BRANCH_ACTION = "переход отклонён: приёмочные тесты — тест критерия не в отчёте"
RED_ACTION = "переход отклонён: приёмочные тесты"
PASSED_NOTE = "приёмочные тесты пройдены"


class Ac15BranchTest(FailToPassSandbox):

    def in_dev_task(self):
        """Задача `pult-vitest` в `in_dev`: планка с тестами двух
        критериев честно прошла выход из `tests_writing`."""
        self.branch_phase(base=True)
        a, b = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (a, b))
        self.write_plank(t, {f"w{self.word()}.test.jsx": self.jsx((a, b))})
        self.passes(t)
        self.branch_phase()
        return t, a, b

    def test_ac15_green_branch_run_without_criterion_record_refused(self):
        """Зелёный прогон ветки без записи теста покрытого критерия либо с записью не `passed` — отказ «… тест критерия не в отчёте» с деталью «AC-n — теста нет в отчёте прогона ветки».

        Сценарий (подслучай — свежая задача в `in_dev`): прогон приёмки
        ветки (а) не несёт записи теста второго критерия; (б) несёт её с
        исходом `skip` (прогон по-прежнему зелёный). Отказ — действие
        «переход отклонён: приёмочные тесты — тест критерия не в отчёте»;
        в (а) деталь несёт «AC-<второй> — теста нет в отчёте прогона ветки»,
        в (б) деталь называет второй критерий; задача в `in_dev`, записи
        «приёмочные тесты пройдены» нет.

        Ловит мутацию: проверка ветки только по вердикту прогона —
        зелёный прогон без теста критерия проходит в `verifying`; запись
        `skipped` засчитана как наличие теста.
        """
        for label in ("нет записи", "пропуск"):
            with self.subTest(case=label, seed=self.seed):
                t, a, b = self.in_dev_task()
                if label == "нет записи":
                    self.drop_numbers.add(b)
                else:
                    self.vitest_case[b] = {"state": "skip", "mode": "skip"}
                rows, output = self.developer_advance(t)
                found = self.details(rows, BRANCH_ACTION)
                self.assertTrue(found, self.explain(rows, output))
                if label == "нет записи":
                    self.assertIn(f"AC-{b} — теста нет в отчёте прогона ветки",
                                  found[-1], self.explain(rows, output))
                else:
                    self.assertIn(f"AC-{b}", found[-1], self.explain(rows, output))
                self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
                self.assertFalse(self.details(rows, PASSED_NOTE),
                                 self.explain(rows, output))

    def test_ac15_repeated_record_after_green_run_refused(self):
        """Запись критерия с повтором при зелёном прогоне ветки (защитная ветка) — тот же отказ «… тест критерия не в отчёте».

        Сценарий: общий вердикт прогона подменён зелёным (`outcome.verdict`
        публичного модуля разборщиков) — так достижим зелёный прогон, где
        тест второго критерия прошёл с `retry_count: 1`. Отказ — действие
        «переход отклонён: приёмочные тесты — тест критерия не в отчёте»,
        задача в `in_dev`.

        Ловит мутацию: проверка ветки смотрит только на исход `passed`,
        не на повторы, — запись с повтором принята, задача в `verifying`.
        """
        t, a, b = self.in_dev_task()
        self.vitest_case[b] = {"retry_count": 1}
        with mock.patch.object(outcome, "verdict",
                               lambda records, code, reason="": (outcome.GREEN, "")):
            rows, output = self.developer_advance(t)
        self.assertTrue(self.details(rows, BRANCH_ACTION), self.explain(rows, output))
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))

    def test_ac15_check_after_green_run_only(self):
        """Проверка наличия тестов критериев — после зелёного прогона: красный прогон — прежний отказ, всё на месте — `verifying`.

        Сценарий (подслучай — свежая задача в `in_dev`): (а) тест первого
        критерия упал (`AssertionError`), записи второго нет — отказ
        «переход отклонён: приёмочные тесты» с «acceptance_tests красные:»,
        записи «… тест критерия не в отчёте» нет; (б) оба теста прошли —
        «приёмочные тесты пройдены», задача в `verifying`.

        Ловит мутацию: проверка наличия поставлена до вердикта прогона —
        в (а) отказ «тест критерия не в отчёте» вместо красного прогона;
        проверка требует записи по критериям без метки — в (б) отказ.
        """
        with self.subTest(case="красный", seed=self.seed):
            t, a, b = self.in_dev_task()
            self.vitest_case[a] = {"state": "fail", "error_name": "AssertionError"}
            self.drop_numbers.add(b)
            rows, output = self.developer_advance(t)
            red = self.details(rows, RED_ACTION)
            self.assertTrue(red and "acceptance_tests красные:" in red[-1],
                            self.explain(rows, output))
            self.assertFalse(self.details(rows, BRANCH_ACTION),
                             self.explain(rows, output))
        with self.subTest(case="зелёный", seed=self.seed):
            t, a, b = self.in_dev_task()
            rows, output = self.developer_advance(t)
            self.assertTrue(self.details(rows, PASSED_NOTE),
                            self.explain(rows, output))
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))


# --------------------------------------------------------------- AC-19

class Ac19RunRecordsTest(FailToPassSandbox):

    @staticmethod
    def run_states(records: list) -> list:
        """(refusal, timed_out, state) элементов `records`, несущих
        состояние прогона (не `CaseResult`): атрибуты либо ключи."""
        found = []
        for item in records:
            if isinstance(item, outcome.CaseResult):
                continue
            get = (item.get if isinstance(item, dict)
                   else lambda key, obj=item: getattr(obj, key, None))
            if get("state") is not None or get("refusal") is not None:
                found.append((get("refusal") or "", bool(get("timed_out")),
                              get("state") or ""))
        return found

    def direct_place(self, files: dict):
        """(профиль, каталог задачи с планкой вне рабочей копии, рабочая
        копия) учебного проекта `pult-vitest`."""
        project = self.vitest_project()
        n = self.numbers(1)[0]
        t = self.new_task(project, (n,), approve=False)
        tdir = Path(tempfile.mkdtemp(prefix="artel-plank-")) / t.id
        self.addCleanup(shutil.rmtree, tdir.parent, True)
        (tdir / PLANK_DIR).mkdir(parents=True)
        for name, text in files(n).items():
            (tdir / PLANK_DIR / name).write_text(text, encoding="utf-8")
        profile = project_profile.decide(project.name).profile
        self.assertIsNotNone(profile, self.note("профиль не построен"))
        return profile, tdir, t

    def test_ac19_records_carry_run_state_and_cases(self):
        """`acceptance.run(…, records=…)` у профиля с отчётом кладёт состояние прогона и записи `CaseResult`; без `records` — прежний исход.

        Сценарий: файл планки с двумя тестами критериев (`AssertionError`
        и `pass`), прямой вызов `run` с профилем компонента и пустым
        списком `records`. После вызова в списке — записи `CaseResult` с
        идентификаторами обоих тестов выкладки и состояние прогона: отказа
        нет, таймаута нет, `state` — «красный». Тот же вызов без `records`
        отдаёт тот же кортеж (зелёно, хвост вывода). Ни один запуск
        раннера в прямых вызовах не несёт `--continue-on-collection-errors`.

        Ловит мутацию: `records` не заполняется у профиля с отчётом —
        список пуст; в него кладётся только сводка без записей или записи
        без состояния; ключ `--continue-on-collection-errors` добавлен в
        `run` безусловно.
        """
        name = f"z{self.word()}.test.jsx"

        def files(n):
            return {name: self.jsx((n, n + 100))}

        profile, tdir, t = self.direct_place(files)
        records: list = []
        with_records = acceptance.run(tdir, cwd=t.wt, command=profile,
                                      records=records)
        plain = acceptance.run(tdir, cwd=t.wt, command=profile)
        cases = [r for r in records if isinstance(r, outcome.CaseResult)]
        rel = self.layout_rel(t, name)
        self.assertEqual(len(cases), 2, self.note(str(records)))
        self.assertTrue(all(c.id.startswith(f"{t.project.comp}:{rel}::")
                            for c in cases), self.note(str(cases)))
        states = self.run_states(records)
        self.assertEqual(states, [("", False, outcome.RED)], self.note(str(records)))
        self.assertEqual(with_records[0], plain[0], self.note(str((with_records, plain))))
        self.assertEqual(with_records[1], plain[1], self.note(str((with_records, plain))))
        self.assertFalse(any(CONTINUE_FLAG in r["argv"] for r in self.runs),
                         self.note(str([r["argv"] for r in self.runs])))

    def test_ac19_early_exits_carry_refusal(self):
        """На ранних выходах `run` у профиля с отчётом `records` несёт отказ плана планки и отказ выкладки с причиной.

        Сценарий (подслучай): профиль компонента без `plank_layout`
        (отказ плана «нет plank_layout»); профиль с `plank_layout`, чей
        родитель `<id>` не скрытый каталог (отказ выкладки). Вызов `run`
        с `records` отдаёт «не зелёно», раннер не запускался, в `records` —
        состояние с непустым отказом, совпадающим с причиной в хвосте.

        Ловит мутацию: ранний выход возвращается до записи в `records` —
        список пуст, гейт выдал бы «теста нет в отчёте».
        """
        cases = (("план планки", ""),
                 ("выкладка", f"frontend/src/pv{self.word(5)}/<id>"))
        for label, layout in cases:
            with self.subTest(case=label, seed=self.seed):
                def files(n):
                    return {f"y{self.word()}.test.jsx": self.jsx((n,))}

                profile, tdir, t = self.direct_place(files)
                profile = dataclasses.replace(profile, plank_layout=layout)
                records: list = []
                self.runs.clear()
                green, tail = acceptance.run(tdir, cwd=t.wt, command=profile,
                                             records=records)
                self.assertFalse(green, self.note(tail))
                self.assertFalse(self.runs, self.note(tail))
                refusals = [s[0] for s in self.run_states(records) if s[0]]
                self.assertTrue(refusals, self.note(f"{records}\n{tail}"))
                self.assertIn(refusals[0], tail, self.note(f"{records}\n{tail}"))

    def test_ac19_continue_flag_only_pytest_gate_run(self):
        """`--continue-on-collection-errors` — только у команды pytest и только в прогоне гейта честного `FAIL_TO_PASS`.

        Сценарий (подслучай): (а) компонент `junit-xml` на pytest — у
        запуска прогона гейта (второго, после сухого сбора) ключ есть, у
        сухого сбора нет; (б) компонент `pult-vitest` — ни один запуск
        ключа не несёт.

        Ловит мутацию: ключ добавлен в общий `run` либо в сухой сбор —
        первый запуск (сухой сбор) несёт его; ключ добавлен к любой
        команде — его несёт Vitest.
        """
        with self.subTest(case="pytest", seed=self.seed):
            n = self.numbers(1)[0]
            project = self.junit_project()
            t = self.new_task(project, (n,))
            self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
            rows, output = self.passes(t)
            self.assertGreaterEqual(len(self.runs), 2, self.explain(rows, output))
            self.assertNotIn(CONTINUE_FLAG, self.runs[0]["argv"],
                             self.explain(rows, output))
            self.assertIn(CONTINUE_FLAG, self.runs[1]["argv"],
                          self.explain(rows, output))
        with self.subTest(case="vitest", seed=self.seed):
            n = self.numbers(1)[0]
            project = self.vitest_project()
            t = self.new_task(project, (n,))
            self.write_plank(t, {f"v{self.word()}.test.jsx": self.jsx((n,))})
            rows, output = self.passes(t)
            self.assertFalse(any(CONTINUE_FLAG in r["argv"] for r in self.runs),
                             self.explain(rows, output))


# --------------------------------------------------------------- AC-26

class Ac26OutOfBoundsTest(FailToPassSandbox):

    def assert_no_gate(self, rows, output) -> None:
        mentions = [r for r in rows if "честный FAIL_TO_PASS" in (r["action"] or "")
                    or "честный FAIL_TO_PASS" in (r["detail"] or "")]
        self.assertFalse(mentions, self.explain(rows, output))
        self.assertFalse(any(CONTINUE_FLAG in r["argv"] for r in self.runs),
                         self.explain(rows, output))

    def test_ac26_own_test_profile_no_gate_and_no_branch_check(self):
        """Запись `test_profile` с `runner: pytest-own` и `report: junit-xml`: гейта нет, прогона на базе нет, проверки наличия тестов на ветке нет.

        Сценарий: задача без опоры SPEC (заведена прямо в `tests_writing`),
        тест критерия на базе проходит. Выход из `tests_writing` — `in_dev`,
        раннер запущен один раз (сухой сбор), ни одной записи журнала с
        «честный FAIL_TO_PASS», ни одного запуска с
        `--continue-on-collection-errors`. Затем прогон ветки зелёный, но
        без записи теста критерия — «приёмочные тесты пройдены», задача в
        `verifying`, отказа «… тест критерия не в отчёте» нет.

        Ловит мутацию: граница по `reported(profile)` без
        `from_components` — у `pytest-own` гейт создан (отказ опоры SPEC или
        «прошёл»); проверка ветки включена у любого профиля с отчётом.
        """
        n = self.numbers(1)[0]
        project = self.own_profile_project()
        t = self.new_task(project, (n,), approve=False)
        self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
        self.junit_case[n] = ("passed", "")
        rows, output = self.passes(t)
        self.assert_no_gate(rows, output)
        self.assertEqual(len(self.runs), 1, self.explain(rows, output))
        self.branch_phase()
        self.drop_numbers.add(n)
        self.junit_default = ("passed", "")
        rows, output = self.developer_advance(t)
        self.assertFalse(self.details(rows, BRANCH_ACTION), self.explain(rows, output))
        self.assertTrue(self.details(rows, PASSED_NOTE), self.explain(rows, output))

    def test_ac26_artel_no_gate_and_no_base_run(self):
        """Артель: гейт не создан, прогона на базе нет, записей журнала гейта нет.

        Сценарий: задача артели без опоры SPEC, планка `test_*.py` с тестом
        критерия, который на базе прошёл бы. Выход из `tests_writing` —
        `in_dev`; `acceptance.run` (прогон по отчёту) за переход не звался;
        записей журнала с «честный FAIL_TO_PASS» нет.

        Ловит мутацию: гейт создаётся у любого профиля — у артели переход
        гонит планку `acceptance.run` и отказывает опорой SPEC.
        """
        project = SimpleNamespace(name=config.DEFAULT_TARGET,
                                  comp=project_profile.DEFAULT_COMPONENT,
                                  layout="", kind="artel", code="app.py")
        n = self.numbers(1)[0]
        t = self.new_task(project, (n,), approve=False)
        text = self.py_plank((n,)).replace("self.assertEqual(2 + 2, 5)",
                                           "self.assertEqual(2 + 2, 4)")
        self.write_plank(t, {f"test_{self.word()}.py": text})
        with mock.patch.object(acceptance, "run", wraps=acceptance.run) as spy:
            rows, output = self.passes(t)
        self.assertFalse(spy.called, self.explain(rows, output))
        self.assert_no_gate(rows, output)


# ------------------------------------------------- AC-16, AC-17, AC-18, AC-21

BANNED_TAIL = " — запрещено в тексте планки"
JSX_HEAD = ("// Группа: разовый\n// Красен до реализации: фикстура {word}.\n"
            "import {{ describe, expect, it, suite, test, vi }} from 'vitest';\n")
TEST_GROUPS_ACTION = "переход отклонён: группы приёмочных тестов"
LONG_LIVED_ACTION = "переход отклонён: долгоживущие файлы tests/"


class BansSandbox(FailToPassSandbox):

    def run_preflight(self, t) -> str:
        from orchestrator import preflight
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                preflight.cmd_preflight(t.id)
            except SystemExit as exc:
                out.write(f"\nSystemExit: {exc.code}")
        return out.getvalue()

    def plank_with(self, line: str, extra: str = "") -> tuple:
        """(текст файла планки, номер строки `line`): шапка, `line`,
        затем `extra`."""
        head = JSX_HEAD.format(word=self.word())
        number = len(head.splitlines()) + 1
        return head + line + "\n" + extra, number

    def banned_line(self, rel: str, number: int) -> re.Pattern:
        return re.compile(re.escape(rel) + rf":{number}: .+{re.escape(BANNED_TAIL)}")

    def ban_lines(self, n: int, m: int) -> list:
        """(случай, строка с запрещённой конструкцией, строка покрытия)."""
        ok = f"it('AC-{n}: опора {self.word()}', () => {{ expect(1).toBe(2); }});"
        body = "() => { expect(1).toBe(2); }"
        return [
            ("it.only", f"it.only('AC-{n}: x', {body});", ""),
            ("test.fails", f"test.fails('AC-{n}: x', {body});", ""),
            (".skipIf", f"it.skipIf(process.env.CI)('AC-{n}: x', {body});", ""),
            (".runIf", f"it.runIf(process.env.CI)('AC-{n}: x', {body});", ""),
            ("retry", f"it('AC-{n}: x', {{ retry: 2 }}, {body});", ""),
            ("timeout", f"it('AC-{n}: x', {{ timeout: 5000 }}, {body});", ""),
            ("число it", f"it('AC-{n}: x', {body}, 5000);", ""),
            ("число describe",
             f"describe('группа', () => {{ it('AC-{n}: x', {body}); }}, 1000);",
             ""),
            ("retry suite",
             f"suite('группа', {{ retry: 3 }}, () => {{ it('AC-{n}: x', {body}); }});",
             ""),
            ("each вторые скобки",
             f"it.each([[1], [2]])('AC-{n}: x %s', (a) => {{ expect(a).toBe(0); }}, 3000);",
             ""),
            ("vi.setConfig", "vi.setConfig({ testTimeout: 10 });", ok + "\n"),
            ("две метки", f"it('AC-{n}: AC-{m}: x', {body});", ""),
            ("describe с меткой",
             f"describe('AC-{n}: группа', () => {{ it('AC-{n}: x', {body}); }});",
             ""),
        ]


class Ac16BansTest(BansSandbox):

    def test_ac16_banned_constructs_refused_with_file_and_line(self):
        """Запрещённые конструкции в тексте файла с меткой — отказ «<файл>:<строка>: <что найдено> — запрещено в тексте планки».

        Сценарий: черновик планки `pult-vitest` с одним файлом, в нём на
        известной строке ровно одна конструкция (подслучай на каждую):
        `it.only`, `test.fails`, `.skipIf`, `.runIf`, `{ retry: 2 }`,
        `{ timeout: … }`, числовой литерал в аргументах первого уровня `it`
        и `describe`, `{ retry }` у `suite`, число во второй паре скобок
        `it.each(t)(…)`, `vi.setConfig`, две метки `AC-<n>: ` в одном имени,
        литерал `describe` с меткой в начале. Вывод предпроверки несёт
        строку «<имя файла>:<номер строки>: … — запрещено в тексте планки».

        Ловит мутацию: аргументы `it.each(t)(…)` берутся из первой пары
        скобок — число во второй не найдено; цепочки `it.only`/`test.fails`
        не распознаются; литерал `describe` не проверяется на метку; номер
        строки считается от нуля — строка в отказе на единицу меньше.
        """
        n, m = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (n, m), approve=False)
        for label, line, extra in self.ban_lines(n, m):
            with self.subTest(case=label, seed=self.seed):
                name = f"b{self.word()}.test.jsx"
                text, number = self.plank_with(
                    line, extra + f"it('AC-{m}: ещё', () => {{ expect(1).toBe(2); }});\n")
                for old in list(t.plank.glob("*")):
                    old.unlink()
                self.write_plank(t, {name: text})
                output = self.run_preflight(t)
                self.assertRegex(output, self.banned_line(name, number),
                                 self.note(f"{label}:\n{text}\n{output}"))


class Ac17NotBannedTest(BansSandbox):

    def test_ac17_comments_strings_body_deeper_objects_and_table_allowed(self):
        """Конструкции в комментариях и строковых литералах, число и `retry`/`timeout` в теле колбэка, в объекте глубже первого уровня и в таблице `.each(…)` — не запрет.

        Сценарий: черновик планки `pult-vitest` (подслучай на каждую
        форму): `// it.only(…)`, `/* vi.setConfig(…) */`, строка
        `'it.only( .fails { retry: 2 }'`, `{ retry: 2, timeout: 5 }` в теле
        колбэка, `{ meta: { retry: 2 } }` аргументом `it`, числа таблицы
        `it.each([[1, 2], [3, 4]])`. В выводе предпроверки нет «— запрещено
        в тексте планки».

        Ловит мутацию: поиск по сырому тексту без вырезания комментариев и
        строк — ложный отказ на комментарии; рассматриваются все объекты
        вызова, а не собственные ключи аргумента первого уровня — ложный
        отказ на `{ meta: { retry } }`; числа ищутся во всех скобках
        вызова — ложный отказ на таблице `.each`.
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,), approve=False)
        body = "() => { expect(1).toBe(2); }"
        cover = f"it('AC-{n}: опора', {body});\n"
        cases = [
            ("комментарий //", f"// it.only('AC-{n}: x', {body}, 5000);", cover),
            ("комментарий /* */", "/* vi.setConfig({ testTimeout: 1 }); it.fails */",
             cover),
            ("строка", "const s = 'it.only( .fails { retry: 2 } vi.setConfig';",
             cover),
            ("тело колбэка",
             f"it('AC-{n}: x', () => {{ run({{ retry: 2, timeout: 5 }}); "
             f"expect(1).toBe(2); }});", ""),
            ("объект глубже",
             f"it('AC-{n}: x', {{ meta: {{ retry: 2, timeout: 9 }} }}, {body});", ""),
            ("таблица each",
             f"it.each([[1, 2], [3, 4]])('AC-{n}: x %s', (a, b) => "
             f"{{ expect(a).toBe(b); }});", ""),
        ]
        for label, line, extra in cases:
            with self.subTest(case=label, seed=self.seed):
                text, _number = self.plank_with(line, extra)
                for old in list(t.plank.glob("*")):
                    old.unlink()
                self.write_plank(t, {f"c{self.word()}.test.jsx": text})
                output = self.run_preflight(t)
                self.assertNotIn(BANNED_TAIL, output,
                                 self.note(f"{label}:\n{text}\n{output}"))

    def test_ac17_pytest_files_not_checked(self):
        """У файлов pytest запреты не проверяются.

        Сценарий: компонент `junit-xml` на pytest; черновик планки — `test_*.py`
        с атрибутами `Probe.only`, `Probe.fails` в коде и тестом
        `test_ac<n>_…`. В выводе предпроверки нет «— запрещено в тексте
        планки».

        Ловит мутацию: запреты применяются к каждому файлу планки, а не
        только к файлам с меткой `AC-<n>: ` — ложный отказ файлу pytest.
        """
        n = self.numbers(1)[0]
        project = self.junit_project()
        t = self.new_task(project, (n,), approve=False)
        text = self.py_plank((n,)) + (
            "\n\nclass Probe:\n    only = 1\n    fails = 2\n\n\n"
            "FLAGS = (Probe.only, Probe.fails)\n")
        self.write_plank(t, {f"test_{self.word()}.py": text})
        output = self.run_preflight(t)
        self.assertNotIn(BANNED_TAIL, output, self.note(output))


class Ac18BanPlacesTest(BansSandbox):

    def test_ac18_bans_in_groups_gate_long_lived_gate_and_preflight(self):
        """Функция запретов действует в гейте групп (файлы планки), в гейте долгоживущих файлов и в предпроверке.

        Сценарий (подслучай — свежая задача): (а) файл планки с `it.only` —
        отказ перехода «переход отклонён: группы приёмочных тестов» с
        деталью «<файл>:<строка>: … — запрещено в тексте планки», и тот же
        текст в выводе предпроверки; (б) долгоживущий файл задачи по
        шаблону с `it.only` (заявка мутации над вызовом есть) — отказ
        «переход отклонён: долгоживущие файлы tests/» с путём файла и
        строкой.

        Ловит мутацию: функция запретов зовётся только в предпроверке —
        переход проходит в `in_dev`; в гейт долгоживущих не добавлена —
        долгоживущий файл с `it.only` проходит.
        """
        with self.subTest(case="планка", seed=self.seed):
            n = self.numbers(1)[0]
            project = self.vitest_project()
            t = self.new_task(project, (n,))
            name = f"o{self.word()}.test.jsx"
            text, number = self.plank_with(
                f"it.only('AC-{n}: x', () => {{ expect(1).toBe(2); }});",
                f"it('AC-{n}: опора', () => {{ expect(1).toBe(2); }});\n")
            self.write_plank(t, {name: text})
            self.assertRegex(self.run_preflight(t), self.banned_line(name, number),
                             self.note(text))
            detail, rows, output = self.refusal(t, TEST_GROUPS_ACTION)
            self.assertRegex(detail, self.banned_line(name, number),
                             self.explain(rows, output))
        with self.subTest(case="долгоживущий", seed=self.seed):
            n, m = self.numbers(2)
            project = self.vitest_project()
            t = self.new_task(project, (n, m))
            self.write_plank(t, {f"p{self.word()}.test.jsx": self.jsx((n,))})
            rel = self.long_rel(t)
            head = ("// Группа: долгоживущий\n"
                    f"// Красен до реализации: фикстура {self.word()}.\n"
                    "import { expect, it } from 'vitest';\n\n"
                    f"// Ловит мутацию: фикстура {self.word()} — сумма другая.\n")
            number = len(head.splitlines()) + 1
            self.write_code(t, rel, head + f"it.only('AC-{m}: y', () => "
                            "{ expect(1).toBe(2); });\n\n"
                            f"// Ловит мутацию: фикстура {self.word()} — другая.\n"
                            f"it('AC-{m}: опора', () => {{ expect(1).toBe(2); }});\n")
            detail, rows, output = self.refusal(t, LONG_LIVED_ACTION)
            self.assertRegex(detail, self.banned_line(rel, number),
                             self.explain(rows, output))

    def test_ac18_preflight_sentinel_green_unchanged(self):
        """Сторож `test_ac9_transition_guard_calls_equal_preflight_and_not_checked` зелёный без правки.

        Сценарий: метод сторожа загружается по имени из
        `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py` и исполняется
        в этом процессе: исход — успех.

        Ловит мутацию: функция запретов зовётся в гейте групп или
        долгоживущих, но не в предпроверке (или наоборот), — множества
        функций guard перехода и предпроверки расходятся, сторож красный.
        """
        name = ("tests.test_01m4p4zp37wv81410ytzhkqc8d_preflight.SentryTest."
                "test_ac9_transition_guard_calls_equal_preflight_and_not_checked")
        suite = unittest.defaultTestLoader.loadTestsFromName(name)
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        self.assertEqual(result.testsRun, 1, self.note(stream.getvalue()))
        self.assertTrue(result.wasSuccessful(), self.note(stream.getvalue()))


class Ac21EachCommentsTest(BansSandbox):

    def test_ac21_each_table_with_comments_recognized(self):
        """Таблица `.each(…)` с комментарием `// don't` или `/* … */` распознаётся, тест критерия из неё найден.

        Сценарий (подслучай): черновик планки, где единственный тест
        критерия — `it.each([...])('AC-<n>: …', …)`, а в многострочной
        таблице (а) комментарий `// don't …` с апострофом; (б) комментарий
        `/* it's … */`. Раздел предпроверки «трассируемость AC» не называет
        критерий непокрытым.

        Ловит мутацию: разбор скобок принимает апостроф комментария за
        начало строки — пара скобок `.each(` не найдена, тест не распознан,
        критерий «нет теста»; пропускается только `//`, а `/* */` нет.
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,), approve=False)
        for label, comment in (("//", "  // don't drop this row\n"),
                               ("/* */", "  /* it's a row */\n")):
            with self.subTest(case=label, seed=self.seed):
                text = (JSX_HEAD.format(word=self.word())
                        + "it.each([\n" + comment + "  [1, 2],\n  [2, 3],\n])"
                        f"('AC-{n}: таблица {self.word()} %s', (a, b) => "
                        "{ expect(a).toBe(b); });\n")
                for old in list(t.plank.glob("*")):
                    old.unlink()
                self.write_plank(t, {f"e{self.word()}.test.jsx": text})
                output = self.run_preflight(t)
                section = output.split("трассируемость AC", 1)
                self.assertEqual(len(section), 2, self.note(output))
                head = section[1].split("\n", 1)[0]
                body = section[1].split("\n\n", 1)[0]
                self.assertNotIn(f"AC-{n}:", body if "отказ" in head else "",
                                 self.note(f"{text}\n{output}"))
                self.assertNotIn("отказ", head, self.note(f"{text}\n{output}"))


# ------------------------------------------------- AC-20, AC-22, AC-24, AC-25

STRAY_ACTION = "переход отклонён: посторонние файлы планки"
AMEND_REFUSAL = ("amend-tests для файлов планки с меткой AC-<n>: — до G3б не "
                 "исполняется; правка планки — reject на гейте")


class CarryOverSandbox(FailToPassSandbox):

    def refused_rule_project(self) -> SimpleNamespace:
        """Проект `pult-vitest` без `tests` у компонента: правило планки не
        строится, у чекпоинта — умолчание с причиной."""
        project = self.vitest_project()
        text = config.TARGETS.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines(keepends=True)
                 if not line.startswith("        tests: ")]
        config.TARGETS.write_text("".join(lines), encoding="utf-8")
        self.assertTrue(project_profile.plank_rule(project.name).refusal,
                        self.note("правило построено"))
        return project

    def stray_record(self, t, names) -> None:
        """Запись чекпоинта о посторонних файлах планки последней записью
        визита (форма записи `checkpoint`)."""
        store.journal(self.conn, t.id, "orchestrator",
                      checkpoint.STRAY_ACCEPTANCE_FILES_ACTION,
                      checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX
                      + ", ".join(names))

    def visit_rows(self, t, action: str) -> list:
        rows = store.task_steps(self.conn, t.id)
        since = max((i for i, r in enumerate(rows)
                     if r["action"] == "state -> tests_writing"), default=-1)
        return [r for r in rows[since + 1:] if r["action"] == action]


class Ac20PlankDefaultOnceTest(CarryOverSandbox):

    def test_ac20_default_rule_journaled_once_per_visit(self):
        """Чекпоинт пишет «правило планки: взято умолчание» один раз на визит `tests_writing` и не пишет вне визита.

        Сценарий: проект, у которого правило планки не строится; задача в
        `tests_writing` после перехода гейта SPEC. Три шага test_author
        подряд (чекпоинт черновика каждый раз) — запись
        «правило планки: взято умолчание» после последней «state ->
        tests_writing» ровно одна. Затем задача переходит в `in_dev`, шаг
        developer с чекпоинтом — новых таких записей нет.

        Ловит мутацию: запись на каждом чекпоинте — их три; визит
        считается от первого, а не последнего входа в состояние; запись
        вне визита `tests_writing` — после шага developer появилась ещё
        одна.
        """
        n = self.numbers(1)[0]
        project = self.refused_rule_project()
        t = self.new_task(project, (n,))
        for _ in range(3):
            self.write_plank(t, {f"s{self.word()}.test.jsx": self.jsx((n,))})
            checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        found = self.visit_rows(t, project_profile.PLANK_RULE_DEFAULT_ACTION)
        self.assertEqual(len(found), 1, self.note(str([dict(r) for r in found])))
        store.set_state(self.conn, t.id, "in_dev", "fsm",
                        expected_state="tests_writing", detail="сценарий")
        before = len([r for r in store.task_steps(self.conn, t.id)
                      if r["action"] == project_profile.PLANK_RULE_DEFAULT_ACTION])
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "PLAN.md").write_text(PLAN_READY.format(task=t.id),
                                        encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        after = len([r for r in store.task_steps(self.conn, t.id)
                     if r["action"] == project_profile.PLANK_RULE_DEFAULT_ACTION])
        self.assertEqual(after, before, self.note("запись вне визита tests_writing"))

    def test_ac20_stray_gate_skips_default_rule_record(self):
        """Последняя запись визита — «правило планки: взято умолчание»: гейт посторонних находит предшествующую запись о посторонних файлах и отказывает по ней.

        Сценарий: после чекпоинта шага в журнал визита ложатся запись
        чекпоинта о посторонних файлах планки (`acceptance_tests/shared….py`)
        и за ней запись «правило планки: взято умолчание». `advance`
        отклонён «переход отклонён: посторонние файлы планки» с деталью
        «планка ссылается на отброшенные файлы: …», называющей отброшенный
        файл.

        Ловит мутацию: гейт посторонних берёт последнюю запись визита без
        пропуска записей умолчания — молчит, задача уходит дальше.
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,))
        stray = f"shared{self.word()}.py"
        self.write_plank(t, {f"s{self.word()}.test.jsx": self.jsx((n,))})

        def default_record():
            self.stray_record(t, [f"{PLANK_DIR}/{stray}"])
            store.journal(self.conn, t.id, "orchestrator",
                          project_profile.PLANK_RULE_DEFAULT_ACTION,
                          f"причина сценария {self.word()}")

        detail, rows, output = self.refusal(t, STRAY_ACTION,
                                            before_advance=default_record)
        self.assertIn("планка ссылается на отброшенные файлы:", detail,
                      self.explain(rows, output))
        self.assertIn(stray, detail, self.explain(rows, output))


class Ac22NestedPlankFileTest(CarryOverSandbox):

    def test_ac22_nested_file_dropped_by_checkpoint_and_not_laid(self):
        """Вложенный файл каталога планки отброшен чекпоинтом как посторонний и не выложен выкладкой компонента.

        Сценарий: (а) черновик планки с `<каталог>/<имя>.test.jsx` рядом с
        файлом первого уровня — после чекпоинта шага в ссылке документов
        вложенного файла нет, а запись журнала о посторонних файлах
        называет его; (б) каталог планки с тем же вложенным файлом
        прогоняется `acceptance.run` с профилем компонента — раннеру
        передан только файл первого уровня, в выкладке `plank_layout` в
        момент запуска вложенного каталога нет.

        Ловит мутацию: правило «плоский каталог» снято — вложенный файл
        уходит в ссылку документов и в выкладку (`rglob` вместо файлов
        первого уровня).
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,))
        sub, nested = f"d{self.word()}", f"x{self.word()}.test.jsx"
        top = f"t{self.word()}.test.jsx"
        self.write_plank(t, {top: self.jsx((n,))})
        (t.plank / sub).mkdir(parents=True, exist_ok=True)
        (t.plank / sub / nested).write_text(self.jsx((n,)), encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        tree = self.git("-C", str(self.clones[t.target]), "ls-tree", "-r",
                        "--name-only", "refs/artifacts/" + t.id)
        self.assertNotIn(f"{sub}/{nested}", tree, self.note(tree))
        self.assertIn(top, tree, self.note(tree))
        strays = [r["detail"] for r in store.task_steps(self.conn, t.id)
                  if r["action"] == checkpoint.STRAY_ACCEPTANCE_FILES_ACTION]
        self.assertTrue(strays and nested in strays[-1], self.note(str(strays)))

        tdir = Path(tempfile.mkdtemp(prefix="artel-plank-")) / t.id
        self.addCleanup(shutil.rmtree, tdir.parent, True)
        (tdir / PLANK_DIR / sub).mkdir(parents=True)
        (tdir / PLANK_DIR / top).write_text(self.jsx((n,)), encoding="utf-8")
        (tdir / PLANK_DIR / sub / nested).write_text(self.jsx((n,)),
                                                     encoding="utf-8")
        root = t.wt / project.layout.replace("<id>", t.id)
        seen = []
        self.on_run = lambda run: seen.append(
            sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            if root.is_dir() else None)
        self.runs.clear()
        acceptance.run(tdir, cwd=t.wt,
                       command=project_profile.decide(project.name).profile)
        self.assertTrue(self.runs, self.note("раннер не запущен"))
        self.assertFalse(any(a.endswith(nested) for a in self.runs[0]["argv"]),
                         self.note(str(self.runs[0]["argv"])))
        self.assertTrue(seen and seen[0] is not None and sub not in seen[0],
                        self.note(str(seen)))


class Ac24RetroAndPlankRunTest(CarryOverSandbox):

    def test_ac24_retro_counts_without_rule(self):
        """`retro` считает планку без правила планки — прежний счёт.

        Сценарий: планка `pult-vitest` в ссылке документов — файл `.test.jsx`
        с двумя тестами `it('AC-<n>: …')` и пометкой `// AC-<m>: skip — …`;
        RETRO снятой задачи (`retro.build_killed`) несёт строку «Приёмочные
        тесты: 0 тест(ов), 0 manual, 0 skip» — разбор Python без правила
        не видит ни тестов `it(...)`, ни пометок `//`.

        Ловит мутацию: `scan_acceptance_tests` требует правило или
        подставляет правило проекта — `retro` падает либо считает тесты
        `it(...)` и пометку `//` (2 теста, 1 skip).
        """
        from orchestrator import retro
        n, m = self.numbers(2)
        project = self.vitest_project()
        t = self.new_task(project, (n, m))
        text = self.jsx((n, n)).replace(
            "import { expect, it } from 'vitest';",
            f"// AC-{m}: skip — внешняя система {self.word()}\n"
            "import { expect, it } from 'vitest';")
        self.write_plank(t, {f"r{self.word()}.test.jsx": text})
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        body = retro.build_killed(self.conn, t.id)
        self.assertIn("Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip", body,
                      self.note(body))

    def test_ac24_plank_run_long_lived_with_refused_rule(self):
        """`plank-run` долгоживущего файла при правиле с отказом построения — код 0, раннер запущен, текста отказа нет.

        Сценарий: проект, у которого правило планки не строится (у
        компонента нет `tests`); долгоживущий файл задачи по шаблону в
        рабочей копии, его тест на прогоне проходит. `plank-run <id>
        <путь>` завершается кодом 0, раннер Vitest запущен с этим файлом,
        в выводе нет причины отказа построения правила.

        Ловит мутацию: `plank-run` проверяет правило планки до разбора
        аргумента долгоживущего файла — отказ «нет tests», раннер не
        запущен.
        """
        from orchestrator import plank_run
        n = self.numbers(1)[0]
        project = self.refused_rule_project()
        reason = project_profile.plank_rule(project.name).refusal
        t = self.new_task(project, (n,))
        rel = self.long_rel(t)
        self.write_code(t, rel, self.long_jsx((n,)))
        self.vitest_default = {"state": "pass", "error_name": None}
        buf = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                plank_run.cmd_plank_run(t.id, rel)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (
                    0 if exc.code is None else 1)
                buf.write(f"\n{exc.code}")
        output = buf.getvalue()
        self.assertEqual(code, 0, self.note(output))
        self.assertTrue(any(a.endswith(rel) for r in self.runs for a in r["argv"]),
                        self.note(output))
        self.assertNotIn(reason, output, self.note(output))


class Ac25AmendAndTemplateTest(CarryOverSandbox):

    def test_ac25_amend_md_only_plank_labelled_long_lived_refused(self):
        """`amend-tests` в режиме рабочей копии: планка только из `.md`, критерий покрыт долгоживущим файлом с меткой, правится этот файл — проход проверками файлов с меткой (SPEC 01M5GXZK2WTZ89AXQ7QY2RJD9R, AC-21).

        Сценарий: задача `in_dev` с локом: планка в ссылке документов — один
        `.md` и перечень сумм; долгоживущий файл с меткой закоммичен в
        кодовую ветку. Оператор правит долгоживущий файл в рабочей копии и
        зовёт `amend-tests`. Вывод без отказа G3б и без «amend-tests:
        отказ»; `tests_locked_sha` сдвинут и равен голове ссылки
        документов; записей «правка планки» на одну больше; голова кодовой
        ветки сдвинута коммитом правки; перечень нового лока несёт сумму
        правленого файла.

        Ловит мутацию: отказ G3б для файлов с меткой оставлен — планка из
        одного `.md` с долгоживущим файлом с меткой не проходит, лок не
        сдвинут; долгоживущий файл с меткой проверяется прежним путём
        Python (строка группы в докстринге) — отказ «долгоживущие файлы
        tests/»; перечень нового лока считается по прежней голове — сумма
        старого текста.
        """
        from orchestrator import amend
        from orchestrator.advance_gates import acceptance as acceptance_gates
        from scripts import guard
        import hashlib
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,), approve=False)
        store.update_task(self.conn, t.id, state="in_dev")
        rel = self.long_rel(t)
        text = self.long_jsx((n,))
        self.write_code(t, rel, text)
        self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", "долгоживущий файл")
        digest = hashlib.sha256((t.wt / rel).read_bytes()).hexdigest()
        self.write_plank(t, {f"n{self.word()}.md": "заметка\n",
                             guard.LONG_LIVED_MANIFEST_NAME:
                                 guard.render_long_lived_manifest({rel: digest})})
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        head = self.docs_head(t)
        self.assertTrue(head, self.note("ссылки документов нет"))
        store.update_task(self.conn, t.id, tests_locked_sha=head)
        store.record_fixation(self.conn, t.id)

        def state_of():
            row = store.get_task(self.conn, t.id)
            code = self.git("-C", str(t.wt), "rev-parse", t.branch).strip()
            amends = [r for r in store.task_steps(self.conn, t.id)
                      if r["action"] == amend.AMEND_ACTION]
            return (self.docs_head(t), code, row["tests_locked_sha"], len(amends))

        before = state_of()
        edited = text + "// правка\n"
        self.write_code(t, rel, edited)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                amend.cmd_amend_tests(t.id, f"правка {self.seed}")
            except SystemExit as exc:
                buf.write(f"\n{exc.code}")
        output = buf.getvalue()
        after = state_of()
        context = self.note(f"{output}\nдо {before}\nпосле {after}")
        self.assertNotIn(AMEND_REFUSAL, output, context)
        self.assertNotIn("amend-tests: отказ", output, context)
        self.assertNotEqual(after[2], before[2], context)
        self.assertEqual(after[2], after[0], context)
        self.assertEqual(after[3], before[3] + 1, context)
        self.assertNotEqual(after[1], before[1], context)
        digests, reason = acceptance_gates.long_lived_manifest(
            t.id, store.get_task(self.conn, t.id), project.name)
        self.assertEqual(reason, "", context)
        self.assertEqual(digests.get(rel),
                         hashlib.sha256(edited.encode("utf-8")).hexdigest(),
                         self.note(f"перечень: {digests}"))

    def test_ac25_each_template_shape_refusal_by_its_reason(self):
        """Каждый отказ формы шаблона `long_lived` сверяется по своей причине, а не только по имени компонента.

        Сценарий: для каждой негодной формы шаблона запись проекта с одним
        компонентом `pult-vitest` пишется в `targets.yaml` песочницы, чтение
        записи (`targets.target`) отказывает `TargetsError`, текст несёт имя
        компонента, «поле 'long_lived'» и причину именно этой формы: `<id>`
        дважды, `<name>` не в последнем сегменте, `<dir>` дважды, `<dir>`
        частью сегмента, нет каталога до заполнителя, последний сегмент не
        под маской `tests`, шаблон вместе с `long_lived_dir`, абсолютный
        путь, нет `<id>`, чужой заполнитель.

        Ловит мутацию: две проверки формы склеены в одну с общей причиной
        (например, «<dir>» и «<id>» одной строкой) — текст причины другой
        формы; проверка последнего сегмента против масок снята — запись
        принята.
        """
        from orchestrator import targets
        cases = [
            ("frontend/src/<dir>/<name>.<id>.<id>.test.jsx", None,
             "<id> ровно один раз и только в последнем сегменте"),
            ("frontend/<name>/x.<id>.test.jsx", None,
             "<name> ровно один раз и только в последнем сегменте"),
            ("frontend/<dir>/<dir>/<name>.<id>.test.jsx", None,
             "<dir> не больше одного раза и только целым сегментом"),
            ("frontend/a<dir>/<name>.<id>.test.jsx", None,
             "<dir> не больше одного раза и только целым сегментом"),
            ("<dir>/<name>.<id>.test.jsx", None,
             "у шаблона long_lived нет каталога до первого заполнителя"),
            ("frontend/src/<dir>/<name>.<id>.spec.ts", None,
             "последний сегмент не подходит под маски tests"),
            ("frontend/src/<dir>/<name>.<id>.test.jsx", "frontend/src",
             "вместе с 'long_lived_dir' — либо шаблон, либо пара полей"),
            ("/frontend/<dir>/<name>.<id>.test.jsx", None,
             "не относительный путь от корня репозитория"),
            ("frontend/<dir>/<name>.test.jsx", None, "нет заполнителя <id>"),
            ("frontend/<foo>/<name>.<id>.test.jsx", None, "заполнитель <foo>"),
        ]
        self.rng.shuffle(cases)
        for template, pair_dir, reason in cases:
            with self.subTest(template=template, seed=self.seed):
                name, comp = f"f{self.word()}", f"c{self.word()}"
                fields = {"command": flow(project_profile.VITEST_BASE_ARGV),
                          "report": "pult-vitest",
                          "report_args": flow(VITEST_REPORT_ARGS),
                          "failure_errors": flow(["AssertionError"]),
                          "select": flow(["--sel", "{tests}"]),
                          "install": flow([str(self.installer)]),
                          "tests": flow(["frontend/src/**/*.test.jsx"]),
                          "plank_layout": "frontend/src/.pv/<id>",
                          "long_lived": template,
                          "weakening_scope": flow(["frontend/src/**"]),
                          "mutation_claim_scope": flow(["frontend/src/**"])}
                if pair_dir:
                    fields["long_lived_dir"] = pair_dir
                lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                         f"      {comp}:\n"]
                lines += [f"        {k}: {v}\n" for k, v in fields.items()]
                self.append_entry("".join(lines))
                with self.assertRaises(targets.TargetsError) as caught:
                    targets.target(name)
                text = str(caught.exception)
                self.assertIn(comp, text, self.note(text))
                self.assertIn("поле 'long_lived'", text, self.note(text))
                self.assertIn(reason, text, self.note(text))
                # Запись снимается: следующая запись не должна падать на этой.
                old = config.TARGETS.read_text(encoding="utf-8")
                config.TARGETS.write_text(
                    old[:old.index(f"  {name}:\n")], encoding="utf-8")


# --------------------------------------------------------------- AC-27

class Ac27OldOutcomesTest(CarryOverSandbox):

    def own_task(self):
        n = self.numbers(1)[0]
        project = self.own_profile_project()
        t = self.new_task(project, (n,), approve=False)
        return t, n

    def no_group(self, numbers) -> str:
        return self.py_plank(numbers).replace("Группа: разовый\n", "")

    def long_py(self, n: int, group: str = "долгоживущий") -> str:
        name = self.word()
        return "\n".join([
            '"""Долгоживущая фикстура ' + name + ".", "", "Группа: " + group,
            "Красен " + "до реализации: фикстура " + name + ".", '"""',
            "import unittest", "", "",
            "class FixtureLongLivedTest(unittest.TestCase):", "",
            f"    def test_ac{n}_{name}(self):",
            '        """Фикстурный метод.', "",
            "        Ловит " + "мутацию: фикстура " + name + " — сумма другая.",
            '        """', "        self.assertEqual(2 + 2, 4)", ""])

    def assert_only(self, rows, output, action: str) -> None:
        refusals = [r["action"] for r in rows
                    if (r["action"] or "").startswith("переход отклонён")]
        self.assertEqual(refusals, [action], self.explain(rows, output))

    def test_ac27_tests_writing_gate_order_and_drop_unchanged(self):
        """Вне границы (запись `test_profile` с `pytest-own` и `report: junit-xml`) порядок гейтов выхода из `tests_writing` и уборка планки — прежние.

        Сценарий (подслучай — свежая задача): (а) запись чекпоинта о
        посторонних файлах последней записью визита и файл без строки
        группы — только «переход отклонён: посторонние файлы планки» с
        «планка ссылается на отброшенные файлы:»; (б) файл планки без строки группы и долгоживущий файл с
        иной группой — только «переход отклонён: группы приёмочных тестов»;
        (в) долгоживущий файл с иной группой и несобирающаяся планка
        (отчёта нет) — только «переход отклонён: долгоживущие файлы tests/»;
        (г) несобирающаяся планка — «переход отклонён: планка не
        собирается», записи «перечень долгоживущих тестов записан» нет. Во
        всех случаях каталога задачи в рабочей копии кода после `advance`
        нет.

        Ловит мутацию: новый гейт или правка порядка переставили гейты —
        в одном из случаев отказ другого гейта или два отказа; уборка
        `drop_from_code_copy` вынесена из `finally` — планка осталась в
        рабочей копии после отказа.
        """
        def stray(t, n):
            self.write_plank(t, {f"test_{self.word()}.py": self.no_group((n,))})
            name = f"{PLANK_DIR}/shared{self.word()}.py"
            kwargs["before_advance"] = lambda: self.stray_record(t, [name])
            return STRAY_ACTION

        def groups(t, n):
            self.write_plank(t, {f"test_{self.word()}.py": self.no_group((n,))})
            self.write_code(t, f"tests/test_{t.low}_{self.word()}.py",
                            self.long_py(n, group="разовый"))
            return TEST_GROUPS_ACTION

        def long_lived(t, n):
            self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
            self.write_code(t, f"tests/test_{t.low}_{self.word()}.py",
                            self.long_py(n, group="разовый"))
            self.no_report_when = lambda run: True
            return LONG_LIVED_ACTION

        def dry_collect(t, n):
            self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
            self.no_report_when = lambda run: True
            return DRY_COLLECT_ACTION

        for label, arrange in (("посторонние", stray), ("группы", groups),
                               ("долгоживущие", long_lived),
                               ("сухой сбор", dry_collect)):
            with self.subTest(case=label, seed=self.seed):
                self.no_report_when = None
                kwargs = {}
                t, n = self.own_task()
                action = arrange(t, n)
                _detail, rows, output = self.refusal(t, action, **kwargs)
                self.assert_only(rows, output, action)
                if action == STRAY_ACTION:
                    self.assertIn("планка ссылается на отброшенные файлы:",
                                  _detail, self.explain(rows, output))
                if action == DRY_COLLECT_ACTION:
                    self.assertFalse(self.details(rows, MANIFEST_NOTE),
                                     self.explain(rows, output))
                self.assertFalse((t.wt / TASKS_DIR / t.id).exists(),
                                 self.explain(rows, output))

    def test_ac27_reserved_helper_hint_unchanged(self):
        """Вне границы `_pult.py` в черновике планки — прежний отказ посторонних файлов с подсказкой про помощник пульта.

        Сценарий: последняя запись визита — запись чекпоинта об
        отброшенном `acceptance_tests/_pult.py` черновика планки записи
        `test_profile`. Отказ «переход отклонён: посторонние файлы
        планки», деталь «планка ссылается на отброшенные файлы: …»
        называет `_pult.py`, вывод перехода несёт подсказку «_pult.py: …»
        про занятое имя помощника.

        Ловит мутацию: правка гейта посторонних (пропуск записей умолчания)
        сломала разбор имён записи — `_pult.py` не назван, подсказка
        прежняя общая.
        """
        t, n = self.own_task()
        self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
        detail, rows, output = self.refusal(
            t, STRAY_ACTION, before_advance=lambda: self.stray_record(
                t, [f"{PLANK_DIR}/_pult.py"]))
        self.assertIn("планка ссылается на отброшенные файлы:", detail,
                      self.explain(rows, output))
        self.assertIn("_pult.py", detail, self.explain(rows, output))
        self.assertIn("_pult.py:", output, self.explain(rows, output))

    def test_ac27_red_acceptance_detail_unchanged(self):
        """Вне границы красный прогон приёмки ветки — прежний отказ «переход отклонён: приёмочные тесты» с деталью «acceptance_tests красные:\\n<хвост>\\nокружение: <fingerprint>».

        Сценарий: задача записи `test_profile` прошла выход из
        `tests_writing`; прогон ветки — тест критерия падает. Деталь
        отказа начинается «acceptance_tests красные:\\n» и содержит строку
        «окружение: »; отказа «… тест критерия не в отчёте» нет.

        Ловит мутацию: формат детали красного прогона изменён правкой тела
        приёмки (новая проверка дописала текст до хвоста либо заменила
        действие).
        """
        t, n = self.own_task()
        self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
        self.passes(t)
        self.branch_phase()
        self.junit_case[n] = ("failure", "assert 1 == 2")
        rows, output = self.developer_advance(t)
        red = self.details(rows, RED_ACTION)
        self.assertTrue(red, self.explain(rows, output))
        self.assertTrue(red[-1].startswith("acceptance_tests красные:\n"),
                        self.explain(rows, output))
        self.assertIn("\nокружение: ", red[-1], self.explain(rows, output))
        self.assertFalse(self.details(rows, BRANCH_ACTION),
                         self.explain(rows, output))


if __name__ == "__main__":
    unittest.main()
