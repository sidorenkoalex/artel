"""Команда пульта `mutation-run`: патчи мутаций против названных тестовых
файлов во временной копии и таблица «мутация → исход».

Группа: долгоживущий
Красен до реализации: команды mutation-run нет — `artel.main` отвечает «Неизвестная команда», таблицы `<id>-mutation-run-<n>.mutations.tsv` и файлов состояния `mutation-run.json`/`mutation-result.json` нет, команда не названа ни в реестре, ни в справке, ни в белом списке роли.

Стенд держит связку «команда — фоновый прогон — git — pytest»: настоящий git
(`tests/sandbox.py::RealGitSandbox`), внешний проект песочницы с клоном и
bare-`origin` (`make_project_repo`), задача в БД пульта с рабочей копией
(`workspace.ensure`). Профиль тестов проекта — как у записи артели (раннер
пульта, `report: junit-xml`); в корне проекта лежит свой `conftest.py`-
сторож, который роняет pytest под `config.ARTEL_ROLE_ENV`, и `pytest.ini`.
Модуль проекта `core_<слово>.py` с двумя функциями и тест
`tests/test_<слово>.py`; патчи мутаций — файлы `mutation-<nnn>.diff`
каталога документов задачи (`artifact_branch.docs_dir`) либо коммит ссылки
`refs/artifacts/<id>` клона.

Команда зовётся в процессе теста — `artel.main()` с подменённым `sys.argv`;
фоновый процесс, который команда запускает (`subprocess.Popen`
интерпретатора с `-c`/`-m orchestrator…`/`…/artel.py`), исполняется здесь
же тем же кодом в окружении, которое команда ему передала (приём
`tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`); прочие
запуски процессов настоящие, ожидания по часам в тесте нет. Узел прогона
`acceptance.run_full_suite` обёрнут наблюдателем: он пишет корень, предел,
флаги и держателя замка каждого вызова и по плану сценария либо зовёт
настоящий узел, либо подменяет исход («предел», исключение, свой отчёт
junit-xml по флагу `--junitxml=` из `extra`). `git` на PATH — обёртка:
пишет вызовы, адресованные временной копии `artel-suite-base-…`, и по флагу
сценария оставляет после `git clean` посторонний файл в копии.

Форма ожидания отчёта (`--wait` тем же вызовом или повторным, как у
`suite-run`) критериями не задана: помощник `mutate` сначала зовёт команду с
`--wait`; если прогона не появилось (нет `mutation-run.json`), запускает
без `--wait` и забирает отчёт повторным вызовом. AC-7 зовёт команду
настоящим подпроцессом CLI копии пульта (`orchestrator/`, `scripts/` в
корне песочницы — образец `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`).
Входы (слова, имена, пределы, порядок патчей) — от зерна; зерно печатается
и входит в текст провала.
"""
import ast
import contextlib
import difflib
import hashlib
import inspect
import io
import json
import os
import random
import re
import runpy
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, artel, config, store, suite_lock, workspace
from tests.sandbox import (RealGitSandbox, _alive_foreign_pid, _dead_pid,
                           make_project_repo)

CODE_ROOT = Path(acceptance.__file__).resolve().parent.parent
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
COPY_PREFIX = "artel-suite-base-"
ROLE_REFUSAL = "команда недоступна процессу роли"

KILLED = "убита"
SURVIVED = "не убита"
COLLECTION = "ошибка сбора, импорта или setup"
UNKNOWN = "итог неизвестен"
CUT = "оборвана по пределу"
NOT_RUN = "не прогнана (предел)"
NOT_APPLIED = "патч не применяется"
TOUCHES = "патч трогает тесты"
RED_CONTROL = "тесты красные без мутаций"
NO_PATCHES = "патчей мутаций нет"
PROFILE_REFUSAL = "профиль проекта не поддержан командой mutation-run"
CONTROL_CUT = re.compile(r"контрольный прогон оборван по пределу (\d+) с")
TIMEOUT_HEAD = "прогон полного набора tests/ превысил "

PROJECT_ENTRY = """  {name}:
    forge: github
    url: file://{origin}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{tail}      install: []
      full_suite_timeout_sec: {limit}
"""
PULT_RUNNER = "      report: junit-xml\n"
OWN_RUNNER = "      runner: pytest-own\n"

GUARD_CONFTEST = '''import json, os


def pytest_configure(config):
    record = {{"role": os.environ.get({role_env!r}),
              "worker": hasattr(config, "workerinput"),
              "cwd": os.path.realpath(os.getcwd())}}
    with open({log!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
    if os.environ.get({role_env!r}):
        raise RuntimeError("сторож песочницы: pytest под признаком роли")
'''

PYTEST_INI = "[pytest]\npythonpath = .\n"

MODULE = """# модуль песочницы {w}
def add(a, b):
    return a + b


def mul(a, b):
    return a * b
"""

TEST_FILE = """import core_{w}


def test_add_{w}():
    assert core_{w}.add(2, 3) == 5


def test_mul_{w}():
    assert core_{w}.mul(2, 3) == 6
"""

MARKED_TEST = """import os

import core_{w}


def test_extra_{w}():
    with open({marks!r}, "a", encoding="utf-8") as fh:
        fh.write(os.path.realpath(os.getcwd()) + "\\n")
    assert core_{w}.add(4, 5) == 9
"""

BREAKS = ("return a - b", "return a * b", "return a + b + 1")

GIT_WRAPPER = '''#!{python}
import json, os, subprocess, sys
REAL = {real!r}
args = sys.argv[1:]
cwd = os.getcwd()
repo, index = cwd, 0
while index + 1 < len(args) and args[index] == "-C":
    repo = os.path.join(repo, args[index + 1])
    index += 2
sub = args[index] if index < len(args) else ""
if any({prefix!r} in str(a) for a in args) or {prefix!r} in cwd:
    applied = False
    if os.path.exists({log!r}):
        with open({log!r}, encoding="utf-8") as fh:
            applied = any(r["sub"] == "apply" and not {{"--check", "--stat",
                          "--numstat", "--summary"}} & set(r["args"])
                          for r in map(json.loads, fh.read().splitlines()))
    with open({log!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"args": args, "cwd": cwd, "sub": sub}}) + "\\n")
    if sub == "clean" and applied and os.path.exists({flag!r}):
        code = subprocess.call([REAL, *args])
        with open(os.path.join(repo, {stray!r}), "w", encoding="utf-8") as fh:
            fh.write("посторонний файл песочницы\\n")
        sys.exit(code)
os.execv(REAL, [REAL, *args])
'''


def junit(cases: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
            f'<testsuite name="pytest">{cases}</testsuite></testsuites>')


def numbered(n: int) -> str:
    return f"mutation-{n:03d}.diff"


def file_diff(path: str, before: str, after: str) -> str:
    lines = difflib.unified_diff(before.splitlines(True),
                                 after.splitlines(True),
                                 f"a/{path}", f"b/{path}")
    return f"diff --git a/{path} b/{path}\n" + "".join(lines)


def new_file_diff(path: str, text: str) -> str:
    body = "".join(f"+{line}\n" for line in text.splitlines())
    count = len(text.splitlines())
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
            f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{count} @@\n{body}")


def move_diff(kind: str, old: str, new: str) -> str:
    return (f"diff --git a/{old} b/{new}\nsimilarity index 100%\n"
            f"{kind} from {old}\n{kind} to {new}\n")


class ShiftedClock:
    """Часы процесса со сдвигом: наблюдатель прогона двигает их вперёд."""

    def __init__(self):
        self.offset = 0.0
        self.real_monotonic = time.monotonic
        self.real_time = time.time
        self.real_perf = time.perf_counter

    def monotonic(self) -> float:
        return self.real_monotonic() + self.offset

    def time(self) -> float:
        return self.real_time() + self.offset

    def perf_counter(self) -> float:
        return self.real_perf() + self.offset


class RunProbe:
    """Обёртка `acceptance.run_full_suite`: запись вызовов и подмена исхода.

    `plan` — номер вызова (с 1) -> действие: "timeout" (исход «предел»),
    "raise" (исключение посреди прогона) или словарь подменённого исхода
    `{"green": bool, "junit": None | текст, "output": текст}` (`None` —
    отчёта нет). Остальные вызовы идут в настоящий узел."""

    def __init__(self, real, clock=None, step: float = 0.0):
        self.real = real
        self.calls = []
        self.plan = {}
        self.clock = clock
        self.step = step

    def __call__(self, root, *args, **kwargs):
        number = len(self.calls) + 1
        limit = kwargs.get("limit", args[4] if len(args) > 4 else None)
        extra = list(kwargs.get("extra", args[2] if len(args) > 2 else ()))
        targets = list(kwargs.get("targets",
                                  args[1] if len(args) > 1 else ("tests",)))
        report = self.junit_path(extra)
        self.calls.append({
            "n": number, "root": os.path.realpath(str(root)),
            "limit": limit, "extra": extra, "targets": targets,
            "junit": report, "holder": suite_lock.holder(),
            "offset": self.clock.offset if self.clock else 0.0})
        action = self.plan.get(number, "real")
        try:
            if action == "real":
                return self.real(root, *args, **kwargs)
            if action == "raise":
                raise RuntimeError("подмена песочницы: исключение посреди прогона")
            if action == "timeout":
                seconds, source = limit or (config.FULL_SUITE_TIMEOUT_SEC,
                                            "config")
                if self.clock is not None:
                    self.clock.offset += float(seconds)
                return False, (f"{TIMEOUT_HEAD}{seconds}с — завис или ждёт "
                               f"сетевой ответ (источник: {source})\n")
            if report is not None:
                path = Path(report)
                path.unlink(missing_ok=True)
                if action["junit"] is not None:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(action["junit"], encoding="utf-8")
            return action["green"], action["output"]
        finally:
            if self.clock is not None:
                self.clock.offset += self.step

    @staticmethod
    def junit_path(extra: list) -> str | None:
        for index, arg in enumerate(extra):
            arg = str(arg)
            for flag in ("--junitxml", "--junit-xml"):
                if arg.startswith(flag + "="):
                    return arg.split("=", 1)[1]
                if arg == flag and index + 1 < len(extra):
                    return str(extra[index + 1])
        return None


class MutationRunSandbox(RealGitSandbox):
    """Проект песочницы, задачи с рабочими копиями, команда в процессе теста."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.probe_dir = Path(tempfile.mkdtemp(prefix="artel-mutation-probe-")
                              ).resolve()
        self.addCleanup(shutil.rmtree, self.probe_dir, ignore_errors=True)
        self.pytest_log = self.probe_dir / "pytest.jsonl"
        self.git_log = self.probe_dir / "git.jsonl"
        self.stray_flag = self.probe_dir / "stray-on"
        self.stray = f"stray-{self.word()}.txt"
        bin_dir = self.probe_dir / "bin"
        bin_dir.mkdir()
        real_git = shutil.which("git")
        self.assertTrue(real_git, "git не найден на PATH")
        wrapper = bin_dir / "git"
        wrapper.write_text(GIT_WRAPPER.format(
            python=sys.executable, real=real_git, prefix=COPY_PREFIX,
            log=str(self.git_log), flag=str(self.stray_flag),
            stray=self.stray), encoding="utf-8")
        wrapper.chmod(0o755)
        env = mock.patch.dict(os.environ, {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "PYTHONDONTWRITEBYTECODE": "1"})
        env.start()
        self.addCleanup(env.stop)
        workers = mock.patch.object(config, "FULL_SUITE_WORKERS", 2)
        workers.start()
        self.addCleanup(workers.stop)
        self.dead_pid = _dead_pid()
        self.entries = []
        self.conn = store.db()
        self.child_errors = []

    # --- фикстуры -----------------------------------------------------------

    def word(self, size: int = 7) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def new_task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ALPHABET) for _ in range(23))

    def write_targets(self) -> None:
        text = "targets:\n" + "".join(self.entries)
        for path in {Path(config.TARGETS), self.root / "targets.yaml"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def add_project(self, runner: str = PULT_RUNNER, limit: int = None,
                    extra_files: dict = None) -> dict:
        """Проект с модулем `core_<w>.py`, тестом `tests/test_<w>.py`,
        вспомогательными файлами `tests/` и сторожем роли в `conftest.py`."""
        w = self.word()
        target = "p" + self.word()
        limit = limit or self.rng.randint(1000, 3000)
        origin = config.PROJECTS / target / "origin.git"
        self.entries.append(PROJECT_ENTRY.format(
            name=target, origin=origin, base=config.MAIN_BRANCH,
            tail=runner, limit=limit))
        self.write_targets()
        clone = make_project_repo(target)
        files = {
            "conftest.py": GUARD_CONFTEST.format(
                role_env=config.ARTEL_ROLE_ENV, log=str(self.pytest_log)),
            "pytest.ini": PYTEST_INI,
            f"core_{w}.py": MODULE.format(w=w),
            f"tests/test_{w}.py": TEST_FILE.format(w=w),
            f"tests/helper_{w}.py": "VALUE = 1\n",
            f"tests/sub/test_sub_{w}.py": "def test_sub():\n    assert True\n",
        }
        files.update(extra_files or {})
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "проект песочницы")
        self.git("-C", str(clone), "push", "-q", "origin", config.MAIN_BRANCH)
        return {"target": target, "w": w, "clone": clone, "limit": limit,
                "module": f"core_{w}.py", "test": f"tests/test_{w}.py",
                "add_node": f"test_add_{w}", "files": files}

    def add_task(self, project: dict, uncommitted: dict = None) -> tuple:
        """(id, рабочая копия) задачи проекта в `in_dev`."""
        task_id = self.new_task_id()
        branch = f"task/{task_id.lower()}-mutation-run"
        store.insert_task(self.conn, task_id, "Фикстура mutation-run",
                          "in_dev", branch, project["target"], 25.0)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, f"рабочая копия не заведена: {error}")
        wt = Path(wt).resolve()
        for rel, text in (uncommitted or {}).items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return task_id, wt

    def docs_dir(self, project: dict, task_id: str) -> Path:
        return config.PROJECTS / project["target"] / "tasks" / task_id

    def write_patches(self, project: dict, task_id: str, patches: list) -> list:
        folder = self.docs_dir(project, task_id)
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for number, text in enumerate(patches, start=1):
            path = folder / numbered(number)
            path.write_text(text, encoding="utf-8")
            paths.append(path)
        return paths

    def commit_ref(self, project: dict, task_id: str, patches: list) -> str:
        """Коммит ссылки `refs/artifacts/<id>` клона с патчами задачи."""
        clone = project["clone"]
        holder = Path(tempfile.mkdtemp(prefix="artel-mutation-ref-"))
        self.addCleanup(shutil.rmtree, holder, ignore_errors=True)
        work = holder / "w"
        self.git("-C", str(clone), "worktree", "add", "-q", "--detach",
                 str(work), "HEAD")
        folder = work / "tasks" / task_id
        folder.mkdir(parents=True)
        for number, text in enumerate(patches, start=1):
            (folder / numbered(number)).write_text(text, encoding="utf-8")
        self.git("-C", str(work), "add", "-A")
        self.git("-C", str(work), "commit", "-q", "-m", "документы задачи")
        sha = self.git("-C", str(work), "rev-parse", "HEAD").strip()
        self.git("-C", str(clone), "update-ref", f"refs/artifacts/{task_id}",
                 sha)
        self.git("-C", str(clone), "worktree", "remove", "--force", str(work))
        return sha

    def module_patch(self, project: dict, old: str, new: str) -> str:
        before = project["files"][project["module"]]
        self.assertIn(old, before)
        return file_diff(project["module"], before, before.replace(old, new))

    def breaking(self, project: dict, index: int = 0) -> str:
        return self.module_patch(project, "return a + b", BREAKS[index])

    def comment(self, project: dict) -> str:
        return self.module_patch(project, f"# модуль песочницы {project['w']}",
                                 f"# модуль песочницы {project['w']}: "
                                 f"{self.word()}")

    # --- команда --------------------------------------------------------------

    def run_child(self, tokens: list, kwargs: dict) -> None:
        """Фоновый процесс команды — в процессе теста, тем же кодом."""
        env = kwargs.get("env")
        environ = (mock.patch.dict(os.environ, env, clear=True)
                   if env is not None else contextlib.nullcontext())
        saved_argv, saved_cwd = sys.argv, os.getcwd()
        try:
            with environ:
                if kwargs.get("cwd"):
                    os.chdir(kwargs["cwd"])
                if tokens[1] == "-c":
                    sys.argv = ["-c", *tokens[3:]]
                    exec(compile(tokens[2], "<mutation-run child>", "exec"),
                         {"__name__": "__main__"})
                elif tokens[1] == "-m":
                    sys.argv = [tokens[2], *tokens[3:]]
                    runpy.run_module(tokens[2], run_name="__main__",
                                     alter_sys=True)
                else:
                    sys.argv = tokens[1:]
                    artel.main()
        except SystemExit as exc:
            if exc.code not in (None, 0):
                self.child_errors.append(f"фоновый процесс: выход {exc.code}")
        except Exception:  # noqa: BLE001 — исход фонового процесса виден тесту
            self.child_errors.append(traceback.format_exc())
        finally:
            sys.argv = saved_argv
            os.chdir(saved_cwd)

    def popen(self):
        real_popen = subprocess.Popen

        def popen(argv, *args, **kwargs):
            tokens = ([str(t) for t in argv]
                      if isinstance(argv, (list, tuple)) else [])
            child = len(tokens) > 2 and tokens[0] == sys.executable and (
                (tokens[1] == "-c" and "orchestrator" in tokens[2])
                or (tokens[1] == "-m" and tokens[2].startswith("orchestrator"))
                or tokens[1].endswith("artel.py"))
            if not child:
                return real_popen(argv, *args, **kwargs)
            self.run_child(tokens, kwargs)
            proc = mock.Mock(pid=self.dead_pid, returncode=0)
            proc.poll.return_value = 0
            proc.wait.return_value = 0
            return proc

        return mock.patch.object(subprocess, "Popen", popen)

    def command(self, *args: str) -> tuple:
        """(код выхода, вывод) `artel.py mutation-run <args>` в процессе теста."""
        buf, code = io.StringIO(), 0
        with mock.patch.object(sys, "argv", ["artel.py", "mutation-run", *args]), \
                self.popen(), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
                if isinstance(code, str):
                    buf.write(code + "\n")
        return (0 if code is None else code), buf.getvalue()

    def state_dir(self, task_id: str) -> Path:
        return suite_lock.directory() / task_id

    def mutate(self, task_id: str, *args: str) -> str:
        """Прогон до отчёта; весь текст: выводы вызовов и файлы хозяйства."""
        texts = [self.command(task_id, *args, "--wait", "1")[1]]
        started = self.state_dir(task_id) / "mutation-run.json"
        result = self.state_dir(task_id) / "mutation-result.json"
        if not started.exists():
            texts.append(self.command(task_id, *args)[1])
            texts.append(self.command(task_id, "--wait", "1")[1])
            if not result.exists():
                texts.append(self.command(task_id, *args, "--wait", "1")[1])
        return "\n".join(texts + [self.state_text(task_id)])

    def state_text(self, task_id: str) -> str:
        folder = self.state_dir(task_id)
        if not folder.is_dir():
            return ""
        parts = []
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                parts.append(path.read_bytes().decode("utf-8", "replace"))
        return "\n".join(parts)

    def table(self, task_id: str) -> tuple:
        """(путь таблицы, строки шапки, строки [(номер, исход, узлы)])."""
        folder = self.state_dir(task_id)
        pattern = re.compile(rf"^{task_id}-mutation-run-(\d+)\.mutations\.tsv$")
        found = sorted(((int(m.group(1)), p) for p in folder.glob("*.tsv")
                        if (m := pattern.match(p.name))), key=lambda x: x[0]) \
            if folder.is_dir() else []
        if not found:
            return None, [], []
        path = found[-1][1]
        header, rows = [], []
        for line in path.read_text(encoding="utf-8").splitlines():
            cols = line.split("\t")
            if cols[0].strip().isdigit():
                rows.append((int(cols[0]), cols[1].strip() if len(cols) > 1
                             else "", cols[2].strip() if len(cols) > 2 else ""))
            else:
                header.append(line)
        return path, header, rows

    def outcomes(self, task_id: str) -> dict:
        return {n: (outcome, nodes) for n, outcome, nodes in
                self.table(task_id)[2]}

    def probe(self, clock=None, step: float = 0.0) -> RunProbe:
        probe = RunProbe(acceptance.run_full_suite, clock, step)
        patcher = mock.patch.object(acceptance, "run_full_suite", probe)
        patcher.start()
        self.addCleanup(patcher.stop)
        return probe

    def lock_spies(self) -> dict:
        spies = {}
        for name in ("acquire", "wait_acquire", "hand", "adopt"):
            spy = mock.Mock(wraps=getattr(suite_lock, name))
            patcher = mock.patch.object(suite_lock, name, spy)
            patcher.start()
            self.addCleanup(patcher.stop)
            spies[name] = spy
        return spies

    def git_records(self) -> list:
        if not self.git_log.exists():
            return []
        return [json.loads(line) for line in
                self.git_log.read_text(encoding="utf-8").splitlines() if line]

    def pytest_records(self) -> list:
        if not self.pytest_log.exists():
            return []
        return [json.loads(line) for line in
                self.pytest_log.read_text(encoding="utf-8").splitlines() if line]

    def explain(self, text: str = "") -> str:
        errors = "\n".join(self.child_errors)[-3000:]
        return (f"зерно: {self.seed}\nвывод и хозяйство команды:\n"
                f"{text[-4000:]}\nсбои фонового процесса:\n{errors}")


class OutcomeTest(MutationRunSandbox):

    def test_ac1_breaking_patch_killed_comment_patch_not_killed(self):
        """Ломающий патч — «убита» с упавшим узлом, правка комментария — «не убита».

        Сценарий: модуль проекта с функциями `add`/`mul` и тест на них;
        патч 1 ломает `add` (вариант поломки от зерна), патч 2 меняет только
        первую строку-комментарий модуля; порядок патчей в наборе — от
        зерна. `mutation-run --ref head --tests tests/test_<w>.py`. В таблице
        у ломающего исход ровно «убита», среди узлов — `test_add_<w>`, у
        комментария — ровно «не убита».

        Ловит мутацию: исход по коду возврата без разбора отчёта или с
        перепутанной веткой — ломающий патч не «убита» либо комментарий не
        «не убита»; узлы не пишутся в таблицу — имени упавшего теста в строке
        нет; прогон без применённого патча — ломающий «не убита».
        """
        project = self.add_project()
        task_id, _wt = self.add_task(project)
        patches = [("break", self.breaking(project, self.rng.randrange(3))),
                   ("comment", self.comment(project))]
        self.rng.shuffle(patches)
        self.write_patches(project, task_id, [text for _, text in patches])
        text = self.mutate(task_id, "--ref", "head", "--tests", project["test"])
        rows = self.outcomes(task_id)
        for number, (kind, _patch) in enumerate(patches, start=1):
            self.assertIn(number, rows, self.explain(text))
            outcome, nodes = rows[number]
            if kind == "break":
                self.assertEqual(outcome, KILLED, self.explain(text))
                self.assertIn(project["add_node"], nodes, self.explain(text))
            else:
                self.assertEqual(outcome, SURVIVED, self.explain(text))

    def test_ac2_syntax_error_and_file_level_failed_are_collection_outcome(self):
        """Синтаксическая ошибка модуля и `failed` уровня файла — «ошибка сбора».

        Сценарий: патч 1 убирает двоеточие в `def add(a, b):` — настоящий
        pytest падает на сборе тестового файла; прогон патча 2 подменён
        отчётом junit-xml с единственной записью `failure` уровня файла
        (сообщение `collection failure`) и ненулевым кодом. Оба патча
        получают ровно «ошибка сбора, импорта или setup» — не «убита» и не
        «не убита».

        Ловит мутацию: любая запись `failed` засчитывается как «убита» без
        учёта признака уровня файла — патч 2 «убита»; ошибка сбора
        (`error` уровня файла) не отличается от прочего ненулевого кода —
        патч 1 «итог неизвестен» или «убита».
        """
        project = self.add_project()
        task_id, _wt = self.add_task(project)
        probe = self.probe()
        name = f"tests.test_{project['w']}"
        probe.plan[3] = {"green": False, "output": f"1 failed {self.word()}\n",
                         "junit": junit(
                             f'<testcase classname="" name="{name}">'
                             '<failure message="collection failure">'
                             'ImportError: подмена песочницы</failure>'
                             '</testcase>')}
        self.write_patches(project, task_id, [
            self.module_patch(project, "def add(a, b):", "def add(a, b)"),
            self.comment(project)])
        text = self.mutate(task_id, "--ref", "head", "--tests", project["test"])
        rows = self.outcomes(task_id)
        self.assertEqual(rows.get(1, ("",))[0], COLLECTION, self.explain(text))
        self.assertEqual(rows.get(2, ("",))[0], COLLECTION, self.explain(text))
        self.assertTrue(all(c["junit"] for c in probe.calls[1:]),
                        f"прогон патча без --junitxml в extra: "
                        f"{probe.calls}; {self.explain(text)}")

    def test_ac3_unappliable_and_test_touching_patches_are_not_run(self):
        """Неприменимый патч — «патч не применяется», трогающие тесты — «патч трогает тесты».

        Сценарий: набор из неприменимого патча (контекст, которого нет в
        модуле) и двенадцати патчей, трогающих тесты: правка файла под
        `tests/`, новый `<каталог>/conftest.py` вне `tests/`,
        `pyproject.toml`, `pytest.ini`, `.pytest.ini`, `pytest.toml`,
        `setup.cfg`, `tox.ini`, переименование модуля в `tests/`,
        переименование файла `tests/` наружу, копирование модуля в `tests/`
        и файла `tests/` наружу; порядок — от зерна. Каждый получает свой
        исход ровно; прогон узла — только контрольный; применяющих вызовов
        `git apply` (без `--check`/`--stat`/`--numstat`/`--summary`) в копии
        не больше двух — их делает только неприменимый патч.

        Ловит мутацию: проверка путей только по `tests/` — `conftest.py` вне
        `tests/` или `tox.ini` прогоняются; переименование/копирование
        сверяется по одному пути — патч из модуля в `tests/` или из `tests/`
        наружу прогоняется; трогающий патч сначала применяется, потом
        отклоняется — применяющих `git apply` больше двух; отказ `git apply`
        не отличается от прочего — исход неприменимого не «патч не
        применяется».
        """
        project = self.add_project()
        w = project["w"]
        task_id, _wt = self.add_task(project)
        probe = self.probe()
        test_text = project["files"][project["test"]]
        sub = self.word()
        touching = [
            file_diff(project["test"], test_text,
                      test_text.replace("== 5", "== 5, 'правка'")),
            new_file_diff(f"{sub}/conftest.py", "X = 1\n"),
            new_file_diff("pyproject.toml", "[tool.sandbox]\nx = 1\n"),
            file_diff("pytest.ini", PYTEST_INI, PYTEST_INI + "addopts = -q\n"),
            new_file_diff(".pytest.ini", "[pytest]\n"),
            new_file_diff("pytest.toml", "[pytest]\n"),
            new_file_diff("setup.cfg", "[metadata]\nname = x\n"),
            new_file_diff("tox.ini", "[tox]\n"),
            move_diff("rename", project["module"], f"tests/core_{w}.py"),
            move_diff("rename", f"tests/helper_{w}.py", f"helper_{w}.py"),
            move_diff("copy", project["module"], f"tests/core_copy_{w}.py"),
            move_diff("copy", f"tests/helper_{w}.py", f"helper_copy_{w}.py"),
        ]
        module = project["files"][project["module"]]
        patches = [(TOUCHES, text) for text in touching]
        patches.append((NOT_APPLIED, file_diff(
            project["module"], module.replace("return a * b", "return a // b"),
            module.replace("return a * b", "return a % b"))))
        self.rng.shuffle(patches)
        self.write_patches(project, task_id, [text for _, text in patches])
        text = self.mutate(task_id, "--ref", "head", "--tests", project["test"])
        rows = self.outcomes(task_id)
        for number, (expected, patch) in enumerate(patches, start=1):
            with self.subTest(number=number, patch=patch.splitlines()[0]):
                self.assertEqual(rows.get(number, ("",))[0], expected,
                                 self.explain(text))
        self.assertEqual(len(probe.calls), 1,
                         f"патчи прогонялись: {probe.calls}; {self.explain(text)}")
        applying = [r for r in self.git_records() if r["sub"] == "apply"
                    and not {"--check", "--stat", "--numstat", "--summary"}
                    & set(r["args"])]
        self.assertLessEqual(len(applying), 2,
                             f"применяющие git apply: {applying}; "
                             f"{self.explain(text)}")

    def test_ac12_unknown_outcome_is_never_not_killed(self):
        """Отчёт нет, не разобран, пуст при ненулевом коде, только passed при ненулевом — «итог неизвестен».

        Сценарий: четыре патча правят комментарий модуля; прогоны патчей
        подменены: отчёта junit-xml нет; отчёт — не XML; отчёт без записей
        при ненулевом коде; ненулевой код, а в отчёте только `passed` и
        `skipped`. Контроль — настоящий. Все четыре строки таблицы — ровно
        «итог неизвестен», ни одна не «не убита».

        Ловит мутацию: «не убита» по отсутствию `failed`/`error` без учёта
        кода возврата — четвёртый (и третий) «не убита»; отсутствующий или
        неразобранный отчёт читается как пустой — «не убита».
        """
        project = self.add_project()
        w = project["w"]
        task_id, _wt = self.add_task(project)
        probe = self.probe()
        out = f"прогон песочницы {self.word()}\n"
        probe.plan.update({
            2: {"green": False, "junit": None, "output": out},
            3: {"green": False, "junit": f"<<< не xml {self.word()}",
                "output": out},
            4: {"green": False, "junit": junit(""), "output": out},
            5: {"green": False, "output": out, "junit": junit(
                f'<testcase classname="tests.test_{w}" name="test_add_{w}" '
                f'time="0.01"/><testcase classname="tests.test_{w}" '
                f'name="test_mul_{w}" time="0.01"><skipped message="s"/>'
                f'</testcase>')},
        })
        self.write_patches(project, task_id,
                           [self.comment(project) for _ in range(4)])
        text = self.mutate(task_id, "--ref", "head", "--tests", project["test"])
        rows = self.outcomes(task_id)
        for number, case in enumerate(("отчёта нет", "отчёт не разобран",
                                       "отчёт пуст", "только passed/skipped"),
                                      start=1):
            with self.subTest(case=case):
                self.assertEqual(rows.get(number, ("",))[0], UNKNOWN,
                                 self.explain(text))


class ControlTest(MutationRunSandbox):

    def test_ac4_red_control_refuses_whole_command(self):
        """Красный или оборванный контроль — отказ всей команды, патчи не прогоняются.

        Сценарий (четыре случая, у каждого своя задача): в контроле падает
        тест; в контроле только ошибка сбора файла (тестовый файл
        импортирует несуществующий модуль); контроль подменён ненулевым
        кодом с отчётом только из `passed`; контроль подменён исходом
        «предел». Первые три — текст «тесты красные без мутаций»; четвёртый
        — «контрольный прогон оборван по пределу N с», N — предел профиля
        или переданный контролю, без «тесты красные без мутаций». Во всех
        случаях узел прогона вызван один раз, строк патчей в таблице нет.

        Ловит мутацию: контроль красный только при `failed` — ошибка сбора
        или ненулевой код без записей проходят, патчи прогоняются; обрыв
        контроля по пределу сводится к «тесты красные без мутаций»; отказ
        контроля печатается, но цикл патчей идёт дальше — вызовов узла
        больше одного.
        """
        w = self.word()
        bad = f"tests/test_bad_{w}.py"
        broken = f"tests/test_broken_{w}.py"
        project = self.add_project(extra_files={
            bad: f"def test_bad_{w}():\n    assert False, 'красный'\n",
            broken: f"import nonexistent_{w}\n\n\ndef test_x():\n    pass\n"})
        cases = [
            ("упавший тест", bad, None),
            ("ошибка сбора", broken, None),
            ("ненулевой код без failed/error", project["test"],
             {"green": False, "output": f"{self.word()}\n", "junit": junit(
                 f'<testcase classname="tests.test_{project["w"]}" '
                 f'name="test_add_{project["w"]}" time="0.01"/>')}),
            ("обрыв по пределу", project["test"], "timeout"),
        ]
        for case, tests, action in cases:
            with self.subTest(case=case):
                task_id, _wt = self.add_task(project)
                probe = RunProbe(acceptance.run_full_suite)
                if action is not None:
                    probe.plan[1] = action
                self.write_patches(project, task_id, [
                    self.breaking(project), self.comment(project)])
                with mock.patch.object(acceptance, "run_full_suite", probe):
                    text = self.mutate(task_id, "--ref", "head", "--tests", tests)
                self.assertEqual(len(probe.calls), 1,
                                 f"{case}: вызовы {probe.calls}; "
                                 f"{self.explain(text)}")
                self.assertEqual(self.table(task_id)[2], [],
                                 f"{case}: {self.explain(text)}")
                if action == "timeout":
                    self.assertNotIn(RED_CONTROL, text, self.explain(text))
                    match = CONTROL_CUT.search(text)
                    self.assertIsNotNone(match, self.explain(text))
                    allowed = {project["limit"]}
                    if probe.calls[0]["limit"]:
                        allowed.add(int(probe.calls[0]["limit"][0]))
                    self.assertIn(int(match.group(1)), allowed,
                                  self.explain(text))
                else:
                    self.assertIn(RED_CONTROL, text, f"{case}: "
                                                     f"{self.explain(text)}")

    def test_ac8_limit_cut_marks_current_and_remaining(self):
        """Обрыв по пределу: текущая — «оборвана по пределу», следующая — «не прогнана (предел)».

        Сценарий: предел профиля L — от зерна; часы процесса сдвигаются на
        L/5 после каждого вызова узла прогона. Три патча: первый ломает
        `add`, прогон второго подменён исходом «предел», третий —
        правка комментария. Таблица: 1 — «убита», 2 — «оборвана по пределу»,
        3 — «не прогнана (предел)»; узел вызван трижды (контроль, 1, 2);
        предел k-го вызова назван и не больше L − (k−1)·L/5 + 1.

        Ловит мутацию: каждому прогону передаётся полный предел профиля —
        второй вызов получает L; предел меряется от старта прогона патча,
        а не команды — то же; после обрыва цикл идёт дальше — третий патч
        прогоняется и не «не прогнана (предел)»; строки оборванной и
        оставшихся мутаций не пишутся.
        """
        limit = self.rng.randint(1000, 3000)
        step = limit // 5
        project = self.add_project(limit=limit)
        task_id, _wt = self.add_task(project)
        clock = ShiftedClock()
        for name in ("monotonic", "time", "perf_counter"):
            patcher = mock.patch(f"time.{name}", getattr(clock, name))
            patcher.start()
            self.addCleanup(patcher.stop)
        probe = self.probe(clock, step)
        probe.plan[3] = "timeout"
        self.write_patches(project, task_id, [
            self.breaking(project), self.comment(project),
            self.comment(project)])
        text = self.mutate(task_id, "--ref", "head", "--tests", project["test"])
        rows = self.outcomes(task_id)
        self.assertEqual(rows.get(1, ("",))[0], KILLED, self.explain(text))
        self.assertEqual(rows.get(2, ("",))[0], CUT, self.explain(text))
        self.assertEqual(rows.get(3, ("",))[0], NOT_RUN, self.explain(text))
        self.assertEqual(len(probe.calls), 3,
                         f"вызовы {probe.calls}; {self.explain(text)}")
        for call in probe.calls:
            with self.subTest(call=call["n"]):
                self.assertIsNotNone(call["limit"], self.explain(text))
                bound = limit - (call["n"] - 1) * step + 1
                self.assertLessEqual(int(call["limit"][0]), bound,
                                     f"предел {call['limit']} вызова "
                                     f"{call['n']}; L={limit}, шаг {step}; "
                                     f"{self.explain(text)}")


class RevisionTest(MutationRunSandbox):

    def test_ac9_worktree_ref_sees_uncommitted_test_for_every_patch(self):
        """`--ref worktree`: незакоммиченный тест прогоняется в контроле и при всех трёх патчах.

        Сценарий: в рабочей копии задачи лежит неотслеживаемый
        `tests/test_extra_<w>.py` (в git его нет), он пишет отметку при
        каждом исполнении; три патча ломают `add` по-разному.
        `--ref worktree --tests tests/test_extra_<w>.py`: отметок ровно
        четыре (контроль и три патча), все три строки — «убита» с узлом
        `test_extra_<w>`; файл остался в рабочей копии неотслеживаемым.

        Ловит мутацию: незакоммиченные файлы не переносятся — контроль
        отказывает, отметок нет; коммита-основы нет и сброс
        `git clean -ffdx` стирает перенесённый файл — второй и третий патч
        не «убита», отметок меньше четырёх; прогон ревизии HEAD без
        незакоммиченного — проверка `--tests` отказывает.
        """
        project = self.add_project()
        w = project["w"]
        marks = self.probe_dir / "marks.txt"
        extra = f"tests/test_extra_{w}.py"
        task_id, wt = self.add_task(project, uncommitted={
            extra: MARKED_TEST.format(w=w, marks=str(marks))})
        self.write_patches(project, task_id,
                           [self.breaking(project, i) for i in range(3)])
        text = self.mutate(task_id, "--ref", "worktree", "--tests", extra)
        rows = self.outcomes(task_id)
        for number in (1, 2, 3):
            with self.subTest(patch=number):
                outcome, nodes = rows.get(number, ("", ""))
                self.assertEqual(outcome, KILLED, self.explain(text))
                self.assertIn(f"test_extra_{w}", nodes, self.explain(text))
        executions = (marks.read_text(encoding="utf-8").splitlines()
                      if marks.exists() else [])
        self.assertEqual(len(executions), 4, self.explain(text))
        status = self.git("-C", str(wt), "status", "--porcelain")
        self.assertIn(f"?? {extra}", status, self.explain(text))

    def test_ac10_patch_range_runs_only_named_patch(self):
        """`--patches 2-2` прогоняет только второй патч: одна строка с номером 2.

        Сценарий: три патча (номер ломающего — от зерна, прочие —
        комментарий); `--patches 2-2`. В таблице ровно одна строка, её номер
        2; узел вызван дважды — контроль и второй патч.

        Ловит мутацию: диапазон не читается и идут все патчи — строк три;
        граница диапазона исключающая — строк нет; нумерация с нуля —
        строка с номером 3 или 1.
        """
        project = self.add_project()
        task_id, _wt = self.add_task(project)
        probe = self.probe()
        broken = self.rng.randrange(3)
        self.write_patches(project, task_id, [
            self.breaking(project) if i == broken else self.comment(project)
            for i in range(3)])
        text = self.mutate(task_id, "--ref", "head", "--tests", project["test"],
                        "--patches", "2-2")
        rows = self.table(task_id)[2]
        self.assertEqual([n for n, _, _ in rows], [2], self.explain(text))
        self.assertEqual(len(probe.calls), 2,
                         f"вызовы {probe.calls}; {self.explain(text)}")

    def test_ac11_table_header_names_source_revision_and_patch_hashes(self):
        """Шапка: sha256 патчей, источник и sha ревизии; таблица рядом с логом.

        Сценарий (два случая): каталог документов задачи на диске есть —
        источник «каталог на диске»; каталога нет, патчи только в коммите
        `refs/artifacts/<id>` — источник «ссылка» с sha этой ссылки, прогон
        идёт (строки обоих патчей есть). В обоих случаях шапка
        `<id>-mutation-run-<n>.mutations.tsv` несёт sha256 каждого патча и
        sha головы ветки задачи (`--ref head`), а рядом в
        `suite_lock.directory()/<id>/` лежит `<id>-mutation-run-<n>.log` с
        тем же `n`.

        Ловит мутацию: без каталога на диске команда отказывает «патчей
        нет», не читая ссылку; источник всегда «каталог на диске» — во
        втором случае нет «ссылка» и sha ссылки; хэш считается от имени
        файла, а не содержимого — sha256 патча в шапке нет; таблица пишется
        в `config.LOGS` или под другим номером, чем лог.
        """
        for source in ("каталог на диске", "ссылка"):
            with self.subTest(source=source):
                project = self.add_project()
                task_id, wt = self.add_task(project)
                patches = [self.breaking(project), self.comment(project)]
                ref_sha = None
                if source == "ссылка":
                    ref_sha = self.commit_ref(project, task_id, patches)
                    self.assertFalse(self.docs_dir(project, task_id).exists())
                else:
                    self.write_patches(project, task_id, patches)
                head = self.git("-C", str(wt), "rev-parse", "HEAD").strip()
                text = self.mutate(task_id, "--ref", "head", "--tests",
                                project["test"])
                path, header, rows = self.table(task_id)
                self.assertIsNotNone(path, self.explain(text))
                self.assertEqual(sorted(n for n, _, _ in rows), [1, 2],
                                 self.explain(text))
                head_text = "\n".join(header)
                self.assertIn(source, head_text, self.explain(text))
                self.assertIn(head, head_text, self.explain(text))
                if ref_sha:
                    self.assertIn(ref_sha, head_text, self.explain(text))
                for patch in patches:
                    digest = hashlib.sha256(patch.encode("utf-8")).hexdigest()
                    self.assertIn(digest, head_text, self.explain(text))
                self.assertEqual(path.parent, self.state_dir(task_id))
                log = path.with_name(path.name.replace(".mutations.tsv",
                                                       ".log"))
                self.assertTrue(log.is_file(), f"нет лога {log}; "
                                               f"{self.explain(text)}")


class RefusalTest(MutationRunSandbox):

    def assert_not_started(self, case: str, code, out: str, probe: RunProbe,
                           spies: dict) -> None:
        self.assertNotIn(code, (0, None), f"{case}: код 0; {self.explain(out)}")
        self.assertEqual(probe.calls, [], f"{case}: узел прогона вызван; "
                                          f"{self.explain(out)}")
        taken = {name: spy.call_args_list for name, spy in spies.items()
                 if spy.called}
        self.assertEqual(taken, {}, f"{case}: замок брался; "
                                    f"{self.explain(out)}")
        self.assertEqual(self.git_records(), [],
                         f"{case}: временная копия заводилась; "
                         f"{self.explain(out)}")

    def test_ac5_invalid_arguments_refused_before_launch(self):
        """Негодные `--tests`/`--patches`/пустой набор — отказ без запуска.

        Сценарий: проект с `tests/test_<w>.py`, `tests/helper_<w>.py`,
        `tests/sub/test_sub_<w>.py`; в рабочей копии задачи — неотслеживаемый
        `tests/test_new_<w>.py`; три патча. Каждый вызов из перечня AC-5
        (каталог `tests` в пяти формах, подкаталог, список с каталогом,
        пустой список, путь вне `tests/`, несуществующий файл, файл не
        `test_*.py`, `--ref base` с файлом только на диске, пустой набор
        патчей другой задачи, `--patches x`, `5-2`, диапазоны ниже и выше
        номеров набора) завершается ненулевым кодом; узел прогона не вызван,
        `suite_lock.acquire/wait_acquire/hand/adopt` не вызваны, git в
        каталоге `artel-suite-base-…` не звался. Пустой набор — текст
        «патчей мутаций нет».

        Ловит мутацию: каталог распознаётся только точным `tests` — формы
        `tests/`, `./tests`, `tests/.` проходят; проверяется лишь первая
        запись списка — `tests/test_<w>.py,tests/` проходит; `--tests`
        сверяется с диском рабочей копии, а не с деревом базы — файл только
        на диске проходит; проверка аргументов после взятия замка или
        создания копии — замок брался; диапазон за номерами набора молча
        усечён — прогон пошёл.
        """
        project = self.add_project()
        w = project["w"]
        task_id, _wt = self.add_task(project, uncommitted={
            f"tests/test_new_{w}.py": "def test_new():\n    assert True\n"})
        self.write_patches(project, task_id, [
            self.breaking(project), self.comment(project),
            self.comment(project)])
        empty_id, _ = self.add_task(project)
        self.docs_dir(project, empty_id).mkdir(parents=True, exist_ok=True)
        ok = project["test"]
        head = ("--ref", "head")
        cases = [
            ("tests", task_id, (*head, "--tests", "tests")),
            ("tests/", task_id, (*head, "--tests", "tests/")),
            ("./tests", task_id, (*head, "--tests", "./tests")),
            ("tests/.", task_id, (*head, "--tests", "tests/.")),
            ("подкаталог", task_id, (*head, "--tests", "tests/sub")),
            ("список с каталогом", task_id,
             (*head, "--tests", f"{ok},tests/")),
            ("пустой список", task_id, (*head, "--tests", "")),
            ("вне tests/", task_id, (*head, "--tests", project["module"])),
            ("нет файла", task_id,
             (*head, "--tests", f"tests/test_missing_{w}.py")),
            ("не test_*.py", task_id, (*head, "--tests", f"tests/helper_{w}.py")),
            ("только на диске", task_id,
             ("--ref", "base", "--tests", f"tests/test_new_{w}.py")),
            ("пустой набор", empty_id, (*head, "--tests", ok)),
            ("--patches x", task_id, (*head, "--tests", ok, "--patches", "x")),
            ("--patches 5-2", task_id,
             (*head, "--tests", ok, "--patches", "5-2")),
            ("ниже набора", task_id, (*head, "--tests", ok, "--patches", "0-2")),
            ("выше набора", task_id,
             (*head, "--tests", ok, "--patches",
              f"2-{3 + self.rng.randint(1, 9)}")),
        ]
        for case, task, args in cases:
            with self.subTest(case=case):
                probe = RunProbe(acceptance.run_full_suite)
                with mock.patch.object(acceptance, "run_full_suite", probe), \
                        contextlib.ExitStack() as stack:
                    spies = {}
                    for name in ("acquire", "wait_acquire", "hand", "adopt"):
                        spies[name] = stack.enter_context(mock.patch.object(
                            suite_lock, name,
                            mock.Mock(wraps=getattr(suite_lock, name))))
                    code, out = self.command(task, *args)
                self.assert_not_started(case, code, out, probe, spies)
                if case == "пустой набор":
                    self.assertIn(NO_PATCHES, out, self.explain(out))

    def test_ac15_other_test_profile_refused(self):
        """Профиль `runner: pytest-own` — отказ «профиль проекта не поддержан командой mutation-run».

        Сценарий: проект с профилем `runner: pytest-own`, задача, патчи и
        годные аргументы. Вызов завершается ненулевым кодом с текстом
        отказа; узел прогона не вызван, `suite_lock.acquire/wait_acquire/
        hand/adopt` не вызваны, временная копия не заводилась.

        Ловит мутацию: профиль не проверяется, и прогон идёт командой
        профиля — узел вызван; проверка профиля в фоновом процессе после
        взятия замка — замок брался; текст отказа иной.
        """
        project = self.add_project(runner=OWN_RUNNER)
        task_id, _wt = self.add_task(project)
        self.write_patches(project, task_id, [self.breaking(project)])
        probe = self.probe()
        spies = self.lock_spies()
        code, out = self.command(task_id, "--ref", "head", "--tests",
                                 project["test"])
        self.assert_not_started("pytest-own", code, out, probe, spies)
        self.assertIn(PROFILE_REFUSAL, out, self.explain(out))


class IsolationTest(MutationRunSandbox):

    def snapshot(self, project: dict, task_id: str, wt: Path) -> dict:
        clone = project["clone"]
        docs = self.docs_dir(project, task_id)
        return {
            "wt status": self.git("-C", str(wt), "status", "--porcelain"),
            "wt HEAD": self.git("-C", str(wt), "rev-parse", "HEAD"),
            "main status": self.git("status", "--porcelain"),
            "main HEAD": self.git("rev-parse", "HEAD"),
            "main heads": self.git("for-each-ref", "refs/heads"),
            "main artifacts": self.git("for-each-ref", "refs/artifacts"),
            "main worktrees": self.git("worktree", "list", "--porcelain"),
            "task ref": self.git("-C", str(clone), "rev-parse",
                                 f"refs/artifacts/{task_id}"),
            "docs": {str(p.relative_to(docs)): p.read_bytes()
                     for p in sorted(docs.rglob("*")) if p.is_file()},
        }

    def test_ac6_copy_removed_and_repositories_untouched(self):
        """Копия убрана при успехе, исключении и постороннем файле; копии и ссылки не меняются.

        Сценарий (три случая, у каждого своя задача, `--ref worktree` с
        неотслеживаемым файлом в рабочей копии; патчи — на диске и в
        `refs/artifacts/<id>`): обычный прогон двух патчей; прогон первого
        патча подменён исключением; после `git clean` в копии обёртка git
        оставляет посторонний файл. Во всех случаях каталог копии (корень
        каждого вызова узла) после команды не существует; не изменились
        `git status --porcelain` и HEAD рабочей копии, `git status
        --porcelain`, HEAD, `refs/heads/*`, `refs/artifacts/*` и
        `git worktree list` главной копии, sha `refs/artifacts/<id>` и
        содержимое каталога документов. В третьем случае второй патч не
        прогонялся, а отказ называет посторонний файл из
        `git status --porcelain`.

        Ловит мутацию: копия убирается только на успешном пути — после
        исключения каталог остаётся; `git status --porcelain` после сброса
        не проверяется — второй патч прогоняется, имени файла в отказе нет;
        сброс или коммит-основа делаются в рабочей копии задачи — её HEAD
        или статус меняются; копия заводится от главной копии — меняется
        `git worktree list` главной копии.
        """
        for case in ("обычный прогон", "исключение", "посторонний файл"):
            with self.subTest(case=case):
                project = self.add_project()
                w = project["w"]
                task_id, wt = self.add_task(project, uncommitted={
                    f"notes_{w}.txt": f"заметка {self.word()}\n"})
                patches = [self.breaking(project), self.comment(project)]
                self.write_patches(project, task_id, patches)
                self.commit_ref(project, task_id, patches)
                probe = RunProbe(acceptance.run_full_suite)
                if case == "исключение":
                    probe.plan[2] = "raise"
                self.stray_flag.unlink(missing_ok=True)
                if case == "посторонний файл":
                    self.stray_flag.write_text("on", encoding="utf-8")
                before = self.snapshot(project, task_id, wt)
                with mock.patch.object(acceptance, "run_full_suite", probe):
                    text = self.mutate(task_id, "--ref", "worktree", "--tests",
                                    project["test"])
                self.stray_flag.unlink(missing_ok=True)
                self.assertTrue(probe.calls, self.explain(text))
                for call in probe.calls:
                    self.assertFalse(Path(call["root"]).exists(),
                                     f"{case}: копия {call['root']} осталась; "
                                     f"{self.explain(text)}")
                self.assertEqual(self.snapshot(project, task_id, wt), before,
                                 f"{case}: {self.explain(text)}")
                if case == "посторонний файл":
                    self.assertEqual(len(probe.calls), 2,
                                     f"вызовы {probe.calls}; "
                                     f"{self.explain(text)}")
                    self.assertIn(self.stray, text, self.explain(text))


class StateTest(MutationRunSandbox):

    def test_ac13_lock_run_number_and_own_state_files(self):
        """Номер прогона в замке с префиксом `m`; свои файлы состояния, `run.json` не тронут.

        Сценарий (две задачи): у первой в хозяйстве `suite-run` уже лежит
        `run.json` прошлого прогона `suite-run` (мёртвый pid), у второй его
        нет. Во время контрольного прогона держатель замка — эта задача с
        номером прогона-строкой, начинающимся с `m`. После команды есть
        `mutation-run.json` и `mutation-result.json`; `run.json` первой —
        байт в байт прежний, у второй его нет.

        Ловит мутацию: номер прогона в замке — число, как у `suite-run`, —
        префикса `m` нет; команда пишет состояние в `run.json`/`result.json`
        `suite-run` — файл первой изменён, у второй появился.
        """
        project = self.add_project()
        for seeded in (True, False):
            with self.subTest(seeded=seeded):
                task_id, _wt = self.add_task(project)
                self.write_patches(project, task_id, [self.comment(project)])
                folder = self.state_dir(task_id)
                folder.mkdir(parents=True, exist_ok=True)
                run_json = folder / "run.json"
                previous = json.dumps({"run": self.rng.randint(1, 9),
                                       "pid": self.dead_pid,
                                       "log": str(folder / "x.log"),
                                       "mode": "full", "started": 1.0}).encode()
                if seeded:
                    run_json.write_bytes(previous)
                probe = RunProbe(acceptance.run_full_suite)
                with mock.patch.object(acceptance, "run_full_suite", probe):
                    text = self.mutate(task_id, "--ref", "head", "--tests",
                                    project["test"])
                self.assertTrue(probe.calls, self.explain(text))
                holder = probe.calls[0]["holder"] or {}
                self.assertEqual(holder.get("task_id"), task_id,
                                 f"держатель {holder}; {self.explain(text)}")
                self.assertIsInstance(holder.get("run"), str,
                                      f"держатель {holder}; {self.explain(text)}")
                self.assertTrue(holder["run"].startswith("m"),
                                f"держатель {holder}; {self.explain(text)}")
                for name in ("mutation-run.json", "mutation-result.json"):
                    self.assertTrue((folder / name).is_file(),
                                    f"нет {name}; {self.explain(text)}")
                if seeded:
                    self.assertEqual(run_json.read_bytes(), previous,
                                     self.explain(text))
                else:
                    self.assertFalse(run_json.exists(), self.explain(text))

    def test_ac13_readonly_db_state_in_suite_run_dir_nothing_written(self):
        """БД только на чтение: состояние — в хозяйстве `suite-run`, в БД ничего не записано.

        Сценарий: открытие БД пульта (`store.db`) отдаёт соединение
        `mode=ro` на всё время команды и её фонового процесса. Прогон
        одного ломающего патча доходит до таблицы («убита»), файлы
        `mutation-run.json`/`mutation-result.json` лежат в
        `suite_lock.directory()/<id>/`, а дамп БД (`iterdump`) до и после
        команды совпадает.

        Ловит мутацию: команда пишет состояние или журнал в БД — отказ
        `sqlite3.OperationalError` роняет команду, таблицы нет; запись в БД
        идёт мимо `store.db` — дамп изменился; состояние кладётся в
        `config.LOGS` вне хозяйства `suite-run` — файлов там нет.
        """
        project = self.add_project()
        task_id, _wt = self.add_task(project)
        self.write_patches(project, task_id, [self.breaking(project)])
        self.conn.commit()

        def readonly_db():
            conn = sqlite3.connect(
                f"{Path(config.DB).resolve().as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            return conn

        def dump() -> list:
            conn = readonly_db()
            try:
                return list(conn.iterdump())
            finally:
                conn.close()

        before = dump()
        with mock.patch.object(store, "db", readonly_db):
            text = self.mutate(task_id, "--ref", "head", "--tests",
                            project["test"])
        self.assertEqual(self.outcomes(task_id).get(1, ("",))[0], KILLED,
                         self.explain(text))
        for name in ("mutation-run.json", "mutation-result.json"):
            self.assertTrue((self.state_dir(task_id) / name).is_file(),
                            f"нет {name}; {self.explain(text)}")
        self.assertEqual(dump(), before, self.explain(text))

    def test_ac13_busy_lock_refuses_at_once_naming_holder(self):
        """Замок занят другим прогоном — отказ сразу с держателем, без контроля и копии.

        Сценарий: замок `suite_lock` держит живой посторонний процесс как
        прогон другой задачи. Вызов команды с годными аргументами
        завершается ненулевым кодом, вывод называет задачу и pid держателя;
        узел прогона не вызван, git в каталоге `artel-suite-base-…` не
        звался; замок после вызова — прежний.

        Ловит мутацию: команда ждёт замок (`wait_acquire`) или берёт его в
        фоне и отказывает молча — держателя в выводе нет; занятый замок
        не проверяется до копии — копия заводилась; команда снимает чужой
        замок — держатель после вызова другой.
        """
        project = self.add_project()
        task_id, _wt = self.add_task(project)
        self.write_patches(project, task_id, [self.breaking(project)])
        other = self.new_task_id()
        pid = _alive_foreign_pid(self)
        suite_lock.hand(other, self.rng.randint(1, 50), pid)
        held = suite_lock.holder()
        self.addCleanup(lambda: suite_lock.path().unlink(missing_ok=True))
        probe = self.probe()
        code, out = self.command(task_id, "--ref", "head", "--tests",
                                 project["test"])
        self.assertNotIn(code, (0, None), self.explain(out))
        self.assertIn(other, out, self.explain(out))
        self.assertIn(str(pid), out, self.explain(out))
        self.assertEqual(probe.calls, [], self.explain(out))
        self.assertEqual(self.git_records(), [], self.explain(out))
        self.assertEqual(suite_lock.holder(), held, self.explain(out))


def registry_keys() -> list:
    """Строковые ключи словаря `table` в исходнике `artel.main`."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(artel.main)))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                and any(isinstance(t, ast.Name) and t.id == "table"
                        for t in node.targets)):
            return [k.value for k in node.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    raise AssertionError("в artel.main нет присваивания `table = {...}`")


def commands_block(doc: str) -> list:
    lines = doc.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "Команды:")
    block = []
    for line in lines[start + 1:]:
        if not line.strip():
            break
        block.append(line)
    return block


class RegistrationTest(MutationRunSandbox):

    def test_ac14_registered_in_table_help_and_role_allowlist(self):
        """`mutation-run` — в `table`, в блоке «Команды:» и доступна процессу роли.

        Сценарий: ключи словаря `table` из исходника `artel.main` содержат
        `mutation-run`; блок «Команды:» докстринга `orchestrator/artel.py`
        называет её отдельным словом команды. Под признаком роли (роль от
        зерна) вызов `artel.py mutation-run` без аргументов не получает
        отказа «команда недоступна процессу роли», а `artel.py kill` в том
        же окружении его получает (признак роли действует).

        Ловит мутацию: команда есть в `table`, но не в белом списке роли —
        отказ роли; не в `table` — «Неизвестная команда» и ключа нет; строка
        справки не добавлена — блок «Команды:» её не называет.
        """
        self.assertIn("mutation-run", registry_keys())
        pattern = re.compile(r"(?:^|(?<=[ |]))mutation-run(?=[ |]|$)")
        self.assertTrue(any(pattern.search(line.strip()) for line in
                            commands_block(artel.__doc__)),
                        "блок «Команды:» не называет mutation-run")
        role = self.rng.choice(sorted(set(config.STATE_ROLE.values())))
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: role}):
            _code, out = self.command()
            buf = io.StringIO()
            with mock.patch.object(sys, "argv", ["artel.py", "kill", "X"]), \
                    contextlib.redirect_stdout(buf), \
                    contextlib.redirect_stderr(buf):
                try:
                    artel.main()
                except SystemExit as exc:
                    buf.write(str(exc.code))
        self.assertNotIn(ROLE_REFUSAL, out, f"роль {role}: {self.explain(out)}")
        self.assertNotIn("Неизвестная команда", out, self.explain(out))
        self.assertIn(ROLE_REFUSAL, buf.getvalue(),
                      f"признак роли не действует: {buf.getvalue()}")


class RoleProcessCliTest(MutationRunSandbox):
    """Настоящий подпроцесс CLI копии пульта в корне песочницы."""

    def setUp(self):
        super().setUp()
        for name in ("orchestrator", "scripts"):
            shutil.copytree(CODE_ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        with open(self.root / "orchestrator" / "config.py", "a",
                  encoding="utf-8") as fh:
            fh.write("\n\n# Песочница теста mutation-run.\n"
                     "FULL_SUITE_WORKERS = 2\n")

    def cli(self, *args: str, role: str) -> str:
        env = {k: v for k, v in os.environ.items()
               if k != config.ARTEL_ROLE_ENV}
        env[config.ARTEL_ROLE_ENV] = role
        proc = subprocess.Popen(
            [sys.executable, str(self.root / "orchestrator" / "artel.py"),
             *args], cwd=str(self.root), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True)
        try:
            raw, _ = proc.communicate(timeout=100)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            raw, _ = proc.communicate()
            self.fail(f"artel.py {' '.join(args)} не вернулся; зерно {self.seed}")
        return raw.decode("utf-8", errors="replace")

    def test_ac7_role_process_cli_runs_xdist_without_role_marker(self):
        """Вызов CLI с `ARTEL_ROLE=developer` и `--wait`: прогон с xdist проходит, исходы получены.

        Сценарий: настоящий подпроцесс `artel.py mutation-run` копии пульта
        (параллель копии — 2) с `ARTEL_ROLE=developer`; в корне проекта —
        `conftest.py`-сторож, роняющий pytest под признаком роли и пишущий
        каждый старт. Два патча: ломающий `add` и правка комментария. В
        таблице 1 — «убита» с `test_add_<w>`, 2 — «не убита»; среди стартов
        pytest есть рабочие процессы xdist, и ни один старт не видел
        признака роли.

        Ловит мутацию: фоновый процесс наследует окружение вызывающего с
        `ARTEL_ROLE` — сторож роняет контроль, исходов нет; команда не
        разрешена роли — отказ, таблицы нет; параллель не передаётся —
        стартов рабочих xdist нет.
        """
        project = self.add_project()
        task_id, _wt = self.add_task(project)
        self.write_patches(project, task_id,
                           [self.breaking(project), self.comment(project)])
        role = config.STATE_ROLE["in_dev"]
        args = ("--ref", "head", "--tests", project["test"])
        outs = [self.cli("mutation-run", task_id, *args, "--wait", "1",
                         role=role)]
        if not (self.state_dir(task_id) / "mutation-run.json").exists():
            outs.append(self.cli("mutation-run", task_id, *args, role=role))
            outs.append(self.cli("mutation-run", task_id, "--wait", "1",
                                 role=role))
            if not (self.state_dir(task_id) / "mutation-result.json").exists():
                outs.append(self.cli("mutation-run", task_id, *args, "--wait",
                                     "1", role=role))
        text = "\n".join(outs + [self.state_text(task_id)])
        rows = self.outcomes(task_id)
        self.assertEqual(rows.get(1, ("", ""))[0], KILLED, self.explain(text))
        self.assertIn(project["add_node"], rows[1][1], self.explain(text))
        self.assertEqual(rows.get(2, ("",))[0], SURVIVED, self.explain(text))
        starts = self.pytest_records()
        self.assertTrue(any(r["worker"] for r in starts),
                        f"стартов рабочих xdist нет: {starts}; "
                        f"{self.explain(text)}")
        self.assertEqual([r for r in starts if r["role"]], [],
                         f"pytest видел признак роли: {starts}; "
                         f"{self.explain(text)}")


if __name__ == "__main__":
    unittest.main()
