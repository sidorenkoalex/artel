"""Действующий предел полного прогона tests/ на гейте мержа и в `suite-run`.

Группа: долгоживущий
Красен до реализации: подполя full_suite_timeout_sec в профиле тестов нет — запись с ним отклоняется «неизвестное подполе», гейт мержа отказывает по профилю без прогона, а suite-run — «профиль не прочитан» (AC-3, AC-5, AC-6, AC-7); текст таймаута на гейте мержа без подполя не называет источник «config» (AC-6); зелёны с рождения test_ac4_* (предел config читается в момент прогона уже сегодня).

Гейт пульта здесь — настоящий `fsm.cmd_approve` задачи артели на
`merge_gate` с приложением PLAN к защищённому пути под `tests/` или
`.github/` (такое приложение требует полного прогона после приложений), на
`tests/sandbox.py::RealGitSandbox` с bare `origin`; подменены только
внешние проверки (цвет CI ветки и main, Draft MR форжа). Набор `tests/`
дерева мержа — один тест-пробник: пишет свой старт и конец в журнал
наблюдения и держится заданное время (или до файла-стопа уборки).

`suite-run` — настоящая команда копии пульта (`orchestrator/`, `scripts/`
в корне песочницы; `config.ROOT` копии считается от её `config.py`, и её
пути — те же, что подменены песочницей) для задачи внешнего проекта с
клоном и bare `origin` (`tests/sandbox.py::make_project_repo`); в конец
`config.py` копии дописаны параллель 1 и предел прогона сценария.

Пределы, имена и времена держания — от зерна; зерно печатается и входит
в текст провала.
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
from tests.sandbox import RealGitSandbox, capture, make_project_repo

CODE_ROOT = Path(acceptance.__file__).resolve().parent.parent
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
PROFILE_HEAD = "    test_profile:\n"

PROBE_TEST = '''import json, os, time


def note(event):
    with open({records!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"event": event, "at": time.time(),
                              "pid": os.getpid(),
                              "ppid": os.getppid()}}) + "\\n")


def test_{name}():
    note("start")
    deadline = time.time() + {hold}
    while time.time() < deadline and not os.path.exists({stop!r}):
        time.sleep(0.05)
    note("end")
'''

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

# Место приложения — защищённый путь под `tests/` либо `.github/`: правка
# там требует полного прогона на гейте мержа. От `config.PROTECTED_PATHS`,
# не литералом: перечень меняет Оператор.
APPENDIX_HOMES = [p for p in config.PROTECTED_PATHS
                  if "*" not in p and p.startswith(("tests/", ".github/"))]

PROJECT_ENTRY = """  {name}:
    forge: github
    url: file://{origin}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      full_suite_timeout_sec: {limit}
      command: [{python}, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""


def standalone(number: int, text: str) -> bool:
    return re.search(rf"(?<![\d.:]){number}(?![\d.:])", text) is not None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class ProbeSandbox(RealGitSandbox):
    """Зерно, журнал наблюдения пробника и уборка его процессов."""

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
        self.probe = Path(tempfile.mkdtemp(prefix="artel-limit-probe-")).resolve()
        self.records = self.probe / "records.jsonl"
        self.stop_file = self.probe / "stop"
        self.addCleanup(self.stop_everything)

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def word(self, size: int = 8) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ALPHABET) for _ in range(23))

    def probe_test(self, hold: float) -> tuple:
        """(имя файла, текст) теста-пробника, держащегося `hold` секунд."""
        name = "probe" + self.word()
        return f"test_{name}.py", PROBE_TEST.format(
            records=str(self.records), name=name, hold=hold,
            stop=str(self.stop_file))

    def events(self, event: str) -> list:
        if not self.records.exists():
            return []
        return [rec for rec in (json.loads(line) for line in
                                self.records.read_text(
                                    encoding="utf-8").splitlines()
                                if line.strip())
                if rec["event"] == event]

    def stop_everything(self) -> None:
        self.stop_file.write_text("stop", encoding="utf-8")
        pids = {pid for rec in self.events("start")
                for pid in (rec["pid"], rec["ppid"])}
        pids -= {os.getpid(), 1}
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and any(pid_alive(p) for p in pids):
            time.sleep(0.1)
        for pid in pids:
            if pid_alive(pid):
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.kill(pid, signal.SIGKILL)
        shutil.rmtree(self.probe, ignore_errors=True)


# --- гейт мержа ---------------------------------------------------------------

class MergeGateLimitSandbox(ProbeSandbox):
    """Задача артели на `merge_gate` с приложением к защищённому пути под
    `tests/` или `.github/`; полный прогон после приложений — настоящий
    pytest по `tests/` дерева мержа."""

    def setUp(self):
        super().setUp()
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.object(config, "FULL_SUITE_WORKERS", "1"),
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

    def set_config_limit(self, seconds: int) -> None:
        patcher = mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", seconds)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_profile_limit(self, seconds: int | None) -> str:
        """Подполе `full_suite_timeout_sec` в профиле артели (`None` — без
        подполя); возвращает текст `targets.yaml`."""
        path = Path(config.TARGETS)
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"^\s+full_suite_timeout_sec:.*\n", "", text,
                      flags=re.MULTILINE)
        if seconds is not None:
            self.assertEqual(text.count(PROFILE_HEAD), 1, self.note(
                f"в targets.yaml песочницы не один профиль:\n{text}"))
            text = text.replace(PROFILE_HEAD, f"{PROFILE_HEAD}      "
                                f"full_suite_timeout_sec: {seconds}\n")
        path.write_text(text, encoding="utf-8")
        return text

    def prepare(self, hold: float, profile_limit: int | None) -> None:
        """Набор `tests/` в main (пробник, держащийся `hold` секунд, и файл
        под приложение), задача на `merge_gate` с приложением PLAN к нему;
        предел профиля артели — `profile_limit`."""
        self.assertTrue(APPENDIX_HOMES, self.note(
            "в config.PROTECTED_PATHS нет пути под tests/ или .github/"))
        home = self.rng.choice(APPENDIX_HOMES)
        appendix_rel = (f"{home}appendix-{self.word()}.txt"
                        if home.endswith("/") else home)
        name, text = self.probe_test(hold)
        (self.root / "tests").mkdir(parents=True, exist_ok=True)
        (self.root / "tests" / name).write_text(text, encoding="utf-8")
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
        self.targets_text = self.set_profile_limit(profile_limit)

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

    def approve(self) -> tuple:
        """(вывод `approve`, секунды)."""
        buf = io.StringIO()
        started = time.monotonic()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_approve(self.task)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), time.monotonic() - started

    def journal(self) -> str:
        rows = store.task_steps(store.db(), self.task)
        return "\n".join(f"{r['action']} | {r['detail'] or ''}" for r in rows)

    def context(self, out: str) -> str:
        return self.note(f"вывод approve:\n{out[-4000:]}\nжурнал задачи:\n"
                         f"{self.journal()[-4000:]}\ntargets.yaml:\n"
                         f"{self.targets_text}")

    @staticmethod
    def timeout_lines(text: str) -> list:
        """Строки текста об исходе таймаута прогона."""
        return [line for line in text.splitlines()
                if "не уложился" in line or "превысил" in line]

    def artel_source(self) -> re.Pattern:
        return re.compile(rf"профиль тестов проекта\W{{0,3}}"
                          rf"{re.escape(config.DEFAULT_TARGET)}(?![\w-])")


class ProfileLimitCutsGateRunTest(MergeGateLimitSandbox):

    def test_ac3_gate_run_is_cut_at_profile_limit_not_config(self):
        """Предел профиля N меньше config — прогон гейта оборван через N секунд.

        Сценарий: `config.FULL_SUITE_TIMEOUT_SEC` — C (40–50 с, от зерна), в
        профиле артели `full_suite_timeout_sec: N` (3–6 с); пробник набора
        держится дольше C. `approve` на `merge_gate` отказывает «прогон не
        уложился в N с» и возвращается раньше C секунд; пробник стартовал.

        Ловит мутацию: прогон гейта мержа по-прежнему берёт
        `config.FULL_SUITE_TIMEOUT_SEC` (подполе профиля читается только
        `suite-run`) — прогон идёт C секунд, отказ называет C, а не N.
        """
        default = self.rng.randint(40, 50)
        limit = self.rng.randint(3, 6)
        self.set_config_limit(default)
        self.prepare(hold=100, profile_limit=limit)

        out, elapsed = self.approve()

        context = self.context(out) + f"\nC={default}, N={limit}, {elapsed:.1f} с"
        self.assertTrue(self.events("start"), context)
        self.assertIn(f"прогон не уложился в {limit} с", out, context)
        self.assertLess(elapsed, default, context)

    def test_ac3_profile_limit_above_config_lets_gate_run_finish(self):
        """Предел профиля N больше config — прогон дольше config не оборван.

        Сценарий: `config.FULL_SUITE_TIMEOUT_SEC` — C (2–3 с), в профиле
        артели N (40–50 с); пробник держится C + 3..5 с и заканчивается
        сам. Пробник дописал «конец», в выводе `approve` нет «не уложился».

        Ловит мутацию: действующий предел — меньший из профиля и config
        (`min(...)`) либо гейт мержа читает только config — pytest убит
        через C секунд, конца пробника нет, отказ «не уложился в C с».
        """
        default = self.rng.randint(2, 3)
        limit = self.rng.randint(40, 50)
        hold = default + self.rng.uniform(3, 5)
        self.set_config_limit(default)
        self.prepare(hold=hold, profile_limit=limit)

        out, elapsed = self.approve()

        context = (self.context(out) + f"\nC={default}, N={limit}, "
                   f"держание {hold:.1f} с, {elapsed:.1f} с")
        self.assertTrue(self.events("start"), context)
        self.assertTrue(self.events("end"), context)
        self.assertNotIn("не уложился", out, context)


class ConfigLimitCutsGateRunTest(MergeGateLimitSandbox):

    def test_ac4_gate_run_without_subfield_is_cut_at_patched_config(self):
        """Без подполя — прогон гейта оборван по подменённому config.

        Сценарий: профиль артели без `full_suite_timeout_sec`;
        `config.FULL_SUITE_TIMEOUT_SEC` подменён тестом на C (3–6 с, от
        зерна) уже после импорта модулей пульта; пробник держится дольше.
        `approve` отказывает «прогон не уложился в C с» и возвращается
        быстрее, чем пробник отпустил бы прогон сам.

        Ловит мутацию: предел без подполя взят при импорте (умолчание
        параметра `timeout=config.FULL_SUITE_TIMEOUT_SEC` или константа
        модуля) — подмена не видна, прогон идёт до конца пробника, отказа
        «не уложился в C с» нет.
        """
        default = self.rng.randint(3, 6)
        hold = self.rng.randint(60, 80)
        self.set_config_limit(default)
        self.prepare(hold=hold, profile_limit=None)

        out, elapsed = self.approve()

        context = self.context(out) + f"\nC={default}, {elapsed:.1f} с"
        self.assertTrue(self.events("start"), context)
        self.assertIn(f"прогон не уложился в {default} с", out, context)
        self.assertLess(elapsed, hold, context)


class TimeoutSourceTextTest(MergeGateLimitSandbox):

    def test_ac6_profile_limit_timeout_names_limit_and_profile_source(self):
        """Таймаут по пределу профиля — текст называет N и профиль проекта.

        Сценарий: C (40–50 с) в config, N (3–6 с) в профиле артели; пробник
        держится дольше. Строки об исходе таймаута в выводе `approve` и в
        журнале задачи (детали отказа) несут N и «профиль тестов проекта
        <имя артели>», без «config».

        Ловит мутацию: источник в текст не дописан (только число) либо
        всегда пишется «config» — «профиль тестов проекта <имя>» в строках
        таймаута нет.
        """
        default = self.rng.randint(40, 50)
        limit = self.rng.randint(3, 6)
        self.set_config_limit(default)
        self.prepare(hold=100, profile_limit=limit)

        out, _ = self.approve()

        context = self.context(out)
        for where, text in (("вывод approve", out),
                            ("журнал задачи", self.journal())):
            lines = self.timeout_lines(text)
            self.assertTrue(lines, self.note(f"{where}: нет строк таймаута\n"
                                             f"{context}"))
            joined = "\n".join(lines)
            self.assertTrue(standalone(limit, joined), self.note(
                f"{where}: строки таймаута не называют {limit}\n{context}"))
            self.assertRegex(joined, self.artel_source(), self.note(
                f"{where}: источник-профиль не назван\n{context}"))
            self.assertNotRegex(joined, r"\bconfig\b", self.note(
                f"{where}: источником назван config\n{context}"))

    def test_ac6_config_limit_timeout_names_limit_and_config_source(self):
        """Таймаут по пределу config — текст называет C и источник «config».

        Сценарий: профиль артели без подполя, C (3–6 с) в config; пробник
        держится дольше. Строки об исходе таймаута в выводе `approve` и в
        журнале задачи несут C и «config», без «профиль тестов проекта».

        Ловит мутацию: источник дописывается только при заданном подполе
        (ветка «config» пропущена) — в строках таймаута «config» нет; либо
        источник назван профилем проекта при его отсутствии.
        """
        default = self.rng.randint(3, 6)
        self.set_config_limit(default)
        self.prepare(hold=100, profile_limit=None)

        out, _ = self.approve()

        context = self.context(out)
        for where, text in (("вывод approve", out),
                            ("журнал задачи", self.journal())):
            lines = self.timeout_lines(text)
            self.assertTrue(lines, self.note(f"{where}: нет строк таймаута\n"
                                             f"{context}"))
            joined = "\n".join(lines)
            self.assertTrue(standalone(default, joined), self.note(
                f"{where}: строки таймаута не называют {default}\n{context}"))
            self.assertRegex(joined, r"\bconfig\b", self.note(
                f"{where}: источник config не назван\n{context}"))
            self.assertNotIn("профиль тестов проекта", joined, self.note(
                f"{where}: источником назван профиль\n{context}"))


class TimeoutTextStartsTest(MergeGateLimitSandbox):

    def test_ac7_timeout_texts_keep_their_starts_with_effective_limit(self):
        """Начала текстов таймаута прежние, число в них — действующий предел.

        Сценарий: C (40–50 с) в config, N (3–6 с) в профиле артели; пробник
        держится дольше. Вывод `approve` содержит «прогон не уложился в N
        с», а исход прогона в нём (после «: » либо с начала строки)
        начинается с «прогон полного набора tests/ превысил Nс»; то же —
        в журнале задачи.

        Ловит мутацию: источник вставлен в начало текста вместо дописывания
        («прогон полного набора tests/ (профиль …) превысил …» или «предел
        профиля N с: прогон …») — прежнего начала с N нет; в начале текста
        осталось значение config.
        """
        default = self.rng.randint(40, 50)
        limit = self.rng.randint(3, 6)
        self.set_config_limit(default)
        self.prepare(hold=100, profile_limit=limit)

        out, _ = self.approve()

        context = self.context(out)
        start = re.compile(rf"(?:^|: )прогон полного набора tests/ превысил "
                           rf"{limit}с", re.MULTILINE)
        for where, text in (("вывод approve", out),
                            ("журнал задачи", self.journal())):
            self.assertIn(f"прогон не уложился в {limit} с", text, self.note(
                f"{where}: нет «прогон не уложился в {limit} с»\n{context}"))
            self.assertRegex(text, start, self.note(
                f"{where}: исход не начинается с «прогон полного набора "
                f"tests/ превысил {limit}с»\n{context}"))


# --- suite-run ----------------------------------------------------------------

class SuiteRunLimitSandbox(ProbeSandbox):
    """Копия пульта в корне песочницы и задача внешнего проекта в `in_dev`."""

    COPY_LIMIT = 60

    def setUp(self):
        super().setUp()
        for name in ("orchestrator", "scripts"):
            shutil.copytree(CODE_ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        with open(self.root / "orchestrator" / "config.py", "a",
                  encoding="utf-8") as fh:
            fh.write("\n\n# Песочница теста предела полного прогона.\n"
                     "FULL_SUITE_WORKERS = '1'\n"
                     f"FULL_SUITE_TIMEOUT_SEC = {self.COPY_LIMIT}\n")
        with open(self.root / ".git" / "info" / "exclude", "a",
                  encoding="utf-8") as fh:
            fh.write("/orchestrator/\n/scripts/\n/targets.yaml\n")
        self.conn = store.db()

    def add_project_task(self, limit: int) -> tuple:
        """(id, рабочая копия) задачи проекта с `full_suite_timeout_sec:
        limit`; база — один быстрый тест, ветка добавляет пробник."""
        target = "p" + self.word()
        origin = config.PROJECTS / target / "origin.git"
        entry = PROJECT_ENTRY.format(name=target, origin=origin,
                                     base=config.MAIN_BRANCH, limit=limit,
                                     python=sys.executable)
        base_text = Path(config.TARGETS).read_text(encoding="utf-8")
        text = base_text.rstrip("\n") + "\n" + entry
        for path in {Path(config.TARGETS), self.root / "targets.yaml"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.targets_text = text
        clone = make_project_repo(target)
        base_name = "base" + self.word()
        (clone / "tests").mkdir()
        (clone / "tests" / f"test_{base_name}.py").write_text(
            f"def test_{base_name}():\n    assert True\n", encoding="utf-8")
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
        name, probe = self.probe_test(hold=100)
        (wt / "tests" / name).write_text(probe, encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", "правка ветки")
        return task_id, wt

    def cli(self, *args: str, cwd: Path, timeout: float) -> tuple:
        """(код выхода, вывод) `artel.py <args>` копии пульта; группа
        процессов вызова добивается после возврата."""
        env = {k: v for k, v in os.environ.items()
               if k != config.ARTEL_ROLE_ENV}
        proc = subprocess.Popen(
            [sys.executable, str(self.root / "orchestrator" / "artel.py"),
             *args], cwd=str(cwd), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True)
        try:
            raw, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_group(proc.pid)
            proc.communicate()
            self.fail(self.note(f"artel.py {' '.join(args)} не вернулся за "
                                f"{timeout} с"))
        finally:
            kill_group(proc.pid)
        return proc.returncode, raw.decode("utf-8", errors="replace")


class SuiteRunProfileLimitTest(SuiteRunLimitSandbox):

    def test_ac5_suite_run_cuts_at_profile_limit_and_reports_it(self):
        """`suite-run` обрывает прогон по пределу профиля N и называет N.

        Сценарий: в `config.py` копии пульта предел — 60 с; в профиле
        проекта задачи `full_suite_timeout_sec: N` (4–7 с, от зерна);
        пробник ветки держится дольше 60 с. Запуск `suite-run`, затем
        `suite-run --wait 1`: отчёт несёт «не уложился» и N в той же
        строке, без 60.

        Ловит мутацию: фоновый прогон `suite-run` берёт
        `config.FULL_SUITE_TIMEOUT_SEC` (подполе профиля читает только
        гейт) — прогон за минуту ожидания не оборван, отчёта нет; либо
        отчёт о таймауте печатает значение config, а не N.
        """
        limit = self.rng.randint(4, 7)
        task_id, wt = self.add_project_task(limit)

        code, launched = self.cli("suite-run", task_id, cwd=wt, timeout=60)
        context = self.note(f"запуск suite-run (код {code}):\n{launched}\n"
                            f"targets.yaml:\n{self.targets_text}")
        self.assertIn("запущен", launched, context)
        code, report = self.cli("suite-run", task_id, "--wait", "1", cwd=wt,
                                timeout=100)
        context = self.note(f"N={limit}; отчёт (код {code}):\n{report}\n"
                            f"targets.yaml:\n{self.targets_text}")
        self.assertTrue(self.events("start"), context)
        lines = [line for line in report.splitlines() if "не уложился" in line]
        self.assertTrue(lines, context)
        self.assertTrue(any(standalone(limit, line) for line in lines), context)
        self.assertFalse(any(standalone(self.COPY_LIMIT, line)
                             for line in lines), context)


if __name__ == "__main__":
    unittest.main()
