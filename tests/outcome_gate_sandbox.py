"""Песочница гейта неослабления по исходам `OutcomeGateSandbox` с константами и помощниками стенда."""
import contextlib
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

from orchestrator import (acceptance, answer, checkpoint, config, fsm,
                          github_adapter, project_profile, store, workspace)
from tests.sandbox import GitignoreCommittedRealGitSandbox, make_project_repo

REAL_POPEN = subprocess.Popen
REAL_RUN = subprocess.run
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
VITEST_BIN = project_profile.VITEST_BASE_ARGV[0]
VITEST_REPORT_ARGS = ["--reporter=default", "--reporter={pult_reporter}",
                      "--outputFile={path}"]
LONG_TEMPLATE = "frontend/src/<dir>/<name>.<id>.test.jsx"
GATE_MODULE = "orchestrator.advance_gates.outcome_integrity"

OUTCOME_ACTION = "переход отклонён: гейт неослабления по исходам"
BROKEN_ACTION = "переход отклонён: гейт неослабления по исходам — сломан правкой"
PREPARE_ACTION = "переход отклонён: гейт неослабления по исходам — подготовка"
GATE_ACTIONS = (OUTCOME_ACTION, BROKEN_ACTION, PREPARE_ACTION)
GATE_WORDS = "по исходам"
TEXT_GATE_ACTION = "переход отклонён: гейт неослабления тестов"
TEXT_GATE_SKIP = "проверка тестов не выполняется: гейт неослабления тестов"
REWORK_ACTION = "переход отклонён: замечания ревью не отработаны"
PASSED_NOTE = "приёмочные тесты пройдены"
FLAKY_ON_BASE = "нестабилен и на базе: "
APPROVED_DETAIL = "гейт SPEC пройден — приёмочные тесты до кода"
MANDATE_MARKER = "Ослабление тестов разрешено:"
SEP = "::"
CLAIM = "Ловит мутацию: фикстура сценария — исход теста другой."

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

REVIEW_CHANGES = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 1
---

# REVIEW: фикстура

## Замечания
1. Замечание фикстуры {word}.
"""

MATRIX_HEADERS = (
    "Что меняется",
    "Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка)",
    "Остаётся ли свойство после изменения",
    "Чем покрыто после (тест файл:строка) или «не покрыто»",
    "Решение")

PY_CLASS = re.compile(r"^class (\w+)\b")
PY_DEF = re.compile(r"^(\s*)def (test_\w+)\(")
PY_VARIANTS = re.compile(r"^\s*# варианты: (.+)$")
VITEST_ANY = re.compile(r"\b(?:it|test)(?:\.[A-Za-z]+)*\(\s*'([^']*)'")
PLANK_PY = re.compile(r"^test_ac\d+_")
PLANK_JS = re.compile(r"^AC-\d+: ")

# Поля записи отчётчика пульта для краткого исхода сценария.
VITEST_KIND = {
    "passed": {"state": "pass", "error_name": None},
    "failed": {"state": "fail", "error_name": "AssertionError"},
    "error": {"state": "fail", "error_name": "TypeError"},
    "skipped": {"state": "skip", "mode": "skip", "error_name": None},
    "todo": {"state": "todo", "mode": "todo", "error_name": None},
    "fails": {"state": "pass", "fails": True, "error_name": None},
    "retried": {"state": "pass", "retry_count": 1, "error_name": None},
}


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def spec_text(task_id: str, numbers) -> str:
    items = "\n\n".join(f"AC-{n}. Критерий фикстуры номер {n}." for n in
                        sorted(numbers))
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура гейта исходов\n\n## Контекст\n\n"
            f"## Требования\n\n## Критерии приёмки\n\n{items}\n\n"
            "## Не входит\n")


def arg_value(args: list, flag: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


def py_source(names) -> str:
    """Текст файла pytest с тестами `names`: `test_x` — функция модуля,
    `Класс::test_x` — метод класса, `test_x[a,b]` — варианты (строка
    `# варианты:` перед методом)."""
    plain, classes = [], {}
    for full in names:
        head, _, variants = full.partition("[")
        if SEP in head:
            klass, name = head.split(SEP, 1)
            classes.setdefault(klass, []).append((name, variants.rstrip("]")))
        else:
            plain.append((head, variants.rstrip("]")))
    lines = ['"""Тесты учебного проекта."""', ""]
    for name, variants in plain:
        if variants:
            lines.append(f"# варианты: {variants}")
        lines += [f"def {name}():", f'    """{CLAIM}"""', "    pass", ""]
    for klass, items in classes.items():
        lines += ["", f"class {klass}:", ""]
        for name, variants in items:
            if variants:
                lines.append(f"    # варианты: {variants}")
            lines += [f"    def {name}(self):", f'        """{CLAIM}"""',
                      "        pass", ""]
    return "\n".join(lines) + "\n"


def py_tests(text: str) -> list:
    """[(classname, name)] тестов текста `py_source` (варианты раскрыты)."""
    found, klass, variants = [], "", []
    for line in text.splitlines():
        m = PY_CLASS.match(line)
        if m:
            klass = m.group(1)
            continue
        m = PY_VARIANTS.match(line)
        if m:
            variants = [v.strip() for v in m.group(1).split(",") if v.strip()]
            continue
        m = PY_DEF.match(line)
        if m:
            owner = klass if m.group(1) else ""
            if not m.group(1):
                klass = ""
            names = ([f"{m.group(2)}[{v}]" for v in variants] if variants
                     else [m.group(2)])
            found += [(owner, n) for n in names]
            variants = []
    return found


def js_source(names) -> str:
    body = "".join(f"// {CLAIM}\nit('{n}', () => {{ expect(1).toBe(1); }});\n"
                   for n in names)
    return "import { expect, it } from 'vitest';\n\n" + body


class RunnerProc:
    """Процесс раннера сценария: запоминает предел `communicate`/`wait` в
    запись запуска; `expire` — первый вызов с пределом бросает
    `TimeoutExpired` сразу, без ожидания."""

    def __init__(self, real, run: dict, expire: bool):
        self.real = real
        self.run = run
        self.expire = expire
        self.fired = False
        self.pid = real.pid

    def _limit(self, timeout):
        if timeout is not None and self.run.get("timeout") is None:
            self.run["timeout"] = timeout
        if self.expire and not self.fired and timeout is not None:
            self.fired = True
            raise subprocess.TimeoutExpired("runner", timeout)

    def communicate(self, *args, timeout=None, **kwargs):
        self._limit(timeout)
        return self.real.communicate(*args, **kwargs)

    def wait(self, timeout=None):
        self._limit(timeout)
        return self.real.wait()

    def kill(self):
        with contextlib.suppress(OSError):
            self.real.kill()

    @property
    def returncode(self):
        return self.real.returncode

    def __getattr__(self, name):
        return getattr(self.real, name)


class OutcomeGateSandbox(GitignoreCommittedRealGitSandbox):
    """Клон артели с `origin`; учебные проекты и задачи заводит сценарий;
    раннеры — шпион `subprocess.Popen`, полный набор — обёртка
    `acceptance.full_suite`, сбои git гейта — шпион `subprocess.run`."""

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
        # Сценарий: (путь, полное имя) -> {"base": [...], "head": [...]}.
        self.cases: dict = {}
        self.counts: dict = {}
        self.plank_green = False
        self.timeout_when = None
        self.no_report_when = None
        self.git_fail = None
        self.runs: list = []
        self.suite_calls: list = []
        self.real_full_suite = acceptance.full_suite
        for patcher in (
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda *args, **kwargs: (True, "")),
                mock.patch.object(subprocess, "Popen", self.spy_popen),
                mock.patch.object(subprocess, "run", self.spy_run),
                mock.patch.object(acceptance, "full_suite", self.spy_full_suite),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
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

    def py_rel(self) -> str:
        return f"tests/test_{self.word()}.py"

    def js_rel(self) -> str:
        return f"frontend/src/{self.word()}.test.jsx"

    def py_name(self) -> str:
        return f"test_{self.word()}"

    def js_name(self) -> str:
        return f"случай {self.word()}"

    # --- шпионы ---------------------------------------------------------

    def in_gate(self) -> bool:
        frame = sys._getframe(1)
        while frame is not None:
            if frame.f_globals.get("__name__") == GATE_MODULE:
                return True
            frame = frame.f_back
        return False

    def spy_run(self, argv, *args, **kwargs):
        """`subprocess.run`: вызов git из кадров модуля гейта, подпавший
        под правило сценария `git_fail`, отвечает отказом без запуска."""
        if (self.git_fail is not None and isinstance(argv, (list, tuple))
                and argv and argv[0] == "git" and self.in_gate()
                and self.git_fail(tuple(str(a) for a in argv[1:]))):
            return subprocess.CompletedProcess(list(argv), 128, "",
                                               "fatal: сбой git сценария\n")
        return REAL_RUN(argv, *args, **kwargs)

    def spy_full_suite(self, root, task_id, *args, **kwargs):
        call = {"root": Path(root), "side": self.side_of(Path(root)),
                "command": kwargs.get("command", args[0] if args else None),
                "fresh": kwargs.get("fresh", args[1] if len(args) > 1 else False)}
        self.suite_calls.append(call)
        return self.real_full_suite(root, task_id, *args, **kwargs)

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
            return self.runner_run("vitest", parts, cwd, args, kwargs)
        if parts[0] == str(self.pytest_cmd):
            return self.runner_run("pytest", parts, cwd, args, kwargs)
        return REAL_POPEN(argv, *args, **kwargs)

    @staticmethod
    def side_of(cwd: Path) -> str:
        """Сторона дерева прогона по метке `app.py` (поиск вверх)."""
        for folder in (cwd, *cwd.parents):
            marker = folder / "app.py"
            if marker.is_file():
                text = marker.read_text(encoding="utf-8")
                if "'base'" in text:
                    return "base"
                if "'head-" in text:
                    return "head"
                return "?"
            if (folder / ".git").exists():
                break
        return "?"

    def runner_files(self, parts: list, cwd: Path, suffix: str) -> tuple:
        """(полный ли прогон, [(путь от `cwd`, текст)]) файлов тестов,
        переданных раннеру; путей нет — полный набор дерева `cwd`."""
        found, explicit, full = [], False, True
        for part in parts:
            if part.startswith("-"):
                continue
            path = Path(part) if os.path.isabs(part) else cwd / part
            if path.is_dir():
                explicit = True
                found += [p for p in sorted(path.rglob("*")) if p.is_file()]
            elif path.is_file() and path.name.endswith(suffix):
                explicit, full = True, False
                found.append(path)
        if not explicit:
            found = [p for p in sorted(cwd.rglob("*")) if p.is_file()]
        files = []
        for p in found:
            rel = os.path.relpath(p, cwd).replace(os.sep, "/")
            if "node_modules" in rel.split("/"):
                continue
            if not p.name.endswith(suffix):
                continue
            if suffix == ".py" and not p.name.startswith("test_"):
                continue
            if not explicit and any(s.startswith(".") for s in rel.split("/")):
                continue
            files.append((rel, p.read_text(encoding="utf-8")))
        return full, files

    def outcome_of(self, side: str, rel: str, name: str) -> str:
        key = (rel, name)
        seq = self.cases.get(key, {}).get(side, ["passed"])
        index = self.counts.get((side, rel, name), 0)
        self.counts[(side, rel, name)] = index + 1
        return seq[min(index, len(seq) - 1)]

    def runner_run(self, kind: str, parts: list, cwd: Path, args, kwargs):
        suffix = ".test.jsx" if kind == "vitest" else ".py"
        full, files = self.runner_files(parts[1:], cwd, suffix)
        run = {"kind": kind, "argv": parts, "cwd": cwd, "side": self.side_of(cwd),
               "full": full, "files": [rel for rel, _ in files],
               "timeout": None, "index": len(self.runs)}
        plank = any(PLANK_PY.match(n) or PLANK_JS.match(n)
                    for _rel, text in files
                    for _c, n in (py_tests(text) if kind == "pytest" else
                                  [("", m.group(1)) for m in
                                   VITEST_ANY.finditer(text)]))
        run["plank"] = plank
        self.runs.append(run)
        if kind == "vitest":
            text, red = self.vitest_report(run, files)
            path = arg_value(parts, "--outputFile")
        else:
            text, red = self.junit_report(run, files)
            path = arg_value(parts, "--junitxml")
        if path and not self.when(self.no_report_when, run):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(text, encoding="utf-8")
        proc = self.answer(1 if red else 0, f"{kind}\n", args, kwargs)
        return RunnerProc(proc, run, self.when(self.timeout_when, run))

    @staticmethod
    def when(predicate, run: dict) -> bool:
        return predicate is not None and bool(predicate(run))

    def junit_report(self, run: dict, files: list) -> tuple:
        cases, red = [], False
        for rel, text in files:
            for klass, name in py_tests(text):
                full = f"{klass}{SEP}{name}" if klass else name
                if PLANK_PY.match(name):
                    kind = "passed" if self.plank_green else "failed"
                else:
                    kind = self.outcome_of(run["side"], rel, full)
                if kind == "missing":
                    continue
                body = {"passed": "",
                        "failed": '<failure message="assert 1 == 2">'
                                  'AssertionError: assert 1 == 2</failure>',
                        "error": '<error message="TypeError">TypeError: '
                                 'boom</error>',
                        "skipped": '<skipped message="пропуск сценария"/>',
                        }[kind]
                red = red or kind in ("failed", "error")
                cases.append(f'<testcase file="{rel}" classname="{klass}" '
                             f'name="{name}" time="0.01">{body}</testcase>')
        text = ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
                '<testsuite name="pytest">' + "".join(cases)
                + "</testsuite></testsuites>")
        return text, red

    def vitest_report(self, run: dict, files: list) -> tuple:
        items, red = [], False
        for rel, text in files:
            for m in VITEST_ANY.finditer(text):
                name = m.group(1)
                if PLANK_JS.match(name):
                    kind = "passed" if self.plank_green else "failed"
                else:
                    kind = self.outcome_of(run["side"], rel, name)
                if kind == "missing":
                    continue
                item = {"file": rel, "name": name, "state": "pass",
                        "mode": "run", "fails": False, "retry_count": 0,
                        "error_name": None, "timeout": False, "hook": None,
                        "duration_ms": 3}
                item.update(VITEST_KIND[kind])
                red = red or item["state"] == "fail" or item["retry_count"] > 0
                items.append(item)
        return json.dumps({"tests": items}), red

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

    def junit_project(self, tests: dict, limit: int | None = None,
                      test_profile: bool = False) -> SimpleNamespace:
        """Учебный проект с единственным компонентом `junit-xml` на
        поддельном `pytest` (либо записью `test_profile` с `report:
        junit-xml` при `test_profile`); `tests` — {путь: [полные имена]}
        тестов базы; `limit` — `full_suite_timeout_sec` компонента."""
        name, comp = f"j{self.word()}", f"c{self.word()}"
        layout = f".pj{self.word(5)}/<id>"
        fields = {"command": flow([str(self.pytest_cmd)]),
                  "report": "junit-xml",
                  "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": flow(["tests/**"]),
                  "mutation_claim_scope": flow(["tests/**"]),
                  "failure_errors": flow(["AssertionError"])}
        if limit is not None:
            fields["full_suite_timeout_sec"] = str(limit)
        if test_profile:
            fields["runner"] = "pytest-own"
            fields.pop("failure_errors")
            lines = [ENTRY_HEAD.format(name=name), "    test_profile:\n"]
            for key, value in fields.items():
                lines.append(f"      {key}: {value}\n")
            comp, layout = project_profile.DEFAULT_COMPONENT, ""
        else:
            fields["plank_layout"] = layout
            lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                     f"      {comp}:\n"]
            for key, value in fields.items():
                lines.append(f"        {key}: {value}\n")
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        files = {"app.py": "APP = 'base'\n"}
        files.update({rel: py_source(names) for rel, names in tests.items()})
        if not tests:
            files["README.md"] = "учебный проект без тестов\n"
        self.commit_project(clone, files)
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, layout=layout,
                               kind="junit", clone=clone)

    def vitest_project(self, tests: dict,
                       limit: int | None = None) -> SimpleNamespace:
        """Учебный проект с единственным компонентом `pult-vitest`; `tests` —
        {путь: [имена]} тестов базы."""
        name, comp = f"v{self.word()}", f"c{self.word()}"
        layout = f"frontend/src/.pv{self.word(5)}/<id>"
        fields = {"command": flow(project_profile.VITEST_BASE_ARGV),
                  "report": "pult-vitest",
                  "report_args": flow(VITEST_REPORT_ARGS),
                  "install": flow([str(self.installer)]),
                  "tests": flow(["frontend/src/**/*.test.jsx"]),
                  "plank_layout": layout,
                  "long_lived": LONG_TEMPLATE,
                  "weakening_scope": flow(["frontend/src/**"]),
                  "mutation_claim_scope": flow(["frontend/claims/**"]),
                  "failure_errors": flow(["AssertionError"]),
                  "select": flow([f"--sel{self.word()}", "{tests}"])}
        if limit is not None:
            fields["full_suite_timeout_sec"] = str(limit)
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        for key, value in fields.items():
            lines.append(f"        {key}: {value}\n")
        lines.append("        tools:\n")
        lines.append(f'          vitest: "{self.vitest_version}"\n')
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        files = {"package.json": '{"name": "web"}\n',
                 "vitest.config.js": "export default {}\n",
                 "package-lock.json": json.dumps({"lockfileVersion": 3}) + "\n",
                 "app.py": "APP = 'base'\n"}
        files.update({rel: js_source(names) for rel, names in tests.items()})
        self.commit_project(clone, files)
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, layout=layout,
                               kind="vitest", clone=clone)

    def drop_select(self) -> None:
        """Снять поле `select` со всех компонентов `targets.yaml` песочницы."""
        text = config.TARGETS.read_text(encoding="utf-8")
        text = re.sub(r"^        select: .*\n", "", text, flags=re.MULTILINE)
        config.TARGETS.write_text(text, encoding="utf-8")

    def bare_project(self) -> SimpleNamespace:
        """Учебный проект без `test_profile` и без `components:` —
        `decide` отдаёт пропуск."""
        name = f"b{self.word()}"
        self.append_entry(ENTRY_HEAD.format(name=name))
        clone = make_project_repo(name)
        self.commit_project(clone, {"app.py": "APP = 'base'\n",
                                    "tests/test_base.py": py_source(
                                        [self.py_name()])})
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=project_profile.DEFAULT_COMPONENT,
                               layout="", kind="bare", clone=clone)

    # --- задачи ---------------------------------------------------------

    def case_id(self, project, rel: str, name: str) -> str:
        return project_profile.test_id(project.comp, rel, name)

    def plank_text(self, project, n: int) -> tuple:
        if project.kind == "vitest":
            return (f"p{self.word()}.test.jsx",
                    "// Группа: разовый\n"
                    f"// Красен до реализации: фикстура {self.word()}.\n"
                    "import { expect, it } from 'vitest';\n\n"
                    f"it('AC-{n}: кнопка {self.word()}', () => "
                    "{ expect(1).toBe(2); });\n")
        name = self.word()
        lines = ['"""Разовая фикстура ' + name + ".", "",
                 "Группа: разовый",
                 "Красен " + "до реализации: фикстура " + name + " ждёт кода.",
                 '"""', "import unittest", "", "",
                 "class FixturePlankTest(unittest.TestCase):", "",
                 f"    def test_ac{n}_{self.word()}(self):",
                 '        """Фикстурный метод."""',
                 "        self.assertEqual(2 + 2, 5)", ""]
        return f"test_{self.word()}.py", "\n".join(lines)

    def in_dev_task(self, project, canary: bool = False):
        """Задача проекта в `in_dev`: SPEC в ссылке документов, переход
        гейта SPEC, планка с тестом критерия (красным на базе), настоящий
        выход из `tests_writing`."""
        n = self.rng.randrange(1, 60)
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Фикстура гейта исходов", "spec_gate",
                          branch, project.name, 25.0, is_canary=canary)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=project.name, wt=Path(wt), project=project)
        t.docs = config.PROJECTS / project.name / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        t.spec = spec_text(tid, (n,))
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, tid, "analyst")
        store.set_state(self.conn, tid, "tests_writing", "operator",
                        expected_state="spec_gate", detail=APPROVED_DETAIL)
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        t.plank.mkdir(parents=True, exist_ok=True)
        plank_name, plank_body = self.plank_text(project, n)
        (t.plank / plank_name).write_text(plank_body, encoding="utf-8")
        self.plank_green = False
        store.journal(self.conn, tid, "test_author", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, tid, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, tid, "test_author")
        rows, output = self.run_advance(tid)
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        self.plank_green = True
        return t

    def artel_in_dev_task(self):
        """Задача артели в `in_dev`: планка `test_*.py` с тестом
        критерия, без опоры SPEC (задача заведена в `tests_writing`)."""
        n = self.rng.randrange(1, 60)
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Фикстура гейта исходов",
                          "tests_writing", branch, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        project = SimpleNamespace(name=config.DEFAULT_TARGET, kind="artel",
                                  comp=project_profile.DEFAULT_COMPONENT,
                                  layout="", clone=self.root)
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=config.DEFAULT_TARGET, wt=Path(wt),
                            project=project)
        t.docs = config.PROJECTS / config.DEFAULT_TARGET / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        t.spec = spec_text(tid, (n,))
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        name = self.word()
        text = "\n".join(['"""Разовая фикстура ' + name + ".", "",
                          "Группа: разовый",
                          "Зелёный " + "с рождения: фикстура " + name + ".",
                          '"""', "import unittest", "", "",
                          "class FixturePlankTest(unittest.TestCase):", "",
                          f"    def test_ac{n}_{self.word()}(self):",
                          '        """Фикстурный метод."""',
                          "        self.assertEqual(2 + 2, 4)", ""])
        (t.plank / f"test_{self.word()}.py").write_text(text, encoding="utf-8")
        store.journal(self.conn, tid, "test_author", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, tid, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, tid, "test_author")
        rows, output = self.run_advance(tid)
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        return t

    def run_advance(self, tid: str) -> tuple:
        before = len(store.task_steps(self.conn, tid))
        self.runs.clear()
        self.suite_calls.clear()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(tid)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, tid)[before:]]
        return rows, buf.getvalue()

    def commit_code(self, t, changes: dict, message: str = "код разработчика"):
        """Коммит правки кодовой ветки: `app.py` — метка головы, `changes` —
        {путь: текст или `None` (удалить)}."""
        files = {"app.py": f"APP = 'head-{self.word()}'\n", **changes}
        for rel, text in files.items():
            path = t.wt / rel
            if text is None:
                self.git("-C", str(t.wt), "rm", "-q", "--", rel)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", message)
        store.update_task(self.conn, t.id, zones=", ".join(sorted(files)))

    def developer_advance(self, t, changes: dict | None = None,
                          finished: bool = False, before=None) -> tuple:
        """Шаг developer: коммит правки кода, PLAN.md `ready` чекпоинтом шага
        (`finished` — и запись «agent run finished»), затем `advance` из
        `in_dev`: (новые записи журнала, вывод). `before` — правка сценария
        между коммитом кода и чекпоинтом артефактов."""
        self.commit_code(t, changes or {})
        if before is not None:
            before()
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "PLAN.md").write_text(PLAN_READY.format(task=t.id),
                                        encoding="utf-8")
        store.journal(self.conn, t.id, "developer", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        if finished:
            store.journal(self.conn, t.id, "developer", "agent run finished",
                          "rc=0, шаг сценария")
        self.counts.clear()
        return self.run_advance(t.id)

    def operator_mandate(self, t, elements) -> None:
        """ANSWER Оператора (`answer.cmd_answer`) с маркером мандата на
        `elements` и матрицей неослабления."""
        row = (", ".join(f"`{e}`" for e in elements),
               "фикстура теста — tests/sandbox.py:1", "да",
               "tests/sandbox.py:1", "ок")
        text = (f"{MANDATE_MARKER} {', '.join(elements)}\n\n"
                "Независимая проверка: матрица подтверждена\n\n"
                f"Основание: решение Оператора ({self.seed}).\n\n"
                "## Матрица неослабления\n\n"
                "| " + " | ".join(MATRIX_HEADERS) + " |\n"
                + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
                + "| " + " | ".join(row) + " |\n")
        path = self.root / ".artel" / f"answer-{self.word()}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                answer.cmd_answer(t.id, str(path))
            except SystemExit as exc:
                self.assertIn(exc.code, (None, 0), self.note(
                    f"answer отказала: {buf.getvalue()}"))

    def role_mandate(self, t, elements):
        """Правка сценария: ANSWER-1.md с маркером мандата в каталоге
        документов — его унесёт автокоммит шага developer."""
        def put():
            t.docs.mkdir(parents=True, exist_ok=True)
            (t.docs / "ANSWER-1.md").write_text(
                f"{MANDATE_MARKER} {', '.join(elements)}\n", encoding="utf-8")
        return put

    # --- наблюдения -----------------------------------------------------

    def state(self, t) -> str:
        return store.get_task(self.conn, t.id)["state"]

    def explain(self, rows: list, output: str) -> str:
        runs = "\n".join(f"{r['kind']} {r['side']} full={r['full']} "
                         f"files={r['files']} timeout={r['timeout']}"
                         for r in self.runs)
        return self.note(
            f"записи: {[(r['action'], r['detail']) for r in rows]}\n"
            f"вывод: {output[-3000:]}\nзапуски:\n{runs}\n"
            f"полный набор: {[(c['side'], c['fresh']) for c in self.suite_calls]}")

    @staticmethod
    def details(rows: list, action: str) -> list:
        return [r["detail"] or "" for r in rows if r["action"] == action]

    @staticmethod
    def gate_rows(rows: list) -> list:
        return [r for r in rows if GATE_WORDS in (r["action"] or "")
                or GATE_WORDS in (r["detail"] or "")]

    def refusal(self, rows: list, output: str, action: str) -> str:
        """Деталь последней записи `action`; провал — записи нет, есть
        запись другого действия гейта исходов, либо задача ушла из
        `in_dev`."""
        found = self.details(rows, action)
        self.assertTrue(found, f"advance не записал «{action}»:\n"
                        + self.explain(rows, output))
        others = [a for a in GATE_ACTIONS if a != action and self.details(rows, a)]
        self.assertEqual(others, [], self.explain(rows, output))
        self.assertEqual(self.state_of(rows), "in_dev", self.explain(rows, output))
        return found[-1]

    def state_of(self, rows: list) -> str:
        tid = self.current
        return store.get_task(self.conn, tid)["state"]

    def no_gate_refusal(self, rows: list, output: str) -> None:
        for action in GATE_ACTIONS:
            self.assertEqual(self.details(rows, action), [],
                             self.explain(rows, output))

    def subset_runs(self, side: str | None = None) -> list:
        return [r for r in self.runs if not r["full"] and not r["plank"]
                and (side is None or r["side"] == side)]

    def full_runs(self) -> list:
        return [r for r in self.runs if r["full"] and not r["plank"]
                and r["side"] in ("base", "head")]

    def lines_with(self, detail: str, text: str) -> list:
        return [line for line in detail.splitlines() if text in line]

    def task(self, project, canary: bool = False):
        t = self.in_dev_task(project, canary=canary)
        self.current = t.id
        return t
