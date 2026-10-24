"""`mutation-run`: ожидание замка `--wait-lock`, копия таблицы `--copy-table`, число рабочих процессов `--workers`.

Группа: долгоживущий
Красен до реализации: команда не знает флагов `--wait-lock`, `--copy-table` и `--workers` — разбор аргументов отказывает «неизвестный флаг», ожидания замка, копии `mutation-run-<n>.tsv` в каталоге документов, `-n` в `extra` и строки шапки о рабочих процессах нет; тесты AC-7, AC-11 и AC-21 держат прежнее поведение и зелены с рождения.

Стенд держит связку «команда — фоновый прогон — замок машины — git —
pytest»: настоящий git (фикстура `real_git`), внешний проект песочницы с
клоном и bare-`origin` (`make_project_repo`), задача в БД пульта с рабочей
копией (`workspace.ensure`). Профиль тестов проекта — раннер пульта с
`report: junit-xml`; модуль проекта `core_<слово>.py` с функциями
`add`/`mul` и тест `tests/test_<слово>.py`; патчи мутаций —
`mutation-<nnn>.diff` каталога документов задачи (`config.PROJECTS /
<проект> / "tasks" / <id>`) либо коммита ссылки `refs/artifacts/<id>`.

Команда зовётся в процессе теста — `artel.main()` с подменённым
`sys.argv`. Фоновый процесс команды (`subprocess.Popen` интерпретатора с
`-c …orchestrator…`) исполняется здесь же тем же кодом в переданном
окружении; pid, который видит команда, — мёртвый либо живой дочерний
процесс песочницы. Узел прогона `acceptance.run_full_suite` обёрнут
шпионом: он пишет `extra` каждого вызова, по плану сценария подменяет
исход («предел», исключение) и зовёт проверку сценария в момент вызова.

Время — виртуальные часы: `time.monotonic`/`time.time` подменены, сон
модулей пульта (`patch_pult_sleep`) не спит, а сдвигает часы. До старта
фонового процесса часы идут только сном; в фоновом процессе — как
настоящие. Замок машины занимает «чужой прогон»: файл замка
`suite_lock.path()` с живым pid песочницы; он снимается сном, когда
виртуальное время дошло до срока сценария. Проверка замка — вызов
`suite_lock.acquire` или `suite_lock.holder` (шпионы по публичным именам).

Входы (слова, имена, число и порядок патчей, сроки, значения флагов) — от
зерна; зерно печатается и входит в текст провала.
"""
import contextlib
import difflib
import inspect
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (acceptance, artel, config, store, suite_lock,
                          workspace)
from tests.sandbox import (_alive_foreign_pid, _dead_pid, make_project_repo,
                           patch_pult_sleep)

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"

KILLED = "убита"
COLUMNS = "номер\tисход\tузлы"
NO_COPY = "копии нет"
EXCEPTION_REPORT = "прогон оборван исключением пульта"
TIMEOUT_HEAD = "прогон полного набора tests/ превысил "
BUSY_REFUSAL = re.compile(r"отказ — на машине уже идёт прогон .*"
                          r"повтори после его конца")
STARTED = re.compile(r"прогон №(\d+) .*запущен")

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
      report: junit-xml
      install: []
      full_suite_timeout_sec: {limit}
"""

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

BREAKS = ("return a - b", "return a * b", "return a + b + 1")


def numbered(n: int) -> str:
    return f"mutation-{n:03d}.diff"


def file_diff(path: str, before: str, after: str) -> str:
    lines = difflib.unified_diff(before.splitlines(True),
                                 after.splitlines(True),
                                 f"a/{path}", f"b/{path}")
    return f"diff --git a/{path} b/{path}\n" + "".join(lines)


def n_values(extra) -> list:
    """Значения `-n` (`-n X`, `-nX`, `--numprocesses X|=X`) по порядку."""
    items = [str(x) for x in extra]
    values = []
    index = 0
    while index < len(items):
        item = items[index]
        if item in ("-n", "--numprocesses") and index + 1 < len(items):
            values.append(items[index + 1])
            index += 2
            continue
        if item.startswith("--numprocesses="):
            values.append(item.split("=", 1)[1])
        elif item.startswith("-n") and not item.startswith("--") and len(item) > 2:
            values.append(item[2:])
        index += 1
    return values


class Clock:
    """Виртуальные часы: до `start_flow` время идёт только сном, после — как
    настоящее (сон тогда настоящий)."""

    def __init__(self):
        self.real_monotonic, self.real_time = time.monotonic, time.time
        self.real_sleep = time.sleep
        self.mono0, self.time0 = self.real_monotonic(), self.real_time()
        self.offset = 0.0
        self.flow_since = None
        self.sleeps = []
        self.after_sleep = None

    def elapsed(self) -> float:
        extra = 0.0 if self.flow_since is None else \
            self.real_monotonic() - self.flow_since
        return self.offset + extra

    def frozen(self) -> bool:
        return self.flow_since is None

    def monotonic(self) -> float:
        return self.mono0 + self.elapsed()

    def time(self) -> float:
        return self.time0 + self.elapsed()

    def sleep(self, seconds) -> None:
        if not self.frozen():
            self.real_sleep(seconds)
            return
        self.sleeps.append((self.elapsed(), float(seconds)))
        self.offset += max(0.0, float(seconds))
        if self.after_sleep is not None:
            self.after_sleep()

    def start_flow(self) -> None:
        if self.flow_since is None:
            self.flow_since = self.real_monotonic()


class RunProbe:
    """Шпион `acceptance.run_full_suite`: `extra` каждого вызова, подмена
    исхода по плану и проверка сценария в момент вызова.

    `plan` — номер вызова (с 1, первый — контрольный прогон) -> "timeout"
    либо "raise"; `hook(номер)` зовётся до исхода вызова."""

    def __init__(self, real):
        self.real = real
        self.signature = inspect.signature(real)
        self.calls = []
        self.plan = {}
        self.hook = None

    def __call__(self, root, *args, **kwargs):
        number = len(self.calls) + 1
        bound = self.signature.bind(root, *args, **kwargs)
        limit = bound.arguments.get("limit")
        self.calls.append({"n": number,
                           "extra": tuple(bound.arguments.get("extra", ()))})
        if self.hook is not None:
            self.hook(number)
        action = self.plan.get(number, "real")
        if action == "raise":
            raise RuntimeError("подмена песочницы: исключение посреди прогона")
        if action == "timeout":
            seconds, source = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")
            return False, (f"{TIMEOUT_HEAD}{seconds}с — завис или ждёт "
                           f"сетевой ответ (источник: {source})\n")
        return self.real(root, *args, **kwargs)


class WatchedOut(io.StringIO):
    """Вывод команды: первая запись со строкой колонок таблицы зовёт
    `on_table` — момент печати таблицы отчётом."""

    def __init__(self, on_table):
        super().__init__()
        self.on_table = on_table
        self.seen = False

    def write(self, text):
        if not self.seen and COLUMNS in text:
            self.seen = True
            self.on_table()
        return super().write(text)


class Bench:
    """Проект песочницы, задачи, команда `mutation-run` в процессе теста."""

    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.start_patch(mock.patch.dict(os.environ,
                                         {"PYTHONDONTWRITEBYTECODE": "1"}))
        # Число рабочих процессов по умолчанию — не 2: значение `--workers 2`
        # отличимо от умолчания.
        self.default_workers = self.rng.choice((1, 3))
        self.start_patch(mock.patch.object(config, "FULL_SUITE_WORKERS",
                                           self.default_workers))
        self.conn = store.db()
        self.entries = []
        self.child_errors = []
        self.child_runs = 0
        self.in_child = False
        self.pid = _dead_pid()
        self.probe = RunProbe(acceptance.run_full_suite)
        self.start_patch(mock.patch.object(acceptance, "run_full_suite",
                                           self.probe))
        self.clock = None
        self.checks = []
        self.race = None
        self.replaces = []
        self.exit_elapsed = None

    def start_patch(self, patcher):
        value = patcher.start()
        self.sandbox.addCleanup(patcher.stop)
        return value

    # --- окружение сценария ---------------------------------------------------

    def use_clock(self) -> Clock:
        """Виртуальные часы и шпионы проверки замка."""
        clock = Clock()
        self.clock = clock
        self.start_patch(mock.patch.object(time, "monotonic", clock.monotonic))
        self.start_patch(mock.patch.object(time, "time", clock.time))
        self.sandbox.addCleanup(patch_pult_sleep(clock.sleep).close)
        real_acquire, real_holder = suite_lock.acquire, suite_lock.holder

        def acquire(*args, **kwargs):
            if self.race is not None and clock.frozen() and \
                    not suite_lock.path().exists() and not self.race["spent"]:
                self.race["spent"] = True
                self.record("acquire", dict(self.race["holder"]))
                return dict(self.race["holder"])
            result = real_acquire(*args, **kwargs)
            self.record("acquire", result)
            return result

        def holder(*args, **kwargs):
            result = real_holder(*args, **kwargs)
            self.record("holder", result)
            return result

        self.start_patch(mock.patch.object(suite_lock, "acquire", acquire))
        self.start_patch(mock.patch.object(suite_lock, "holder", holder))
        return clock

    def record(self, kind: str, result) -> None:
        if self.clock is not None and self.clock.frozen():
            self.checks.append({"at": self.clock.elapsed(), "kind": kind,
                                "result": result})

    def busy_checks(self) -> list:
        return [c for c in self.checks if c["result"] is not None]

    def foreign_lock(self) -> dict:
        """Замок машины за «чужим прогоном»: другая задача, живой pid."""
        holder = {"task_id": self.new_task_id(),
                  "pid": _alive_foreign_pid(self.sandbox),
                  "run": self.rng.randint(1, 9)}
        path = suite_lock.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(holder), encoding="utf-8")
        return holder

    def lock_pid(self):
        try:
            return json.loads(suite_lock.path().read_text(encoding="utf-8")).get("pid")
        except (OSError, ValueError):
            return None

    def release_at(self, seconds: float) -> None:
        """Чужой прогон снимает замок, когда виртуальное время дошло до
        `seconds` от старта часов."""
        def after_sleep():
            if self.clock.elapsed() >= seconds:
                with contextlib.suppress(FileNotFoundError):
                    suite_lock.path().unlink()
        self.clock.after_sleep = after_sleep

    def spy_replace(self) -> None:
        real_replace = os.replace

        def replace(src, dst, *args, **kwargs):
            self.replaces.append((str(src), str(dst)))
            return real_replace(src, dst, *args, **kwargs)

        self.start_patch(mock.patch.object(os, "replace", replace))

    def word(self, size: int = 7) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def new_task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ALPHABET) for _ in range(23))

    def add_project(self) -> dict:
        w = self.word()
        target = "p" + self.word()
        limit = self.rng.randint(1000, 3000)
        origin = config.PROJECTS / target / "origin.git"
        self.entries.append(PROJECT_ENTRY.format(
            name=target, origin=origin, base=config.MAIN_BRANCH, limit=limit))
        text = "targets:\n" + "".join(self.entries)
        for path in {Path(config.TARGETS), self.sandbox.root / "targets.yaml"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        clone = make_project_repo(target)
        files = {"pytest.ini": PYTEST_INI,
                 f"core_{w}.py": MODULE.format(w=w),
                 f"tests/test_{w}.py": TEST_FILE.format(w=w)}
        for rel, body in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        self.sandbox.git("-C", str(clone), "add", "-A")
        self.sandbox.git("-C", str(clone), "commit", "-q", "-m",
                         "проект песочницы")
        self.sandbox.git("-C", str(clone), "push", "-q", "origin",
                         config.MAIN_BRANCH)
        return {"target": target, "w": w, "clone": clone,
                "module": f"core_{w}.py", "test": f"tests/test_{w}.py",
                "files": files}

    def add_task(self, project: dict) -> str:
        task_id = self.new_task_id()
        branch = f"task/{task_id.lower()}-mutation-flags"
        store.insert_task(self.conn, task_id, "Фикстура mutation-run",
                          "in_dev", branch, project["target"], 25.0)
        _wt, error = workspace.ensure(task_id, branch)
        if error:
            raise RuntimeError(f"рабочая копия не заведена: {error}")
        return task_id

    def docs_dir(self, project: dict, task_id: str) -> Path:
        return config.PROJECTS / project["target"] / "tasks" / task_id

    def write_patches(self, project: dict, task_id: str, patches: list) -> None:
        folder = self.docs_dir(project, task_id)
        folder.mkdir(parents=True, exist_ok=True)
        for number, text in enumerate(patches, start=1):
            (folder / numbered(number)).write_text(text, encoding="utf-8")

    def commit_ref(self, project: dict, task_id: str, patches: list) -> str:
        """Коммит ссылки `refs/artifacts/<id>` клона с патчами задачи."""
        clone = project["clone"]
        holder = Path(tempfile.mkdtemp(prefix="artel-mutation-ref-"))
        self.sandbox.addCleanup(shutil.rmtree, holder, ignore_errors=True)
        work = holder / "w"
        self.sandbox.git("-C", str(clone), "worktree", "add", "-q",
                         "--detach", str(work), "HEAD")
        folder = work / "tasks" / task_id
        folder.mkdir(parents=True)
        for number, text in enumerate(patches, start=1):
            (folder / numbered(number)).write_text(text, encoding="utf-8")
        self.sandbox.git("-C", str(work), "add", "-A")
        self.sandbox.git("-C", str(work), "commit", "-q", "-m",
                         "документы задачи")
        sha = self.sandbox.git("-C", str(work), "rev-parse", "HEAD").strip()
        self.sandbox.git("-C", str(clone), "update-ref",
                         f"refs/artifacts/{task_id}", sha)
        self.sandbox.git("-C", str(clone), "worktree", "remove", "--force",
                         str(work))
        return sha

    def breaking(self, project: dict) -> str:
        before = project["files"][project["module"]]
        return file_diff(project["module"], before,
                         before.replace("return a + b",
                                        self.rng.choice(BREAKS)))

    def comment(self, project: dict) -> str:
        before = project["files"][project["module"]]
        old = f"# модуль песочницы {project['w']}"
        return file_diff(project["module"], before,
                         before.replace(old, f"{old}: {self.word()}"))

    def patch_set(self, project: dict, low: int = 2, high: int = 3) -> list:
        """Ломающий `add` патч первым и правки комментария; число — от зерна."""
        return [self.breaking(project)] + [
            self.comment(project) for _ in range(self.rng.randint(low, high) - 1)]

    def task_with_patches(self, low: int = 2, high: int = 3) -> tuple:
        project = self.add_project()
        task_id = self.add_task(project)
        patches = self.patch_set(project, low, high)
        self.write_patches(project, task_id, patches)
        return project, task_id, patches

    # --- команда --------------------------------------------------------------

    def run_child(self, tokens: list, kwargs: dict) -> None:
        """Фоновый процесс команды — в процессе теста, тем же кодом."""
        self.child_runs += 1
        if self.clock is not None:
            self.clock.start_flow()
        env = kwargs.get("env")
        environ = (mock.patch.dict(os.environ, env, clear=True)
                   if env is not None else contextlib.nullcontext())
        saved_argv, saved_cwd = sys.argv, os.getcwd()
        self.in_child = True
        try:
            with environ:
                if kwargs.get("cwd"):
                    os.chdir(kwargs["cwd"])
                sys.argv = ["-c", *tokens[3:]]
                exec(compile(tokens[2], "<mutation-run child>", "exec"),
                     {"__name__": "__main__"})
        except SystemExit as exc:
            if exc.code not in (None, 0):
                self.child_errors.append(f"фоновый процесс: выход {exc.code}")
        except Exception:  # noqa: BLE001 — исход фонового процесса виден тесту
            self.child_errors.append(traceback.format_exc())
        finally:
            self.in_child = False
            sys.argv = saved_argv
            os.chdir(saved_cwd)

    def popen(self):
        real_popen = subprocess.Popen

        def popen(argv, *args, **kwargs):
            tokens = ([str(t) for t in argv]
                      if isinstance(argv, (list, tuple)) else [])
            child = (len(tokens) > 2 and tokens[0] == sys.executable
                     and tokens[1] == "-c" and "orchestrator" in tokens[2])
            if not child:
                return real_popen(argv, *args, **kwargs)
            self.run_child(tokens, kwargs)
            proc = mock.Mock(pid=self.pid, returncode=None)
            proc.poll.return_value = None
            return proc

        return mock.patch.object(subprocess, "Popen", popen)

    def command(self, *args: str, out: io.StringIO | None = None) -> tuple:
        """(код выхода, вывод stdout и stderr) `artel.py mutation-run <args>`;
        прерывание `KeyboardInterrupt` — код "KeyboardInterrupt"."""
        buf, code = (out if out is not None else io.StringIO()), 0
        with mock.patch.object(sys, "argv", ["artel.py", "mutation-run", *args]), \
                self.popen(), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
                if isinstance(code, str):
                    buf.write(code + "\n")
            except KeyboardInterrupt:
                code = "KeyboardInterrupt"
        if self.clock is not None:
            self.exit_elapsed = self.clock.elapsed()
        return (0 if code is None else code), buf.getvalue()

    def run_args(self, task_id: str, project: dict, *extra: str) -> tuple:
        return (task_id, "--ref", "head", "--tests", project["test"], *extra)

    def state_dir(self, task_id: str) -> Path:
        return suite_lock.directory() / task_id

    def run_files(self, task_id: str) -> list:
        """Файлы прогона задачи: журналы, таблицы, файл прогона."""
        folder = self.state_dir(task_id)
        if not folder.is_dir():
            return []
        return sorted(p.name for p in folder.iterdir()
                      if p.name.endswith((".log", ".tsv"))
                      or p.name == "mutation-run.json")

    def table_path(self, task_id: str, run_no: int) -> Path:
        return self.state_dir(task_id) / \
            f"{task_id}-mutation-run-{run_no}.mutations.tsv"

    def last_run_no(self, task_id: str) -> int | None:
        pattern = re.compile(rf"^{task_id}-mutation-run-(\d+)\.mutations\.tsv$")
        folder = self.state_dir(task_id)
        found = sorted(int(m.group(1)) for p in folder.glob("*.tsv")
                       if (m := pattern.match(p.name))) \
            if folder.is_dir() else []
        return found[-1] if found else None

    def copy_path(self, project: dict, task_id: str, run_no: int) -> Path:
        return self.docs_dir(project, task_id) / f"mutation-run-{run_no}.tsv"

    def copies(self, project: dict, task_id: str) -> list:
        folder = self.docs_dir(project, task_id)
        if not folder.is_dir():
            return []
        return sorted(p.name for p in folder.iterdir()
                      if re.fullmatch(r"mutation-run-\d+\.tsv", p.name))

    def names(self, project: dict, task_id: str) -> set:
        """Имена всех файлов каталога документов, скрытые тоже."""
        folder = self.docs_dir(project, task_id)
        if not folder.is_dir():
            return set()
        return {p.relative_to(folder).as_posix() for p in folder.rglob("*")}

    def snapshot(self, project: dict, task_id: str) -> dict:
        folder = self.docs_dir(project, task_id)
        if not folder.is_dir():
            return {}
        return {p.relative_to(folder).as_posix(): p.read_bytes()
                for p in sorted(folder.rglob("*")) if p.is_file()}

    def result_path(self, task_id: str) -> Path:
        return self.state_dir(task_id) / "mutation-result.json"

    def report(self, task_id: str) -> str:
        path = self.result_path(task_id)
        if not path.exists():
            return ""
        return json.loads(path.read_text(encoding="utf-8")).get("report", "")

    def run_no_of(self, out: str) -> int:
        match = STARTED.search(out)
        if match is None:
            raise AssertionError(f"прогон не запущен: {self.explain(out)}")
        return int(match.group(1))

    def explain(self, text: str = "") -> str:
        errors = "\n".join(self.child_errors)[-3000:]
        return (f"зерно: {self.seed}\nвывод команды:\n{text[-4000:]}\n"
                f"сбои фонового процесса:\n{errors}")


@pytest.fixture
def bench(real_git):
    """Стенд команды поверх песочницы `real_git`."""
    return Bench(real_git)


def path_printed(path: Path, out: str) -> bool:
    return str(path) in out or str(path.resolve()) in out


# ------------------------------------------------------------ --wait-lock


def test_ac1_lock_released_in_time_waits_then_starts(bench):
    """Замок чужого прогона снят до срока `--wait-lock N`: строка ожидания с держателем, затем прогон.

    Сценарий: замок машины держит прогон другой задачи (живой pid
    песочницы); `mutation-run … --wait-lock N` (N — от зерна, от 1 до
    `config.SUITE_RUN_MAX_WAIT_MIN`), чужой прогон снимает замок на
    виртуальной секунде, взятой от зерна до срока. В выводе до строки
    «прогон №<n> … запущен» есть строка с задачей и pid держателя; фоновый
    прогон исполнен — в таблице строка на каждый патч, отказа нет.

    Ловит мутацию: флаг `--wait-lock` разобран, но замок берётся прежним
    одиночным `acquire` — отказ сразу при занятом замке; ожидание идёт
    молча — строки с держателем нет; после освобождения замка команда
    выходит, не запустив прогон.
    """
    project, task_id, patches = bench.task_with_patches()
    clock = bench.use_clock()
    holder = bench.foreign_lock()
    minutes = bench.rng.randint(1, config.SUITE_RUN_MAX_WAIT_MIN)
    bench.release_at(bench.rng.uniform(1, minutes * 60 - 11))
    code, out = bench.command(*bench.run_args(task_id, project, "--wait-lock",
                                              str(minutes)))
    lines = out.split("\n")
    started = [i for i, line in enumerate(lines) if STARTED.search(line)]
    assert started, bench.explain(out)
    waiting = [i for i, line in enumerate(lines)
               if holder["task_id"] in line and str(holder["pid"]) in line]
    assert waiting and waiting[0] < started[0], bench.explain(out)
    assert clock.sleeps, bench.explain(out)
    assert code == 0, bench.explain(out)
    run_no = bench.run_no_of(out)
    rows = [line for line in bench.table_path(task_id, run_no).read_text(
        encoding="utf-8").split("\n") if line.split("\t")[0].isdigit()]
    assert len(rows) == len(patches), bench.explain(out)


def test_ac2_lock_busy_whole_term_refuses_after_term(bench):
    """Замок занят весь срок: отказ с держателем и «ожидание N мин истекло» в окне [N·60, N·60+10] с.

    Сценарий: замок держит прогон другой задачи до конца сценария;
    `mutation-run … --wait-lock N` (N — от зерна). Команда выходит с
    ненулевым кодом; строка со словами «ожидание N мин истекло» называет
    задачу и pid держателя; виртуальное время от первой проверки, увидевшей
    занятый замок, до выхода команды — не меньше N·60 и не больше N·60 + 10
    с; файлов прогона (журнал, таблица, `mutation-run.json`) нет, фоновый
    процесс не запускался.

    Ловит мутацию: срок считается в секундах вместо минут — отказ через N
    с; последний сон не урезан до остатка и шаг опроса кратен 60 с — отказ
    позже срока на минуту; отказ прежним текстом без «ожидание N мин
    истекло»; лог прогона заводится до ожидания — файл журнала остаётся.
    """
    project, task_id, _patches = bench.task_with_patches()
    clock = bench.use_clock()
    holder = bench.foreign_lock()
    minutes = bench.rng.randint(1, config.SUITE_RUN_MAX_WAIT_MIN)
    code, out = bench.command(*bench.run_args(task_id, project, "--wait-lock",
                                              str(minutes)))
    assert code not in (0, None), bench.explain(out)
    phrase = f"ожидание {minutes} мин истекло"
    refusal = [line for line in out.split("\n") if phrase in line]
    assert refusal, bench.explain(out)
    assert holder["task_id"] in refusal[-1], bench.explain(out)
    assert str(holder["pid"]) in refusal[-1], bench.explain(out)
    busy = bench.busy_checks()
    assert busy, bench.explain(out)
    waited = bench.exit_elapsed - busy[0]["at"]
    assert minutes * 60 <= waited <= minutes * 60 + 10, \
        f"ждала {waited} с при сроке {minutes} мин; {bench.explain(out)}"
    assert bench.run_files(task_id) == [], bench.explain(out)
    assert bench.child_runs == 0, bench.explain(out)
    assert bench.probe.calls == [], bench.explain(out)
    assert clock.sleeps, bench.explain(out)


def test_ac3_lock_checks_at_least_ten_seconds_apart(bench):
    """Между соседними проверками замка во время ожидания — не меньше 10 с виртуального времени.

    Сценарий: замок чужого прогона снимается на виртуальной секунде от
    зерна до срока `--wait-lock N`; проверки замка — вызовы
    `suite_lock.acquire`/`suite_lock.holder` до старта фонового процесса,
    вызовы в один и тот же виртуальный момент — одна проверка. Проверок
    не меньше двух (занятый замок и освобождённый), каждая следующая —
    не раньше чем через 10 с после предыдущей.

    Ловит мутацию: ожидание переиспользует `suite_lock.wait_acquire` или
    шаг `suite_lock.POLL_SEC` — проверки раз в 1 с; сон стоит только в
    ветке «держатель сменился» — повторные проверки без паузы.
    """
    project, task_id, _patches = bench.task_with_patches(2, 2)
    bench.use_clock()
    bench.foreign_lock()
    minutes = bench.rng.randint(1, config.SUITE_RUN_MAX_WAIT_MIN)
    bench.release_at(bench.rng.uniform(15, minutes * 60 - 11))
    _code, out = bench.command(*bench.run_args(task_id, project, "--wait-lock",
                                               str(minutes)))
    assert STARTED.search(out), bench.explain(out)
    moments = []
    for check in bench.checks:
        if not moments or check["at"] - moments[-1] > 1e-6:
            moments.append(check["at"])
    assert len(moments) >= 2, f"проверки: {bench.checks}; {bench.explain(out)}"
    gaps = [b - a for a, b in zip(moments, moments[1:])]
    assert min(gaps) >= 10 - 1e-6, f"интервалы: {gaps}; {bench.explain(out)}"


def test_ac4_lost_race_for_freed_lock_keeps_waiting(bench):
    """Освободившийся замок перехватил другой прогон: ожидание продолжается, прогон стартует.

    Сценарий: замок чужого прогона снимается до срока; первое взятие
    замка после его освобождения (подменённый `suite_lock.acquire`)
    отвечает держателем третьей задачи, следующее — настоящее. Команда не
    отказывает: после проигранного взятия есть ещё проверка замка, прогон
    запущен, таблица несёт строку на каждый патч.

    Ловит мутацию: держатель, полученный от `acquire` после освобождения
    замка, считается окончательным — отказ «на машине уже идёт прогон» до
    срока; после проигранной гонки ожидание выходит без прогона.
    """
    project, task_id, patches = bench.task_with_patches(2, 2)
    bench.use_clock()
    bench.foreign_lock()
    minutes = bench.rng.randint(1, config.SUITE_RUN_MAX_WAIT_MIN)
    bench.release_at(bench.rng.uniform(1, minutes * 60 - 25))
    bench.race = {"spent": False,
                  "holder": {"task_id": bench.new_task_id(),
                             "pid": _alive_foreign_pid(bench.sandbox),
                             "run": 1}}
    code, out = bench.command(*bench.run_args(task_id, project, "--wait-lock",
                                              str(minutes)))
    assert bench.race["spent"], f"гонки не было: {bench.explain(out)}"
    assert code == 0, bench.explain(out)
    assert not BUSY_REFUSAL.search(out), bench.explain(out)
    lost = next(i for i, c in enumerate(bench.checks)
                if c["result"] == bench.race["holder"])
    assert bench.checks[lost + 1:], bench.explain(out)
    run_no = bench.run_no_of(out)
    rows = [line for line in bench.table_path(task_id, run_no).read_text(
        encoding="utf-8").split("\n") if line.split("\t")[0].isdigit()]
    assert len(rows) == len(patches), bench.explain(out)


def test_ac5_waiting_takes_no_lock_and_sigint_leaves_nothing(bench):
    """Во время ожидания замок не взят и файлов прогона нет; SIGINT из сна — выход без прогона.

    Сценарий: замок держит чужой прогон; `--wait-lock N`; в каждом сне
    ожидания фиксируется держатель файла замка и файлы прогона задачи;
    сон с номером от зерна (1–3) бросает `KeyboardInterrupt`. В каждом сне
    держатель — чужой pid, файлов прогона нет; после выхода команды замок
    по-прежнему за чужим прогоном, файлов прогона нет, фоновый процесс не
    запускался, узел прогона не вызывался.

    Ловит мутацию: команда сначала заводит лог прогона (`_new_log`) и лишь
    потом ждёт замок — в сне виден файл журнала; ожидание держит замок
    за собой и перехватывает его у чужого процесса; `KeyboardInterrupt`
    перехвачен ожиданием как «замок свободен» — прогон стартует.
    """
    project, task_id, _patches = bench.task_with_patches(2, 2)
    clock = bench.use_clock()
    holder = bench.foreign_lock()
    minutes = bench.rng.randint(1, config.SUITE_RUN_MAX_WAIT_MIN)
    stop = bench.rng.randint(1, min(3, minutes * 6 - 1))
    seen = []

    def after_sleep():
        seen.append({"lock": bench.lock_pid(),
                     "files": bench.run_files(task_id)})
        if len(seen) >= stop:
            raise KeyboardInterrupt

    clock.after_sleep = after_sleep
    code, out = bench.command(*bench.run_args(task_id, project, "--wait-lock",
                                              str(minutes)))
    assert len(seen) == stop, bench.explain(out)
    assert all(s["lock"] == holder["pid"] for s in seen), \
        f"{seen}; {bench.explain(out)}"
    assert all(s["files"] == [] for s in seen), f"{seen}; {bench.explain(out)}"
    assert code != 0, bench.explain(out)
    assert bench.lock_pid() == holder["pid"], bench.explain(out)
    assert bench.run_files(task_id) == [], bench.explain(out)
    assert bench.child_runs == 0, bench.explain(out)
    assert bench.probe.calls == [], bench.explain(out)
    assert not any(c["kind"] == "acquire" and c["result"] is None
                   for c in bench.checks), bench.explain(out)


@pytest.mark.parametrize("case", ["без значения", "отрицательное",
                                  "больше предела", "дробное", "не число",
                                  "сумма с --wait"])
def test_ac6_bad_wait_lock_refused_without_run(bench, case):
    """Неверный `--wait-lock` или сумма с `--wait` выше предела — отказ без прогона.

    Сценарий: замок машины свободен, патчи и тесты верны; `--wait-lock`
    стоит последним аргументом без значения, со значением отрицательным,
    больше `config.SUITE_RUN_MAX_WAIT_MIN`, дробным или не числом
    (значения — от зерна) — отказ: код выхода ненулевой, текст называет
    `--wait-lock` и минуты; либо `--wait-lock a --wait b`, каждое в
    пределе, а сумма больше — текст называет предел. Ни в одном случае
    фоновый процесс не запускался, узел прогона не вызывался, файлов
    прогона нет.

    Ловит мутацию: `--wait-lock` разобран без проверки диапазона —
    значение больше предела или отрицательное принято и прогон запущен;
    значение приведено `float`/`int(float(…))` — дробное принято; сумма
    `--wait-lock` и `--wait` не проверяется — прогон запущен; флаг без
    значения съедает отсутствующий аргумент молча.
    """
    project, task_id, _patches = bench.task_with_patches(2, 2)
    limit = config.SUITE_RUN_MAX_WAIT_MIN
    if case == "без значения":
        extra = ("--wait-lock",)
    elif case == "отрицательное":
        extra = ("--wait-lock", str(-bench.rng.randint(1, 30)))
    elif case == "больше предела":
        extra = ("--wait-lock", str(limit + bench.rng.randint(1, 30)))
    elif case == "дробное":
        extra = ("--wait-lock", f"{bench.rng.randint(0, limit - 1)}.5")
    elif case == "не число":
        extra = ("--wait-lock", bench.word(3))
    else:
        first = bench.rng.randint(1, limit)
        second = bench.rng.randint(limit - first + 1, limit)
        extra = ("--wait-lock", str(first), "--wait", str(second))
    code, out = bench.command(*bench.run_args(task_id, project, *extra))
    assert code not in (0, None), bench.explain(out)
    if case == "сумма с --wait":
        assert str(limit) in out, bench.explain(out)
    else:
        assert "--wait-lock" in out, bench.explain(out)
        assert "минут" in out, bench.explain(out)
    assert bench.child_runs == 0, bench.explain(out)
    assert bench.probe.calls == [], bench.explain(out)
    assert bench.run_files(task_id) == [], bench.explain(out)


def test_ac7_without_wait_lock_busy_lock_refuses_at_once(bench):
    """Без `--wait-lock` занятый замок — отказ сразу прежним текстом, без сна.

    Сценарий: замок держит чужой прогон; `mutation-run` без `--wait-lock`.
    Код выхода ненулевой, вывод несёт «отказ — на машине уже идёт прогон …
    повтори после его конца» с задачей держателя; сна до выхода не было;
    фоновый процесс не запускался, файлов прогона нет.

    Ловит мутацию: умолчание `--wait-lock` — не 0, а предел или минута —
    команда ждёт замок без флага; отказ без флага переписан новым текстом
    ожидания («ожидание 0 мин истекло»).
    """
    project, task_id, _patches = bench.task_with_patches(2, 2)
    clock = bench.use_clock()
    holder = bench.foreign_lock()
    code, out = bench.command(*bench.run_args(task_id, project))
    assert code not in (0, None), bench.explain(out)
    assert BUSY_REFUSAL.search(out), bench.explain(out)
    assert holder["task_id"] in out, bench.explain(out)
    assert clock.sleeps == [], f"сны: {clock.sleeps}; {bench.explain(out)}"
    assert bench.child_runs == 0, bench.explain(out)
    assert bench.run_files(task_id) == [], bench.explain(out)


# ------------------------------------------------------------ --copy-table


def test_ac8_finished_run_copy_equals_table(bench):
    """Законченный прогон с `--copy-table`: `mutation-run-<n>.tsv` первого уровня каталога документов равен таблице.

    Сценарий: два–три патча, `mutation-run … --copy-table --wait 1`. В
    каталоге документов задачи файл `mutation-run-<n>.tsv` (n — номер
    прогона из вывода) побайтно равен основной таблице прогона в хозяйстве
    `suite-run`, таблица несёт строку на каждый патч.

    Ловит мутацию: копия пишется только после шапки — строк исходов в ней
    нет; копия кладётся в каталог хозяйства `suite-run` или в подкаталог
    документов; имя копии — имя основной таблицы
    (`<id>-mutation-run-<n>.mutations.tsv`); номер в имени — не номер
    прогона.
    """
    project, task_id, patches = bench.task_with_patches()
    code, out = bench.command(*bench.run_args(task_id, project, "--copy-table",
                                              "--wait", "1"))
    run_no = bench.run_no_of(out)
    table = bench.table_path(task_id, run_no).read_bytes()
    rows = [line for line in table.decode("utf-8").split("\n")
            if line.split("\t")[0].isdigit()]
    assert len(rows) == len(patches), bench.explain(out)
    copy = bench.copy_path(project, task_id, run_no)
    assert copy.is_file(), bench.explain(out)
    assert copy.read_bytes() == table, bench.explain(out)
    assert code == 0, bench.explain(out)


@pytest.mark.parametrize("outcome", ["предел", "законченный"])
def test_ac9_copy_equals_table_at_every_patch_run(bench, outcome):
    """Копия равна таблице в момент прогона каждого патча и в конце, в том числе у оборванного по пределу.

    Сценарий: три–четыре патча, первый ломает `add`; «предел» — прогон
    второго патча подменён исходом «предел». Внутри шпиона узла прогона
    при каждом вызове патча (со второго вызова) копия
    `mutation-run-<n>.tsv` побайтно равна основной таблице на этот момент.
    После прогона копия равна таблице; у оборванного прогона она несёт
    строку «убита» патча 1, записанную до обрыва.

    Ловит мутацию: копия пишется один раз в конце `_mutate` — при прогоне
    патчей её нет или в ней одна шапка; копия обновляется только в конце
    успешного прогона — у оборванного пределом её нет; копия обновляется
    до записи строки в основную таблицу — отстаёт на строку.
    """
    project, task_id, _patches = bench.task_with_patches(3, 4)
    if outcome == "предел":
        bench.probe.plan[3] = "timeout"
    moments = []

    def hook(number):
        if number < 2:
            return
        run_no = bench.last_run_no(task_id)
        table = bench.table_path(task_id, run_no).read_bytes()
        copy = bench.copy_path(project, task_id, run_no)
        moments.append((number, copy.read_bytes() == table
                        if copy.is_file() else "копии нет"))

    bench.probe.hook = hook
    _code, out = bench.command(*bench.run_args(task_id, project, "--copy-table",
                                               "--wait", "1"))
    run_no = bench.run_no_of(out)
    assert moments, bench.explain(out)
    assert all(equal is True for _n, equal in moments), \
        f"{moments}; {bench.explain(out)}"
    table = bench.table_path(task_id, run_no).read_bytes()
    copy = bench.copy_path(project, task_id, run_no)
    assert copy.read_bytes() == table, bench.explain(out)
    first = [line for line in copy.read_text(encoding="utf-8").split("\n")
             if line.startswith("1\t")]
    assert first and first[0].split("\t")[1] == KILLED, bench.explain(out)


def test_ac10_no_docs_dir_no_copy_and_one_no_copy_line(bench):
    """Каталога документов нет: копии нет, прогон закончен, отчёт — одна строка «копии нет» без пути копии.

    Сценарий: патчи только в коммите ссылки `refs/artifacts/<id>` клона,
    каталога документов задачи на диске нет; `mutation-run … --copy-table
    --wait 1`. Прогон законченный (код 0, таблица с исходом каждого
    патча); файлов `mutation-run-<n>.tsv` под каталогом документов нет;
    ровно одна строка вывода несёт «копии нет»; имени
    `mutation-run-<n>.tsv` в выводе нет.

    Ловит мутацию: копия пишется с `mkdir(parents=True)` — каталог
    документов создаётся и копия появляется; запись копии без каталога
    роняет фоновый прогон исключением; отчёт печатает путь копии без
    проверки её наличия; «копии нет» печатается на каждую строку таблицы.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    patches = bench.patch_set(project)
    bench.commit_ref(project, task_id, patches)
    shutil.rmtree(bench.docs_dir(project, task_id), ignore_errors=True)
    code, out = bench.command(*bench.run_args(task_id, project, "--copy-table",
                                              "--wait", "1"))
    run_no = bench.run_no_of(out)
    assert code == 0, bench.explain(out)
    rows = [line for line in bench.table_path(task_id, run_no).read_text(
        encoding="utf-8").split("\n") if line.split("\t")[0].isdigit()]
    assert len(rows) == len(patches), bench.explain(out)
    assert bench.copies(project, task_id) == [], bench.explain(out)
    assert sum(NO_COPY in line for line in out.split("\n")) == 1, \
        bench.explain(out)
    assert f"mutation-run-{run_no}.tsv" not in out, bench.explain(out)


def test_ac11_without_copy_table_docs_dir_unchanged(bench):
    """Без `--copy-table` имена и байты каталога документов после прогона и отчётов прежние.

    Сценарий: патчи в каталоге документов; прогон `--wait 1` и повторный
    `--wait 0` без `--copy-table`. Снимок каталога (имена и байты всех
    файлов, скрытых тоже) до и после равен; файлов `mutation-run-<n>.tsv`
    нет.

    Ловит мутацию: копия таблицы пишется всегда, без флага; признак
    «с копией» по умолчанию истина в файле прогона — отчётный вызов
    кладёт копию.
    """
    project, task_id, _patches = bench.task_with_patches()
    before = bench.snapshot(project, task_id)
    _code, out = bench.command(*bench.run_args(task_id, project, "--wait", "1"))
    _code, again = bench.command(task_id, "--wait", "0")
    assert bench.last_run_no(task_id) is not None, bench.explain(out)
    assert bench.snapshot(project, task_id) == before, bench.explain(out + again)
    assert bench.copies(project, task_id) == [], bench.explain(out + again)


def test_ac12_copy_table_leaves_ref_branch_and_worktree(bench):
    """Прогон с `--copy-table` не двигает `refs/artifacts/<id>`, ветку задачи и не меняет рабочую копию.

    Сценарий: патчи в каталоге документов и в коммите ссылки документов;
    прогон `--copy-table --wait 1` и повторный `--wait 0`. До и после
    равны: sha `refs/artifacts/<id>` и ветки задачи клона, HEAD и
    `git status --porcelain` рабочей копии, `refs/artifacts/*` пульта;
    копия при этом записана.

    Ловит мутацию: копия коммитится в ссылку документов — sha `refs/artifacts/<id>` сдвигается; копия
    пишется в рабочую копию задачи — `git status` несёт новый файл.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    patches = bench.patch_set(project)
    bench.write_patches(project, task_id, patches)
    bench.commit_ref(project, task_id, patches)
    clone = str(project["clone"])
    branch = store.get_task(bench.conn, task_id)["branch"]
    wt = str(workspace.path(task_id, project["target"]))

    def state() -> dict:
        git = bench.sandbox.git
        return {"ref": git("-C", clone, "rev-parse", f"refs/artifacts/{task_id}"),
                "branch": git("-C", clone, "rev-parse", f"refs/heads/{branch}"),
                "head": git("-C", wt, "rev-parse", "HEAD"),
                "status": git("-C", wt, "status", "--porcelain",
                              "--untracked-files=all"),
                "pult": git("for-each-ref", "refs/artifacts")}

    before = state()
    _code, out = bench.command(*bench.run_args(task_id, project, "--copy-table",
                                               "--wait", "1"))
    _code, again = bench.command(task_id, "--wait", "0")
    assert bench.copies(project, task_id), bench.explain(out)
    assert state() == before, bench.explain(out + again)


def test_ac13_reports_print_copy_path(bench):
    """Отчёт `--wait` и повторный отчёт после конца прогона с `--copy-table` печатают путь копии.

    Сценарий: прогон `--copy-table --wait 1`, затем отчёт `--wait <0|1>`
    (значение — от зерна). Вывод обоих вызовов несёт путь файла
    `mutation-run-<n>.tsv` каталога документов задачи.

    Ловит мутацию: путь копии печатается только строкой запуска, а не
    отчётом; повторный отчёт путь не печатает — признак копии не сохранён
    в файле прогона; печатается путь основной таблицы вместо копии.
    """
    project, task_id, _patches = bench.task_with_patches()
    _code, out = bench.command(*bench.run_args(task_id, project, "--copy-table",
                                               "--wait", "1"))
    run_no = bench.run_no_of(out)
    copy = bench.copy_path(project, task_id, run_no)
    assert copy.is_file(), bench.explain(out)
    assert path_printed(copy, out), bench.explain(out)
    _code, again = bench.command(task_id, "--wait", str(bench.rng.randint(0, 1)))
    assert path_printed(copy, again), bench.explain(again)


@pytest.mark.parametrize("damage", ["удалена", "подменена"])
@pytest.mark.parametrize("phase", ["закончен", "идёт"])
def test_ac16_report_restores_copy_before_table(bench, damage, phase):
    """Отчётный вызов без флага восстанавливает копию из таблицы до печати таблицы.

    Сценарий: прогон с `--copy-table` исполнен; «идёт» — отчёт
    `mutation-result.json` убран, pid фонового процесса — живой процесс
    песочницы; копию `mutation-run-<n>.tsv` удалили или подменили другими
    байтами. Отчётный вызов `--wait 0` без `--copy-table`: в момент первой
    записи строки колонок таблицы в вывод копия уже побайтно равна
    основной таблице; после вызова — тоже.

    Ловит мутацию: отчётный вызов копию не трогает — удалённой нет,
    подменённая прежняя; копия перезаписывается после печати таблицы;
    перезапись только у законченного прогона (в ветке отчёта), а не при
    идущем; копия пишется, только если её нет, — подменённая не
    восстановлена.
    """
    project, task_id, _patches = bench.task_with_patches()
    if phase == "идёт":
        bench.pid = _alive_foreign_pid(bench.sandbox)
    _code, out = bench.command(*bench.run_args(task_id, project, "--copy-table"))
    run_no = bench.run_no_of(out)
    if phase == "идёт":
        bench.result_path(task_id).unlink()
    copy = bench.copy_path(project, task_id, run_no)
    table = bench.table_path(task_id, run_no)
    assert copy.is_file(), bench.explain(out)
    if damage == "удалена":
        copy.unlink()
    else:
        copy.write_bytes(f"подмена {bench.word()}\n".encode("utf-8"))
    at_print = []
    stream = WatchedOut(lambda: at_print.append(
        copy.is_file() and copy.read_bytes() == table.read_bytes()))
    _code, again = bench.command(task_id, "--wait", "0", out=stream)
    assert at_print == [True], f"{at_print}; {bench.explain(again)}"
    assert copy.read_bytes() == table.read_bytes(), bench.explain(again)


def test_ac16_report_of_run_without_copy_flag_creates_no_copy(bench):
    """Отчётный вызов для прогона без `--copy-table` копию не создаёт.

    Сценарий: прогон без `--copy-table` закончен; отчётные вызовы `--wait 0`
    дважды. Файлов `mutation-run-<n>.tsv` в каталоге документов нет.

    Ловит мутацию: отчётный вызов перезаписывает копию всегда, не глядя на
    признак прогона «с копией»; признак читается из отчётного вызова, а
    не из прогона, и по умолчанию истина.
    """
    project, task_id, _patches = bench.task_with_patches(2, 2)
    _code, out = bench.command(*bench.run_args(task_id, project))
    bench.run_no_of(out)
    for _ in range(2):
        _code, again = bench.command(task_id, "--wait", "0")
        assert bench.copies(project, task_id) == [], bench.explain(again)


@pytest.mark.parametrize("flag", [("--wait-lock", "1"), ("--copy-table",),
                                  ("--workers", "1")])
def test_ac17_report_only_with_run_flag_refused(bench, flag):
    """Вызов только отчёта с `--wait-lock`, `--copy-table` или `--workers` — отказ без прогона.

    Сценарий: прогон задачи закончен, отчётный `--wait 0` без флага
    проходит с кодом 0; тот же вызов с флагом прогона — код ненулевой,
    текст называет флаг; новых вызовов узла прогона, фоновых процессов и
    журналов прогона нет.

    Ловит мутацию: режим только отчёта не проверяет новых флагов — флаг
    молча отброшен и отчёт напечатан с кодом 0; флаг в режиме отчёта
    запускает новый прогон по прежним аргументам.
    """
    project, task_id, _patches = bench.task_with_patches(2, 2)
    _code, out = bench.command(*bench.run_args(task_id, project))
    bench.run_no_of(out)
    code, plain = bench.command(task_id, "--wait", "0")
    assert code == 0, bench.explain(plain)
    calls, runs, files = (len(bench.probe.calls), bench.child_runs,
                          bench.run_files(task_id))
    code, refused = bench.command(task_id, "--wait", "0", *flag)
    assert code not in (0, None), bench.explain(refused)
    assert flag[0] in refused, bench.explain(refused)
    assert len(bench.probe.calls) == calls, bench.explain(refused)
    assert bench.child_runs == runs, bench.explain(refused)
    assert bench.run_files(task_id) == files, bench.explain(refused)


@pytest.mark.parametrize("outcome", ["законченный", "предел", "исключение"])
def test_ac19_docs_dir_gains_only_copy_without_replace(bench, outcome):
    """После прогона с `--copy-table` в каталоге документов прибавилась только копия, без `os.replace`.

    Сценарий: прогон законченный, оборванный пределом на втором патче или
    исключением из шпиона узла прогона на втором патче; отчёт `--wait 1`.
    Множество имён каталога документов (скрытые тоже, вглубь) после
    прогона равно прежнему плюс `mutation-run-<n>.tsv`; ни один вызов
    `os.replace` за команду не касался каталога документов.

    Ловит мутацию: копия пишется атомарно через временный файл
    `.mutation-run-<n>.tsv.tmp` и `os.replace` — вызов `os.replace` в
    каталог документов; временный файл остаётся при исключении — лишнее
    скрытое имя; копия пишется вместе с промежуточными файлами
    (`.partial`) — лишнее имя.
    """
    project, task_id, _patches = bench.task_with_patches(3, 3)
    if outcome == "предел":
        bench.probe.plan[3] = "timeout"
    elif outcome == "исключение":
        bench.probe.plan[3] = "raise"
    bench.spy_replace()
    docs = bench.docs_dir(project, task_id)
    before = bench.names(project, task_id)
    _code, out = bench.command(*bench.run_args(task_id, project, "--copy-table",
                                               "--wait", "1"))
    run_no = bench.run_no_of(out)
    if outcome == "исключение":
        assert EXCEPTION_REPORT in bench.report(task_id), bench.explain(out)
    assert bench.names(project, task_id) == before | {f"mutation-run-{run_no}.tsv"}, \
        bench.explain(out)
    roots = (str(docs), str(docs.resolve()))
    touching = [r for r in bench.replaces
                if any(side.startswith(root) for side in r for root in roots)]
    assert touching == [], f"{touching}; {bench.explain(out)}"


def test_ac19_exception_before_table_leaves_docs_dir_as_is(bench):
    """Исключение до записи основной таблицы: каталог документов прежний и после отчёта.

    Сценарий: прогон с `--copy-table`, в фоновом процессе поиск клона
    проекта (`workspace.repo`, без клона нет sha ревизии для шапки)
    бросает исключение; отчёт `--wait 1`, затем повторный `--wait 0`.
    Основной таблицы прогона нет; множество имён каталога документов
    (скрытые тоже) после прогона и после повторного отчёта — прежнее.

    Ловит мутацию: копия создаётся на старте фонового процесса пустой или
    с шапкой до записи основной таблицы; отчётный вызов пишет копию, не
    проверив, что основная таблица есть (пустой файл копии).
    """
    project, task_id, _patches = bench.task_with_patches(2, 2)
    real_repo = workspace.repo

    def repo(*args, **kwargs):
        if bench.in_child:
            raise RuntimeError("подмена песочницы: клон проекта не найден")
        return real_repo(*args, **kwargs)

    bench.start_patch(mock.patch.object(workspace, "repo", repo))
    before = bench.names(project, task_id)
    _code, out = bench.command(*bench.run_args(task_id, project, "--copy-table",
                                               "--wait", "1"))
    run_no = bench.run_no_of(out)
    assert EXCEPTION_REPORT in bench.report(task_id), bench.explain(out)
    assert not bench.table_path(task_id, run_no).exists(), bench.explain(out)
    assert bench.names(project, task_id) == before, bench.explain(out)
    _code, again = bench.command(task_id, "--wait", "0")
    assert bench.names(project, task_id) == before, bench.explain(again)


# ------------------------------------------------------------ --workers


def cpu_patch(count: int) -> list:
    patches = [mock.patch.object(os, "cpu_count", lambda: count)]
    if hasattr(os, "process_cpu_count"):
        patches.append(mock.patch.object(os, "process_cpu_count",
                                         lambda: count))
    return patches


def test_ac20_workers_value_is_last_n_of_every_run(bench):
    """`--workers 2`: в `extra` контрольного прогона и каждого патча последнее значение `-n` — 2.

    Сценарий: число процессоров подменено (от зерна, не меньше 2); прогон
    двух–трёх патчей `--workers 2 --wait 1`. Шпион узла прогона вызван
    контрольным прогоном и по разу на патч; в `extra` каждого вызова есть
    `-n` и последнее его значение — `2`.

    Ловит мутацию: `-n` передан только контрольному прогону — у прогонов
    патчей его нет; `-n` поставлен перед флагами, а в `extra` уже есть
    `-n` умолчания позже — последним идёт не 2; `--workers` разобран, но в
    `extra` не передан.
    """
    for patcher in cpu_patch(bench.rng.randint(2, 32)):
        bench.start_patch(patcher)
    project, task_id, patches = bench.task_with_patches()
    code, out = bench.command(*bench.run_args(task_id, project, "--workers",
                                              "2", "--wait", "1"))
    assert code == 0, bench.explain(out)
    assert len(bench.probe.calls) == 1 + len(patches), bench.explain(out)
    for call in bench.probe.calls:
        values = n_values(call["extra"])
        assert values and values[-1] == "2", f"{call}; {bench.explain(out)}"


def test_ac21_without_workers_no_other_n(bench):
    """Без `--workers` в `extra` вызовов узла прогона нет `-n`, отличного от `config.FULL_SUITE_WORKERS`.

    Сценарий: прогон двух–трёх патчей `--wait 1` без `--workers`
    (`config.FULL_SUITE_WORKERS` подменён значением от зерна). У каждого
    вызова шпиона узла прогона все значения `-n` в `extra` равны
    `config.FULL_SUITE_WORKERS`.

    Ловит мутацию: умолчание `--workers` — `os.cpu_count()` или 1 и оно
    всегда идёт в `extra` — число рабочих процессов меняется без флага.
    """
    project, task_id, patches = bench.task_with_patches()
    code, out = bench.command(*bench.run_args(task_id, project, "--wait", "1"))
    assert code == 0, bench.explain(out)
    assert len(bench.probe.calls) == 1 + len(patches), bench.explain(out)
    for call in bench.probe.calls:
        assert set(n_values(call["extra"])) <= {str(config.FULL_SUITE_WORKERS)}, \
            f"{call}; {bench.explain(out)}"


@pytest.mark.parametrize("case", ["0", "отрицательное", "не число",
                                  "больше числа процессоров", "без значения"])
def test_ac22_bad_workers_refused_without_run(bench, case):
    """Неверный `--workers` — отказ без прогона, текст называет флаг.

    Сценарий: число процессоров подменено значением от зерна; `--workers`
    со значением 0, отрицательным, не числом, больше числа процессоров
    (значения — от зерна) либо последним аргументом без значения. Код
    выхода ненулевой, вывод называет `--workers`; узел прогона не
    вызывался, фоновый процесс не запускался, файлов прогона нет.

    Ловит мутацию: проверка `1 <= n` пропущена — 0 или отрицательное
    принято; верхняя граница не проверяется или сравнивается с
    `config.FULL_SUITE_WORKERS` — значение больше числа процессоров
    принято; нечисловое значение передано в `-n` как есть.
    """
    cpus = bench.rng.randint(1, 16)
    for patcher in cpu_patch(cpus):
        bench.start_patch(patcher)
    project, task_id, _patches = bench.task_with_patches(2, 2)
    extra = {"0": ("--workers", "0"),
             "отрицательное": ("--workers", str(-bench.rng.randint(1, 8))),
             "не число": ("--workers", bench.word(3)),
             "больше числа процессоров": ("--workers",
                                          str(cpus + bench.rng.randint(1, 5))),
             "без значения": ("--workers",)}[case]
    code, out = bench.command(*bench.run_args(task_id, project, *extra))
    assert code not in (0, None), bench.explain(out)
    assert "--workers" in out, bench.explain(out)
    assert bench.probe.calls == [], bench.explain(out)
    assert bench.child_runs == 0, bench.explain(out)
    assert bench.run_files(task_id) == [], bench.explain(out)


@pytest.mark.parametrize("workers", ["--workers 2", "без флага"])
def test_ac23_table_header_names_worker_count(bench, workers):
    """Шапка основной таблицы называет число рабочих процессов: 2 с `--workers 2`, иначе умолчание конфига.

    Сценарий: число процессоров подменено (не меньше 2); прогон с
    `--workers 2` либо без флага (`config.FULL_SUITE_WORKERS` — 1 или 3 от
    зерна). Среди строк шапки (`#`) таблицы есть строка о рабочих
    процессах (`рабоч`/`workers`/`-n`), несущая число `2` либо
    `config.FULL_SUITE_WORKERS` отдельным числом.

    Ловит мутацию: шапка всегда пишет `config.FULL_SUITE_WORKERS` — при
    `--workers 2` в ней умолчание; строки о рабочих процессах в шапке нет.
    """
    for patcher in cpu_patch(bench.rng.randint(2, 32)):
        bench.start_patch(patcher)
    project, task_id, _patches = bench.task_with_patches(2, 2)
    extra = ("--workers", "2") if workers == "--workers 2" else ()
    expected = "2" if extra else str(config.FULL_SUITE_WORKERS)
    _code, out = bench.command(*bench.run_args(task_id, project, *extra,
                                               "--wait", "1"))
    run_no = bench.run_no_of(out)
    header = [line for line in bench.table_path(task_id, run_no).read_text(
        encoding="utf-8").split("\n") if line.startswith("#")]
    about = [line for line in header
             if any(key in line for key in ("рабоч", "workers", "-n "))]
    number = re.compile(rf"(?<![\w.]){re.escape(expected)}(?![\w.])")
    assert any(number.search(line) for line in about), \
        f"шапка: {header}; {bench.explain(out)}"
