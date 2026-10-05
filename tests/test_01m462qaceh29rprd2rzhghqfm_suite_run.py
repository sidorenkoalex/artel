"""Команда `suite-run`: полный прогон тестов проекта задачи из шага роли.

Команда прогоняет полный набор тестов проекта задачи в её рабочей копии
командой профиля тестов проекта с параллелью `config.FULL_SUITE_WORKERS`
через узел пульта `acceptance.run_full_suite`/`full_suite`, отдельным
отвязанным процессом; отчёт забирается `--wait`, повтор упавших —
`--failed`. Упавшие сравниваются с итогом базы ветки задачи (сохранённым
гейтом или прогоном базы во временной рабочей копии клона); одновременно
идёт один прогон (замок); роли команда доступна и состояния задачи не
меняет.

Группа: долгоживущий
Красен до реализации: команды suite-run в диспетчере artel.py нет — копия пульта отвечает «Неизвестная команда», прогон не запускается; в config нет SUITE_RUN_*; миссия разработчика не называет suite-run; full_suite не сохраняет перечень упавших.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`) и КОПИЯ
кода пульта (`orchestrator/`, `scripts/`) в её корне: `config.ROOT`
считается от расположения `config.py`, поэтому команда, вызванная
подпроцессом из копии, и её отвязанный фоновый процесс видят пути
песочницы (БД, логи, `targets.yaml`, область проектов) — те же, что
подменены в процессе теста. В конец `config.py` копии дописаны параллель
и предел прогона сценария; в конец `acceptance.py` копии — наблюдатель
публичного узла `run_full_suite`/`full_suite` (корень и pid вызова).

Проект задачи — внешний target с клоном и bare `origin`
(`tests/sandbox.py::make_project_repo`), его тесты — файлы `tests/` от
зерна. Команда профиля тестов — `[<обёртка>/python3, -m, pytest]`:
обёртка пишет argv, cwd, `ARTEL_ROLE`, pid/ppid и HEAD каталога прогона в
журнал наблюдения и исполняет настоящий интерпретатор. `conftest.py`
проекта пишет каждый старт pytest (в том числе мимо профиля). Тест
«со шлагбаумом» ждёт файла-разрешения — так прогон держится идущим,
сколько нужно сценарию. Команда зовётся подпроцессом в своей группе
процессов; после её возврата группа добивается SIGKILL — как обрыв вызова
инструмента роли.
"""
import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, brief, config, review, role_prompt, store, workspace
from tests.sandbox import RealGitSandbox, make_project_repo

CODE_ROOT = Path(acceptance.__file__).resolve().parent.parent
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
ROLE_REFUSAL = "команда недоступна процессу роли"
STILL_RUNNING = "ещё идёт"
NO_BASE = "база не посчитана"
NEW_ON_BRANCH = "новые на ветке"
ALSO_ON_BASE = "падают и на базе"
EXCEPTIONS = ("ValueError", "RuntimeError", "TypeError", "LookupError",
              "ArithmeticError", "BufferError", "EOFError")

PROJECT_ENTRY = """  {name}:
    forge: github
    url: file://{origin}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

PROFILE = """    test_profile:
      command: [{command}]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

WRAPPER = '''#!{python}
import json, os, subprocess, sys, time
cwd = os.getcwd()
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd,
                      capture_output=True, text=True).stdout.strip()
record = {{"argv": sys.argv[1:], "cwd": os.path.realpath(cwd),
          "role": os.environ.get({role_env!r}), "pid": os.getpid(),
          "ppid": os.getppid(), "head": head, "at": time.time()}}
with open({calls!r}, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\\n")
if os.path.exists({garbage!r}):
    with open({garbage!r}, encoding="utf-8") as fh:
        keep = fh.read().strip()
    if os.path.realpath(cwd) != keep:
        os.write(1, b"\\xff\\xfe\\xfd broken output\\n")
        sys.exit(1)
os.execv({python!r}, [{python!r}, *sys.argv[1:]])
'''

CONFTEST = '''import json, os


def pytest_configure(config):
    record = {{"cwd": os.path.realpath(os.getcwd()),
              "role": os.environ.get({role_env!r}),
              "worker": hasattr(config, "workerinput")}}
    with open({path!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
'''

NODE_PROBE = '''

# Песочница теста suite-run: наблюдатель публичного узла полного прогона.
import json as probe_json
import os as probe_os

probe_original_run_full_suite = run_full_suite
probe_original_full_suite = full_suite


def probe_record(kind, root):
    with open({path!r}, "a", encoding="utf-8") as fh:
        fh.write(probe_json.dumps({{"kind": kind,
                                   "root": probe_os.path.realpath(str(root)),
                                   "pid": probe_os.getpid()}}) + "\\n")


def run_full_suite(root, *args, **kwargs):
    probe_record("run_full_suite", root)
    return probe_original_run_full_suite(root, *args, **kwargs)


def full_suite(root, *args, **kwargs):
    probe_record("full_suite", root)
    return probe_original_full_suite(root, *args, **kwargs)
'''


def passing(name: str) -> str:
    return f"def test_{name}():\n    assert True\n"


def failing(name: str, exc: str, message: str) -> str:
    return f"def test_{name}():\n    raise {exc}({message!r})\n"


def skipped(name: str) -> str:
    return ("import pytest\n\n\n@pytest.mark.skip(reason='песочница')\n"
            f"def test_{name}():\n    assert False\n")


def gated(name: str, release: Path, tail: str) -> str:
    return (f"def test_{name}():\n    import os, time\n"
            f"    deadline = time.time() + 100\n"
            f"    while not os.path.exists({str(release)!r}) "
            f"and time.time() < deadline:\n"
            f"        time.sleep(0.1)\n    {tail}\n")


def node_id(name: str) -> str:
    return f"tests/test_{name}.py::test_{name}"


def standalone(number: int, text: str) -> bool:
    return re.search(rf"(?<![\d.:]){number}(?![\d.:])", text) is not None


def phrase_number(text: str, phrase: str) -> int | None:
    """Число рядом с фразой отчёта: «фраза: N», «фраза (N)», «N — фраза»."""
    match = (re.search(rf"{phrase}\W{{0,4}}(\d+)", text)
             or re.search(rf"(\d+)\W{{0,4}}{phrase}", text))
    return int(match.group(1)) if match else None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SuiteRunSandbox(RealGitSandbox):
    """Копия пульта, проекты с профилем тестов и задачи с рабочими копиями."""

    TIMEOUT_SEC = 600
    WORKERS = None

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.probe = Path(tempfile.mkdtemp(prefix="artel-suite-probe-")).resolve()
        self.addCleanup(self.stop_everything)
        self.release_file = self.probe / "release"
        self.calls_file = self.probe / "calls.jsonl"
        self.pytest_file = self.probe / "pytest.jsonl"
        self.node_file = self.probe / "node.jsonl"
        self.garbage_file = self.probe / "garbage-outside"
        for name in ("orchestrator", "scripts"):
            shutil.copytree(CODE_ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        self.workers = self.WORKERS or self.rng.choice([1, 2])
        with open(self.root / "orchestrator" / "config.py", "a",
                  encoding="utf-8") as fh:
            fh.write(f"\n\n# Песочница теста suite-run.\n"
                     f"FULL_SUITE_WORKERS = {str(self.workers)!r}\n"
                     f"FULL_SUITE_TIMEOUT_SEC = {self.TIMEOUT_SEC}\n")
        with open(self.root / "orchestrator" / "acceptance.py", "a",
                  encoding="utf-8") as fh:
            fh.write(NODE_PROBE.format(path=str(self.node_file)))
        bin_dir = self.probe / "bin"
        bin_dir.mkdir()
        self.python = bin_dir / "python3"
        self.python.write_text(WRAPPER.format(
            python=sys.executable, role_env=config.ARTEL_ROLE_ENV,
            calls=str(self.calls_file), garbage=str(self.garbage_file)),
            encoding="utf-8")
        self.python.chmod(0o755)
        self.entries = {config.DEFAULT_TARGET: PROJECT_ENTRY.format(
            name=config.DEFAULT_TARGET, origin="/nonexistent/artel",
            base=config.MAIN_BRANCH) + PROFILE.format(
            command="python3, -m, pytest")}
        self.write_targets()
        self.workspaces = []
        self.conn = store.db()

    # --- фикстуры ---------------------------------------------------------

    def word(self, size: int = 8) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ALPHABET) for _ in range(23))

    def write_targets(self) -> None:
        text = "targets:\n" + "".join(self.entries.values())
        for path in {Path(config.TARGETS), self.root / "targets.yaml"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def add_project(self, files: dict, command="pytest") -> str:
        """Проект с профилем тестов (`command`: "pytest" — обёртка с
        `-m pytest`; список — своя команда; `None` — без профиля) и тестами
        `files` на базовой ветке. Возвращает имя target."""
        target = "p" + self.word()
        origin = config.PROJECTS / target / "origin.git"
        entry = PROJECT_ENTRY.format(name=target, origin=origin,
                                     base=config.MAIN_BRANCH)
        if command == "pytest":
            command = [str(self.python), "-m", "pytest"]
        if command is not None:
            entry += PROFILE.format(command=", ".join(command))
        self.entries[target] = entry
        self.write_targets()
        clone = make_project_repo(target)
        tests = clone / "tests"
        tests.mkdir()
        (tests / "conftest.py").write_text(CONFTEST.format(
            role_env=config.ARTEL_ROLE_ENV, path=str(self.pytest_file)),
            encoding="utf-8")
        self.write_files(clone, files)
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "тесты проекта")
        self.git("-C", str(clone), "push", "-q", "origin", config.MAIN_BRANCH)
        return target

    def clone(self, target: str) -> Path:
        return config.PROJECTS / target / "repo"

    def base_sha(self, target: str) -> str:
        return self.git("-C", str(self.clone(target)), "rev-parse",
                        f"origin/{config.MAIN_BRANCH}").strip()

    def write_files(self, repo: Path, files: dict) -> None:
        for name, text in files.items():
            path = repo / "tests" / f"test_{name}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def add_task(self, target: str, committed: dict = None,
                 uncommitted: dict = None) -> tuple:
        """(id, рабочая копия) задачи проекта `target` в `in_dev`."""
        task_id = self.task_id()
        branch = f"task/{task_id.lower()}-suite-run"
        store.insert_task(self.conn, task_id, "Фикстура suite-run", "in_dev",
                          branch, target, 25.0)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, f"рабочая копия не заведена: {error}")
        wt = Path(wt).resolve()
        if committed:
            self.write_files(wt, committed)
            self.git("-C", str(wt), "add", "-A")
            self.git("-C", str(wt), "commit", "-q", "-m", "правка ветки")
        if uncommitted:
            self.write_files(wt, uncommitted)
        self.workspaces.append(str(wt))
        return task_id, wt

    def hold(self) -> None:
        self.release_file.unlink(missing_ok=True)

    def release(self) -> None:
        self.release_file.write_text("go", encoding="utf-8")

    # --- команда ------------------------------------------------------------

    def cli(self, *args: str, cwd: Path = None, role: str = None,
            home: str = None, timeout: float = 100) -> tuple:
        """(код выхода, вывод, секунды) `artel.py <args>` копии пульта."""
        env = {k: v for k, v in os.environ.items()
               if k != config.ARTEL_ROLE_ENV}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if role is not None:
            env[config.ARTEL_ROLE_ENV] = role
        if home is not None:
            env["HOME"] = home
        started = time.monotonic()
        proc = subprocess.Popen(
            [sys.executable, str(self.root / "orchestrator" / "artel.py"),
             *args], cwd=str(cwd or self.root), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            raw, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill_group(proc.pid)
            proc.communicate()
            self.fail(f"artel.py {' '.join(args)} не вернулся за {timeout} с; "
                      f"зерно: {self.seed}")
        finally:
            self.kill_group(proc.pid)
        out = raw.decode("utf-8", errors="replace")
        return proc.returncode, out, time.monotonic() - started

    @staticmethod
    def kill_group(pgid: int) -> None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def launch(self, task_id: str, *extra: str, **kwargs) -> str:
        code, out, _ = self.cli("suite-run", task_id, *extra, **kwargs)
        self.assertNotIn(ROLE_REFUSAL, out, self.explain(out))
        self.assertTrue(self.paths_in(out),
                        f"запуск не назвал путь к логу; {self.explain(out)}")
        return out

    def report(self, task_id: str, **kwargs) -> str:
        _code, out, _ = self.cli("suite-run", task_id, "--wait", "1",
                                 **kwargs)
        self.assertNotIn(STILL_RUNNING, out,
                         f"прогон не завершился за минуту; {self.explain(out)}")
        return out

    def explain(self, output: str) -> str:
        return f"зерно: {self.seed}; вывод suite-run:\n{output[-3000:]}"

    def paths_in(self, output: str) -> list:
        found = []
        for raw in re.findall(r"/[^\s'\"«»(),;`]+", output):
            raw = raw.rstrip(".:")
            if raw.startswith(str(self.root)):
                found.append(Path(raw))
        return found

    # --- наблюдение ---------------------------------------------------------

    @staticmethod
    def read_jsonl(path: Path) -> list:
        if not path.exists():
            return []
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def calls(self) -> list:
        return [c for c in self.read_jsonl(self.calls_file)
                if "--collect-only" not in c["argv"]]

    def branch_calls(self, wt: Path) -> list:
        return [c for c in self.calls() if c["cwd"] == os.path.realpath(wt)]

    def base_calls(self) -> list:
        return [c for c in self.calls() if c["cwd"] not in self.workspaces]

    def wait_until(self, condition, what: str, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.2)
        self.fail(f"не дождались: {what}; зерно: {self.seed}")

    def wait_branch_call(self, wt: Path, count: int = 1) -> dict:
        self.wait_until(lambda: len(self.branch_calls(wt)) >= count,
                        f"прогон ветки №{count} в {wt}")
        return self.branch_calls(wt)[count - 1]

    def wait_dead(self, pid: int, timeout: float = 90) -> None:
        self.wait_until(lambda: not pid_alive(pid),
                        f"фоновый процесс {pid} завершился", timeout)

    def stop_everything(self) -> None:
        self.release()
        pids = set()
        for call in self.read_jsonl(self.calls_file):
            pids.update((call["pid"], call["ppid"]))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and any(pid_alive(p) for p in pids):
            time.sleep(0.2)
        for pid in pids:
            if pid_alive(pid) and pid != os.getpid():
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        shutil.rmtree(self.probe, ignore_errors=True)


class RunShapeTest(SuiteRunSandbox):

    def test_ac1_branch_run_in_workspace_with_profile_and_workers(self):
        """Прогон ветки идёт в рабочей копии задачи командой профиля с `-n`.

        Сценарий: проект с несколькими зелёными тестами, задача с коммитом на
        ветке; параллель копии пульта — 1 или 2 от зерна. `suite-run <id>`,
        затем `--wait`. Обёртка-интерпретатор профиля вызвана с cwd, равным
        рабочей копии задачи, с `-m pytest` и парой `-n <параллель>`;
        наблюдатель узла записал вызов `run_full_suite`/`full_suite` с
        корнем — рабочей копией — в том самом процессе, что породил pytest.

        Ловит мутацию: прогон в клоне проекта или в корне пульта — cwd
        обёртки не рабочая копия; литерал `-n auto` вместо
        `config.FULL_SUITE_WORKERS` — пары `-n <параллель>` нет; pytest
        интерпретатором пульта мимо профиля — обёртка не вызвана; свой
        `subprocess.run` мимо узла — у процесса-родителя pytest нет записи
        наблюдателя.
        """
        names = [self.word() for _ in range(2 + self.rng.randrange(3))]
        target = self.add_project({n: passing(n) for n in names})
        extra = self.word()
        task_id, wt = self.add_task(target, committed={extra: passing(extra)})
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        calls = self.branch_calls(wt)
        self.assertTrue(calls, f"обёртка профиля не вызвана в рабочей копии; "
                               f"{self.explain(out)}")
        argv = calls[0]["argv"]
        self.assertEqual(argv[:2], ["-m", "pytest"], self.explain(out))
        pairs = list(zip(argv, argv[1:]))
        self.assertIn(("-n", str(self.workers)), pairs,
                      f"argv {argv}; {self.explain(out)}")
        nodes = [n for n in self.read_jsonl(self.node_file)
                 if n["root"] == os.path.realpath(wt)
                 and n["pid"] == calls[0]["ppid"]]
        self.assertTrue(nodes, f"прогон шёл мимо run_full_suite/full_suite; "
                               f"записи узла {self.read_jsonl(self.node_file)}; "
                               f"{self.explain(out)}")

    def test_ac2_uncommitted_edit_is_seen_by_run(self):
        """Незакоммиченная правка рабочего дерева видна прогону.

        Сценарий: на базе проекта тест `test_<имя>` зелёный; в рабочей копии
        задачи он переписан так, что падает, и правка НЕ закоммичена. Отчёт
        `--wait` называет этот тест упавшим (имя теста в отчёте).

        Ловит мутацию: прогон ветки идёт на чистой выкладке HEAD (свежий
        worktree/clone ветки или stash перед прогоном) — тест зелёный, его
        имени в отчёте нет.
        """
        flip = self.word()
        others = [self.word() for _ in range(2)]
        files = {n: passing(n) for n in others}
        files[flip] = passing(flip)
        target = self.add_project(files)
        message = f"незакоммиченная правка {self.word()}"
        task_id, wt = self.add_task(
            target, uncommitted={flip: failing(flip, "ValueError", message)})
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        self.assertIn(f"test_{flip}", out, self.explain(out))
        status = self.git("-C", str(wt), "status", "--porcelain")
        self.assertIn(f"test_{flip}.py", status,
                      f"незакоммиченная правка пропала из рабочей копии; "
                      f"{self.explain(out)}")


class ProfileRefusalTest(SuiteRunSandbox):

    def assert_no_run(self, out: str) -> None:
        time.sleep(3)
        self.assertEqual(self.calls(), [], f"команда профиля вызвана; "
                                           f"{self.explain(out)}")
        self.assertEqual(self.read_jsonl(self.pytest_file), [],
                         f"pytest проекта запускался; {self.explain(out)}")

    def test_ac3_project_without_profile_is_refused(self):
        """Проект без профиля тестов — отказ без прогона.

        Сценарий: запись проекта в `targets.yaml` без `test_profile`, задача с
        рабочей копией и тестами `tests/`. `suite-run <id>` завершается
        ненулевым кодом, вывод называет причину (профиль тестов); ни
        команда профиля, ни pytest проекта (`conftest.py` пишет каждый
        старт) не запускались.

        Ловит мутацию: без профиля команда откатывается на pytest пульта —
        `conftest.py` проекта записал старт; отказ печатается, но код выхода
        0 — код не ненулевой.
        """
        target = self.add_project({self.word(): passing("x")}, command=None)
        task_id, wt = self.add_task(target)
        code, out, _ = self.cli("suite-run", task_id, cwd=wt, timeout=60)
        self.assertNotEqual(code, 0, self.explain(out))
        self.assertRegex(out.lower(), r"профил", self.explain(out))
        self.assert_no_run(out)

    def test_ac4_non_pytest_profile_command_is_refused(self):
        """Команда профиля, не запускающая pytest, — отказ без прогона.

        Сценарий: профиль с командой обёртки-интерпретатора, но не pytest
        (`-m unittest`, `-m nose2`, скрипт прогона — выбор от зерна).
        `suite-run <id>` завершается ненулевым кодом, вывод называет
        причину (упоминает pytest); обёртка и pytest проекта не вызывались.

        Ловит мутацию: флаги параллели дописываются к любой команде профиля
        — обёртка вызвана с `-n`; проверка «это pytest» смотрит только на
        имя интерпретатора `python3` — прогон запущен.
        """
        variants = ([str(self.python), "-m", "unittest"],
                    [str(self.python), "-m", "nose2"],
                    [str(self.python), "run_tests.py"])
        command = self.rng.choice(variants)
        target = self.add_project({self.word(): passing("x")}, command=command)
        task_id, wt = self.add_task(target)
        code, out, _ = self.cli("suite-run", task_id, cwd=wt, timeout=60)
        self.assertNotEqual(code, 0, f"команда {command}; {self.explain(out)}")
        self.assertIn("pytest", out, self.explain(out))
        self.assert_no_run(out)


class RoleEnvironmentTest(SuiteRunSandbox):

    def test_ac5_runs_have_no_artel_role_in_environment(self):
        """Окружение прогонов ветки и базы не несёт `ARTEL_ROLE`.

        Сценарий: `suite-run <id>` и `--wait` вызваны с `ARTEL_ROLE` случайной
        роли в окружении; сохранённого итога базы нет — идёт и прогон базы.
        Обёртка профиля в прогоне ветки и в прогоне базы видит `ARTEL_ROLE`
        отсутствующим; `conftest.py` проекта — тоже во всех процессах pytest.

        Ловит мутацию: окружение прогона — копия `os.environ` вызвавшего
        процесса без снятия маркера роли — обёртка записала роль; маркер
        снят только у прогона ветки, а прогон базы берёт окружение заново —
        роль в записи прогона базы.
        """
        names = [self.word() for _ in range(2)]
        target = self.add_project({n: passing(n) for n in names})
        task_id, wt = self.add_task(target)
        role = f"role_{self.word()}"
        self.launch(task_id, cwd=wt, role=role)
        out = self.report(task_id, cwd=wt, role=role)
        self.assertTrue(self.branch_calls(wt), self.explain(out))
        self.assertTrue(self.base_calls(), f"прогона базы не было; "
                                           f"{self.explain(out)}")
        for call in self.calls():
            self.assertIsNone(call["role"], f"роль в окружении прогона {call}; "
                                            f"{self.explain(out)}")
        records = self.read_jsonl(self.pytest_file)
        self.assertTrue(records, self.explain(out))
        for record in records:
            self.assertIsNone(record["role"], f"{record}; {self.explain(out)}")

    def test_ac22_role_process_is_not_refused(self):
        """Процесс роли исполняет `suite-run` и `--wait`.

        Сценарий: два варианта окружения шага роли — маркер `ARTEL_ROLE` со
        случайной ролью и HOME, равный дому роли копии пульта, без маркера.
        В обоих `suite-run <id>` не отказывает текстом «команда недоступна
        процессу роли», прогон ветки запускается, `--wait` под тем же
        окружением отдаёт отчёт.

        Ловит мутацию: `suite-run` не внесена в `_ROLE_ALLOWED_COMMANDS` —
        диспетчер отказывает процессу роли, обёртка профиля не вызвана.
        """
        target = self.add_project({self.word(): passing("x")})
        variants = (("маркер", {"role": f"role_{self.word()}"}),
                    ("HOME роли", {"home": str(self.root / ".artel" / "home")}))
        for label, env in variants:
            with self.subTest(variant=label):
                task_id, wt = self.add_task(target)
                code, out, _ = self.cli("suite-run", task_id, cwd=wt, **env)
                self.assertNotIn(ROLE_REFUSAL, out, self.explain(out))
                self.wait_branch_call(wt)
                out = self.report(task_id, cwd=wt, **env)
                self.assertNotIn(ROLE_REFUSAL, out, self.explain(out))


class BackgroundTest(SuiteRunSandbox):

    def gated_task(self) -> tuple:
        """(id, рабочая копия, имя теста-шлагбаума): база проекта зелёная,
        ветка добавляет тест, падающий после разрешения."""
        self.hold()
        target = self.add_project({self.word(): passing("ok")})
        gate = self.word()
        task_id, wt = self.add_task(target, committed={gate: gated(
            gate, self.release_file,
            f"raise ValueError('шлагбаум {self.word()}')")})
        return task_id, wt, gate

    def test_ac6_returns_before_run_ends_and_run_survives_caller(self):
        """Команда возвращается сразу, прогон живёт отдельным процессом.

        Сценарий: база проекта зелёная, тест ветки задачи держит прогон до
        файла-разрешения и затем падает.
        `suite-run <id>` вызвана в своей группе процессов и вернулась, пока
        разрешения нет, — то есть до конца прогона; вывод несёт номер
        прогона и путь к логу под корнем пульта. Сразу после возврата вся
        группа вызова добита SIGKILL (обрыв вызова инструмента роли), но
        прогон ветки стартует и его процесс жив; после разрешения `--wait`
        отдаёт отчёт с упавшим тестом-шлагбаумом, файл лога существует.

        Ловит мутацию: прогон без `start_new_session` (в группе вызвавшего)
        — SIGKILL группы обрывает его, отчёта нет; команда ждёт конца
        прогона на переднем плане — не возвращается до разрешения.
        """
        task_id, wt, gate = self.gated_task()
        out = self.launch(task_id, cwd=wt)
        self.assertFalse(self.release_file.exists())
        self.assertRegex(out, r"(?<![\w/.-])\d+(?![\w/.-])",
                         f"номера прогона нет; {self.explain(out)}")
        log_paths = self.paths_in(out)
        call = self.wait_branch_call(wt)
        time.sleep(1)
        self.assertTrue(pid_alive(call["ppid"]),
                        f"фоновый прогон оборван вместе с вызовом; "
                        f"{self.explain(out)}")
        self.release()
        report = self.report(task_id, cwd=wt)
        self.assertIn(f"test_{gate}", report, self.explain(report))
        self.assertTrue(any(p.is_file() for p in log_paths),
                        f"лога по путям {log_paths} нет; {self.explain(out)}")

    def test_ac7_second_launch_reports_running_run(self):
        """Повторный запуск при идущем прогоне не заводит второй.

        Сценарий: прогон задачи держится шлагбаумом; второй `suite-run <id>`
        без `--wait` выводит путь к логу того же идущего прогона; после
        разрешения и отчёта обёртка профиля вызывалась в рабочей копии
        ровно один раз.

        Ловит мутацию: проверки «прогон этой задачи уже идёт» нет — второй
        вызов заводит новый прогон: другой путь к логу и второй вызов pytest
        в рабочей копии.
        """
        task_id, wt, _gate = self.gated_task()
        first = self.launch(task_id, cwd=wt)
        self.wait_branch_call(wt)
        second = self.launch(task_id, cwd=wt)
        common = set(self.paths_in(first)) & set(self.paths_in(second))
        self.assertTrue(common, f"второй вызов не назвал лог идущего прогона; "
                                f"первый:\n{first}\nвторой:\n{second}; "
                                f"зерно: {self.seed}")
        self.release()
        out = self.report(task_id, cwd=wt)
        self.assertEqual(len(self.branch_calls(wt)), 1, self.explain(out))

    def test_ac8_wait_reports_finished_or_still_running(self):
        """`--wait` отдаёт отчёт завершённого либо «ещё идёт» без обрыва.

        Сценарий: прогон держится шлагбаумом. `--wait 0` печатает «ещё
        идёт» с ходом прогона (числа) и выходит ненулевым кодом, процесс
        прогона жив. Затем `--wait 1` запущен параллельно, и разрешение дано
        во время его ожидания — он печатает отчёт с упавшим тестом. Затем
        ещё `--wait 1` после завершения — отчёт сразу. Прогон в рабочей
        копии был один (не перезапускался).

        Ловит мутацию: ожидание по истечении срока прерывает прогон —
        процесс прогона мёртв, отчёта нет; «ещё идёт» выходит кодом 0;
        `--wait` перезапускает прогон — второй вызов pytest; отчёт печатается
        только по завершении до вызова — ожидающий вызов возвращает «ещё
        идёт».
        """
        task_id, wt, gate = self.gated_task()
        self.launch(task_id, cwd=wt)
        call = self.wait_branch_call(wt)
        code, out, _ = self.cli("suite-run", task_id, "--wait", "0", cwd=wt,
                                timeout=40)
        self.assertNotEqual(code, 0, self.explain(out))
        self.assertIn(STILL_RUNNING, out, self.explain(out))
        self.assertRegex(out, r"\d", f"хода прогона нет; {self.explain(out)}")
        self.assertTrue(pid_alive(call["ppid"]),
                        f"прогон оборван ожиданием; {self.explain(out)}")

        result = {}

        def waiting():
            result["out"] = self.cli("suite-run", task_id, "--wait", "1",
                                     cwd=wt, timeout=100)[1]

        thread = threading.Thread(target=waiting)
        thread.start()
        time.sleep(2)
        self.release()
        thread.join(110)
        within = result.get("out", "")
        self.assertNotIn(STILL_RUNNING, within, self.explain(within))
        self.assertIn(f"test_{gate}", within, self.explain(within))

        self.wait_dead(call["ppid"])
        _code, after, elapsed = self.cli("suite-run", task_id, "--wait", "1",
                                         cwd=wt)
        self.assertIn(f"test_{gate}", after, self.explain(after))
        self.assertLess(elapsed, 45, self.explain(after))
        self.assertEqual(len(self.branch_calls(wt)), 1, self.explain(after))

    def test_ac9_wait_without_any_run_is_refused(self):
        """`--wait` без прогонов задачи — отказ с подсказкой.

        Сценарий: свежая задача, `suite-run <id> --wait 1`. Команда
        возвращается сразу (не ждёт минуту) ненулевым кодом, вывод называет
        `suite-run` и id задачи; обёртка профиля не вызывалась.

        Ловит мутацию: `--wait` без прогона сам запускает прогон — обёртка
        вызвана; ожидание несуществующего прогона длится весь срок — вызов
        не укладывается в 40 с; код выхода 0.
        """
        target = self.add_project({self.word(): passing("x")})
        task_id, wt = self.add_task(target)
        code, out, _ = self.cli("suite-run", task_id, "--wait", "1", cwd=wt,
                                timeout=40)
        self.assertNotEqual(code, 0, self.explain(out))
        self.assertIn("suite-run", out, self.explain(out))
        self.assertIn(task_id, out, self.explain(out))
        time.sleep(2)
        self.assertEqual(self.calls(), [], self.explain(out))

    def test_ac10_wait_above_limit_is_refused_without_waiting(self):
        """`--wait` больше `SUITE_RUN_MAX_WAIT_MIN` — отказ без ожидания.

        Сценарий: в `config` есть `SUITE_RUN_MAX_WAIT_MIN = 9`. При идущем
        (держится шлагбаумом) прогоне `suite-run <id> --wait <предел + k>`
        (k от зерна) возвращается за секунды ненулевым кодом, без «ещё
        идёт», с причиной, называющей предел; прогон жив.

        Ловит мутацию: предела нет — команда ждёт десятки минут (вызов не
        укладывается в 40 с); предел сверяется литералом иного значения —
        отказ не называет 9 либо не наступает.
        """
        self.assertEqual(config.SUITE_RUN_MAX_WAIT_MIN, 9)
        task_id, wt, _gate = self.gated_task()
        self.launch(task_id, cwd=wt)
        call = self.wait_branch_call(wt)
        minutes = config.SUITE_RUN_MAX_WAIT_MIN + 1 + self.rng.randrange(20)
        code, out, _ = self.cli("suite-run", task_id, "--wait", str(minutes),
                                cwd=wt, timeout=40)
        self.assertNotEqual(code, 0, self.explain(out))
        self.assertNotIn(STILL_RUNNING, out, self.explain(out))
        self.assertTrue(standalone(config.SUITE_RUN_MAX_WAIT_MIN, out),
                        f"причина не называет предел; {self.explain(out)}")
        self.assertTrue(pid_alive(call["ppid"]), self.explain(out))


class TimeoutTest(SuiteRunSandbox):
    TIMEOUT_SEC = 15
    WORKERS = 1

    def test_ac11_branch_run_over_limit_reports_partial_numbers(self):
        """Прогон ветки сверх предела — «не уложился» с числами успевшего.

        Сценарий: предел прогона копии — 15 с, параллель 1. На ветке — P
        зелёных и F падающих быстрых тестов и последним по порядку тест,
        висящий до разрешения (его не дают); на базе — один зелёный тест.
        Отчёт `--wait` несёт «не уложился», числа P + 1 и F и путь к
        существующему файлу лога.

        Ловит мутацию: исход предела не отличается от красного прогона —
        «не уложился» нет; разбор идёт только по итоговой строке pytest,
        которой у оборванного прогона нет, — чисел P и F нет; таймаут
        поднимает исключение в фоновом процессе — отчёта нет.
        """
        self.hold()
        target = self.add_project({self.word(): passing("base")})
        n_pass = 3 + self.rng.randrange(4)
        n_fail = 1 + self.rng.randrange(2)
        committed = {}
        for _ in range(n_pass):
            name = "a" + self.word()
            committed[name] = passing(name)
        for _ in range(n_fail):
            name = "b" + self.word()
            committed[name] = failing(name, "ValueError", "быстрый сбой")
        committed["zz" + self.word()] = gated("zzblock", self.release_file,
                                             "pass")
        task_id, wt = self.add_task(target, committed=committed)
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        self.assertIn("не уложился", out, self.explain(out))
        # Зелёных — P тестов ветки и тест базы проекта.
        for number in (n_pass + 1, n_fail):
            self.assertTrue(standalone(number, out),
                            f"числа {number} нет; {self.explain(out)}")
        self.assertTrue(any(p.is_file() for p in self.paths_in(out)),
                        f"лога нет; {self.explain(out)}")


class BaseComparisonTest(SuiteRunSandbox):

    def red_base_project(self, n_base: int) -> tuple:
        names = [self.word() for _ in range(n_base)]
        files = {n: failing(n, "RuntimeError", "сбой и на базе") for n in names}
        files[self.word()] = passing("ok")
        return self.add_project(files), names

    def new_failures(self, count: int) -> dict:
        files = {}
        for index in range(count):
            name = self.word()
            files[name] = failing(name, EXCEPTIONS[index],
                                  f"новый сбой {self.word()}")
        return files

    def test_ac12_failures_split_into_new_and_also_on_base(self):
        """Упавшие делятся на «новые на ветке» и «падают и на базе».

        Сценарий: на базе падают N_base тестов; ветка добавляет N_new своих
        падающих тестов с разными признаками ошибки (N_base ≠ N_new, от
        зерна). Итога базы нет — его считает прогон базы. В отчёте рядом с
        «падают и на базе» — N_base, рядом с «новые на ветке» — N_new, имена
        новых упавших названы.

        Ловит мутацию: сравнение с базой перепутано или не сделано — все
        упавшие считаются новыми (рядом с «новые на ветке» N_base + N_new)
        либо числа меняются местами.
        """
        n_base = 1 + self.rng.randrange(3)
        n_new = self.rng.choice([n for n in (1, 2, 3) if n != n_base])
        target, _names = self.red_base_project(n_base)
        new = self.new_failures(n_new)
        task_id, wt = self.add_task(target, committed=new)
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        self.assertEqual(phrase_number(out, ALSO_ON_BASE), n_base,
                         self.explain(out))
        self.assertEqual(phrase_number(out, NEW_ON_BRANCH), n_new,
                         self.explain(out))
        for name in new:
            self.assertIn(f"test_{name}", out, self.explain(out))

    def gate_tree(self, target: str) -> Path:
        gate = self.probe / f"gate-{self.word()}"
        self.git("-C", str(self.clone(target)), "worktree", "add", "-q",
                 "--detach", str(gate), self.base_sha(target))
        return gate

    def test_ac13_gate_full_suite_result_is_reused_as_base(self):
        """Итог гейта по sha дерева служит итогом базы `suite-run`.

        Сценарий: на базе падают N_base тестов. Гейт пульта прогоняет
        `acceptance.full_suite` (в процессе теста) на рабочей копии клона,
        выписанной на sha базы. Затем задача с новым падающим тестом:
        `suite-run` не прогоняет базу (обёртка вызвана только в рабочей
        копии задачи), а отчёт несёт N_base рядом с «падают и на базе».

        Ловит мутацию: `full_suite` гейта не сохраняет перечень упавших или
        сохраняет его не по sha дерева прогона (по id задачи, по имени
        ветки) — `suite-run` прогоняет базу сам, обёртка вызвана вне рабочей
        копии.
        """
        n_base = 1 + self.rng.randrange(3)
        target, _names = self.red_base_project(n_base)
        gate = self.gate_tree(target)
        with mock.patch.object(config, "FULL_SUITE_WORKERS", str(self.workers)):
            result = acceptance.full_suite(gate, self.task_id())
        self.assertFalse(result.green, result.detail)
        before = len(self.base_calls())
        new = self.new_failures(1)
        task_id, wt = self.add_task(target, committed=new)
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        self.assertEqual(len(self.base_calls()), before,
                         f"база прогнана, хотя итог гейта есть; "
                         f"{self.explain(out)}")
        self.assertEqual(phrase_number(out, ALSO_ON_BASE), n_base,
                         self.explain(out))

    def test_ac14_base_run_in_temporary_copy_at_diff_base(self):
        """Прогон базы — тем же процессом, после ветки, во временной копии.

        Сценарий: итога базы нет; ветка задачи несёт свой коммит. Обёртка
        профиля вызвана дважды: сначала в рабочей копии задачи, затем в
        каталоге, который не рабочая копия задачи и не клон, с HEAD, равным
        sha базы ветки (`origin/main` клона на момент заведения), и с тем же
        родительским процессом, что прогон ветки.

        Ловит мутацию: база прогоняется в рабочей копии задачи (checkout
        базы поверх правок) — cwd совпадает; база берётся от HEAD ветки или
        от локальной ветки клона — HEAD прогона базы не sha базы; база
        прогоняется отдельным процессом или до ветки — другой ppid или
        порядок.
        """
        target = self.add_project({self.word(): passing("x")})
        base = self.base_sha(target)
        extra = self.word()
        task_id, wt = self.add_task(target, committed={extra: passing(extra)})
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        calls = self.calls()
        branch = [i for i, c in enumerate(calls)
                  if c["cwd"] == os.path.realpath(wt)]
        bases = [i for i, c in enumerate(calls)
                 if c["cwd"] != os.path.realpath(wt)]
        self.assertEqual(len(branch), 1, self.explain(out))
        self.assertEqual(len(bases), 1, self.explain(out))
        base_call = calls[bases[0]]
        self.assertGreater(bases[0], branch[0], self.explain(out))
        self.assertNotEqual(base_call["cwd"],
                            os.path.realpath(self.clone(target)),
                            self.explain(out))
        self.assertFalse(base_call["cwd"].startswith(os.path.realpath(wt) + "/"),
                         self.explain(out))
        self.assertEqual(base_call["head"], base, self.explain(out))
        self.assertEqual(base_call["ppid"], calls[branch[0]]["ppid"],
                         self.explain(out))

    def test_ac15_same_base_is_run_once_across_runs_and_tasks(self):
        """Итог базы одной sha считается один раз на все прогоны и задачи.

        Сценарий: две задачи одного проекта от одной базы с падающими на
        базе тестами. Прогон задачи A, затем задачи B, затем ещё раз A:
        обёртка вызвана вне рабочих копий задач (прогон базы) ровно один
        раз; отчёт B несёт N_base рядом с «падают и на базе».

        Ловит мутацию: итог базы хранится по задаче, а не по sha — B
        прогоняет базу второй раз; итог не сохраняется вовсе — база
        прогоняется на каждом запуске.
        """
        n_base = 1 + self.rng.randrange(3)
        target, _names = self.red_base_project(n_base)
        task_a, wt_a = self.add_task(target, committed=self.new_failures(1))
        task_b, wt_b = self.add_task(target, committed=self.new_failures(1))
        self.launch(task_a, cwd=wt_a)
        self.report(task_a, cwd=wt_a)
        self.launch(task_b, cwd=wt_b)
        out_b = self.report(task_b, cwd=wt_b)
        self.launch(task_a, cwd=wt_a)
        self.wait_branch_call(wt_a, 2)
        out = self.report(task_a, cwd=wt_a)
        self.assertEqual(len(self.base_calls()), 1, self.explain(out))
        self.assertEqual(phrase_number(out_b, ALSO_ON_BASE), n_base,
                         self.explain(out_b))


class BaseTimeoutTest(SuiteRunSandbox):
    TIMEOUT_SEC = 15
    WORKERS = 1

    def blocking_base_project(self) -> tuple:
        self.hold()
        block = "zz" + self.word()
        fail = self.word()
        files = {block: gated(block, self.release_file, "pass"),
                 fail: failing(fail, "ValueError", "сбой и на базе"),
                 self.word(): passing("ok")}
        return self.add_project(files), block, fail

    def test_ac16_timed_out_base_is_not_saved(self):
        """Незавершённый прогон базы — «база не посчитана», итог не сохранён.

        Сценарий: предел копии — 15 с; на базе тест висит до разрешения, на
        ветке он переписан быстрым, ещё один тест падает и там, и там.
        Первый отчёт: «база не посчитана», числа рядом с «падают и на базе»
        нет. Разрешение дано; второй `suite-run` той же задачи прогоняет
        базу заново (второй вызов обёртки вне рабочей копии), и его отчёт
        уже несёт 1 рядом с «падают и на базе».

        Ловит мутацию: итог базы сохраняется и при таймауте (пустой перечень
        упавших) — второй прогон базу не гонит, а первый отчёт делит
        упавшие на «новые»/«на базе».
        """
        target, block, _fail = self.blocking_base_project()
        task_id, wt = self.add_task(target, committed={block: passing(block)})
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        self.assertIn(NO_BASE, out, self.explain(out))
        self.assertIsNone(phrase_number(out, ALSO_ON_BASE), self.explain(out))
        self.release()
        self.launch(task_id, cwd=wt)
        self.wait_branch_call(wt, 2)
        out = self.report(task_id, cwd=wt)
        self.assertEqual(len(self.base_calls()), 2, self.explain(out))
        self.assertEqual(phrase_number(out, ALSO_ON_BASE), 1, self.explain(out))

    def test_ac16_timed_out_gate_run_saves_nothing(self):
        """Прогон гейта сверх предела итога по своей sha не сохраняет.

        Сценарий: на базе тест висит до разрешения; `acceptance.full_suite`
        гейта (в процессе теста, предел 5 с) на рабочей копии клона с sha
        базы не укладывается. Затем разрешение дано, и `suite-run` задачи с
        этой базой прогоняет базу сам — обёртка вызвана вне рабочей копии.

        Ловит мутацию: `full_suite` сохраняет перечень упавших и для
        таймаута — `suite-run` берёт пустой итог гейта и базу не гонит.
        """
        target, block, _fail = self.blocking_base_project()
        gate = self.probe / f"gate-{self.word()}"
        self.git("-C", str(self.clone(target)), "worktree", "add", "-q",
                 "--detach", str(gate), self.base_sha(target))
        with mock.patch.object(config, "FULL_SUITE_WORKERS", "1"), \
                mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 5):
            result = acceptance.full_suite(gate, self.task_id())
        self.assertFalse(result.green, result.detail)
        self.release()
        task_id, wt = self.add_task(target, committed={block: passing(block)})
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        self.assertEqual(len(self.base_calls()), 1,
                         f"база не прогнана после таймаута гейта; "
                         f"{self.explain(out)}")


class ReportTest(SuiteRunSandbox):

    def test_ac17_report_numbers_groups_examples_and_log(self):
        """Отчёт: числа, группы по признаку ошибки, до трёх примеров, лог.

        Сценарий: на базе P зелёных и S пропущенных тестов; ветка добавляет
        G групп падающих тестов разного размера: в группе тип исключения и
        первая строка сообщения общие, вторая строка у каждого теста своя.
        В отчёте — числа P, S и всего упавших; строка признака каждой группы
        несёт тип, первую строку и размер группы; из имён тестов группы
        названо от одного до min(3, размер); путь к логу — существующий
        файл, где названы все упавшие тесты.

        Ловит мутацию: группировка по всему тексту сообщения — группы
        дробятся по второй строке, размер в строке группы не тот; примеров
        не ограничено тремя — названо больше; путь к логу не тот файл или
        лог без полного вывода.
        """
        n_pass = 2 + self.rng.randrange(3)
        n_skip = 1 + self.rng.randrange(2)
        files = {}
        for _ in range(n_pass):
            name = self.word()
            files[name] = passing(name)
        for _ in range(n_skip):
            name = self.word()
            files[name] = skipped(name)
        target = self.add_project(files)
        sizes = self.rng.sample(range(1, 7), 2 + self.rng.randrange(3))
        groups = []
        committed = {}
        for index, size in enumerate(sizes):
            exc = EXCEPTIONS[index]
            first = f"группа {self.word()} {self.word()}"
            names = []
            for _ in range(size):
                name = self.word()
                names.append(name)
                committed[name] = failing(name, exc, f"{first}\n{self.word()}")
            groups.append((exc, first, names))
        n_fail = sum(sizes)
        task_id, wt = self.add_task(target, committed=committed)
        self.launch(task_id, cwd=wt)
        out = self.report(task_id, cwd=wt)
        for number in (n_pass, n_skip, n_fail):
            self.assertTrue(standalone(number, out),
                            f"числа {number} нет; {self.explain(out)}")
        for exc, first, names in groups:
            lines = [line for line in out.splitlines() if first in line]
            self.assertTrue(lines, f"группы «{first}» нет; {self.explain(out)}")
            self.assertTrue(any(exc in line and standalone(len(names), line)
                                for line in lines),
                            f"строка группы «{first}» без типа {exc} или "
                            f"размера {len(names)}; {self.explain(out)}")
            shown = [n for n in names if f"test_{n}" in out]
            self.assertTrue(1 <= len(shown) <= min(3, len(names)),
                            f"примеров группы «{first}»: {len(shown)}; "
                            f"{self.explain(out)}")
        logs = [p for p in self.paths_in(out) if p.is_file()]
        self.assertTrue(logs, f"лога нет; {self.explain(out)}")
        log_text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                             for p in logs)
        for _exc, _first, names in groups:
            for name in names:
                self.assertIn(f"test_{name}", log_text, self.explain(out))

    def test_ac18_groups_and_signature_line_are_capped(self):
        """Групп в отчёте не больше 10, строка признака — не длиннее 200.

        Сценарий: константы `SUITE_RUN_MAX_GROUPS = 10` и
        `SUITE_RUN_MAX_LINE_CHARS = 200` есть в `config`. Задача A: ветка
        добавляет 10 + E групп по k тестов (E, k от зерна) — названо ровно
        10 групп и строка «и ещё E групп, E·k тестов». Задача B: группа с
        первой строкой сообщения длиннее 300 символов — в отчёте её начало
        (150 символов), но не первые 250.

        Ловит мутацию: предел групп не применён — названы все группы и
        строки «и ещё» нет; хвост считает группы или тесты не так; строка
        признака не обрезается — в отчёте сообщение целиком.
        """
        self.assertEqual(config.SUITE_RUN_MAX_GROUPS, 10)
        self.assertEqual(config.SUITE_RUN_MAX_LINE_CHARS, 200)
        target = self.add_project({self.word(): passing("x")})
        extra = 1 + self.rng.randrange(3)
        size = 1 + self.rng.randrange(2)
        firsts = []
        committed = {}
        for index in range(config.SUITE_RUN_MAX_GROUPS + extra):
            first = f"группа {self.word()} {self.word()}"
            firsts.append(first)
            for _ in range(size):
                name = self.word()
                committed[name] = failing(name, EXCEPTIONS[index % 7], first)
        task_a, wt_a = self.add_task(target, committed=committed)
        self.launch(task_a, cwd=wt_a)
        out = self.report(task_a, cwd=wt_a)
        shown = [f for f in firsts if f in out]
        self.assertEqual(len(shown), config.SUITE_RUN_MAX_GROUPS,
                         self.explain(out))
        tail = re.search(r"и ещё (\d+) групп\w*,\s*(\d+) тест", out)
        self.assertIsNotNone(tail, self.explain(out))
        self.assertEqual((int(tail.group(1)), int(tail.group(2))),
                         (extra, extra * size), self.explain(out))

        long_line = " ".join(self.word() for _ in range(40))
        self.assertGreater(len(long_line), 300)
        name = self.word()
        task_b, wt_b = self.add_task(
            target, committed={name: failing(name, "ValueError", long_line)})
        self.launch(task_b, cwd=wt_b)
        out = self.report(task_b, cwd=wt_b)
        self.assertIn(long_line[:150], out, self.explain(out))
        self.assertNotIn(long_line[:config.SUITE_RUN_MAX_LINE_CHARS + 50], out,
                         self.explain(out))


class FailedRerunTest(SuiteRunSandbox):

    def test_ac19_failed_reruns_exactly_last_failures(self):
        """`--failed` повторяет ровно упавшие прошлого прогона, фоново.

        Сценарий: ветка добавляет k падающих тестов и падающий тест со
        шлагбаумом. Полный прогон (разрешение дано) — отчёт. Затем один из
        упавших исправлен незакоммиченной правкой, разрешение снято, и
        `suite-run <id> --failed` возвращается, пока прогон держится:
        обёртка вызвана в рабочей копии с id тестов ровно из перечня
        упавших, без `--lf`/`--last-failed`, с `-p no:cacheprovider`; база
        не прогонялась второй раз. После разрешения `--wait` отдаёт отчёт
        без исправленного теста. Второй `--failed` передаёт уже перечень без
        исправленного (перечень перезаписан).

        Ловит мутацию: `--failed` через `--lf` кеша pytest — флаг в argv;
        гонится весь набор — в argv каталог `tests` вместо id; перечень не
        перезаписывается повтором — второй `--failed` снова несёт
        исправленный тест; повтор гонит базу — второй вызов вне рабочей
        копии.
        """
        self.release()
        target = self.add_project({self.word(): passing("x")})
        committed = {}
        failed = []
        for index in range(2 + self.rng.randrange(2)):
            name = self.word()
            failed.append(name)
            committed[name] = failing(name, EXCEPTIONS[index],
                                      f"сбой {self.word()}")
        gate = self.word()
        committed[gate] = gated(gate, self.release_file,
                                "raise EOFError('шлагбаум')")
        task_id, wt = self.add_task(target, committed=committed)
        self.launch(task_id, cwd=wt)
        self.report(task_id, cwd=wt)
        bases = len(self.base_calls())

        fixed = failed[0]
        self.write_files(wt, {fixed: passing(fixed)})
        self.hold()
        out = self.launch(task_id, "--failed", cwd=wt)
        call = self.wait_branch_call(wt, 2)
        self.assertFalse(self.release_file.exists())
        argv = call["argv"]
        ids = {a for a in argv if "::" in a}
        self.assertEqual(ids, {node_id(n) for n in failed + [gate]},
                         f"argv {argv}; {self.explain(out)}")
        self.assertNotIn("tests", argv, self.explain(out))
        self.assertNotIn("--lf", argv, self.explain(out))
        self.assertNotIn("--last-failed", argv, self.explain(out))
        self.assertIn(("-p", "no:cacheprovider"), list(zip(argv, argv[1:])),
                      self.explain(out))
        self.release()
        report = self.report(task_id, cwd=wt)
        self.assertNotIn(f"test_{fixed}", report, self.explain(report))
        self.assertIn(f"test_{gate}", report, self.explain(report))
        self.assertEqual(len(self.base_calls()), bases, self.explain(report))

        self.launch(task_id, "--failed", cwd=wt)
        call = self.wait_branch_call(wt, 3)
        self.report(task_id, cwd=wt)
        ids = {a for a in call["argv"] if "::" in a}
        self.assertEqual(ids, {node_id(n) for n in failed[1:] + [gate]},
                         f"перечень не перезаписан повтором; argv "
                         f"{call['argv']}; зерно: {self.seed}")

    def test_ac20_failed_without_previous_run_is_refused(self):
        """`--failed` без прошлого прогона — отказ с подсказкой.

        Сценарий: свежая задача, `suite-run <id> --failed`: ненулевой код,
        вывод называет `suite-run` и id задачи; ни обёртка профиля, ни
        pytest проекта не запускались.

        Ловит мутацию: без перечня `--failed` гонит весь набор (пустой
        список id) — обёртка вызвана; отказ кодом 0.
        """
        target = self.add_project({self.word(): passing("x")})
        task_id, wt = self.add_task(target)
        code, out, _ = self.cli("suite-run", task_id, "--failed", cwd=wt,
                                timeout=60)
        self.assertNotEqual(code, 0, self.explain(out))
        self.assertIn("suite-run", out, self.explain(out))
        self.assertIn(task_id, out, self.explain(out))
        time.sleep(3)
        self.assertEqual(self.calls(), [], self.explain(out))
        self.assertEqual(self.read_jsonl(self.pytest_file), [],
                         self.explain(out))


class LockTest(SuiteRunSandbox):

    def test_ac21_single_run_lock_refuses_and_releases(self):
        """Замок одного прогона: отказ занятым, свободен после конца и смерти.

        Сценарий: прогон задачи A держится шлагбаумом; запуск задачи B
        возвращается за секунды ненулевым кодом, вывод называет id A и pid
        фонового процесса A (родителя pytest), прогона B нет. После
        разрешения и конца A запуск B проходит. Затем новый прогон A
        держится шлагбаумом, его фоновый процесс и pytest убиты SIGKILL —
        замок остался с pid несуществующего процесса; запуск B проходит.

        Ловит мутацию: замка нет — B стартует параллельно; запуск ждёт
        освобождения замка — вызов не укладывается в 30 с; отказ без pid
        или id держателя; замок не снимается в `finally` либо живость pid
        не проверяется — B после конца A или после смерти держателя
        отказывает.
        """
        self.hold()
        gate = self.word()
        target = self.add_project({gate: gated(gate, self.release_file,
                                               "pass")})
        task_a, wt_a = self.add_task(target)
        task_b, wt_b = self.add_task(target)
        self.launch(task_a, cwd=wt_a)
        holder = self.wait_branch_call(wt_a)["ppid"]
        code, out, _ = self.cli("suite-run", task_b, cwd=wt_b, timeout=30)
        self.assertNotEqual(code, 0, self.explain(out))
        self.assertIn(task_a, out, self.explain(out))
        self.assertTrue(standalone(holder, out),
                        f"pid держателя {holder} не назван; {self.explain(out)}")
        time.sleep(2)
        self.assertEqual(self.branch_calls(wt_b), [], self.explain(out))

        self.release()
        self.wait_dead(holder)
        self.launch(task_b, cwd=wt_b)
        done_b = self.wait_branch_call(wt_b)["ppid"]
        self.wait_dead(done_b)

        self.hold()
        self.launch(task_a, cwd=wt_a)
        stale = self.wait_branch_call(wt_a, 2)
        for pid in (stale["ppid"], stale["pid"]):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.wait_dead(stale["ppid"], 20)
        self.release()
        out = self.launch(task_b, cwd=wt_b)
        self.wait_branch_call(wt_b, 2)


class FootprintTest(SuiteRunSandbox):
    TIMEOUT_SEC = 15
    WORKERS = 1

    def outside_state(self) -> dict:
        """Файлы корня пульта вне его каталога состояния: всё, кроме кода
        копии и `.artel/` (область проектов `.artel/projects` — включена),
        без внутренностей `.git`; файл — по сумме содержимого."""
        snapshot = {}
        skip = {self.root / "orchestrator", self.root / "scripts"}
        state = self.root / ".artel"
        projects = Path(config.PROJECTS)
        for path in self.root.rglob("*"):
            if any(path == s or s in path.parents for s in skip):
                continue
            if ".git" in path.relative_to(self.root).parts:
                continue
            if (state in path.parents or path == state) and not (
                    path == projects or projects in path.parents):
                continue
            rel = path.relative_to(self.root).as_posix()
            if path.is_file() and not path.is_symlink():
                snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                snapshot[rel] = "каталог"
        return snapshot

    def test_ac23_task_state_untouched_and_no_files_outside_state(self):
        """Состояние задачи и файлы вне каталога состояния не меняются.

        Сценарий: задача с незакоммиченной правкой; `suite-run <id>` и
        `--wait` до конца фонового прогона (с прогоном базы). Строка задачи
        в БД, её lease и журнал шагов до и после совпадают; набор файлов и
        их содержимое вне каталога состояния пульта (включая рабочую копию
        задачи и клон проекта) тот же; список рабочих копий клона прежний.

        Ловит мутацию: команда берёт lease или пишет запись журнала шагов о
        прогоне — строки БД расходятся; перечень упавших или итог базы
        пишутся в рабочую копию или клон — новый файл; временная копия базы
        не убрана или не снята с учёта клона — лишний каталог или запись
        `git worktree list`.
        """
        name = self.word()
        target = self.add_project({name: passing(name),
                                   self.word(): failing("y", "ValueError",
                                                        "сбой")})
        task_id, wt = self.add_task(target, uncommitted={
            name: failing(name, "ValueError", "правка")})

        def db_state():
            row = dict(store.get_task(self.conn, task_id))
            lease = store.lease_row(self.conn, task_id)
            steps = [dict(r) for r in store.task_steps(self.conn, task_id)]
            return row, dict(lease) if lease else None, steps

        worktrees = self.git("-C", str(self.clone(target)), "worktree", "list")
        before_db, before_files = db_state(), self.outside_state()
        self.launch(task_id, cwd=wt)
        holder = self.wait_branch_call(wt)["ppid"]
        out = self.report(task_id, cwd=wt)
        self.wait_dead(holder)
        self.assertEqual(db_state(), before_db, self.explain(out))
        after_files = self.outside_state()
        self.assertEqual(
            {k: v for k, v in after_files.items() if before_files.get(k) != v},
            {}, f"файлы вне каталога состояния; {self.explain(out)}")
        self.assertEqual(set(before_files) - set(after_files), set(),
                         self.explain(out))
        self.assertEqual(self.git("-C", str(self.clone(target)), "worktree",
                                  "list"), worktrees, self.explain(out))

    def test_ac24_base_copy_removed_on_every_outcome(self):
        """Временная копия базы убрана на любом исходе фонового прогона.

        Сценарий: четыре проекта со своими базами — база зелёная; база
        красная; база висит до разрешения дольше предела 15 с; прогон базы
        отдаёт байты не UTF-8 (исключение разбора вывода в фоновом
        процессе). Для каждого: после смерти фонового процесса каталога, где
        шёл прогон базы, нет, и клон не числит его рабочей копией.

        Ловит мутацию: уборка копии стоит после разбора исхода, а не в
        `finally`, — после таймаута или исключения каталог остаётся;
        каталог удаляется без `git worktree remove`/`prune` — клон числит
        его рабочей копией.
        """
        self.hold()
        outcomes = ("зелёная", "красная", "предел", "исключение")
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                block = "zz" + self.word()
                files = {self.word(): passing("ok")}
                if outcome == "красная":
                    files[self.word()] = failing("r", "ValueError", "сбой")
                if outcome == "предел":
                    files[block] = gated(block, self.release_file, "pass")
                target = self.add_project(files)
                committed = ({block: passing(block)} if outcome == "предел"
                             else None)
                task_id, wt = self.add_task(target, committed=committed)
                if outcome == "исключение":
                    self.garbage_file.write_text(os.path.realpath(wt),
                                                 encoding="utf-8")
                try:
                    known = len(self.base_calls())
                    self.launch(task_id, cwd=wt)
                    holder = self.wait_branch_call(wt)["ppid"]
                    self.wait_dead(holder)
                finally:
                    self.garbage_file.unlink(missing_ok=True)
                bases = self.base_calls()[known:]
                self.assertEqual(len(bases), 1, f"исход {outcome}; "
                                                f"зерно: {self.seed}")
                place = bases[0]["cwd"]
                self.assertFalse(os.path.exists(place),
                                 f"копия базы {place} осталась; исход "
                                 f"{outcome}; зерно: {self.seed}")
                listed = self.git("-C", str(self.clone(target)), "worktree",
                                  "list", "--porcelain")
                self.assertNotIn(place, listed, f"исход {outcome}; "
                                                f"зерно: {self.seed}")


class MissionTest(unittest.TestCase):

    def test_ac25_developer_mission_names_suite_run_with_pult_path(self):
        """Миссия разработчика называет `suite-run`, `--wait`, `--failed`.

        Сценарий: миссия роли developer собрана штатно
        (`role_prompt.mission_brief_package` с каталогом документов) для
        нескольких случайных id; компоненты брифа подменены пустыми. Текст
        содержит `python3 <config.ROOT>/orchestrator/artel.py suite-run <id>`
        — форму строки о `plank-run` — и формы `--wait` и `--failed`.

        Ловит мутацию: миссия называет команду без полного пути пульта
        (`artel.py suite-run`) — полного пути нет; формы `--wait`/`--failed`
        не названы.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        pult = config.ROOT / "orchestrator" / "artel.py"
        with mock.patch.object(brief, "developer_brief", return_value=""), \
                mock.patch.object(review, "review_package", return_value=""):
            for _ in range(3):
                task_id = "01M" + "".join(rng.choice(ALPHABET)
                                          for _ in range(23))
                t = {"branch": f"task/{task_id.lower()}-x", "title": "x",
                     "reviewed_iter": 0}
                docs = Path(f"/tmp/docs_{rng.randrange(1 << 30):x}") / task_id
                mission, _b, _p = role_prompt.mission_brief_package(
                    None, task_id, t, "developer", "/tmp/cwd", docs_dir=docs)
                self.assertIn(f"python3 {pult} suite-run {task_id}", mission,
                              f"зерно: {seed}\n{mission}")
                self.assertIn("--wait", mission, f"зерно: {seed}\n{mission}")
                self.assertIn("--failed", mission, f"зерно: {seed}\n{mission}")


if __name__ == "__main__":
    unittest.main()
