"""Планка внешнего проекта исполняется внутри `long_lived_dir`: корень, конфиг, импорты и фикстуры проекта.

Группа: долгоживущий
Красен до реализации: прогоны планки `pytest-own` исполняют её из каталога планки под `tasks` рабочей копии, вне `workdir` — pytest не находит `pyproject.toml`, `pythonpath` и `conftest.py` проекта (сбор красный на импорте модуля проекта), каталога выкладки под `long_lived_dir` на запуске pytest нет, общий `info/exclude` клона без записи, остаток выкладки виден git, уходит в коммит чекпоинта и в сбор полного набора, `drop_from_code_copy` его не убирает, строки о `long_lived_dir` вне `workdir` нет (AC-1, AC-2, AC-4 — AC-12); AC-3 держит прежний исход и зелён с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): клон учебного
внешнего проекта — `tests.sandbox.make_project_repo` со своим `origin`,
рабочая копия задачи — `workspace.ensure` (настоящий `git worktree` клона).
Профиль проекта — `runner: pytest-own` со случайными `workdir` и
`long_lived_dir` под ним; команда профиля — интерпретатор этого процесса
(`sys.executable -m pytest`), то есть прогоны идут настоящим pytest. Код
учебного проекта создаётся тестом во временном каталоге: `pyproject.toml`
в `workdir` с `pythonpath` на каталог исходников, модуль проекта со
значением от зерна и `conftest.py` в `long_lived_dir` с фикстурой того же
значения. Приёмочный тест учебной задачи импортирует модуль проекта и
берёт фикстуру из этого `conftest.py`.

Запуск pytest наблюдается подменой `subprocess.Popen`: в момент запуска
записываются argv, рабочий каталог, цели (аргументы-пути, разрешённые от
рабочего каталога), наличие и содержимое каталога выкладки
`<рабочая копия>/<long_lived_dir>/.artel-plank/<id>/acceptance_tests`, а
по запросу сценария — общий файл исключений клона, `git status` рабочей
копии и `changed_paths()` помощника пульта из выкладки. Затем запуск идёт
настоящим `Popen` либо отвечает исходом сценария (красный, таймаут, нет
команды, исключение). Прочие вызовы (git) — настоящий `subprocess`.
Остаток выкладки, переживший обрыв, имитируется записью файлов по пути
выкладки после прогона. Имена, значения и каталоги — из `random`, зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`run`/`collect`/`run_plank` копируют каталог планки в выкладку под
`long_lived_dir` после записи шаблона `**/.artel-plank/` в общий
`info/exclude` и убирают её в `finally`, `drop_from_code_copy` убирает
остаток, полный прогон получает `--ignore=<long_lived_dir>/.artel-plank`,
при `long_lived_dir` вне `workdir` выкладки нет и печатается строка о
случае; все методы зелёные. Снятие `--ignore` краснит AC-8 в ветке
`norecursedirs` без каталогов с точкой.
"""
import contextlib
import errno
import hashlib
import importlib.util
import io
import os
import random
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, amend, artel, checkpoint, config, idgen,
                          project_profile, store, workspace)
from scripts import guard
from tests.sandbox import RealGitSandbox, artel_target_entry, make_project_repo

REAL_POPEN = subprocess.Popen
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
LAYOUT_DIR = ".artel-plank"
PLANK_DIR = "acceptance_tests"
HELPER = "_pult.py"
# Опции pytest и интерпретатора, чьё значение — следующий аргумент argv.
OPTIONS_WITH_VALUE = ("-m", "-p", "-o", "-c", "-k", "--rootdir", "--junitxml")

ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [{python}, -m, pytest]
      long_lived_dir: {lld}
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [{lld}/**/*.py]
      mutation_claim_scope: [{lld}/test_*.py]
      report: junit-xml
      install: []
      runner: pytest-own
      workdir: {workdir}
"""

PYPROJECT = """[tool.pytest.ini_options]
pythonpath = ["{src}"]
{extra}"""

CONFTEST = """import pytest


@pytest.fixture
def {fixture}():
    return {value}
"""

BASE_TEST = """import {module}


def test_base_{word}({fixture}):
    assert {module}.VALUE == {fixture}
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
budget_usd: 30
---

# SPEC: фикстура учебного проекта

## Контекст

Фикстура песочницы.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстурный критерий.

## Не входит

Ничего.
"""

PLANK_GREEN = '''"""Фикстура планки учебного проекта.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import {module}


def test_ac1_probe_{word}({fixture}):
    """Модуль проекта и фикстура его conftest."""
    assert {module}.VALUE == {fixture} == {value}
'''

PLANK_RED_TAIL = '''

def test_ac1_red_{word}({fixture}):
    """Фикстурный красный тест."""
    assert {fixture} == -1
'''

PLANK_PLAIN = '''"""Фикстура планки без кода проекта."""


def test_ac1_plain_{word}():
    assert 2 + 2 == 4
'''

LEFTOVER_RED = '''def test_ac1_leftover_{word}():
    assert False, "узел остатка выкладки собран"
'''

LONG_LIVED_PLAIN = '''import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def test_{word}(self):
        self.assertEqual(2 + 2, 4)
'''

LONG_LIVED_AMEND = '''"""Фикстура долгоживущего файла песочницы.

Группа: долгоживущий
"""
import random
import unittest


class FixtureLongLived{cls}Test(unittest.TestCase):

    def test_ac1_long_{word}(self):
        """Фикстурный метод долгоживущего файла.

        Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать.
        """
        seed = random.randrange(1 << 30)
        self.assertEqual(1 + 1, 2, f"зерно: {{seed}}")
'''


def is_pytest(argv) -> bool:
    parts = [str(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    return any(Path(p).name in ("pytest", "py.test") for p in parts) or any(
        a == "-m" and b == "pytest" for a, b in zip(parts, parts[1:]))


def files_under(folder: Path) -> dict:
    """{путь от `folder`: байты} файлов каталога без кеша байткода."""
    if not folder.is_dir():
        return {}
    found = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_file() and "__pycache__" not in rel.split("/") \
                and not rel.endswith(".pyc"):
            found[rel] = path.read_bytes()
    return found


def under(path: str, folder: str) -> bool:
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def capture_out(fn, *args, **kwargs) -> str:
    """Вывод вызова вместе с текстом ненулевого `SystemExit`."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue()


class ScenarioProc:
    """Процесс подменённого pytest с исходом сценария."""
    pid = 2_000_000_000
    stdin = stdout = stderr = None

    CODES = {"green": 0, "red": 1, "empty": 5}
    TEXTS = {"green": "1 passed in 0.01s\n", "red": "1 failed in 0.01s\n",
             "empty": "no tests ran in 0.01s\n"}

    def __init__(self, argv, mode):
        self.args = argv
        self.mode = mode
        self.returncode = self.CODES.get(mode, 0)
        self.timed_out = False

    def communicate(self, input=None, timeout=None):
        if self.mode == "timeout" and not self.timed_out:
            self.timed_out = True
            raise subprocess.TimeoutExpired(self.args, timeout or 1,
                                            output="", stderr="")
        return self.TEXTS.get(self.mode, ""), ""

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        pass

    terminate = kill

    def send_signal(self, sig):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class PlankLayoutSandbox(RealGitSandbox):
    """Учебный внешний проект с профилем `pytest-own` и `long_lived_dir`
    внутри `workdir`; второй проект — с `long_lived_dir` вне `workdir`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"sled{self.word()}"
        self.workdir = f"wd{self.word()}"
        self.lld = f"{self.workdir}/t{self.word()}"
        self.src = f"src{self.word()}"
        self.module = f"mod{self.word()}"
        self.fixture = f"probe_{self.word()}"
        self.value = self.rng.randrange(10 ** 5, 10 ** 6)
        self.ext_out = f"out{self.word()}"
        self.out_workdir = f"wd{self.word()}"
        self.out_lld = f"t{self.word()}"
        self.add_synced_origin()
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + ENTRY.format(name=self.ext, base=config.MAIN_BRANCH,
                           python=sys.executable, lld=self.lld,
                           workdir=self.workdir)
            + ENTRY.format(name=self.ext_out, base=config.MAIN_BRANCH,
                           python=sys.executable, lld=self.out_lld,
                           workdir=self.out_workdir),
            encoding="utf-8")
        self.ext_clone = make_project_repo(self.ext)
        self.commit_to_main(self.ext_clone, self.project_files())
        self.calls: list = []
        self.mode = "real"
        self.current = None
        self.probe = False
        for patcher in (mock.patch.object(subprocess, "Popen", self.spy_popen),
                        mock.patch.dict(os.environ,
                                        {config.ARTEL_ROLE_ENV: ""})):
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def explain(self, output: str) -> str:
        calls = "\n".join(f"{c['argv']} @ {c['cwd']}" for c in self.calls)
        return self.note(f"вывод:\n{output[-3000:]}\nвызовы pytest:\n{calls}")

    def project_files(self, norecurse: str | None = None) -> dict:
        extra = f'norecursedirs = ["{norecurse}"]\n' if norecurse else ""
        return {
            f"{self.workdir}/pyproject.toml": PYPROJECT.format(src=self.src,
                                                               extra=extra),
            f"{self.workdir}/{self.src}/{self.module}.py":
                f"VALUE = {self.value}\n",
            f"{self.lld}/conftest.py": CONFTEST.format(fixture=self.fixture,
                                                       value=self.value),
            f"{self.lld}/test_base_{self.word()}.py": BASE_TEST.format(
                module=self.module, fixture=self.fixture, word=self.word()),
        }

    def commit_to_main(self, clone: Path, files: dict) -> None:
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def profile(self, target: str):
        profile = project_profile.decide(target).profile
        self.assertIsNotNone(profile, self.note(f"профиля {target} нет"))
        return profile

    def target_of(self, task_id: str) -> str:
        return store.task_target(self.conn, task_id)

    def new_task(self, target: str, state: str) -> str:
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, target, config.DEFAULT_BUDGET_USD)
        _wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.commit_docs(task_id, {"SPEC.md": SPEC_TEXT.format(task=task_id)})
        return task_id

    def branch(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["branch"]

    def docs_dir(self, task_id: str) -> Path:
        return config.PROJECTS / self.target_of(task_id) / "tasks" / task_id

    def wt(self, task_id: str) -> Path:
        return workspace.path(task_id, self.target_of(task_id))

    def plank_dir(self, task_id: str) -> Path:
        """Каталог планки задачи под `tasks` рабочей копии кода."""
        return self.wt(task_id) / "tasks" / task_id / PLANK_DIR

    def lld_of(self, task_id: str) -> str:
        return self.profile(self.target_of(task_id)).long_lived_dir

    def layout_root(self, task_id: str) -> Path:
        return self.wt(task_id) / self.lld_of(task_id) / LAYOUT_DIR / task_id

    def layout(self, task_id: str) -> Path:
        return self.layout_root(task_id) / PLANK_DIR

    def write_docs(self, task_id: str, files: dict) -> None:
        for rel, text in files.items():
            path = self.docs_dir(task_id) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit_docs(self, task_id: str, files: dict) -> None:
        """Файлы в каталог документов и в ссылку документов задачи."""
        self.write_docs(task_id, files)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            checkpoint.commit_step_artifacts(self.conn, task_id, "test_author")
        store.record_fixation(self.conn, task_id)

    def plank(self, red: bool = False) -> tuple:
        """(имя файла, текст, имя зелёного теста, имя красного теста)."""
        word, red_word = self.word(), self.word()
        text = PLANK_GREEN.format(module=self.module, fixture=self.fixture,
                                  value=self.value, word=word)
        if red:
            text += PLANK_RED_TAIL.format(fixture=self.fixture, word=red_word)
        return (f"test_ac1_{self.word()}.py", text, f"test_ac1_probe_{word}",
                f"test_ac1_red_{red_word}")

    def draft(self, task_id: str, red: bool = False) -> tuple:
        """Черновик планки в каталоге документов (`tests_writing`)."""
        plank = self.plank(red)
        self.write_docs(task_id, {f"{PLANK_DIR}/{plank[0]}": plank[1]})
        return plank

    def commit_code(self, task_id: str, files: dict, push: bool = True) -> None:
        wt = self.wt(task_id)
        for rel, text in files.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", "код задачи")
        if push:
            branch = self.branch(task_id)
            self.git("-C", str(wt), "push", "-q", "-f", "origin",
                     f"{branch}:{branch}")

    def leave_leftover(self, task_id: str, files: dict) -> None:
        """Остаток выкладки, переживший обрыв прогона без уборки."""
        for rel, text in files.items():
            path = self.layout(task_id) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------ git

    def status(self, task_id: str) -> str:
        return self.git("-C", str(self.wt(task_id)), "status", "--porcelain",
                        "--untracked-files=all")

    def exclude_path(self, task_id: str) -> Path:
        wt = self.wt(task_id)
        raw = Path(self.git("-C", str(wt), "rev-parse", "--git-path",
                            "info/exclude").strip())
        return raw if raw.is_absolute() else wt / raw

    def exclude_text(self, task_id: str) -> str:
        path = self.exclude_path(task_id)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def head(self, task_id: str) -> str:
        return self.git("-C", str(self.wt(task_id)), "rev-parse", "HEAD").strip()

    # ------------------------------------------------------------ запуск pytest

    def targets_of(self, argv: list, cwd: str) -> list:
        """(абсолютный путь, узел) аргументов-путей вызова pytest,
        разрешённых от его рабочего каталога."""
        found = []
        for prev, arg in zip(argv, argv[1:]):
            if arg.startswith("-") or prev in OPTIONS_WITH_VALUE:
                continue
            path, _sep, node = arg.partition("::")
            found.append((os.path.realpath(os.path.join(cwd, path)), node))
        return found

    def helper_changed_paths(self, helper: Path):
        """`changed_paths()` помощника пульта, лежащего в выкладке."""
        spec = importlib.util.spec_from_file_location(
            f"pult_probe_{self.word()}", helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.changed_paths()

    def record(self, argv, kwargs) -> dict:
        argv = [str(a) for a in argv]
        cwd = kwargs.get("cwd")
        cwd = os.path.realpath(cwd if cwd is not None else os.getcwd())
        call = {"argv": argv, "cwd": cwd,
                "targets": self.targets_of(argv, cwd)}
        task = self.current
        if task is not None:
            call["layout_exists"] = self.layout_root(task).is_dir()
            call["layout_files"] = files_under(self.layout(task))
            call["disk_plank"] = files_under(self.plank_dir(task))
            call["any_layout"] = self.layout_dirs(task)
            if self.probe:
                call["exclude"] = self.exclude_text(task)
                call["status"] = self.status(task)
                helper = self.layout(task) / HELPER
                call["changed"] = (self.helper_changed_paths(helper)
                                   if helper.is_file() else None)
        self.calls.append(call)
        return call

    def spy_popen(self, argv, *args, **kwargs):
        if not is_pytest(argv):
            return REAL_POPEN(argv, *args, **kwargs)
        self.record(argv, kwargs)
        if self.mode == "real":
            return REAL_POPEN(argv, *args, **kwargs)
        if self.mode == "notfound":
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT),
                                    str(argv[0]))
        if self.mode == "boom":
            raise RuntimeError(f"сбой внутри прогона (зерно {self.seed})")
        return ScenarioProc(argv, self.mode)

    def layout_dirs(self, task_id: str) -> list:
        """Каталоги с именем каталога выкладки в рабочей копии (вне `.git`)."""
        found = []
        for top, dirs, _files in os.walk(self.wt(task_id)):
            dirs[:] = [d for d in dirs if d != ".git"]
            found += [os.path.join(top, d) for d in dirs if d == LAYOUT_DIR]
        return found

    # ------------------------------------------------------------ прогоны

    def direct(self, task_id: str, fn, files: dict) -> tuple:
        """`fn` (`acceptance.collect`/`acceptance.run`) по планке `files`,
        выложенной `plank_in_code_copy`; (исход, вывод, статус до, статус
        после, исключение)."""
        self.current = task_id
        self.calls = []
        wt = self.wt(task_id)
        profile = self.profile(self.target_of(task_id))
        result, error = (None, ""), None
        with acceptance.plank_in_code_copy(task_id, self.branch(task_id), wt,
                                           files=files) as tdir:
            before = self.status(task_id)
            try:
                result = fn(tdir, cwd=wt, command=profile)
            except RuntimeError as exc:
                error = exc
            after = self.status(task_id)
        return result[0], result[1], before, after, error

    def plank_run(self, task_id: str, *extra: str) -> tuple:
        """(код выхода, весь вывод, исключение) `artel.py plank-run <id>
        [путь]`; вызовы pytest — в `self.calls`."""
        self.current = task_id
        self.calls = []
        argv = ["artel.py", "plank-run", task_id, *extra]
        out, err = io.StringIO(), io.StringIO()
        code, error = None, None
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out), \
                redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
            except RuntimeError as exc:
                error = exc
        message = "" if code is None or isinstance(code, int) else str(code)
        status = code if isinstance(code, int) else (0 if code is None else 1)
        return status, "\n".join((out.getvalue(), err.getvalue(), message)), \
            error

    def places(self, task_id: str, files: dict) -> list:
        """(место, вызов -> (исход, вывод, статус до, статус после, ошибка))
        трёх прогонов планки: сбор, прогон, `plank-run`."""
        def run_plank():
            before = self.status(task_id)
            code, output, error = self.plank_run(task_id)
            return code == 0, output, before, self.status(task_id), error
        return [
            ("collect", lambda: self.direct(task_id, acceptance.collect, files)),
            ("run", lambda: self.direct(task_id, acceptance.run, files)),
            ("plank-run", run_plank),
        ]


class Ac1ProjectImportsAndFixturesTest(PlankLayoutSandbox):

    def test_ac1_collect_and_run_green_with_project_code_and_fixture(self):
        """Приёмочный тест учебного проекта импортирует модуль проекта и берёт фикстуру его `conftest.py`: сбор «собралось», прогон «зелёно».

        Сценарий: задача учебного проекта (`workdir` с `pyproject.toml`,
        `pythonpath` на каталог исходников, `conftest.py` с фикстурой в
        `long_lived_dir`); планка — один файл, который импортирует модуль
        проекта и сверяет его значение с фикстурой. Сухой сбор
        `acceptance.collect` и прогон `acceptance.run` настоящим pytest по
        профилю проекта возвращают `True`; каждый — одним запуском pytest.

        Ловит мутацию: планка исполняется из каталога под `tasks` рабочей
        копии (вне `workdir`) — pytest не видит `pyproject.toml`, импорт
        модуля проекта падает, сбор возвращает `False` с ошибкой импорта;
        выкладка ложится в `workdir`, а не под `long_lived_dir` — фикстура
        `conftest.py` не найдена, прогон возвращает `False`.
        """
        task_id = self.new_task(self.ext, "tests_writing")
        name, text, _green, _red = self.plank()
        for label, fn in (("collect", acceptance.collect),
                          ("run", acceptance.run)):
            with self.subTest(place=label, seed=self.seed):
                ok, output, _before, _after, error = self.direct(
                    task_id, fn, {name: text})
                self.assertIsNone(error, self.explain(f"{label}: {error}"))
                self.assertTrue(ok, self.explain(f"{label}: не зелёно\n{output}"))
                self.assertEqual(len(self.calls), 1, self.explain(output))


class Ac2PlankRunTargetsTest(PlankLayoutSandbox):

    def test_ac2_plank_run_targets_are_layout_paths_and_exit_zero(self):
        """`plank-run <id>`, `<id> <файл>` и `<id> <файл>::<узел>` гонят одной целью путь выкладки и завершаются кодом 0.

        Сценарий: задача учебного проекта в `tests_writing`, черновик
        планки — тот же приёмочный тест (модуль проекта и фикстура
        `conftest.py`). Каждый из трёх вызовов запускает pytest ровно раз;
        единственная цель, разрешённая от рабочего каталога вызова, —
        каталог выкладки `<рабочая копия>/<long_lived_dir>/.artel-plank/<id>/acceptance_tests`,
        тот же путь с `/<файл>` и тот же путь с `/<файл>::<узел>`; код
        выхода команды — 0.

        Ловит мутацию: `plank-run` гонит прежний каталог планки под `tasks`
        — цель не путь выкладки, импорт модуля проекта падает, код
        ненулевой; аргумент `<файл>` не переводится в путь выкладки либо
        узел `::<узел>` отбрасывается — цель не та, что в ожидании; к
        цели добавлен весь каталог выкладки — целей две.
        """
        task_id = self.new_task(self.ext, "tests_writing")
        name, _text, green, _red = self.draft(task_id)
        layout = self.layout(task_id)
        for args, expected in (
                ((), [(str(layout), "")]),
                ((name,), [(str(layout / name), "")]),
                ((f"{name}::{green}",), [(str(layout / name), green)])):
            with self.subTest(args=args, seed=self.seed):
                code, output, error = self.plank_run(task_id, *args)
                self.assertIsNone(error, self.explain(f"{error}\n{output}"))
                self.assertEqual(len(self.calls), 1, self.explain(output))
                self.assertTrue(self.calls[0]["layout_exists"],
                                self.explain(f"выкладки нет на запуске\n{output}"))
                real = [(os.path.realpath(path), node)
                        for path, node in expected]
                self.assertEqual(self.calls[0]["targets"], real,
                                 self.explain(output))
                self.assertEqual(code, 0, self.explain(output))


class Ac3LongLivedPathWithoutLayoutTest(PlankLayoutSandbox):

    def test_ac3_long_lived_path_creates_no_layout_and_targets_no_plank(self):
        """`plank-run <id> <долгоживущий путь>[::<узел>]` не создаёт каталог выкладки и не гонит планку.

        Сценарий: задача учебного проекта в `tests_writing` с черновиком
        планки; свой долгоживущий файл (шаблон профиля) лежит в рабочей
        копии. Вызов с путём и с `<путь>::<тест>` запускает pytest; в
        момент запуска (шпион на `Popen`) каталога
        `<рабочая копия>/<long_lived_dir>/.artel-plank/<id>/` на диске нет,
        и ни одна цель вызова не лежит ни под каталогом планки под
        `tasks` рабочей копии, ни под этим каталогом выкладки.

        Ловит мутацию: выкладка делается на каждом `plank-run`, в том числе
        с путём долгоживущего файла, — каталог выкладки есть на запуске
        pytest; путь долгоживущего файла гонится вместе с планкой — среди
        целей путь выкладки или каталога планки.
        """
        task_id = self.new_task(self.ext, "tests_writing")
        self.draft(task_id)
        profile = self.profile(self.ext)
        rel = f"{profile.long_lived_prefix(task_id)}{self.word()}.py"
        self.assertTrue(profile.is_long_lived(task_id, rel), self.note(rel))
        test_name = f"test_{self.word()}"
        path = self.wt(task_id) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(LONG_LIVED_PLAIN.format(word=test_name[5:]),
                        encoding="utf-8")
        plank = os.path.realpath(self.plank_dir(task_id))
        layout = os.path.realpath(self.layout_root(task_id))
        for node in ("", f"FixtureLongLivedTest::{test_name}"):
            with self.subTest(node=node, seed=self.seed):
                arg = f"{rel}::{node}" if node else rel
                _code, output, error = self.plank_run(task_id, arg)
                self.assertIsNone(error, self.explain(f"{error}\n{output}"))
                self.assertEqual(len(self.calls), 1, self.explain(output))
                call = self.calls[0]
                self.assertFalse(call["layout_exists"],
                                 self.explain(f"выкладка на запуске\n{output}"))
                for target, _node in call["targets"]:
                    self.assertFalse(under(target, plank) or under(target, layout),
                                     self.explain(f"цель {target}\n{output}"))


class Ac4AmendTestsLayoutTest(PlankLayoutSandbox):

    def docs_head(self, task_id: str) -> str:
        return self.git("-C", str(self.ext_clone), "for-each-ref",
                        "--format=%(objectname)",
                        "refs/artifacts/" + task_id).strip()

    def locked_task(self, long_lived: bool) -> tuple:
        """Задача `in_dev` с планкой лока (и перечнем долгоживущего файла)
        и правкой Оператора планки на диске рабочей копии; (id, правленые
        файлы каталога планки)."""
        task_id = self.new_task(self.ext, "in_dev")
        name, text, _green, _red = self.plank()
        files = {f"{PLANK_DIR}/{name}": text}
        if long_lived:
            profile = self.profile(self.ext)
            rel = f"{profile.long_lived_prefix(task_id)}{self.word()}.py"
            self.commit_code(task_id, {rel: LONG_LIVED_AMEND.format(
                cls=self.word().capitalize(), word=self.word())})
            digest = hashlib.sha256(
                (self.wt(task_id) / rel).read_bytes()).hexdigest()
            files[f"{PLANK_DIR}/{guard.LONG_LIVED_MANIFEST_NAME}"] = \
                guard.render_long_lived_manifest({rel: digest})
        self.commit_docs(task_id, files)
        store.update_task(self.conn, task_id,
                          tests_locked_sha=self.docs_head(task_id),
                          draft_mr_created=1)
        store.record_fixation(self.conn, task_id)
        edited = {}
        for rel, body in files.items():
            if Path(rel).name.startswith("test_"):
                body += f"\n# правка Оператора {self.word()}\n"
            edited[rel[len(PLANK_DIR) + 1:]] = body.encode("utf-8")
            target = self.plank_dir(task_id) / rel[len(PLANK_DIR) + 1:]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body.encode("utf-8"))
        return task_id, edited

    def test_ac4_amend_tests_both_branches_run_from_layout(self):
        """`amend-tests` с перечнем долгоживущих и без него проходит сбор и прогон из выкладки с файлами правки и помощником.

        Сценарий: задача учебного проекта в `in_dev` с зафиксированной
        планкой (приёмочный тест на модуле и фикстуре проекта), в одной
        ветви — с долгоживущим файлом в кодовой ветке и перечнем его
        суммы в планке. Оператор правит файл планки на диске рабочей копии
        и зовёт `amend-tests`. Каждый запуск pytest (сбор и прогон)
        застаёт выкладку, чьи файлы побайтно равны файлам каталога планки
        рабочей копии в тот же момент (правленые файлы и помощник, который
        выкладывает `plank_helper_laid_out`); правка проходит без отказа —
        лок сдвинут, запись правки планки в журнале.

        Ловит мутацию: ветвь `amend-tests` гонит прежний каталог планки под
        `tasks` — выкладки на запуске нет, сбор красный на импорте модуля
        проекта, отказ «сухой сбор … не прошёл»; выкладка берётся из
        ссылки документов, а не с диска — файл правки в выкладке без
        правки; помощник в выкладку не кладётся — файла `_pult.py` в ней
        нет.
        """
        for long_lived in (False, True):
            with self.subTest(long_lived=long_lived, seed=self.seed):
                task_id, edited = self.locked_task(long_lived)
                old = store.get_task(self.conn, task_id)["tests_locked_sha"]
                self.current = task_id
                self.calls = []
                output = capture_out(amend.cmd_amend_tests, task_id,
                                     f"правка планки {self.seed}")
                self.assertNotIn("отказ", output, self.explain(output))
                self.assertTrue(self.calls, self.explain(output))
                for call in self.calls:
                    self.assertTrue(call["layout_exists"],
                                    self.explain(f"выкладки нет\n{output}"))
                    self.assertIn(HELPER, call["layout_files"],
                                  self.explain(f"нет помощника\n{output}"))
                    for rel, body in edited.items():
                        self.assertEqual(call["layout_files"].get(rel), body,
                                         self.explain(f"{rel} не с диска\n{output}"))
                    self.assertEqual(call["layout_files"], call["disk_plank"],
                                     self.explain(f"выкладка не равна диску\n{output}"))
                row = store.get_task(self.conn, task_id)
                self.assertNotEqual(row["tests_locked_sha"], old,
                                    self.explain(output))
                actions = [r["action"] for r in store.task_steps(self.conn,
                                                                 task_id)]
                self.assertIn(amend.AMEND_ACTION, actions, self.explain(output))


class Ac5CleanupOnEveryOutcomeTest(PlankLayoutSandbox):

    def test_ac5_layout_removed_and_status_restored_on_every_outcome(self):
        """Сбор, прогон и `plank-run` убирают выкладку на зелёном, красном исходе, таймауте, отказе запуска и исключении.

        Сценарий: задача учебного проекта в `tests_writing` с черновиком
        планки. Для каждого из трёх мест и каждого исхода запуска pytest
        (зелёный, красный, превышение `config.ACCEPTANCE_TIMEOUT_SEC`,
        команда профиля не найдена, исключение внутри прогона) выкладка
        есть в момент запуска, а после возврата каталога
        `<long_lived_dir>/.artel-plank/<id>/` в рабочей копии нет и
        `git status --porcelain --untracked-files=all` совпадает с выводом
        до прогона.

        Ловит мутацию: уборка выкладки не в `finally` — на таймауте, отказе
        запуска или исключении каталог выкладки остаётся на диске; уборка
        снимает только файлы планки, а каталог `.artel-plank/<id>/` или
        кеш байткода остаются — каталог есть после прогона.
        """
        task_id = self.new_task(self.ext, "tests_writing")
        name, text, _green, _red = self.draft(task_id)
        for mode in ("green", "red", "timeout", "notfound", "boom"):
            for label, call in self.places(task_id, {name: text}):
                with self.subTest(place=label, mode=mode, seed=self.seed):
                    self.mode = mode
                    try:
                        _ok, output, before, after, error = call()
                    finally:
                        self.mode = "real"
                    if mode == "boom":
                        self.assertIsInstance(error, RuntimeError,
                                              self.explain(output))
                    self.assertEqual(len(self.calls), 1, self.explain(output))
                    self.assertTrue(self.calls[0]["layout_exists"],
                                    self.explain(f"выкладки нет на запуске\n{output}"))
                    self.assertFalse(self.layout_root(task_id).exists(),
                                     self.explain(f"выкладка осталась\n{output}"))
                    self.assertEqual(after, before, self.explain(output))


class Ac6SharedExcludeTest(PlankLayoutSandbox):

    def test_ac6_shared_exclude_single_pattern_hides_leftover(self):
        """Общий `info/exclude` клона несёт одну строку шаблона выкладки без id задач; остаток не виден git и убирается `drop_from_code_copy`.

        Сценарий: две задачи учебного проекта; рабочие копии — `git
        worktree` клона (`.git` рабочей копии — файл, файл исключений по
        `git rev-parse --git-path info/exclude` лежит вне рабочей копии).
        После прогона планки первой задачи в файле ровно одна строка с
        `.artel-plank` и нет строк с id задач; второй прогон той же задачи
        и прогон другой задачи файл не меняют; нового `.gitignore` в
        дереве рабочих копий нет. Файлы, оставленные по пути выкладки
        (имитация обрыва без уборки), не видны в `git status --porcelain
        --untracked-files=all`, а `acceptance.drop_from_code_copy` убирает
        каталог `.artel-plank/<id>/` с диска.

        Ловит мутацию: шаблон пишется на каждый прогон — строк две и
        больше, файл растёт; запись несёт id задачи — строка с id;
        исключение кладётся `.gitignore` в дерево — новый `.gitignore`;
        записи нет — остаток виден строкой `??`; `drop_from_code_copy`
        убирает только каталог под `tasks` — остаток на диске.
        """
        first = self.new_task(self.ext, "tests_writing")
        second = self.new_task(self.ext, "tests_writing")
        name, text, _green, _red = self.plank()
        files = {name: text}
        for task_id in (first, second):
            wt = self.wt(task_id)
            self.assertTrue((wt / ".git").is_file(),
                            self.note(f"{wt} — не git worktree"))
            self.assertFalse(under(os.path.realpath(self.exclude_path(task_id)),
                                   os.path.realpath(wt)),
                             self.note("файл исключений внутри рабочей копии"))
        ignores = {t: self.gitignores(t) for t in (first, second)}

        ok, output, *_rest = self.direct(first, acceptance.run, files)
        self.assertTrue(ok, self.explain(output))
        text_after = self.exclude_text(first)
        lines = [line for line in text_after.splitlines() if LAYOUT_DIR in line]
        self.assertEqual(len(lines), 1, self.note(f"info/exclude:\n{text_after}"))
        for task_id in (first, second):
            self.assertFalse(any(task_id.lower() in line.lower()
                                 for line in text_after.splitlines()),
                             self.note(f"строка с id {task_id}:\n{text_after}"))
        for task_id in (first, second):
            ok, output, *_rest = self.direct(task_id, acceptance.run, files)
            self.assertTrue(ok, self.explain(output))
            self.assertEqual(self.exclude_text(task_id), text_after,
                             self.explain(f"info/exclude изменён\n{output}"))
        for task_id in (first, second):
            self.assertEqual(self.gitignores(task_id), ignores[task_id],
                             self.note("новый .gitignore в дереве"))

        before = self.status(first)
        self.leave_leftover(first, {name: text, HELPER: "TASK_ID = ''\n"})
        self.assertEqual(self.status(first), before,
                         self.note("остаток выкладки виден git"))
        acceptance.drop_from_code_copy(first, self.wt(first))
        self.assertFalse(self.layout_root(first).exists(),
                         self.note("drop_from_code_copy не убрал остаток"))

    def gitignores(self, task_id: str) -> set:
        found = set()
        for top, dirs, files in os.walk(self.wt(task_id)):
            dirs[:] = [d for d in dirs if d != ".git"]
            found |= {os.path.join(top, f) for f in files if f == ".gitignore"}
        return found


class Ac7BranchDiffTest(PlankLayoutSandbox):

    def test_ac7_branch_diff_carries_no_plank_files(self):
        """Дифф ветки задачи после прогонов планки и чекпоинта не несёт файлов планки и путей выкладки.

        Сценарий: задача учебного проекта в `tests_writing` с черновиком
        планки; прогон `acceptance.run` и `plank-run`, затем в рабочей
        копии появляется файл кода задачи, и чекпоинт developer
        (`checkpoint.commit_success_checkpoint`, `git add -A`) коммитит её.
        Дифф ветки от `origin/<база>` несёт файл кода (чекпоинт
        состоялся), но ни одного пути под `.artel-plank` и ни одного файла
        с именем файла планки или помощника.

        Ловит мутацию: выкладка не убирается или не исключена из git —
        файл выкладки уходит в коммит чекпоинта и в дифф ветки; планка
        выкладывается в отслеживаемое место дерева — её файл в диффе.
        """
        task_id = self.new_task(self.ext, "tests_writing")
        name, text, _green, _red = self.draft(task_id)
        ok, output, *_rest = self.direct(task_id, acceptance.run, {name: text})
        self.assertTrue(ok, self.explain(output))
        code, output, error = self.plank_run(task_id)
        self.assertIsNone(error, self.explain(output))
        self.assertEqual(code, 0, self.explain(output))
        code_rel = f"kod{self.word()}/m{self.word()}.py"
        path = self.wt(task_id) / code_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"A = {self.seed}\n", encoding="utf-8")
        capture_out(checkpoint.commit_success_checkpoint, self.conn, task_id,
                    "developer")
        diff = self.git("-C", str(self.wt(task_id)), "diff", "--name-only",
                        f"origin/{config.MAIN_BRANCH}...HEAD").split()
        self.assertIn(code_rel, diff, self.note(f"чекпоинт не состоялся: {diff}"))
        for rel in diff:
            self.assertNotIn(LAYOUT_DIR, rel, self.note(f"дифф: {diff}"))
            self.assertNotIn(Path(rel).name, (name, HELPER),
                             self.note(f"дифф: {diff}"))


class Ac8FullSuiteIsolationTest(PlankLayoutSandbox):

    def test_ac8_full_suite_skips_layout_leftover_at_any_norecursedirs(self):
        """Полный прогон набора с целью `long_lived_dir` не собирает остаток выкладки; итог по `clean_tree_sha` без узлов планки; argv без `acceptance_tests`.

        Сценарий: задача учебного проекта, в одной ветви — с
        `norecursedirs` проекта без каталогов с точкой (закоммичен в ветку
        задачи). После прогона планки по пути выкладки остаётся файл с
        падающим тестом (обрыв без уборки). `acceptance.full_suite` по
        профилю проекта настоящим pytest: исход — зелёный, в логе нет
        путей `.artel-plank`, итог сохранён под `clean_tree_sha` рабочей
        копии и не несёт узлов `.artel-plank`; ни один аргумент argv
        полного прогона не содержит `acceptance_tests`.

        Ловит мутацию: полный прогон не исключает выкладку — при
        `norecursedirs` без точек pytest собирает упавший узел остатка,
        исход красный, узел в сохранённом итоге; исключение передано
        аргументом с `acceptance_tests` — подстрока в argv; остаток виден
        git — дерево грязное, итог под sha не сохранён.
        """
        for norecurse in (None, f"build{self.word()}"):
            with self.subTest(norecurse=norecurse, seed=self.seed):
                task_id = self.new_task(self.ext, "in_dev")
                if norecurse:
                    self.commit_code(task_id, {
                        f"{self.workdir}/pyproject.toml": PYPROJECT.format(
                            src=self.src,
                            extra=f'norecursedirs = ["{norecurse}"]\n')},
                        push=False)
                name, text, _green, _red = self.plank()
                ok, output, *_rest = self.direct(task_id, acceptance.run,
                                                 {name: text})
                self.assertTrue(ok, self.explain(output))
                self.leave_leftover(task_id, {
                    f"test_ac1_left_{self.word()}.py":
                        LEFTOVER_RED.format(word=self.word()),
                    HELPER: "TASK_ID = ''\n"})
                self.current = None
                self.calls = []
                wt = self.wt(task_id)
                with redirect_stdout(io.StringIO()):
                    result = acceptance.full_suite(
                        wt, task_id, command=self.profile(self.ext), fresh=True)
                log = (result.log_path.read_text(encoding="utf-8")
                       if result.log_path else result.detail)
                self.assertTrue(self.calls, self.note(result.detail))
                for call in self.calls:
                    self.assertFalse(any(PLANK_DIR in arg for arg in call["argv"]),
                                     self.note(f"argv: {call['argv']}"))
                self.assertEqual(result.outcome, acceptance.FULL_SUITE_GREEN,
                                 self.note(f"{result.detail}\n{log[-3000:]}"))
                self.assertNotIn(LAYOUT_DIR, log, self.note(log[-3000:]))
                sha = acceptance.clean_tree_sha(wt)
                self.assertTrue(sha, self.note(f"дерево грязное:\n"
                                               f"{self.status(task_id)}"))
                saved = acceptance.saved_failures(sha)
                self.assertIsNotNone(saved, self.note("итог под sha не сохранён"))
                self.assertFalse([n for n in saved if LAYOUT_DIR in n],
                                 self.note(f"итог: {saved}"))


class Ac9InvisibleDuringRunTest(PlankLayoutSandbox):

    def test_ac9_layout_invisible_to_changed_paths_and_zone_status(self):
        """Во время прогона строка исключения уже записана, `changed_paths()` и статус гейта зон без путей выкладки; после прогона входы гейтов прежние.

        Сценарий: задача учебного проекта в `in_dev` с закоммиченным кодом и
        зафиксированной планкой. Сбор, прогон и `plank-run`: в момент
        запуска pytest файлы выкладки на диске, в общем файле исключений
        клона есть строка `.artel-plank`, а `changed_paths()` помощника из
        выкладки и `git status --porcelain --untracked-files=all` рабочей
        копии (список путей гейта зон) не несут путей `.artel-plank`.
        После прогона и при остатке выкладки на диске статус, голова ветки
        и дерево `long_lived_dir` головы — те же, что на этой ветке до
        прогонов: гейт зон и сверка долгоживущих файлов по перечню читают
        ровно эти входы.

        Ловит мутацию: исключение дописывается после записи файлов
        выкладки или не дописывается — на запуске строки нет, путь
        выкладки в `changed_paths()` и в статусе строкой `??`; остаток
        выкладки виден git — статус после прогона отличается от исходного.
        """
        task_id = self.new_task(self.ext, "in_dev")
        self.commit_code(task_id, {f"kod{self.word()}/m.py": f"A = {self.seed}\n"})
        name, text, _green, _red = self.plank()
        self.commit_docs(task_id, {f"{PLANK_DIR}/{name}": text})
        wt = str(self.wt(task_id))
        base_status = self.status(task_id)
        base_head = self.head(task_id)
        base_tree = self.git("-C", wt, "ls-tree", "-r", "HEAD", "--",
                             self.lld)
        self.probe = True
        for label, call in self.places(task_id, {name: text}):
            with self.subTest(place=label, seed=self.seed):
                ok, output, _before, _after, error = call()
                self.assertIsNone(error, self.explain(output))
                self.assertEqual(len(self.calls), 1, self.explain(output))
                seen = self.calls[0]
                self.assertTrue(seen["layout_files"],
                                self.explain(f"файлов выкладки нет\n{output}"))
                self.assertTrue(any(LAYOUT_DIR in line for line in
                                    seen["exclude"].splitlines()),
                                self.explain(f"исключения нет:\n{seen['exclude']}"))
                self.assertIsNotNone(seen["changed"], self.explain(output))
                self.assertFalse([p for p in seen["changed"] if LAYOUT_DIR in p],
                                 self.explain(f"changed_paths: {seen['changed']}"))
                self.assertNotIn(LAYOUT_DIR, seen["status"],
                                 self.explain(f"статус:\n{seen['status']}"))
        self.probe = False
        self.leave_leftover(task_id, {name: text, HELPER: "TASK_ID = ''\n"})
        self.assertEqual(self.status(task_id), base_status,
                         self.note("статус после прогона другой"))
        self.assertEqual(self.head(task_id), base_head, self.note("голова сдвинута"))
        self.assertEqual(self.git("-C", wt, "ls-tree", "-r", "HEAD", "--",
                                  self.lld), base_tree,
                         self.note("дерево long_lived_dir изменено"))


class Ac10CheckpointLeftoverTest(PlankLayoutSandbox):

    def test_ac10_leftover_not_committed_by_checkpoint(self):
        """Остаток выкладки не попадает в коммит `git add -A` чекпоинта и в область `weakening_scope`.

        Сценарий: задача учебного проекта в `in_dev`; прогон планки,
        затем по пути выкладки остаются файлы (имитация неудачной уборки),
        в рабочей копии появляется файл кода задачи, и чекпоинт developer
        (`checkpoint.commit_success_checkpoint`) коммитит рабочую копию. В
        дереве коммита есть файл кода, но нет путей `.artel-plank`; среди
        путей диффа ветки, попадающих в `weakening_scope` профиля, путей
        выкладки нет.

        Ловит мутацию: каталог выкладки не исключён из git (или исключён
        `.gitignore`, который чекпоинт снимает) — `git add -A` подбирает
        остаток, путь `.artel-plank` в дереве коммита и в области гейта
        неослабления.
        """
        task_id = self.new_task(self.ext, "in_dev")
        name, text, _green, _red = self.plank()
        ok, output, *_rest = self.direct(task_id, acceptance.run, {name: text})
        self.assertTrue(ok, self.explain(output))
        self.leave_leftover(task_id, {name: text, HELPER: "TASK_ID = ''\n"})
        code_rel = f"kod{self.word()}/m{self.word()}.py"
        path = self.wt(task_id) / code_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"A = {self.seed}\n", encoding="utf-8")
        capture_out(checkpoint.commit_success_checkpoint, self.conn, task_id,
                    "developer")
        wt = str(self.wt(task_id))
        tree = self.git("-C", wt, "ls-tree", "-r", "--name-only",
                        "HEAD").split()
        self.assertIn(code_rel, tree, self.note(f"чекпоинт не состоялся: {tree}"))
        self.assertFalse([p for p in tree if LAYOUT_DIR in p],
                         self.note(f"дерево коммита: {tree}"))
        diff = self.git("-C", wt, "diff", "--name-only",
                        f"origin/{config.MAIN_BRANCH}...HEAD").split()
        profile = self.profile(self.ext)
        scoped = [p for p in diff if profile.in_weakening_scope(p)]
        self.assertFalse([p for p in scoped if LAYOUT_DIR in p],
                         self.note(f"область неослабления: {scoped}"))


class Ac11NodePathsTest(PlankLayoutSandbox):

    def test_ac11_node_path_names_task_and_plank_file(self):
        """Путь узла планки в выводе несёт id задачи и имя файла планки; заголовок называет каталог планки под `tasks`.

        Сценарий: задача учебного проекта в `tests_writing`, черновик
        планки с зелёным и красным тестом на модуле и фикстуре проекта.
        Вывод `acceptance.run` (красный) и `plank-run` несёт строку с узлом
        `<файл>::<красный тест>`, в которой есть id задачи; первая строка
        вывода `acceptance.run` — «планка: <каталог>, cwd: …», где каталог
        оканчивается на `tasks`/<id>/`acceptance_tests`.

        Ловит мутацию: выкладка без сегмента id задачи — узел без id;
        заголовок печатает путь выкладки вместо каталога планки — каталог
        заголовка не оканчивается на каталог планки задачи; планка гонится
        из прежнего места — импорт модуля проекта падает, узла
        `<файл>::<тест>` в выводе нет.
        """
        task_id = self.new_task(self.ext, "tests_writing")
        name, text, _green, red = self.draft(task_id, red=True)
        node = f"{name}::{red}"
        ok, output, *_rest = self.direct(task_id, acceptance.run, {name: text})
        self.assertFalse(ok, self.explain(output))
        header = output.splitlines()[0] if output else ""
        self.assertTrue(header.startswith("планка: "), self.explain(output))
        folder = header[len("планка: "):].split(", cwd: ")[0]
        self.assertTrue(folder.endswith(os.path.join("tasks", task_id, PLANK_DIR)),
                        self.explain(f"заголовок: {header}"))
        code, plank_output, _error = self.plank_run(task_id)
        self.assertNotEqual(code, 0, self.explain(plank_output))
        for label, text_out in (("run", output), ("plank-run", plank_output)):
            with self.subTest(place=label, seed=self.seed):
                lines = [line for line in text_out.splitlines() if node in line]
                self.assertTrue(lines, self.explain(f"узла {node} нет\n{text_out}"))
                self.assertTrue(any(task_id in line for line in lines),
                                self.explain(f"узел без id задачи: {lines}"))


class Ac12OutsideWorkdirTest(PlankLayoutSandbox):

    def test_ac12_long_lived_dir_outside_workdir_keeps_previous_path(self):
        """При `long_lived_dir` вне `workdir` сбор, прогон и `plank-run` гонят планку из прежнего каталога, без выкладки, и называют этот случай строкой вывода.

        Сценарий: второй учебный проект, у которого `long_lived_dir` лежит
        вне `workdir`. Задача в `tests_writing` с черновиком планки без кода
        проекта. В момент запуска pytest каждая цель лежит под каталогом
        планки под `tasks` рабочей копии, каталога `.artel-plank` нигде в
        рабочей копии нет (ни на запуске, ни после); вывод каждого места
        несёт строку, называющую `long_lived_dir` и `workdir`.

        Ловит мутацию: выкладка делается и при `long_lived_dir` вне
        `workdir` — каталог `.artel-plank` в рабочей копии, цель вне
        каталога планки; строка о случае не печатается — её нет в выводе.
        """
        clone = make_project_repo(self.ext_out)
        self.commit_to_main(clone, {
            f"{self.out_workdir}/pyproject.toml": "[tool.pytest.ini_options]\n",
            f"{self.out_lld}/test_base_{self.word()}.py":
                "def test_base():\n    assert True\n"})
        task_id = self.new_task(self.ext_out, "tests_writing")
        name = f"test_ac1_{self.word()}.py"
        text = PLANK_PLAIN.format(word=self.word())
        self.write_docs(task_id, {f"{PLANK_DIR}/{name}": text})
        plank = os.path.realpath(self.plank_dir(task_id))
        for label, call in self.places(task_id, {name: text}):
            with self.subTest(place=label, seed=self.seed):
                _ok, output, _before, _after, error = call()
                self.assertIsNone(error, self.explain(output))
                self.assertEqual(len(self.calls), 1, self.explain(output))
                seen = self.calls[0]
                self.assertEqual(seen["any_layout"], [], self.explain(output))
                self.assertTrue(seen["targets"], self.explain(output))
                for target, _node in seen["targets"]:
                    self.assertTrue(under(target, plank),
                                    self.explain(f"цель {target}\n{output}"))
                self.assertEqual(self.layout_dirs(task_id), [],
                                 self.explain(output))
                self.assertTrue(any("long_lived_dir" in line and "workdir" in line
                                    for line in output.splitlines()),
                                self.explain(f"строки о случае нет\n{output}"))
