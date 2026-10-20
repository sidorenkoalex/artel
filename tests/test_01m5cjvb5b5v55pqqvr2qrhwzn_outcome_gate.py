"""Гейт неослабления по исходам на переходе `in_dev -> verifying`: `PASS_TO_PASS`, перепрогоны, сравнение отчётов, мандат, отказы и журнал.

Группа: долгоживущий
Красен до реализации: гейта исходов нет — `advance` из `in_dev` у компонента `components:` с `report` не гоняет полный набор на выписках базы и головы, не перепрогоняет красные тесты, не сравнивает отчёты, не пишет ни отказов «переход отклонён: гейт неослабления по исходам…», ни записи пройденного гейта, ни строки «нестабилен и на базе: …» — сломанный, нестабильный, исчезнувший и ставший пропуском тест уходит в `verifying`; зелены и на базе ветки методы, держащие отсутствие гейта и прогонов: граница (оба метода AC-1), отказ гейта по тексту без прогона исходов (первый метод AC-2) и «пропуск на ветке не перепрогоняется» (второй метод AC-6).

Стенд — настоящий git (`tests.sandbox.GitignoreCommittedRealGitSandbox`):
клон артели — корень песочницы с bare `origin`; учебный внешний проект —
`tests.sandbox.make_project_repo` со своим `origin` и записью `components:`
в `targets.yaml` песочницы (один компонент `junit-xml` на поддельном
`pytest` либо один `pult-vitest`). Задача проходит настоящий выход из
`tests_writing` (планка с тестом критерия, красным на базе), затем шаг
developer: коммит правки кода (и, по сценарию, файлов `tests/`) в кодовую
ветку, PLAN.md `ready` чекпоинтом шага, `fsm.cmd_advance`. Исход —
состояние задачи и записи журнала (действие и деталь).

Раннеры подменены без Node и без сети шпионом `subprocess.Popen`: запуск
`node_modules/.bin/vitest` (и `--version`), поддельного `pytest` вне дерева
и установки `install` записывает argv, рабочий каталог, сторону и предел
времени и пишет отчёт сценария (JSON отчётчика пульта по `--outputFile`
либо JUnit по `--junitxml`). СТОРОНА различается по выписке, не по номеру
прогона: метка — файл `app.py` в дереве прогона (`APP = 'base'` на базе,
`APP = 'head-…'` на голове кодовой ветки). Исход теста задаётся сценарием
последовательностью по стороне: первый прогон стороны, где тест есть
среди файлов раннера, — первый элемент, следующий — второй и т. д.
Прогоны полного набора (`acceptance.full_suite`) наблюдаются обёрткой
`wraps`: корень выписки, профиль, `fresh`.

Сбои подготовки — шпион `subprocess.run`: отказ git только для вызовов,
в стеке которых есть кадр модуля гейта
`orchestrator.advance_gates.outcome_integrity` (имя модуля — из требования
1 SPEC): `merge-base` (база не определена), чтение кодовой ветки (голова
не прочитана), выписка (`worktree add`/`clone`/`archive`) с sha нужной
стороны.

Мандат — `answer.cmd_answer` Оператора (ANSWER-n с маркером «Ослабление
тестов разрешено:» и матрицей неослабления) либо ANSWER, положенный
автокоммитом шага developer.

Имена проектов, файлов, тестов, числа тестов и пределы — из `random`;
зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
модуль гейта с выписками базы/головы, `PASS_TO_PASS`, перепрогонами по
записям теста, сравнением отчётов, мандатом, порядком находок, тремя
действиями и записью пройденного гейта — все методы файла зелёные.
"""
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


# ---------------------------------------------------------------- AC-1

class Ac1OutOfBoundsTest(OutcomeGateSandbox):

    def assert_no_gate(self, rows, output) -> None:
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.gate_rows(rows), [], self.explain(rows, output))
        self.assertEqual(self.full_runs(), [], self.explain(rows, output))

    def test_ac1_artel_and_test_profile_no_gate(self):
        """Артель и запись `test_profile` с `report: junit-xml`: полного набора нет, записей гейта исходов нет, переход как прежде.

        Сценарий (подслучай — свежая задача): (а) задача артели с зелёной
        планкой; (б) учебный проект с `test_profile` (`runner: pytest-own`,
        `report: junit-xml`) и тестом, который на ветке падает. Шаг
        developer, `advance` из `in_dev`: `acceptance.full_suite` не
        звался, раннер полного набора на выписке не запускался, ни одной
        записи с «по исходам», в (б) — «приёмочные тесты пройдены» и
        `verifying`.

        Ловит мутацию: граница по `reported(profile)` без
        `from_components` — у `test_profile` с `report` гейт создан: полный
        набор прогнан, сломанный тест даёт отказ «… — сломан правкой»;
        гейт создаётся у любого профиля — у артели звался `full_suite`.
        """
        with self.subTest(case="артель", seed=self.seed):
            t = self.artel_in_dev_task()
            self.current = t.id
            rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        with self.subTest(case="test_profile", seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name]}, test_profile=True)
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
            rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            self.assertTrue(self.details(rows, PASSED_NOTE), self.explain(rows, output))
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))

    def test_ac1_decide_skip_refusal_and_canary_no_gate(self):
        """Пропуск и отказ решения `decide` и канареечная задача: гейт исходов не создаётся.

        Сценарий (подслучай): (а) канареечная задача проекта с компонентом
        `junit-xml`, тест базы на ветке падает; (б) проект задачи без
        `test_profile` и `components:` (пропуск решения; переход доходит
        до записи пропуска гейта по тексту); (в) `decide`, позванный из
        модуля гейта, отдаёт отказ (подмена публичного
        `project_profile.decide` только для кадров гейта), тест базы на
        ветке падает. Во всех — `acceptance.full_suite` не звался, раннер
        полного набора на выписке не запускался, записей с «по исходам»
        нет; в (а) и (в) задача ушла в `verifying`.

        Ловит мутацию: условие `t["is_canary"]` пропущено — у канарейки
        полный набор прогнан и отказ «… — сломан правкой»; отказ решения
        `decide` у гейта исходов — отказ перехода (запись с «по исходам»)
        или прогон по профилю записи в обход решения — `full_suite` звался.
        """
        with self.subTest(case="канарейка", seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name]})
            t = self.task(project, canary=True)
            self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
            rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        with self.subTest(case="пропуск decide", seed=self.seed):
            project = self.bare_project()
            self.assertTrue(project_profile.decide(project.name).skip,
                            self.note("решение не пропуск"))
            tid = ulid(self.rng)
            branch = f"task/{tid.lower()}-{self.word()}"
            store.insert_task(self.conn, tid, "Фикстура", "in_dev", branch,
                              project.name, 25.0)
            wt, error = workspace.ensure(tid, branch)
            self.assertIsNone(error, self.note(str(error)))
            t = SimpleNamespace(id=tid, branch=branch, target=project.name,
                                wt=Path(wt), project=project,
                                docs=config.PROJECTS / project.name / TASKS_DIR / tid)
            self.current = tid
            rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            # Переход дошёл до соседа гейта: пропуск гейта по тексту записан.
            self.assertTrue(self.details(rows, TEXT_GATE_SKIP), self.explain(rows, output))
        with self.subTest(case="отказ decide", seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name]})
            t = self.task(project)
            self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
            real = project_profile.decide
            refusal = f"профиль сценария {self.word()} не прочитан"

            def decide(target, *args, **kwargs):
                if self.in_gate():
                    return project_profile.Decision(target, refusal=refusal)
                return real(target, *args, **kwargs)
            with mock.patch.object(project_profile, "decide", decide):
                rows, output = self.developer_advance(t)
            self.assert_no_gate(rows, output)
            self.assertEqual(self.state(t), "verifying", self.explain(rows, output))


# ---------------------------------------------------------------- AC-2

class Ac2PlaceTest(OutcomeGateSandbox):

    def test_ac2_text_gate_refusal_first_no_outcome_runs(self):
        """Отказ гейта неослабления по тексту — прогона исходов нет.

        Сценарий: проект `junit-xml` с двумя тестами в файле `tests/`;
        правка ветки удаляет один тест из файла без мандата. `advance`
        записывает «переход отклонён: гейт неослабления тестов»;
        `acceptance.full_suite` не звался, записей гейта исходов нет.

        Ловит мутацию: гейт исходов поставлен до гейта по тексту — полный
        набор прогнан, и отказ — «гейт неослабления по исходам» (исчезнувший
        тест), а не отказ по тексту.
        """
        rel, keep, gone = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit_project({rel: [keep, gone]})
        t = self.task(project)
        rows, output = self.developer_advance(t, {rel: py_source([keep])})
        self.assertTrue(self.details(rows, TEXT_GATE_ACTION), self.explain(rows, output))
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.gate_rows(rows), [], self.explain(rows, output))

    def test_ac2_outcome_refusal_stops_before_review_rework_gate(self):
        """Отказ гейта исходов — гейт переделки ревью не исполняется; при пройденном гейте исходов тот же REVIEW.md даёт отказ переделки.

        Сценарий (подслучай — свежая задача): после коммита кода задача
        проходит `in_dev -> review -> in_dev`, в ссылку документов ложится
        REVIEW.md `changes_requested` автокоммитом шага reviewer, шага
        developer после него нет. (а) Тест базы на ветке
        красен все три раза — отказ «… — сломан правкой», записи «переход
        отклонён: замечания ревью не отработаны» нет. (б) Все тесты зелены
        — гейт исходов пройден, отказ переделки ревью есть.

        Ловит мутацию: гейт исходов поставлен после гейта переделки ревью —
        в (а) отказ переделки ревью вместо отказа гейта исходов.
        """
        for label in ("сломан", "зелёный"):
            with self.subTest(case=label, seed=self.seed):
                rel, name = self.py_rel(), self.py_name()
                project = self.junit_project({rel: [name]})
                t = self.task(project)
                if label == "сломан":
                    self.cases[(rel, name)] = {"base": ["passed"],
                                               "head": ["failed"]}

                def review():
                    store.set_state(self.conn, t.id, "review", "fsm",
                                    expected_state="in_dev",
                                    detail="сценарий: на ревью")
                    t.docs.mkdir(parents=True, exist_ok=True)
                    (t.docs / "REVIEW.md").write_text(
                        REVIEW_CHANGES.format(task=t.id, word=self.word()),
                        encoding="utf-8")
                    store.journal(self.conn, t.id, "reviewer",
                                  "agent run started", "шаг сценария")
                    checkpoint.commit_step_artifacts(self.conn, t.id, "reviewer")
                    store.set_state(self.conn, t.id, "in_dev", "fsm",
                                    expected_state="review",
                                    detail="сценарий: замечания ревью")
                rows, output = self.developer_advance(t, before=review)
                if label == "сломан":
                    self.refusal(rows, output, BROKEN_ACTION)
                    self.assertEqual(self.details(rows, REWORK_ACTION), [],
                                     self.explain(rows, output))
                else:
                    self.no_gate_refusal(rows, output)
                    self.assertTrue(self.details(rows, REWORK_ACTION),
                                    self.explain(rows, output))


# ---------------------------------------------------------------- AC-3

class Ac3RunsTest(OutcomeGateSandbox):

    def test_ac3_full_suite_on_base_and_head_checkouts_fresh(self):
        """Полный набор компонента — дважды, `fresh=True`, на отдельных выписках базы и головы; сторона — по метке дерева.

        Сценарий: проект `junit-xml` с двумя-тремя файлами тестов, все
        зелёные на обеих сторонах. `acceptance.full_suite` позван ровно
        дважды, оба раза с `fresh=True` и профилем компонента; корни — два
        разных каталога, ни один не рабочая копия задачи; метка одного
        корня — база, другого — голова; раннер компонента запущен полным
        набором по разу на каждой стороне; гейт пройден, отказа нет.

        Ловит мутацию: голова гоняется в рабочей копии задачи — корень
        совпадает с рабочей копией; база гоняется на дереве головы (одна
        выписка дважды) — обе метки «head»; `fresh` не передан — `False`
        в вызове.
        """
        tests = {self.py_rel(): [self.py_name() for _ in range(2)]
                 for _ in range(self.rng.randint(2, 3))}
        project = self.junit_project(tests)
        t = self.task(project)
        rows, output = self.developer_advance(t)
        self.no_gate_refusal(rows, output)
        calls = self.suite_calls
        self.assertEqual(len(calls), 2, self.explain(rows, output))
        self.assertTrue(all(c["fresh"] is True for c in calls), self.explain(rows, output))
        self.assertEqual(sorted(c["side"] for c in calls), ["base", "head"],
                         self.explain(rows, output))
        roots = {os.path.realpath(c["root"]) for c in calls}
        self.assertEqual(len(roots), 2, self.explain(rows, output))
        self.assertNotIn(os.path.realpath(t.wt), roots, self.explain(rows, output))
        for c in calls:
            self.assertEqual(getattr(c["command"], "component", None),
                             project.comp, self.explain(rows, output))
        sides = sorted(r["side"] for r in self.full_runs())
        self.assertEqual(sides, ["base", "head"], self.explain(rows, output))


# ---------------------------------------------------------------- AC-4

class Ac4PrepareTest(OutcomeGateSandbox):

    def prepared(self, git_fail=None, timeout_when=None, no_report_when=None):
        rel, name = self.py_rel(), self.py_name()
        project = self.junit_project({rel: [name]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
        clone = t.project.clone
        base = self.git("-C", str(clone), "merge-base",
                        f"origin/{config.MAIN_BRANCH}", t.branch).strip()
        self.git_fail = git_fail(t, base) if git_fail else None
        self.timeout_when = timeout_when
        self.no_report_when = no_report_when
        return t

    def assert_prepare(self, t, rows, output, side_words=()) -> str:
        detail = self.refusal(rows, output, PREPARE_ACTION)
        self.assertTrue(detail.strip(), self.explain(rows, output))
        self.assertEqual(self.subset_runs(), [], self.explain(rows, output))
        self.assertNotEqual(self.state(t), "verifying", self.explain(rows, output))
        if side_words:
            low = detail.lower()
            self.assertTrue(any(w in low for w in side_words),
                            self.explain(rows, output))
        return detail

    def test_ac4_git_preparation_failures_refuse(self):
        """Сбой подготовки git — отказ «… — подготовка» с причиной, без сравнения и без перепрогонов.

        Сценарий (подслучай — свежая задача, тест базы на ветке красен):
        git отказывает только вызовам из модуля гейта — (а) `merge-base`
        (база `diff_base` не определена); (б) любое чтение кодовой ветки,
        кроме `merge-base` (голова не прочитана); (в) выписка с sha базы;
        (г) выписка с sha головы (или по имени ветки). В каждом —
        отказ «переход отклонён: гейт неослабления по исходам —
        подготовка» с непустой деталью, ни «… — сломан правкой», ни общего
        отказа, перепрогонов нет, задача не в `verifying`.

        Ловит мутацию: `None` от `diff_base` или пустая голова — гейт
        пропущен (задача уходит дальше без отказа); сбой выписки
        проглочен — сравнение по одной стороне даёт «сломан правкой» или
        проход.
        """
        def merge_base(t, base):
            return lambda args: "merge-base" in args

        def head_read(t, base):
            return lambda args: "merge-base" not in args and any(
                t.branch in a for a in args)

        def checkout(side):
            def rule(t, base):
                head = self.git("-C", str(t.project.clone), "rev-parse",
                                t.branch).strip()
                wanted = base if side == "base" else head

                def fail(args):
                    making = ("worktree" in args and "add" in args) or \
                        "clone" in args or "archive" in args
                    return making and any(
                        wanted in a or (side == "head" and t.branch in a)
                        for a in args)
                return fail
            return rule

        cases = (("база не определена", merge_base),
                 ("голова не прочитана", head_read),
                 ("выписка базы", checkout("base")),
                 ("выписка головы", checkout("head")))
        for label, rule in cases:
            with self.subTest(case=label, seed=self.seed):
                t = self.prepared(git_fail=rule)
                rows, output = self.developer_advance(t)
                self.git_fail = None
                self.assert_prepare(t, rows, output)

    def test_ac4_side_not_started_or_timeout_refuses_naming_side(self):
        """Исход стороны «неизвестно/не начат» или таймаут на базе либо на ветке — отказ подготовки, названа сторона.

        Сценарий (подслучай — свежая задача, тест базы на ветке красен):
        (а) раннер полного набора на базе не пишет отчёт (исход
        «неизвестно»); (б) то же на голове; (в) полный прогон базы
        превышает предел; (г) то же на голове. Отказ «… — подготовка»,
        деталь называет сторону («баз…» либо «ветк…»/«голов…»),
        перепрогонов нет, отказа «… — сломан правкой» нет.

        Ловит мутацию: «неизвестно» на базе принят за пустой отчёт — набор
        `PASS_TO_PASS` пуст, гейт пройден; таймаут головы принят за
        красный прогон — находки «сломан правкой» вместо отказа подготовки;
        сторона в отказе не названа.
        """
        base_words, head_words = ("баз",), ("ветк", "голов")
        cases = (("неизвестно база", "base", "report", base_words),
                 ("неизвестно голова", "head", "report", head_words),
                 ("таймаут база", "base", "timeout", base_words),
                 ("таймаут голова", "head", "timeout", head_words))
        for label, side, kind, words in cases:
            with self.subTest(case=label, seed=self.seed):
                def pick(run, side=side):
                    return run["full"] and not run["plank"] and run["side"] == side
                t = self.prepared(timeout_when=pick if kind == "timeout" else None,
                                  no_report_when=pick if kind == "report" else None)
                rows, output = self.developer_advance(t)
                self.timeout_when = self.no_report_when = None
                self.assert_prepare(t, rows, output, words)


# ---------------------------------------------------------------- AC-5

class Ac5PassToPassTest(OutcomeGateSandbox):

    def test_ac5_retried_on_base_not_in_pass_to_pass(self):
        """Тест, прошедший на базе с повтором, — вне `PASS_TO_PASS`: красный на ветке не находка и не перепрогоняется (`pult-vitest` и `junit-xml`).

        Сценарий (подслучай): (а) `pult-vitest`: на базе тест `pass` с
        `retry_count: 1`, на ветке — `fail`; соседний тест зелён везде.
        Отказов гейта исходов нет, перепрогонов нет. (б) Контроль — тот же
        тест без повтора на базе: отказ «… — сломан правкой».

        Ловит мутацию: в набор берётся любой `passed` базы без сверки
        `retries == 0` — в (а) тест перепрогоняется и даёт «сломан
        правкой».
        """
        for retried in (True, False):
            with self.subTest(retried=retried, seed=self.seed):
                rel, name, other = self.js_rel(), self.js_name(), self.js_name()
                project = self.vitest_project({rel: [name, other]})
                t = self.task(project)
                self.cases[(rel, name)] = {
                    "base": ["retried" if retried else "passed", "passed"],
                    "head": ["failed"]}
                rows, output = self.developer_advance(t)
                if retried:
                    self.no_gate_refusal(rows, output)
                    self.assertEqual(self.subset_runs(), [], self.explain(rows, output))
                else:
                    detail = self.refusal(rows, output, BROKEN_ACTION)
                    self.assertIn(self.case_id(project, rel, name), detail,
                                  self.explain(rows, output))

    def test_ac5_no_tests_on_base_empty_pass_to_pass(self):
        """«Нет тестов» на базе — `PASS_TO_PASS` пуст: новый красный тест ветки не находка.

        Сценарий: проект `junit-xml` без каталога `tests/` на базе; ветка
        добавляет файл `tests/` с тестом, который на ветке падает. Полный
        набор прогнан на обеих сторонах, отказа гейта исходов нет,
        перепрогонов нет.

        Ловит мутацию: «нет тестов» базы принят за отказ подготовки или за
        «все тесты исчезли» — отказ гейта исходов на ветке без единой
        находки по `PASS_TO_PASS`.
        """
        project = self.junit_project({})
        t = self.task(project)
        rel, name = self.py_rel(), self.py_name()
        self.cases[(rel, name)] = {"head": ["failed"]}
        rows, output = self.developer_advance(t, {rel: py_source([name])})
        self.no_gate_refusal(rows, output)
        self.assertEqual(len(self.suite_calls), 2, self.explain(rows, output))
        self.assertEqual(self.subset_runs(), [], self.explain(rows, output))


# ---------------------------------------------------------------- AC-6

class Ac6RerunTest(OutcomeGateSandbox):

    def test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit(self):
        """Красный на ветке (`failed`, `error`, `passed` с повтором) — по два перепрогона на ветке и на базе только по своему файлу, с пределом компонента.

        Сценарий (подслучай — свежая задача): у компонента
        `full_suite_timeout_sec` из `random`; два-три файла тестов, тест
        первого файла на ветке — (а) `failed` (`junit-xml`); (б) `error`
        (`junit-xml`); (в) `passed` с `retry_count: 1` (`pult-vitest`);
        перепрогоны зелёные на обеих сторонах. Перепрогонов ветки — два,
        базы — два; каждый передаёт раннеру только файл красного теста;
        предел каждого — `full_suite_timeout_sec` компонента.

        Ловит мутацию: перепрогон по всем файлам набора — в запуске файлы
        других тестов; перепрогон базы пропущен — перепрогонов базы ноль;
        предел — `config.FULL_SUITE_TIMEOUT_SEC` либо предел приёмки — не
        тот предел в запуске; `passed` с повтором не считается красным —
        перепрогонов нет.
        """
        for kind in ("failed", "error", "retried"):
            with self.subTest(kind=kind, seed=self.seed):
                limit = self.rng.randint(300, 900)
                vitest = kind == "retried"
                rel_of = self.js_rel if vitest else self.py_rel
                name_of = self.js_name if vitest else self.py_name
                tests = {rel_of(): [name_of()] for _ in range(self.rng.randint(2, 3))}
                (rel, (name,)), = list(tests.items())[:1]
                project = (self.vitest_project(tests, limit=limit) if vitest
                           else self.junit_project(tests, limit=limit))
                t = self.task(project)
                self.cases[(rel, name)] = {"base": ["passed"],
                                           "head": [kind, "passed"]}
                rows, output = self.developer_advance(t)
                for side in ("head", "base"):
                    runs = self.subset_runs(side)
                    self.assertEqual(len(runs), 2, self.explain(rows, output))
                    for run in runs:
                        self.assertEqual(run["files"], [rel], self.explain(rows, output))
                        self.assertEqual(run["timeout"], limit, self.explain(rows, output))

    def test_ac6_skipped_on_branch_not_rerun(self):
        """Тест `PASS_TO_PASS`, ставший на ветке `skipped`, не перепрогоняется.

        Сценарий: проект `junit-xml`; тест базы зелён, на ветке — пропуск.
        Перепрогонов нет ни на одной стороне (находка «стал пропуском» —
        предмет AC-9).

        Ловит мутацию: `skipped` на ветке считается красным — тест
        перепрогоняется дважды на каждой стороне.
        """
        rel, name, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit_project({rel: [name, other]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["skipped"]}
        rows, output = self.developer_advance(t)
        self.assertEqual(self.subset_runs(), [], self.explain(rows, output))


# ---------------------------------------------------------------- AC-7

class Ac7RerunPrepareTest(OutcomeGateSandbox):

    def test_ac7_rerun_preparation_refusals(self):
        """Отказ подготовки перепрогона: `pult-vitest` без `select`, исход перепрогона не «зелёный» и не «красный», пропуск или нет записи на перепрогоне базы.

        Сценарий (подслучай — свежая задача, тест базы на ветке красен):
        (а) компонент `pult-vitest`, с записи которого после выхода из
        `tests_writing` снят `select`; (б) перепрогон ветки без
        отчёта (исход «неизвестно»); (в) перепрогон ветки превышает предел;
        (г) на перепрогоне базы запись теста `skipped`; (д) на перепрогоне
        базы записи теста нет. В каждом — отказ «переход отклонён: гейт
        неослабления по исходам — подготовка», находки «сломан правкой»
        нет.

        Ловит мутацию: без `select` перепрогон идёт полным набором — отказа
        подготовки нет; «неизвестно»/предел перепрогона принят за красный —
        отказ «сломан правкой»; пропуск или отсутствие записи на базе
        принят за красный базы — «нестабилен и на базе», гейт пройден.
        """
        def rerun_head(run):
            return not run["full"] and not run["plank"] and run["side"] == "head"

        cases = ("без select", "неизвестно", "таймаут", "база пропуск",
                 "база нет записи")
        for label in cases:
            with self.subTest(case=label, seed=self.seed):
                vitest = label == "без select"
                rel = self.js_rel() if vitest else self.py_rel()
                name = self.js_name() if vitest else self.py_name()
                project = (self.vitest_project({rel: [name]}) if vitest
                           else self.junit_project({rel: [name]}))
                t = self.task(project)
                if vitest:
                    # Выход из `tests_writing` гоняет планку подмножеством —
                    # `select` снимается с записи после него.
                    self.drop_select()
                base = {"база пропуск": ["passed", "skipped"],
                        "база нет записи": ["passed", "missing"]}.get(
                            label, ["passed"])
                self.cases[(rel, name)] = {"base": base, "head": ["failed"]}
                self.no_report_when = rerun_head if label == "неизвестно" else None
                self.timeout_when = rerun_head if label == "таймаут" else None
                rows, output = self.developer_advance(t)
                self.no_report_when = self.timeout_when = None
                self.refusal(rows, output, PREPARE_ACTION)

    def test_ac7_branch_rerun_red_kinds(self):
        """На перепрогоне ветки `failed`, `error`, `passed` с повтором, `skipped` или нет записи — красный этого прогона: трижды красный — «сломан правкой».

        Сценарий (подслучай — свежая задача): тест базы зелён на базе
        трижды, на ветке полный прогон — `failed`, оба перепрогона ветки —
        (а) `failed`, (б) `error`, (в) `skipped`, (г) нет записи (`junit-
        xml`), (д) `passed` с `retry_count: 1` (`pult-vitest`). Отказ «… —
        сломан правкой» с идентификатором теста.

        Ловит мутацию: `skipped` или отсутствие записи на перепрогоне ветки
        — зелёный либо отказ подготовки; `passed` с повтором — зелёный;
        итог — «нестабилен после правки» (общий отказ) вместо «сломан
        правкой».
        """
        for kind in ("failed", "error", "skipped", "missing", "retried"):
            with self.subTest(kind=kind, seed=self.seed):
                vitest = kind == "retried"
                rel = self.js_rel() if vitest else self.py_rel()
                name = self.js_name() if vitest else self.py_name()
                project = (self.vitest_project({rel: [name]}) if vitest
                           else self.junit_project({rel: [name]}))
                t = self.task(project)
                self.cases[(rel, name)] = {"base": ["passed"],
                                           "head": ["failed", kind]}
                rows, output = self.developer_advance(t)
                detail = self.refusal(rows, output, BROKEN_ACTION)
                self.assertIn(self.case_id(project, rel, name), detail,
                              self.explain(rows, output))


# ---------------------------------------------------------------- AC-8

class Ac8VerdictByRecordTest(OutcomeGateSandbox):

    def test_ac8_broken_unstable_and_flaky_on_base(self):
        """«Сломан правкой», «нестабилен после правки» и «нестабилен и на базе» по исходам трёх прогонов.

        Сценарий (подслучай — свежая задача, проект `junit-xml`): (а) на
        ветке красный трижды, база зелёна трижды — отказ «… — сломан
        правкой» с идентификатором; (б) на ветке красный, затем зелёный
        (порядок из `random`) — общий отказ «переход отклонён: гейт
        неослабления по исходам» с идентификатором; (в) на ветке трижды
        красный, база красна на одном из перепрогонов (`failed` или
        `error`) — отказа гейта исходов нет, в журнале строка «нестабилен и
        на базе: <идентификатор>».

        Ловит мутацию: «нестабилен» не отличается от «сломан» — в (б)
        действие «… — сломан правкой»; красная база перепрогона не читается
        — в (в) отказ «сломан правкой»; строка о базе не пишется — её нет
        в журнале.
        """
        for label in ("сломан", "нестабилен", "база"):
            with self.subTest(case=label, seed=self.seed):
                rel, name = self.py_rel(), self.py_name()
                project = self.junit_project({rel: [name, self.py_name()]})
                t = self.task(project)
                tid = self.case_id(project, rel, name)
                head = ["failed", "failed", "failed"]
                base = ["passed", "passed", "passed"]
                if label == "нестабилен":
                    head[self.rng.choice((1, 2))] = "passed"
                if label == "база":
                    base[self.rng.choice((1, 2))] = self.rng.choice(("failed", "error"))
                self.cases[(rel, name)] = {"base": base, "head": head}
                rows, output = self.developer_advance(t)
                if label == "сломан":
                    self.assertIn(tid, self.refusal(rows, output, BROKEN_ACTION),
                                  self.explain(rows, output))
                elif label == "нестабилен":
                    self.assertIn(tid, self.refusal(rows, output, OUTCOME_ACTION),
                                  self.explain(rows, output))
                else:
                    self.no_gate_refusal(rows, output)
                    texts = [f"{r['action']} {r['detail'] or ''}" for r in rows]
                    self.assertTrue(any(FLAKY_ON_BASE + tid in x for x in texts),
                                    self.explain(rows, output))

    def test_ac8_neighbour_red_in_same_file_does_not_redden_rerun(self):
        """Итог перепрогона — по записи теста: красный сосед в том же файле не делает зелёную запись красной.

        Сценарий: в одном файле тест A (`PASS_TO_PASS`) и сосед B, красный
        на базе и на ветке во всех прогонах. A на ветке: полный прогон —
        `failed`, оба перепрогона — `passed`; на базе A зелён. Итог A —
        «нестабилен после правки»: общий отказ с идентификатором A, не
        «… — сломан правкой» и не «нестабилен и на базе».

        Ловит мутацию: итог перепрогона по вердикту прогона (красный из-за
        B) — A красен трижды на ветке и база красна — отказа гейта нет или
        отказ «сломан правкой».
        """
        rel, a, b = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit_project({rel: [a, b]})
        t = self.task(project)
        self.cases[(rel, a)] = {"base": ["passed"], "head": ["failed", "passed"]}
        self.cases[(rel, b)] = {"base": ["failed"], "head": ["failed"]}
        rows, output = self.developer_advance(t)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertIn(self.case_id(project, rel, a), detail, self.explain(rows, output))
        self.assertNotIn(self.case_id(project, rel, b), detail, self.explain(rows, output))


# ---------------------------------------------------------------- AC-9

class Ac9CompareTest(OutcomeGateSandbox):

    def test_ac9_vitest_records_findings_and_non_findings(self):
        """Сравнение записей `pult-vitest`: исчезнувший, ставший пропуском, `todo`/`fails` появились, новый пропуск/`todo`/`fails` — находки; неизменные `todo`/`fails` — нет.

        Сценарий: один проект `pult-vitest`, один отказ. База: `gone`
        (`pass`, на ветке файла нет теста), `s_pass`/`s_fail`/`s_err`
        (`pass`/`fail AssertionError`/`fail TypeError`, на ветке `skip`),
        `to_todo` (`pass`, на ветке `todo`), `to_fails` (`pass`, на ветке
        `pass` с `fails`), `keep_todo` (`todo` на обеих сторонах),
        `keep_fails` (`pass` с `fails` на обеих), `quiet` (зелёный везде).
        Ветка добавляет `new_skip`, `new_todo`, `new_fails`, `new_pass`.
        Общий отказ «… по исходам»: идентификаторы всех находок — в детали,
        каждый ровно одной строкой; `keep_todo`, `keep_fails`, `quiet`,
        `new_pass` в детали нет. Деталь несёт итоговую строку о росте
        пропусков без идентификатора теста.

        Ловит мутацию: «стал пропуском» только у `passed` базы — у `s_fail`/
        `s_err` нет находки; `todo`/`fails` — находка без сверки с базой —
        `keep_todo`/`keep_fails` в отказе; новый идентификатор не
        проверяется — `new_*` нет в детали; у `to_todo` две находки (пропуск
        и `todo`) — две строки; рост пропусков — отдельные строки по
        тестам без итоговой.
        """
        rel, gone_rel = self.js_rel(), self.js_rel()
        n = {k: self.js_name() for k in (
            "gone", "s_pass", "s_fail", "s_err", "to_todo", "to_fails",
            "keep_todo", "keep_fails", "quiet", "new_skip", "new_todo",
            "new_fails", "new_pass")}
        base_names = [n[k] for k in ("s_pass", "s_fail", "s_err", "to_todo",
                                     "to_fails", "keep_todo", "keep_fails",
                                     "quiet")]
        project = self.vitest_project({rel: base_names, gone_rel: [n["gone"]]})
        t = self.task(project)
        plan = {"s_pass": ("passed", "skipped"), "s_fail": ("failed", "skipped"),
                "s_err": ("error", "skipped"), "to_todo": ("passed", "todo"),
                "to_fails": ("passed", "fails"), "keep_todo": ("todo", "todo"),
                "keep_fails": ("fails", "fails"),
                "new_skip": ("passed", "skipped"), "new_todo": ("passed", "todo"),
                "new_fails": ("passed", "fails")}
        for key, (base, head) in plan.items():
            self.cases[(rel, n[key])] = {"base": [base], "head": [head]}
        head_names = base_names + [n[k] for k in ("new_skip", "new_todo",
                                                  "new_fails", "new_pass")]
        rows, output = self.developer_advance(t, {rel: js_source(head_names),
                                                  gone_rel: js_source([])})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        found = ("s_pass", "s_fail", "s_err", "to_todo", "to_fails",
                 "new_skip", "new_todo", "new_fails")
        for key in found:
            cid = self.case_id(project, rel, n[key])
            self.assertEqual(len(self.lines_with(detail, cid)), 1,
                             self.explain(rows, output) + f"\n{key}: {cid}")
        gone = self.case_id(project, gone_rel, n["gone"])
        self.assertEqual(len(self.lines_with(detail, gone)), 1, self.explain(rows, output))
        for key in ("keep_todo", "keep_fails", "quiet", "new_pass"):
            self.assertNotIn(self.case_id(project, rel, n[key]), detail,
                             self.explain(rows, output) + f"\n{key}")
        ids = [self.case_id(project, rel, x) for x in n.values()] + [gone]
        summary = [line for line in detail.splitlines() if "пропуск" in line.lower()
                   and not any(cid in line for cid in ids)]
        self.assertTrue(summary, self.explain(rows, output))

    def test_ac9_junit_records_findings(self):
        """Сравнение записей `junit-xml`: исчезнувший тест и тест базы `passed`/`failed`/`error`, ставший пропуском, — находки; новый пропуск — находка.

        Сценарий: проект `junit-xml`; тест `gone` исчез из отчёта ветки
        (записи нет, текст файла не менялся), `s_pass`/`s_fail`/`s_err` на
        ветке `skipped`, новый тест ветки `new_skip` — пропуск, новый
        `new_pass` — зелёный. Общий отказ: идентификаторы `gone`, `s_*`,
        `new_skip` — каждый одной строкой; `new_pass` в детали нет.

        Ловит мутацию: исчезновение ищется только по тексту файлов
        (гейт по тексту), а не по отчёту — `gone` без находки; «стал
        пропуском» только у `passed` — `s_fail`/`s_err` без находки.
        """
        rel = self.py_rel()
        n = {k: self.py_name() for k in ("gone", "s_pass", "s_fail", "s_err",
                                         "new_skip", "new_pass")}
        base_names = [n[k] for k in ("gone", "s_pass", "s_fail", "s_err")]
        project = self.junit_project({rel: base_names})
        t = self.task(project)
        plan = {"gone": ("passed", "missing"), "s_pass": ("passed", "skipped"),
                "s_fail": ("failed", "skipped"), "s_err": ("error", "skipped")}
        for key, (base, head) in plan.items():
            self.cases[(rel, n[key])] = {"base": [base], "head": [head]}
        new_rel = self.py_rel()
        self.cases[(new_rel, n["new_skip"])] = {"head": ["skipped"]}
        rows, output = self.developer_advance(
            t, {new_rel: py_source([n["new_skip"], n["new_pass"]])})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        for key in ("gone", "s_pass", "s_fail", "s_err"):
            cid = self.case_id(project, rel, n[key])
            self.assertEqual(len(self.lines_with(detail, cid)), 1,
                             self.explain(rows, output) + f"\n{key}")
        self.assertEqual(len(self.lines_with(
            detail, self.case_id(project, new_rel, n["new_skip"]))), 1,
            self.explain(rows, output))
        self.assertNotIn(self.case_id(project, new_rel, n["new_pass"]), detail,
                         self.explain(rows, output))

    def test_ac9_one_finding_per_id_senior_kind(self):
        """Один идентификатор — одна находка, старшая: красный трижды тест, у которого появилось `fails`, — только «сломан правкой».

        Сценарий: `pult-vitest`; тест базы `pass` без `fails`; на ветке
        все три прогона — `fail` с `fails: true`. Отказ — действие «… —
        сломан правкой» (непокрытые находки только этого вида),
        идентификатор теста — ровно в одной строке детали.

        Ловит мутацию: находка сравнения («появилось `fails`») добавляется
        к находке «сломан правкой» — две находки, действие общего отказа и
        две строки с идентификатором.
        """
        rel, name = self.js_rel(), self.js_name()
        project = self.vitest_project({rel: [name, self.js_name()]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
        with mock.patch.dict(VITEST_KIND, {"failed": {
                "state": "fail", "error_name": "AssertionError", "fails": True}}):
            rows, output = self.developer_advance(t)
        detail = self.refusal(rows, output, BROKEN_ACTION)
        self.assertEqual(len(self.lines_with(detail, self.case_id(project, rel, name))),
                         1, self.explain(rows, output))


# --------------------------------------------------------------- AC-10

class Ac10OrderTest(OutcomeGateSandbox):

    def test_ac10_findings_order_and_one_line_each(self):
        """Порядок находок одного отказа: исчезнувшие → «сломан правкой» → «нестабилен после правки» → прочие; внутри вида — по идентификатору.

        Сценарий: проект `junit-xml`; по два теста каждого вида в
        случайных файлах: исчезнувшие из отчёта ветки, трижды красные на
        ветке, красные один раз из трёх, ставшие пропуском. Общий отказ;
        строки с идентификаторами идут видами в указанном порядке, внутри
        вида — по возрастанию идентификатора; у каждой находки своя
        строка, не несущая идентификатора другой находки.

        Ловит мутацию: находки в порядке отчёта или в порядке сравнения
        (прочие раньше красных) — порядок строк другой; внутри вида без
        сортировки — пары идут в порядке файлов; все находки одной
        строкой.
        """
        kinds = ("gone", "broken", "unstable", "skip")
        names = {k: [(self.py_rel(), self.py_name()) for _ in range(2)]
                 for k in kinds}
        tests: dict = {}
        for items in names.values():
            for rel, name in items:
                tests.setdefault(rel, []).append(name)
        project = self.junit_project(tests)
        t = self.task(project)
        plan = {"gone": {"base": ["passed"], "head": ["missing"]},
                "broken": {"base": ["passed"], "head": ["failed"]},
                "unstable": {"base": ["passed"], "head": ["failed", "passed"]},
                "skip": {"base": ["passed"], "head": ["skipped"]}}
        for kind, items in names.items():
            for rel, name in items:
                self.cases[(rel, name)] = plan[kind]
        rows, output = self.developer_advance(t)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        lines = detail.splitlines()
        ids = {k: sorted(self.case_id(project, r, n) for r, n in items)
               for k, items in names.items()}
        expected = [cid for k in kinds for cid in ids[k]]
        every = set(expected)
        position = []
        for cid in expected:
            found = [i for i, line in enumerate(lines) if cid in line]
            self.assertEqual(len(found), 1, self.explain(rows, output) + f"\n{cid}")
            others = [o for o in every if o != cid and o in lines[found[0]]]
            self.assertEqual(others, [], self.explain(rows, output))
            position.append(found[0])
        self.assertEqual(position, sorted(position), self.explain(rows, output))


# --------------------------------------------------------------- AC-11

class Ac11MandateTest(OutcomeGateSandbox):

    def broken_task(self, names):
        """Проект `junit-xml` с классами тестов в одном файле; тесты
        `names` — трижды красные на ветке."""
        rel = self.py_rel()
        project = self.junit_project({rel: names + [self.py_name()]})
        t = self.task(project)
        for name in names:
            self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
        return project, t, rel

    def test_ac11_file_and_prefix_mandate_cover_findings(self):
        """Мандат Оператора на путь файла и на префикс `путь::Класс`/`путь::Класс::метод` снимает находки этого файла; мандат на другой файл — нет.

        Сценарий (подслучай — свежая задача, тесты класса `K` трижды
        красные на ветке): ANSWER Оператора с маркером «Ослабление тестов
        разрешено:» (а) на путь файла; (б) на `путь::K`; (в) на
        `путь::K::test_x` при единственном красном `K::test_x[a]`/`[b]`
        (варианты); (г) на путь другого файла. В (а)–(в) отказа гейта
        исходов нет; в (г) — отказ «… — сломан правкой».

        Ловит мутацию: мандат сверяется точным равенством с
        идентификатором — префикс класса и метод с вариантами не покрывают;
        покрытие по имени файла без пути — мандат другого файла покрывает.
        """
        for label in ("файл", "класс", "метод", "другой файл"):
            with self.subTest(case=label, seed=self.seed):
                klass = "K" + self.word().capitalize()
                method = self.py_name()
                if label == "метод":
                    names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
                else:
                    names = [f"{klass}{SEP}{self.py_name()}" for _ in range(2)]
                project, t, rel = self.broken_task(names)
                element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
                           "метод": f"{rel}{SEP}{klass}{SEP}{method}",
                           "другой файл": self.py_rel()}[label]
                self.operator_mandate(t, [element])
                rows, output = self.developer_advance(t, finished=True)
                if label == "другой файл":
                    self.refusal(rows, output, BROKEN_ACTION)
                else:
                    self.no_gate_refusal(rows, output)

    def test_ac11_prefix_needs_separator_after_it(self):
        """Префикс `путь::Класс` не покрывает `путь::КлассДругой::метод`: за префиксом иной символ.

        Сценарий: в файле тесты классов `K<слово>` и `K<слово>Other`, оба
        трижды красные на ветке; мандат Оператора — `путь::K<слово>`. Отказ
        «… — сломан правкой»; деталь несёт идентификатор теста класса
        `K<слово>Other` и не несёт идентификатора теста класса `K<слово>`.

        Ловит мутацию: покрытие — `startswith` без сверки следующего
        символа — `K<слово>Other` покрыт, отказа нет.
        """
        klass = "K" + self.word().capitalize()
        own, other = f"{klass}{SEP}{self.py_name()}", f"{klass}Other{SEP}{self.py_name()}"
        project, t, rel = self.broken_task([own, other])
        self.operator_mandate(t, [f"{rel}{SEP}{klass}"])
        rows, output = self.developer_advance(t, finished=True)
        detail = self.refusal(rows, output, BROKEN_ACTION)
        self.assertIn(self.case_id(project, rel, other), detail, self.explain(rows, output))
        self.assertNotIn(self.case_id(project, rel, own), detail, self.explain(rows, output))

    def test_ac11_role_autocommitted_answer_does_not_cover(self):
        """ANSWER с маркером мандата, унесённый автокоммитом шага developer, находку не снимает.

        Сценарий: тест трижды красный на ветке; ANSWER-1.md с маркером
        «Ослабление тестов разрешено: <путь файла>» кладётся в каталог
        документов и уходит в ссылку автокоммитом шага developer. Отказ
        «… — сломан правкой» с идентификатором теста.

        Ловит мутацию: мандат собран без отбраковки автокоммита роли —
        находка покрыта, отказа нет.
        """
        name = self.py_name()
        project, t, rel = self.broken_task([name])
        rows, output = self.developer_advance(t, before=self.role_mandate(t, [rel]))
        self.assertIn(self.case_id(project, rel, name),
                      self.refusal(rows, output, BROKEN_ACTION),
                      self.explain(rows, output))


# --------------------------------------------------------------- AC-13

class Ac13PassedRecordTest(OutcomeGateSandbox):

    def test_ac13_passed_gate_journal_counts(self):
        """Пройденный гейт пишет запись с числом тестов базы и ветки, числом прошедших перепрогон, числом прогонов файлов и числом покрытых мандатом находок.

        Сценарий: проект `junit-xml`; на базе `nb` тестов (из `random`), из
        них `m` исчезают на ветке в файле под мандатом Оператора, ветка
        добавляет `k` новых зелёных; один тест трижды красен на ветке и
        красен на одном перепрогоне базы («нестабилен и на базе»). Гейт
        пройден; среди новых записей журнала есть запись, несущая отдельными
        числами `nb`, число тестов ветки, 1 (тестов прошедших перепрогон),
        4 (прогонов файлов) и `m` (покрытых находок).

        Ловит мутацию: запись пройденного гейта не пишется — записи с
        числами нет; число покрытых мандатом находок не указано — нет
        числа `m`; прогоны файлов не посчитаны — нет числа 4.
        """
        nb = self.rng.randint(11, 19)
        m = self.rng.randint(2, 3)
        k = self.rng.randint(21, 29)
        covered = self.py_rel()
        gone = [self.py_name() for _ in range(m)]
        flaky_rel, flaky = self.py_rel(), self.py_name()
        rest_rel = self.py_rel()
        rest = [self.py_name() for _ in range(nb - m - 1)]
        tests = {covered: gone, flaky_rel: [flaky], rest_rel: rest}
        project = self.junit_project(tests)
        t = self.task(project)
        self.cases[(flaky_rel, flaky)] = {"base": ["passed", "failed", "passed"],
                                          "head": ["failed"]}
        new_rel = self.py_rel()
        added = [self.py_name() for _ in range(k)]
        self.operator_mandate(t, [covered])
        rows, output = self.developer_advance(
            t, {covered: None, new_rel: py_source(added)}, finished=True)
        self.no_gate_refusal(rows, output)
        nh = nb - m + k
        wanted = (nb, nh, 1, 4, m)

        def numbers(row) -> set:
            text = f"{row['action']} {row['detail'] or ''}"
            return {int(x) for x in re.findall(r"(?<![\w.:-])\d+(?![\w.:-])", text)}
        self.assertTrue(any(set(wanted) <= numbers(r) for r in rows),
                        self.explain(rows, output) + f"\nожидались числа {wanted}")


if __name__ == "__main__":
    unittest.main()
