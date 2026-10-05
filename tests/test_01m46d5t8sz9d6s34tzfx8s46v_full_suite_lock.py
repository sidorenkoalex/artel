"""Один полный прогон tests/ на машину; исходы полного прогона на гейте мержа.

Группа: долгоживущий
Красен до реализации: замка полных прогонов нет — второй прогон гейта, прогон notes и прогон при идущем suite-run стартуют pytest параллельно, ожидание не журналится, в config нет FULL_SUITE_LOCK_WAIT_SEC (исхода «прогон не начат» нет), suite-run при прогоне гейта не отказывает (к написанию планки команды suite-run в коде нет вовсе — сценарии с ней красны и от этого), а гейт мержа на таймауте пишет «приложения ломают тесты»; зелёны с рождения test_ac7_dead_holder_does_not_delay_gate_run, test_ac8_* (без замка нечему задерживать следующий прогон) и test_ac10_red_run_refuses_as_before (красный отказ гейта мержа уже такой).

Валидация стабом: все методы зелёные на временном стабе — замок-файл с
pid и задачей держателя в `acceptance.run_full_suite`/`full_suite`
(ожидание с записью журнала, предел ожидания, мёртвый pid, снятие в
`finally`), тексты таймаута и «не начат» в `fsm_merge_gate` и минимальная
команда `suite-run` (отказ занятым, фоновый прогон под замком); снятие
`finally` у замка краснит test_ac8_lock_free_after_exception_in_run. Самой
команды `suite-run` (своя задача) в коде к написанию планки ещё нет:
форма её вызова взята из её долгоживущих тестов (`artel.py suite-run <id>`
из рабочей копии задачи, отказ занятым — ненулевой код и id держателя).

Прогон гейта пульта здесь — публичный узел, который зовут все гейты
(автогейт приёмки, approve в `acceptance`, гейт мержа):
`acceptance.full_suite(<дерево>, <id задачи>)`; прогон `notes` — тот узел,
который зовёт `notes`: `acceptance.run_full_suite(<дерево>)` без задачи.
Гейт мержа (AC-9..AC-11) — настоящий `fsm.cmd_approve` задачи артели на
`merge_gate` с приложением PLAN к защищённому пути под `tests/` или
`.github/` — такое приложение требует полного прогона (`tests/sandbox.py::
RealGitSandbox`, bare `origin`); подменены только внешние проверки (цвет CI
ветки и main, Draft MR форжа).

Замок — на машину, поэтому соперники — разные ПРОЦЕССЫ: держатель и
соперник запускаются отдельными интерпретаторами из КОПИИ кода пульта
(`orchestrator/`, `scripts/`) в корне песочницы — `config.ROOT` копии
считается от расположения её `config.py`, и её пути (БД, логи,
`targets.yaml`, область проектов) — те же, что подменены песочницей в
процессе теста (тот же приём, что у долгоживущих тестов `suite-run`).
В конец `config.py` копии дописаны параллель `1` и предел прогона
сценария; отдельный процесс может переопределить значения `config` на
себя (предел прогона, предел ожидания).

Каждое дерево прогона несёт `tests/conftest.py`, пишущий старт pytest
(`pytest_configure` главного процесса), и тест, пишущий свой старт и конец
в общий журнал наблюдения; тест «со шлагбаумом» ждёт файла-разрешения —
так прогон держится идущим, сколько нужно сценарию.
"""
import contextlib
import io
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          github_adapter, store, workspace)
from tests.sandbox import (ARTEL_TEST_PROFILE, RealGitSandbox, capture,
                           make_project_repo)

CODE_ROOT = Path(acceptance.__file__).resolve().parent.parent
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
NOT_STARTED = "прогон не начат"
MACHINE_BUSY = "машина занята"
BROKEN_BY_APPENDIX = "приложения ломают тесты"
FIX_APPENDIX = re.compile(r"почин\w*\s+приложени", re.IGNORECASE)

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

# Профиль тестов внешнего проекта задачи `suite-run` — та же форма, что у
# долгоживущих тестов самой команды.
PROJECT_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

CONFTEST = '''import json, os, time


def pytest_configure(config):
    if hasattr(config, "workerinput"):
        return
    with open({records!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"run": {label!r}, "event": "start",
                              "at": time.time(), "pid": os.getpid(),
                              "ppid": os.getppid()}}) + "\\n")
'''

PROBE_TEST = '''import json, os, time


def note(event):
    with open({records!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"run": {label!r}, "event": event,
                              "at": time.time(), "pid": os.getpid(),
                              "ppid": os.getppid()}}) + "\\n")


def test_{name}():
    note("test")
    deadline = time.time() + 100
    while not os.path.exists({release!r}) and time.time() < deadline:
        time.sleep(0.05)
    note("end")
    {tail}
'''

PASSING = "def test_{name}():\n    assert True\n"

# Отдельный процесс пульта: прогон гейта (`full_suite`) либо прогон без
# задачи (`run_full_suite`, как у `notes`). Итог — JSON в файл; `linger` —
# процесс остаётся жив после прогона до появления файла.
DRIVER = r'''
import json, os, sys, time
from pathlib import Path

root, spec_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
from orchestrator import acceptance, config
for name, value in spec["config"].items():
    setattr(config, name, value)
if spec["broken_python"]:
    sys.executable = "/nonexistent/artel-python3"
result = {"pid": os.getpid(), "called": time.time()}
try:
    if spec["kind"] == "gate":
        run = acceptance.full_suite(Path(spec["tree"]), spec["task"])
        result.update(green=bool(run.green), outcome=str(run.outcome),
                      text=f"{run.outcome}\n{run.detail}")
    else:
        green, output = acceptance.run_full_suite(Path(spec["tree"]))
        result.update(green=bool(green), outcome="", text=str(output)[-4000:])
except Exception as exc:
    result.update(green=False, outcome="", text="", error=repr(exc))
result["returned"] = time.time()
Path(spec["out"] + ".tmp").write_text(json.dumps(result), encoding="utf-8")
os.replace(spec["out"] + ".tmp", spec["out"])
while spec["linger"] and not os.path.exists(spec["linger"]):
    time.sleep(0.1)
'''


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Child:
    """Отдельный процесс пульта с прогоном: Popen, файл итога, вывод."""

    def __init__(self, proc, out: Path, log: Path, linger: Path, label: str):
        self.proc, self.out, self.log = proc, out, log
        self.linger, self.label = linger, label
        self.spawned = time.time()

    def output(self) -> str:
        try:
            return self.log.read_text(encoding="utf-8", errors="replace")[-3000:]
        except FileNotFoundError:
            return ""


class LockSandbox(RealGitSandbox):
    """Копия пульта в корне песочницы, деревья прогонов и журнал наблюдения."""

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.probe = Path(tempfile.mkdtemp(prefix="artel-lock-probe-")).resolve()
        self.records = self.probe / "records.jsonl"
        self.children: list[Child] = []
        self.addCleanup(self.stop_everything)

        for name in ("orchestrator", "scripts"):
            shutil.copytree(CODE_ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        with open(self.root / "orchestrator" / "config.py", "a",
                  encoding="utf-8") as fh:
            fh.write("\n\n# Песочница теста замка полных прогонов.\n"
                     "FULL_SUITE_WORKERS = '1'\n"
                     "FULL_SUITE_TIMEOUT_SEC = 300\n")
        # Копия пульта и её декларация проектов — не часть дерева
        # репозитория песочницы: `git status`/мерж их не видят.
        with open(self.root / ".git" / "info" / "exclude", "a",
                  encoding="utf-8") as fh:
            fh.write("/orchestrator/\n/scripts/\n/targets.yaml\n")
        for name, value in (("FULL_SUITE_WORKERS", "1"),
                            ("FULL_SUITE_TIMEOUT_SEC", 300)):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.entries = {config.DEFAULT_TARGET: TARGET_ENTRY.format(
            name=config.DEFAULT_TARGET, url="file:///nonexistent/artel",
            base=config.MAIN_BRANCH) + ARTEL_TEST_PROFILE}
        self.write_targets()
        self.conn = store.db()

    # --- фикстуры ---------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def word(self, size: int = 8) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ALPHABET) for _ in range(23))

    def add_task(self, state: str = "acceptance") -> str:
        task_id = self.task_id()
        store.insert_task(self.conn, task_id, "Фикстура замка прогонов", state,
                          f"task/{task_id.lower()}-lock",
                          config.DEFAULT_TARGET, 25.0)
        return task_id

    def write_targets(self) -> None:
        text = "targets:\n" + "".join(self.entries.values())
        for path in {Path(config.TARGETS), self.root / "targets.yaml"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def release_path(self, label: str) -> Path:
        return self.probe / f"release-{label}"

    def release(self, label: str) -> None:
        self.release_path(label).write_text("go", encoding="utf-8")

    def suite_files(self, label: str, tail: str = "pass",
                    gated: bool = False) -> dict:
        """Файлы `tests/` прогона `label`: conftest-наблюдатель, тест-пробник
        (со шлагбаумом либо без) и от нуля до трёх простых зелёных тестов."""
        if not gated:
            self.release(label)
        files = {
            "conftest.py": CONFTEST.format(records=str(self.records),
                                           label=label),
            f"test_{label}.py": PROBE_TEST.format(
                records=str(self.records), label=label, name=label,
                release=str(self.release_path(label)), tail=tail),
        }
        for _ in range(self.rng.randint(0, 3)):
            name = self.word()
            files[f"test_{name}.py"] = PASSING.format(name=name)
        return files

    def tree(self, label: str, tail: str = "pass", gated: bool = False) -> Path:
        """Дерево прогона вне репозитория песочницы с `tests/` от `suite_files`."""
        root = self.probe / f"tree-{label}"
        for rel, text in self.suite_files(label, tail, gated).items():
            path = root / "tests" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    # --- наблюдение -------------------------------------------------------

    def events(self, label: str, event: str) -> list:
        if not self.records.exists():
            return []
        found = []
        for line in self.records.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["run"] == label and rec["event"] == event:
                found.append(rec)
        return found

    def first_at(self, label: str, event: str) -> float:
        recs = self.events(label, event)
        self.assertTrue(recs, self.note(f"нет события {event} прогона {label}"))
        return min(r["at"] for r in recs)

    def wait_until(self, condition, what: str, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.1)
        self.fail(self.note(f"не дождались за {timeout} с: {what}"))

    def wait_event(self, label: str, event: str, timeout: float = 60) -> None:
        self.wait_until(lambda: bool(self.events(label, event)),
                        f"событие {event} прогона {label}", timeout)

    # --- отдельные процессы пульта ----------------------------------------

    def spawn(self, kind: str, tree: Path, task: str = None,
              overrides: dict = None, broken_python: bool = False,
              linger: bool = False) -> Child:
        """Отдельный процесс копии пульта с прогоном `kind` ("gate" —
        `full_suite(tree, task)`, "notes" — `run_full_suite(tree)`)."""
        label = tree.name
        out = self.probe / f"result-{label}-{len(self.children)}.json"
        log = self.probe / f"output-{label}-{len(self.children)}.txt"
        stay = self.probe / f"linger-{label}-{len(self.children)}"
        spec = self.probe / f"spec-{label}-{len(self.children)}.json"
        spec.write_text(json.dumps({
            "kind": kind, "tree": str(tree), "task": task, "out": str(out),
            "config": overrides or {}, "broken_python": broken_python,
            "linger": str(stay) if linger else ""}), encoding="utf-8")
        with open(log, "wb") as fh:
            proc = subprocess.Popen(
                [sys.executable, "-c", DRIVER, str(self.root), str(spec)],
                cwd=str(self.root), stdout=fh, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True)
        child = Child(proc, out, log, stay, label)
        self.children.append(child)
        return child

    def result(self, child: Child, timeout: float = 90) -> dict:
        self.wait_until(lambda: child.out.exists(),
                        f"итог прогона {child.label}; вывод процесса:\n"
                        f"{child.output()}", timeout)
        return json.loads(child.out.read_text(encoding="utf-8"))

    def describe(self, child: Child, result: dict) -> str:
        return self.note(f"итог прогона {child.label}: {result}\n"
                         f"вывод процесса:\n{child.output()}")

    @staticmethod
    def kill_group(pgid: int) -> None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def stop_everything(self) -> None:
        for path in self.probe.glob("tree-*"):
            self.release(path.name)
        for child in self.children:
            child.linger.write_text("go", encoding="utf-8")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and any(
                c.proc.poll() is None for c in self.children):
            time.sleep(0.1)
        for child in self.children:
            self.kill_group(child.proc.pid)
            with contextlib.suppress(Exception):
                child.proc.wait(timeout=5)
        pids = set()
        if self.records.exists():
            for line in self.records.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    pids.update((rec["pid"], rec["ppid"]))
        pids.discard(os.getpid())
        pids.discard(1)
        for pid in pids:
            if pid_alive(pid):
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.kill(pid, signal.SIGKILL)
        shutil.rmtree(self.probe, ignore_errors=True)

    # --- suite-run ----------------------------------------------------------

    def suite_task(self, gated: bool) -> tuple:
        """(id, рабочая копия, метка прогона) задачи внешнего проекта в
        `in_dev`, чей прогон `suite-run` наблюдается: база проекта — один
        зелёный тест, ветка задачи добавляет наблюдатель и пробник."""
        target = "p" + self.word()
        origin = config.PROJECTS / target / "origin.git"
        self.entries[target] = TARGET_ENTRY.format(
            name=target, url=f"file://{origin}",
            base=config.MAIN_BRANCH) + PROJECT_PROFILE
        self.write_targets()
        clone = make_project_repo(target)
        base_name = self.word()
        (clone / "tests").mkdir()
        (clone / "tests" / f"test_{base_name}.py").write_text(
            PASSING.format(name=base_name), encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "тесты проекта")
        self.git("-C", str(clone), "push", "-q", "origin", config.MAIN_BRANCH)

        task_id = self.task_id()
        branch = f"task/{task_id.lower()}-suite-run"
        store.insert_task(self.conn, task_id, "Фикстура suite-run", "in_dev",
                          branch, target, 25.0)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        wt = Path(wt).resolve()
        label = "s" + self.word()
        for rel, text in self.suite_files(label, gated=gated).items():
            (wt / "tests" / rel).write_text(text, encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", "правка ветки")
        return task_id, wt, label

    def suite_run(self, task_id: str, wt: Path, timeout: float = 60) -> tuple:
        """(код выхода, вывод, секунды) `artel.py suite-run <id>` копии пульта
        из рабочей копии задачи; группа процессов вызова добивается после
        возврата (фоновый прогон команды живёт своей сессией)."""
        started = time.monotonic()
        proc = subprocess.Popen(
            [sys.executable, str(self.root / "orchestrator" / "artel.py"),
             "suite-run", task_id], cwd=str(wt),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            raw, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill_group(proc.pid)
            proc.communicate()
            self.fail(self.note(f"suite-run {task_id} не вернулся за "
                                f"{timeout} с"))
        finally:
            self.kill_group(proc.pid)
        return (proc.returncode, raw.decode("utf-8", errors="replace"),
                time.monotonic() - started)

    def assert_waited_for(self, first: str, second: str) -> None:
        """pytest прогона `second` стартовал не раньше конца теста `first`."""
        end_first = self.first_at(first, "end")
        start_second = self.first_at(second, "start")
        self.assertGreaterEqual(start_second, end_first, self.note(
            f"pytest прогона {second} стартовал в {start_second:.2f}, "
            f"раньше конца прогона {first} ({end_first:.2f}) — шли "
            f"параллельно"))

    def hold_then_contend(self, holder: Child, holder_label: str,
                          contender_label: str) -> None:
        """Держатель идёт (его тест стартовал); соперник за несколько секунд
        не стартовал pytest."""
        time.sleep(self.rng.uniform(2.0, 3.5))
        self.assertEqual(self.events(contender_label, "start"), [], self.note(
            f"pytest прогона {contender_label} стартовал, пока прогон "
            f"{holder_label} шёл; вывод держателя:\n{holder.output()}"))


class GateRunsQueueTest(LockSandbox):

    def test_ac1_gate_runs_of_two_tasks_go_one_after_another(self):
        """Два прогона гейта разных задач, запущенные вместе, идут по очереди.

        Сценарий: прогон гейта задачи A держится шлагбаумом (его тест уже
        идёт); тогда же стартует прогон гейта задачи B. Пока A держится,
        pytest прогона B не стартовал; после разрешения A прогон B
        завершается зелёным, а старт его pytest — не раньше конца теста A.
        Порядок запуска двух процессов и состав их наборов — от зерна.

        Ловит мутацию: замка нет (или он на задачу, а не на машину) — pytest
        прогона B стартует сразу, параллельно идущему A; замок отказывает
        вместо ожидания — B возвращается не зелёным, без прогона.
        """
        task_a, task_b = self.add_task(), self.add_task()
        label_a, label_b = "a" + self.word(), "b" + self.word()
        holder = self.spawn("gate", self.tree(label_a, gated=True), task_a)
        self.wait_event(label_a, "test")
        contender = self.spawn("gate", self.tree(label_b), task_b)
        self.hold_then_contend(holder, label_a, label_b)

        self.release(label_a)
        res_b = self.result(contender)
        res_a = self.result(holder)
        self.assertTrue(res_a["green"], self.describe(holder, res_a))
        self.assertTrue(res_b["green"], self.describe(contender, res_b))
        self.assert_waited_for(label_a, label_b)


class SuiteRunAndNotesWaitTest(LockSandbox):

    def test_ac2_gate_run_waits_for_suite_run(self):
        """Прогон гейта, начатый при идущем `suite-run`, ждёт его конца.

        Сценарий: `suite-run` задачи S запущен, его прогон держится
        шлагбаумом (тест уже идёт); стартует прогон гейта задачи B. Пока S
        держится, pytest прогона B не стартовал; после разрешения S прогон B
        зелёный, и его pytest стартовал не раньше конца теста S.

        Ловит мутацию: замок `suite-run` остался отдельным от замка гейтов
        (правило «один прогон на машину» в двух местах) — прогон гейта не
        видит идущий `suite-run` и стартует параллельно.
        """
        task_s, wt, label_s = self.suite_task(gated=True)
        code, out, _ = self.suite_run(task_s, wt)
        self.wait_event(label_s, "test")
        task_b = self.add_task()
        label_b = "b" + self.word()
        contender = self.spawn("gate", self.tree(label_b), task_b)
        time.sleep(self.rng.uniform(2.0, 3.5))
        self.assertEqual(self.events(label_b, "start"), [], self.note(
            f"pytest гейта стартовал при идущем suite-run; вывод suite-run "
            f"(код {code}):\n{out}"))

        self.release(label_s)
        res_b = self.result(contender)
        self.assertTrue(res_b["green"], self.describe(contender, res_b))
        self.assert_waited_for(label_s, label_b)

    def test_ac2_notes_run_waits_for_busy_lock(self):
        """Прогон `notes` (без задачи) при занятом замке ждёт, а не идёт рядом.

        Сценарий: прогон гейта задачи A держится шлагбаумом; стартует прогон
        набора тем узлом, которым его зовёт `notes`
        (`acceptance.run_full_suite` без задачи). Пока A держится, pytest
        прогона `notes` не стартовал; после разрешения A он зелёный, и
        стартовал не раньше конца теста A.

        Ловит мутацию: замок взят только в `full_suite` (узле гейтов с
        задачей), а `run_full_suite`, которым зовёт `notes`, идёт мимо него —
        прогон `notes` стартует параллельно A.
        """
        task_a = self.add_task()
        label_a, label_n = "a" + self.word(), "n" + self.word()
        holder = self.spawn("gate", self.tree(label_a, gated=True), task_a)
        self.wait_event(label_a, "test")
        contender = self.spawn("notes", self.tree(label_n))
        self.hold_then_contend(holder, label_a, label_n)

        self.release(label_a)
        res_n = self.result(contender)
        self.assertTrue(res_n["green"], self.describe(contender, res_n))
        self.assert_waited_for(label_a, label_n)


class SuiteRunRefusesTest(LockSandbox):

    def test_ac3_suite_run_refuses_at_once_while_gate_run_holds(self):
        """`suite-run` при идущем прогоне гейта сразу отказывает с держателем.

        Сценарий: прогон гейта задачи A держится шлагбаумом; `suite-run`
        задачи S возвращается за секунды ненулевым кодом, и вывод называет
        id задачи A; прогона S нет ни сразу, ни после разрешения и конца
        прогона A (отказ не превращается в отложенный прогон).

        Ловит мутацию: замок `suite-run` отдельный от замка гейтов — `suite-run`
        запускает прогон параллельно (код 0, pytest S стартует); `suite-run`
        ждёт замок, как гейт, — вызов не возвращается за 30 с; отказ без
        держателя — id A в выводе нет.
        """
        task_a = self.add_task()
        label_a = "a" + self.word()
        holder = self.spawn("gate", self.tree(label_a, gated=True), task_a)
        self.wait_event(label_a, "test")
        task_s, wt, label_s = self.suite_task(gated=False)

        code, out, _ = self.suite_run(task_s, wt, timeout=30)
        self.assertNotEqual(code, 0, self.note(f"suite-run не отказал:\n{out}"))
        self.assertIn(task_a, out, self.note(
            f"отказ suite-run не называет держателя {task_a}:\n{out}"))
        time.sleep(2)
        self.assertEqual(self.events(label_s, "start"), [], self.note(out))

        self.release(label_a)
        self.result(holder)
        time.sleep(2)
        self.assertEqual(self.events(label_s, "start"), [], self.note(
            f"прогон suite-run пошёл после отказа:\n{out}"))


class WaitJournalTest(LockSandbox):

    def test_ac4_waiting_gate_run_journals_the_holder_task(self):
        """Ожидание замка прогоном гейта — запись журнала задачи с держателем.

        Сценарий: прогон гейта задачи A держится шлагбаумом; прогон гейта
        задачи B ждёт замок; после разрешения A и конца B журнал задачи B
        несёт запись, называющую id задачи A, чей прогон шёл.

        Ловит мутацию: ожидание не журналится вовсе либо запись пишется без
        держателя (только «замок занят») — id A в журнале B нет.
        """
        task_a, task_b = self.add_task(), self.add_task()
        label_a, label_b = "a" + self.word(), "b" + self.word()
        holder = self.spawn("gate", self.tree(label_a, gated=True), task_a)
        self.wait_event(label_a, "test")
        contender = self.spawn("gate", self.tree(label_b), task_b)
        self.hold_then_contend(holder, label_a, label_b)
        self.release(label_a)
        res_b = self.result(contender)

        rows = store.task_steps(store.db(), task_b)
        journal = [f"{r['action']} | {r['detail'] or ''}" for r in rows]
        self.assertTrue([e for e in journal if task_a in e], self.note(
            f"в журнале {task_b} нет записи о держателе {task_a}:\n"
            + "\n".join(journal) + f"\n{self.describe(contender, res_b)}"))


class RunLimitTest(LockSandbox):

    def test_ac5_wait_longer_than_run_limit_keeps_full_run_limit(self):
        """Ожидание дольше предела прогона не съедает предел самого прогона.

        Сценарий: предел прогона соперника `config.FULL_SUITE_TIMEOUT_SEC` —
        T секунд (от зерна), его набор идёт около секунды. Держатель — прогон
        гейта задачи A со своим большим пределом — держится шлагбаумом, пока
        соперник (гейт задачи B) не прождёт дольше T; затем разрешён. Старт
        pytest соперника — позже его запуска больше чем на T, а его исход —
        зелёный прогон (`acceptance.FULL_SUITE_GREEN`), не таймаут.

        Ловит мутацию: предел прогона отсчитывается от начала ожидания
        (общий срок на ожидание и прогон, `timeout=` от остатка) — после
        ожидания дольше T у прогона не остаётся времени, исход «таймаут
        прогона».
        """
        limit = self.rng.randint(6, 9)
        task_a, task_b = self.add_task(), self.add_task()
        label_a, label_b = "a" + self.word(), "b" + self.word()
        holder = self.spawn("gate", self.tree(label_a, gated=True), task_a,
                            overrides={"FULL_SUITE_TIMEOUT_SEC": 120})
        self.wait_event(label_a, "test")
        contender = self.spawn(
            "gate", self.tree(label_b, tail="time.sleep(0.5)"), task_b,
            overrides={"FULL_SUITE_TIMEOUT_SEC": limit})
        time.sleep(limit + self.rng.uniform(1.5, 2.5))
        self.assertEqual(self.events(label_b, "start"), [], self.note(
            "соперник стартовал pytest, не дождавшись держателя"))
        self.release(label_a)
        res_b = self.result(contender)

        self.assertGreater(self.first_at(label_b, "start") - contender.spawned,
                           limit, self.describe(contender, res_b))
        self.assertTrue(res_b["green"], self.describe(contender, res_b))
        self.assertEqual(res_b["outcome"], acceptance.FULL_SUITE_GREEN,
                         self.describe(contender, res_b))


class WaitLimitTest(LockSandbox):

    def test_ac6_config_declares_lock_wait_limit(self):
        """В `orchestrator/config.py` предел ожидания замка — 1800 с.

        Ловит мутацию: константы нет либо значение другое (например, предел
        ожидания приравнен к `FULL_SUITE_TIMEOUT_SEC`).
        """
        self.assertEqual(getattr(config, "FULL_SUITE_LOCK_WAIT_SEC", None),
                         1800)

    def test_ac6_wait_over_limit_is_not_started_without_pytest(self):
        """Ожидание сверх предела — исход «прогон не начат», pytest не идёт.

        Сценарий: прогон гейта задачи A держится шлагбаумом всё время
        сценария; прогон гейта задачи B с пределом ожидания
        `FULL_SUITE_LOCK_WAIT_SEC` в несколько секунд (от зерна) возвращается,
        пока A ещё держится: не зелёный, исход — не красный прогон
        (`acceptance.FULL_SUITE_RED`) и не таймаут прогона, текст исхода
        несёт «прогон не начат», «машина занята» и id задачи A; pytest
        прогона B не стартовал.

        Ловит мутацию: по истечении ожидания прогон всё равно запускается
        (pytest B стартует); исход «не начат» сведён к красному прогону или
        к таймауту; текст не называет держателя.
        """
        wait = self.rng.randint(2, 4)
        task_a, task_b = self.add_task(), self.add_task()
        label_a, label_b = "a" + self.word(), "b" + self.word()
        self.spawn("gate", self.tree(label_a, gated=True), task_a)
        self.wait_event(label_a, "test")
        contender = self.spawn("gate", self.tree(label_b), task_b,
                               overrides={"FULL_SUITE_LOCK_WAIT_SEC": wait})
        res_b = self.result(contender, timeout=wait + 40)

        context = self.describe(contender, res_b)
        self.assertFalse(res_b["green"], context)
        self.assertNotIn(res_b["outcome"], (acceptance.FULL_SUITE_RED,
                                            acceptance.FULL_SUITE_TIMEOUT),
                         context)
        self.assertIn(NOT_STARTED, res_b["text"], context)
        self.assertIn(MACHINE_BUSY, res_b["text"], context)
        self.assertIn(task_a, res_b["text"], context)
        self.assertEqual(self.events(label_b, "start"), [], context)


class DeadHolderTest(LockSandbox):

    def dead_holder(self) -> str:
        """Прогон гейта задачи A держится шлагбаумом и убит SIGKILL вместе с
        pytest: замок остался за процессом, которого больше нет."""
        task_a = self.add_task()
        label_a = "a" + self.word()
        holder = self.spawn("gate", self.tree(label_a, gated=True), task_a)
        self.wait_event(label_a, "test")
        self.kill_group(holder.proc.pid)
        holder.proc.wait(timeout=20)
        for rec in self.events(label_a, "test") + self.events(label_a, "start"):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(rec["pid"], signal.SIGKILL)
        return task_a

    def test_ac7_dead_holder_does_not_delay_gate_run(self):
        """Замок мёртвого процесса не задерживает прогон гейта.

        Сценарий: держатель — прогон гейта задачи A — убит SIGKILL посреди
        прогона; прогон гейта задачи B с пределом ожидания в две минуты
        стартует pytest за считанные секунды и зелёный.

        Ловит мутацию: живость pid держателя не проверяется (замок считается
        занятым, пока запись есть) — B ждёт до предела ожидания и не
        стартует за 20 с.
        """
        self.dead_holder()
        task_b = self.add_task()
        label_b = "b" + self.word()
        contender = self.spawn("gate", self.tree(label_b), task_b,
                               overrides={"FULL_SUITE_LOCK_WAIT_SEC": 120})
        self.wait_event(label_b, "start", timeout=20)
        res_b = self.result(contender)
        self.assertTrue(res_b["green"], self.describe(contender, res_b))

    def test_ac7_dead_holder_does_not_refuse_suite_run(self):
        """Замок мёртвого процесса не даёт отказа `suite-run`.

        Сценарий: держатель — прогон гейта задачи A — убит SIGKILL посреди
        прогона; `suite-run` задачи S не называет A в выводе, и pytest её
        прогона стартует.

        Ловит мутацию: живость pid держателя не проверяется — `suite-run`
        отказывает «занято прогоном A», прогона S нет.
        """
        task_a = self.dead_holder()
        task_s, wt, label_s = self.suite_task(gated=False)
        code, out, _ = self.suite_run(task_s, wt, timeout=60)
        self.assertNotIn(task_a, out, self.note(
            f"suite-run сослался на мёртвого держателя (код {code}):\n{out}"))
        self.wait_event(label_s, "start", timeout=60)


class ReleaseOnEveryOutcomeTest(LockSandbox):

    def check_released_after(self, kind: str) -> None:
        """Прогон гейта задачи A с исходом `kind` закончился, а его процесс
        остаётся жив; следующий прогон гейта (задача B, предел ожидания две
        минуты) стартует pytest за считанные секунды и зелёный."""
        task_a, task_b = self.add_task(), self.add_task()
        label_a, label_b = "a" + self.word(), "b" + self.word()
        overrides, broken = {}, False
        if kind == "green":
            tree = self.tree(label_a)
        elif kind == "red":
            tree = self.tree(label_a, tail=f"assert False, {self.word()!r}")
        elif kind == "timeout":
            tree = self.tree(label_a, gated=True)
            overrides["FULL_SUITE_TIMEOUT_SEC"] = self.rng.randint(3, 5)
        else:
            tree, broken = self.tree(label_a), True
        holder = self.spawn("gate", tree, task_a, overrides=overrides,
                            broken_python=broken, linger=True)
        res_a = self.result(holder)
        context = self.describe(holder, res_a)
        self.assertEqual(res_a["green"], kind == "green", context)
        if kind == "timeout":
            self.assertEqual(res_a["outcome"], acceptance.FULL_SUITE_TIMEOUT,
                             context)
        if kind == "red":
            self.assertEqual(res_a["outcome"], acceptance.FULL_SUITE_RED,
                             context)

        contender = self.spawn("gate", self.tree(label_b), task_b,
                               overrides={"FULL_SUITE_LOCK_WAIT_SEC": 120})
        self.wait_event(label_b, "start", timeout=20)
        self.assertTrue(pid_alive(holder.proc.pid), context)
        res_b = self.result(contender)
        self.assertTrue(res_b["green"], self.describe(contender, res_b))

    def test_ac8_lock_free_after_green_run(self):
        """После зелёного прогона замок свободен: следующий идёт без ожидания.

        Ловит мутацию: замок снимается только на не зелёном исходе (снятие в
        ветке отказа, а не в `finally`) — следующий прогон ждёт живого
        держателя и не стартует за 20 с.
        """
        self.check_released_after("green")

    def test_ac8_lock_free_after_red_run(self):
        """После красного прогона замок свободен: следующий идёт без ожидания.

        Ловит мутацию: замок снимается только на зелёном исходе — следующий
        прогон ждёт живого держателя и не стартует за 20 с.
        """
        self.check_released_after("red")

    def test_ac8_lock_free_after_timed_out_run(self):
        """После таймаута прогона замок свободен: следующий идёт без ожидания.

        Ловит мутацию: ветка `TimeoutExpired` возвращает исход раньше снятия
        замка — следующий прогон ждёт живого держателя и не стартует за 20 с.
        """
        self.check_released_after("timeout")

    def test_ac8_lock_free_after_exception_in_run(self):
        """После исключения в ходе прогона замок свободен.

        Сценарий: интерпретатор прогона недоступен — запуск pytest бросает
        исключение внутри взятого замка.

        Ловит мутацию: снятие замка не в `finally` — исключение уносит его, и
        следующий прогон ждёт живого держателя, не стартуя за 20 с.
        """
        self.check_released_after("exception")


# --- гейт мержа -------------------------------------------------------------

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
zones: feature.txt
---

# SPEC: фикстура

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

APPENDIX_BASE = "".join(f"# строка {n:02d}\n" for n in range(1, 21))

# Место приложения — защищённый путь (приложение PLAN бывает только к ним)
# под `tests/` либо `.github/`: правка там требует полного прогона на гейте
# мержа. От `config.PROTECTED_PATHS`, не литералом: перечень меняет
# Оператор; каталог — файл в нём.
APPENDIX_HOMES = [p for p in config.PROTECTED_PATHS
                  if "*" not in p and p.startswith(("tests/", ".github/"))]


class MergeGateSandbox(LockSandbox):
    """Задача артели на `merge_gate`: ветка с кодом задачи, PLAN.md с
    приложением к защищённому пути под `tests/` или `.github/` в ссылке
    документов; полный прогон после приложений — настоящий pytest по
    `tests/` дерева мержа."""

    def setUp(self):
        super().setUp()
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.object(ci, "branch_status",
                                  lambda branch, repo=None:
                                  (True, "зелёный (тест)")),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def prepare(self, tail: str, gated: bool = False) -> str:
        """Набор `tests/` в main (наблюдатель, пробник с хвостом `tail`,
        файл под приложение), задача на `merge_gate` с приложением PLAN к
        `tests/`. Возвращает метку прогона набора."""
        label = "m" + self.word()
        self.assertTrue(APPENDIX_HOMES, self.note(
            "в config.PROTECTED_PATHS нет пути под tests/ или .github/"))
        home = self.rng.choice(APPENDIX_HOMES)
        appendix_rel = (f"{home}appendix-{self.word()}.txt"
                        if home.endswith("/") else home)
        for rel, text in self.suite_files(label, tail, gated).items():
            path = self.root / "tests" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (self.root / appendix_rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / appendix_rel).write_text(APPENDIX_BASE, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "набор tests/")
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)

        self.task = self.task_id()
        self.branch = f"task/{self.task.lower()}-x"
        self.checkout(self.branch, create=True)
        (self.root / "feature.txt").write_text("код задачи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.task}: код задачи")
        self.checkout(config.MAIN_BRANCH)

        line = self.rng.choice(APPENDIX_BASE.splitlines())
        path = self.root / appendix_rel
        path.write_text(APPENDIX_BASE.replace(
            line, f"{line} — правка {self.rng.randrange(10**6)}"),
            encoding="utf-8")
        diff = self.git("diff", "--", appendix_rel)
        self.git("checkout", "-q", "--", appendix_rel)
        store.insert_task(store.db(), self.task, f"Задача {self.task}",
                          "merge_gate", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.write_plan(diff)
        self.main_before = self.origin_main_sha()
        return label

    def write_plan(self, diff: str) -> None:
        text = (f"---\ntask: {self.task}\ntype: plan\n"
                f"author_role: developer\nstatus: ready\n"
                f"schema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
                f"Фикстура.\n\n## Приложение 1: правка теста\n\n"
                f"```diff\n{diff}```\n")
        docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=self.task),
                                      encoding="utf-8")
        (docs / "PLAN.md").write_text(text, encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, store.db(), self.task,
                "developer")

    def approve(self) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_approve(self.task)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def state(self) -> str:
        return store.get_task(store.db(), self.task)["state"]

    def origin_main_sha(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse",
                        "refs/heads/" + config.MAIN_BRANCH).strip()

    def assert_stays_on_gate(self, out: str) -> None:
        context = self.note(f"вывод approve:\n{out}")
        self.assertEqual(self.state(), "merge_gate", context)
        self.assertEqual(self.origin_main_sha(), self.main_before, context)

    def assert_not_blamed_on_appendix(self, out: str) -> None:
        context = self.note(f"вывод approve:\n{out}")
        self.assertNotIn(BROKEN_BY_APPENDIX, out, context)
        self.assertIsNone(FIX_APPENDIX.search(out), context)


class MergeGateOutcomesTest(MergeGateSandbox):

    def test_ac9_timeout_is_refused_as_timeout_not_as_broken_appendix(self):
        """Таймаут прогона после приложений — отказ «не уложился», не поломка.

        Сценарий: предел `config.FULL_SUITE_TIMEOUT_SEC` — N секунд (от
        зерна), тест набора держится шлагбаумом дольше. `approve` на
        `merge_gate` отказывает текстом «прогон не уложился в N с» с путём к
        существующему файлу лога прогона; в тексте нет «приложения ломают
        тесты» и указания починить приложение; задача на `merge_gate`,
        `origin/main` не сдвинут.

        Ловит мутацию: гейт печатает один отказ «приложения ломают тесты …
        почини приложение» на любом не зелёном исходе (сегодняшний текст) —
        фразы «не уложился» нет, слова о поломке есть; отказ без пути к логу.
        """
        limit = self.rng.randint(3, 6)
        patcher = mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", limit)
        patcher.start()
        self.addCleanup(patcher.stop)
        label = self.prepare("pass", gated=True)

        out = self.approve()

        self.assertTrue(self.events(label, "start"), self.note(
            f"прогон после приложений не запускался:\n{out}"))
        self.assertIn(f"прогон не уложился в {limit} с", out,
                      self.note(f"вывод approve:\n{out}"))
        logs = [Path(p.rstrip(".,:;)»")) for p in
                re.findall(r"/[^\s'\"«(),;`]+", out)]
        logs = [p for p in logs if p.is_file()
                and Path(config.LOGS) in p.resolve().parents]
        self.assertTrue(logs, self.note(f"нет пути к логу прогона:\n{out}"))
        self.assert_not_blamed_on_appendix(out)
        self.assert_stays_on_gate(out)

    def test_ac10_red_run_refuses_as_before(self):
        """Красный прогон после приложений — отказ «приложения ломают тесты:».

        Сценарий: тест набора в дереве мержа падает (сообщение от зерна);
        `approve` на `merge_gate` отказывает текстом с «приложения ломают
        тесты:», задача остаётся на `merge_gate`.

        Ловит мутацию: различение исходов сводит красный прогон к таймауту
        или к «прогон не начат» (условие по исходу перепутано) — текста
        «приложения ломают тесты:» в отказе нет.
        """
        label = self.prepare(f"assert False, {self.word()!r}")

        out = self.approve()

        self.assertTrue(self.events(label, "start"), self.note(out))
        self.assertIn(f"{BROKEN_BY_APPENDIX}:", out,
                      self.note(f"вывод approve:\n{out}"))
        self.assertEqual(self.state(), "merge_gate", self.note(out))

    def test_ac11_not_started_is_refused_with_holder(self):
        """Исход «прогон не начат» на гейте мержа — свой отказ с держателем.

        Сценарий: прогон гейта задачи H (отдельный процесс пульта) держится
        шлагбаумом всё время сценария; предел ожидания замка
        `config.FULL_SUITE_LOCK_WAIT_SEC` — несколько секунд (от зерна).
        `approve` на `merge_gate` отказывает текстом с id задачи H, без
        «приложения ломают тесты», без указания починить приложение и без
        «не уложился»; pytest дерева мержа не стартовал; задача на
        `merge_gate`, `origin/main` не сдвинут.

        Ловит мутацию: исход «не начат» уходит в общую ветку отказа гейта —
        «приложения ломают тесты … почини приложение»; либо в ветку
        таймаута — «не уложился»; отказ не называет держателя.
        """
        wait = self.rng.randint(2, 4)
        patcher = mock.patch.object(config, "FULL_SUITE_LOCK_WAIT_SEC", wait)
        patcher.start()
        self.addCleanup(patcher.stop)
        holder_task = self.add_task()
        holder_label = "h" + self.word()
        self.spawn("gate", self.tree(holder_label, gated=True), holder_task)
        self.wait_event(holder_label, "test")
        label = self.prepare("pass")

        out = self.approve()

        context = self.note(f"вывод approve:\n{out}")
        self.assertIn(holder_task, out, context)
        self.assertNotIn("не уложился", out, context)
        self.assertEqual(self.events(label, "start"), [], context)
        self.assert_not_blamed_on_appendix(out)
        self.assert_stays_on_gate(out)


if __name__ == "__main__":
    unittest.main()
