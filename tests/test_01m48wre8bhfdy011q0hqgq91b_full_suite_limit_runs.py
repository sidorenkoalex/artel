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
`config.py` копии дописаны параллель 1, предел прогона сценария и часы
`proc.wait` прогона pytest (`COPY_CLOCK`).

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
from tests.sandbox import (RealGitSandbox, capture, make_project_repo,
                           wait_processes_gone)

CODE_ROOT = Path(acceptance.__file__).resolve().parent.parent
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
ID_LETTERS = "".join(ch for ch in ALPHABET if not ch.isdigit())
PROFILE_HEAD = "    test_profile:\n"
# Потолок реального ожидания обрыва, от которого зависит исход (SPEC
# 01M56T94ZJE6H973HEBTM0Q0TD, требование 3); время подменённых часов не в счёт.
REAL_WAIT_CEILING_SEC = 5

PROBE_TEST = '''import json, os, time


def note(event):
    with open({records!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"event": event, "at": time.time(),
                              "mono": time.monotonic(),
                              "pid": os.getpid(),
                              "ppid": os.getppid(),
                              "pgid": os.getpgid(0)}}) + "\\n")


def test_{name}():
    note("start")
    for _ in range(int({hold} / 0.05) + 1):
        if os.path.exists({stop!r}):
            break
        time.sleep(0.05)
    note("end")
'''
# Пробник держится числом пауз, а не сроком по часам (SPEC
# 01M4G8MNEPECNX1TCEDW4T4RPX, требование 3): срок по `time.time()` на
# медленной машине истекал раньше предела прогона, и прогон заканчивался
# сам — отчёта «не уложился» не было. Пауз хватает не меньше чем на `hold`
# секунд.

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

# Часы `proc.wait` прогона pytest в копии пульта (SPEC
# 01M56T94ZJE6H973HEBTM0Q0TD, требование 2): настоящий `Popen.wait` с
# переданным ему пределом считает время по `subprocess._time`; на время
# такого вызова часы стоят, а когда пробник прогона (его группа процессов)
# записал «start», каждое чтение показывает ещё на предел профиля N больше —
# обрыв делает сам `Popen.wait` копии, без N секунд реального времени и без
# зависимости от того, сколько пробник ждал процессора. Перевод на каждом
# чтении, а не однократно: срок `endtime`, прочитанный и до старта пробника,
# и после него, истекает на следующем же чтении (гонка 07.10). Предел,
# отличный от N, часы не переводят и отпускают пробник: прогон кончается
# сам, отчёта «не уложился» нет. Отметки `wait_enter`/`clock_jump`/`cut` в
# журнале пробника (по `time.monotonic`) — доказательство, что часы
# опрошены и переведены и сколько реально длилось ожидание обрыва.
COPY_CLOCK = '''

# Песочница теста предела полного прогона: часы proc.wait прогона pytest.
import json as _sandbox_json
import os as _sandbox_os
import subprocess as _sandbox_subprocess
import threading as _sandbox_threading
import time as _sandbox_time

_sandbox_call = _sandbox_threading.local()
_sandbox_real_clock = _sandbox_subprocess._time
_sandbox_real_wait = _sandbox_subprocess.Popen.wait


def _sandbox_note(event, pgid, **fields):
    fields.update(event=event, pgid=pgid, pid=_sandbox_os.getpid(),
                  mono=_sandbox_time.monotonic())
    with open({records!r}, "a", encoding="utf-8") as fh:
        fh.write(_sandbox_json.dumps(fields) + "\\n")


def _sandbox_probe_started(pgid):
    try:
        with open({records!r}, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return False
    for line in lines:
        try:
            rec = _sandbox_json.loads(line)
        except ValueError:
            continue
        if rec.get("event") == "start" and rec.get("pgid") == pgid:
            return True
    return False


def _sandbox_clock():
    call = getattr(_sandbox_call, "state", None)
    if call is None:
        return _sandbox_real_clock()
    if call["cut"] and _sandbox_probe_started(call["pgid"]):
        if not call["jumped"]:
            call["jumped"] = True
            _sandbox_note("clock_jump", call["pgid"])
        call["at"] += {limit!r}
    return call["at"]


def _sandbox_wait(self, timeout=None):
    args = self.args if isinstance(self.args, (list, tuple)) else [self.args]
    if timeout is None or "pytest" not in [str(a) for a in args]:
        return _sandbox_real_wait(self, timeout)
    cut = timeout == {limit!r}
    if not cut:
        with open({stop!r}, "w", encoding="utf-8") as fh:
            fh.write("stop")
    _sandbox_note("wait_enter", self.pid, timeout=timeout)
    _sandbox_call.state = {{"at": _sandbox_real_clock(), "pgid": self.pid,
                           "cut": cut, "jumped": False}}
    try:
        return _sandbox_real_wait(self, timeout)
    except _sandbox_subprocess.TimeoutExpired:
        _sandbox_note("cut", self.pid, timeout=timeout)
        raise
    finally:
        _sandbox_call.state = None


_sandbox_subprocess._time = _sandbox_clock
_sandbox_subprocess.Popen.wait = _sandbox_wait
'''


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
        wait_processes_gone(pids, pid_alive)
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
        профиле артели `full_suite_timeout_sec: N` (11–13 с); пробник набора
        держится дольше C. `approve` на `merge_gate` отказывает «прогон не
        уложился в N с» и возвращается раньше C секунд; пробник стартовал.

        Ловит мутацию: прогон гейта мержа по-прежнему берёт
        `config.FULL_SUITE_TIMEOUT_SEC` (подполе профиля читается только
        `suite-run`) — прогон идёт C секунд, отказ называет C, а не N.
        """
        default = self.rng.randint(40, 50)
        limit = self.rng.randint(11, 13)
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
        `config.FULL_SUITE_TIMEOUT_SEC` подменён тестом на C (11–13 с, от
        зерна) уже после импорта модулей пульта; пробник держится дольше.
        `approve` отказывает «прогон не уложился в C с» и возвращается
        быстрее, чем пробник отпустил бы прогон сам.

        Ловит мутацию: предел без подполя взят при импорте (умолчание
        параметра `timeout=config.FULL_SUITE_TIMEOUT_SEC` или константа
        модуля) — подмена не видна, прогон идёт до конца пробника, отказа
        «не уложился в C с» нет.
        """
        default = self.rng.randint(11, 13)
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

    def task_id(self) -> str:
        # Id стоит в начале строки отчёта «не уложился», а `standalone`
        # считает число отдельно стоящим и между буквами: цифры id давали
        # там `COPY_LIMIT` (…K60X…) — около 1% зёрен (падение 17.10).
        return "01M" + "".join(self.rng.choice(ID_LETTERS) for _ in range(23))

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
        limit`; база — один быстрый тест, ветка добавляет пробник. Часы
        `proc.wait` прогона pytest копии пульта переводятся на `limit`
        (`COPY_CLOCK`)."""
        with open(self.root / "orchestrator" / "config.py", "a",
                  encoding="utf-8") as fh:
            fh.write(COPY_CLOCK.format(records=str(self.records),
                                       stop=str(self.stop_file), limit=limit))
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

    def run_traces(self, task_id: str) -> str:
        """Записи пробника и файлы `suite-run` задачи — для текста провала:
        по одному коду выхода `--wait` исход не восстановить (копилка
        07.10)."""
        try:
            records = self.records.read_text(encoding="utf-8")
        except OSError:
            records = "(нет)\n"
        parts = [f"записи пробника:\n{records}"]
        logs = self.root / ".artel" / "logs" / "suite-run" / task_id
        for path in sorted(logs.glob("*")) if logs.is_dir() else ():
            text = path.read_bytes().decode("utf-8", errors="replace")
            parts.append(f"{path.name}:\n{text[-4000:]}")
        return "\n".join(parts)


class SuiteRunProfileLimitTest(SuiteRunLimitSandbox):

    def test_ac5_suite_run_cuts_at_profile_limit_and_reports_it(self):
        """`suite-run` обрывает прогон по пределу профиля N и называет N.

        Сценарий: в `config.py` копии пульта предел — 60 с; в профиле
        проекта задачи `full_suite_timeout_sec: N` (11–13 с, от зерна);
        пробник ветки держится дольше 60 с. Часы `proc.wait` прогона pytest
        копии (`COPY_CLOCK`) стоят, пока пробник не стартовал, и тогда
        переходят на N: обрыв делает настоящий `Popen.wait` копии без N
        секунд реального времени. Запуск `suite-run`, затем
        `suite-run --wait 1`: отчёт несёт «не уложился» и N в той же
        строке, без 60. Журнал пробника показывает, что этот обрыв
        случился в вызове с пределом N, что часы того вызова переведены,
        и что реальное ожидание обрыва (от входа в `proc.wait` либо старта
        пробника, что позже) по `time.monotonic` короче 5 с.

        Ловит мутацию: фоновый прогон `suite-run` берёт
        `config.FULL_SUITE_TIMEOUT_SEC` (подполе профиля читает только
        гейт) либо `proc.wait` получает предел, отличный от N — часы его не
        переводят, пробник отпущен, прогон кончается сам, строки «не
        уложился» нет; либо отчёт о таймауте печатает значение config, а не
        N; либо `Popen.wait` копии не опрашивает подменённые часы (обрыв
        чужими средствами) — отметки `clock_jump` нет; либо обрыв вернулся
        к реальному отсчёту N (11–13 с) — реальное ожидание не короче 5 с.
        """
        limit = self.rng.randint(11, 13)
        task_id, wt = self.add_project_task(limit)

        code, launched = self.cli("suite-run", task_id, cwd=wt, timeout=60)
        context = self.note(f"запуск suite-run (код {code}):\n{launched}\n"
                            f"targets.yaml:\n{self.targets_text}")
        self.assertIn("запущен", launched, context)
        code, report = self.cli("suite-run", task_id, "--wait", "1", cwd=wt,
                                timeout=100)
        context = self.note(f"N={limit}; отчёт (код {code}):\n{report}\n"
                            f"targets.yaml:\n{self.targets_text}\n"
                            f"{self.run_traces(task_id)}")
        self.assertTrue(self.events("start"), context)
        lines = [line for line in report.splitlines() if "не уложился" in line]
        self.assertTrue(lines, context)
        self.assertTrue(any(standalone(limit, line) for line in lines), context)
        self.assertFalse(any(standalone(self.COPY_LIMIT, line)
                             for line in lines), context)

        cuts = [rec for rec in self.events("cut") if rec["timeout"] == limit]
        self.assertTrue(cuts, f"обрыва прогона pytest в proc.wait копии с "
                        f"пределом {limit} нет\n{context}")
        pgid = cuts[0]["pgid"]
        self.assertTrue(
            [rec for rec in self.events("clock_jump") if rec["pgid"] == pgid],
            f"подмена часов копии не сработала: Popen.wait прогона {pgid} не "
            f"опросил подменённые часы после старта пробника — обрыв не по "
            f"ним\n{context}")
        entered = [rec["mono"] for rec in self.events("wait_enter")
                   if rec["pgid"] == pgid]
        started = [rec["mono"] for rec in self.events("start")
                   if rec.get("pgid") == pgid]
        self.assertTrue(entered and started, context)
        waited = cuts[0]["mono"] - max(max(entered), min(started))
        self.assertLess(waited, REAL_WAIT_CEILING_SEC,
                        f"реальное ожидание обрыва {waited:.1f} с не короче "
                        f"{REAL_WAIT_CEILING_SEC} с\n{context}")


class SuiteRunFixtureIdTest(unittest.TestCase):

    def test_fixture_task_ids_have_no_digits_after_prefix(self):
        """Id задачи песочницы `suite-run` после префикса `01M` — без цифр, при любом зерне набора.

        Сценарий: зёрна 0–2999, id генератором `SuiteRunLimitSandbox.task_id`;
        часть после `01M` не пуста и не содержит цифр — число id не может
        стать отдельно стоящим `COPY_LIMIT` в строке «не уложился».

        Ловит мутацию: генератор id песочницы `suite-run` вернули к алфавиту
        с цифрами (`ALPHABET`) или в `ID_LETTERS` попала цифра — на 3000
        зёрнах id с цифрой после префикса находится всегда.
        """
        bad = []
        for seed in range(3000):
            holder = mock.Mock(rng=random.Random(seed))
            task_id = SuiteRunLimitSandbox.task_id(holder)
            rest = task_id.removeprefix("01M")
            if rest == task_id or not rest or re.search(r"\d", rest):
                bad.append((seed, task_id))
        self.assertEqual(bad[:5], [], f"id с цифрами после префикса: {len(bad)}")


# Пробник проверки часов: «pytest» в argv — как у прогона pytest пульта;
# старт пишется после флага (если задан), держание — до файла-стопа или
# `hold` секунд, чтобы сломанные часы дали провал, а не зависание.
CLOCK_PROBE = '''import json, os, sys, time
records, stop, flag, hold = sys.argv[1:5]
if flag:
    deadline = time.monotonic() + 10
    while not os.path.exists(flag) and time.monotonic() < deadline:
        time.sleep(0.01)
with open(records, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"event": "start", "pgid": os.getpgid(0),
                         "mono": time.monotonic()}) + "\\n")
deadline = time.monotonic() + float(hold)
while not os.path.exists(stop) and time.monotonic() < deadline:
    time.sleep(0.02)
'''


class CopyClockOrderTest(unittest.TestCase):
    """`COPY_CLOCK` в процессе теста против настоящего процесса-пробника:
    оба порядка «старт пробника / первое чтение часов в `Popen.wait`»
    детерминированно (SPEC 01M56T94ZJE6H973HEBTM0Q0TD, требование 2)."""

    LIMIT = 12
    HOLD = 10

    def setUp(self):
        work = Path(tempfile.mkdtemp(prefix="artel-copy-clock-")).resolve()
        self.addCleanup(shutil.rmtree, work, True)
        self.records = work / "records.jsonl"
        self.stop_file = work / "stop"
        self.flag = work / "first-clock-read"
        # Подмены `subprocess` снимаются здесь; `COPY_CLOCK` ставит свои.
        for patcher in (mock.patch.object(subprocess, "_time",
                                          subprocess._time),
                        mock.patch.object(subprocess.Popen, "wait",
                                          subprocess.Popen.wait)):
            patcher.start()
            self.addCleanup(patcher.stop)
        exec(COPY_CLOCK.format(records=str(self.records),
                               stop=str(self.stop_file), limit=self.LIMIT),
             {"__name__": "copy_clock"})

    def spawn(self, flag: Path | None) -> subprocess.Popen:
        proc = subprocess.Popen(
            [sys.executable, "-c", CLOCK_PROBE, str(self.records),
             str(self.stop_file), str(flag or ""), str(self.HOLD), "pytest"],
            stdin=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(proc.wait)
        self.addCleanup(kill_group, proc.pid)
        return proc

    def events(self, event: str) -> list:
        if not self.records.exists():
            return []
        return [rec for rec in map(json.loads, self.records.read_text(
            encoding="utf-8").splitlines()) if rec["event"] == event]

    def assert_cut_by_real_wait(self, proc: subprocess.Popen) -> None:
        started = time.monotonic()
        # Не `assertRaises`: он стирает traceback, а по нему видно, кто бросил.
        try:
            code = proc.wait(timeout=self.LIMIT)
        except subprocess.TimeoutExpired as exc:
            tb = exc.__traceback__
        else:
            self.fail(f"обрыва нет: wait вернул {code}")
        waited = time.monotonic() - started
        while tb.tb_next is not None:
            tb = tb.tb_next
        self.assertEqual(
            (tb.tb_frame.f_code.co_name,
             Path(tb.tb_frame.f_code.co_filename).name),
            ("_wait", "subprocess.py"),
            "TimeoutExpired бросил не настоящий Popen._wait")
        self.assertLess(waited, REAL_WAIT_CEILING_SEC)
        self.assertEqual([r["pgid"] for r in self.events("clock_jump")],
                         [proc.pid])
        self.assertEqual([r["pgid"] for r in self.events("cut")], [proc.pid])

    def test_probe_started_before_first_clock_read_is_cut(self):
        """Пробник стартовал до первого чтения часов — настоящий `Popen._wait` обрывает быстро.

        Сценарий: `proc.wait(timeout=N)` зовётся лишь после записи «start»
        пробника. Ожидается `TimeoutExpired` из `subprocess.Popen._wait`
        короче 5 с реального времени, отметки `clock_jump` и `cut` того же
        процесса.

        Ловит мутацию: часы переводятся однократно при старте пробника
        (гонка 07.10) — перевод уходит в само чтение `endtime`, обрыва нет,
        пробник отпускает `wait` через `HOLD` секунд без `TimeoutExpired`.
        """
        proc = self.spawn(None)
        deadline = time.monotonic() + REAL_WAIT_CEILING_SEC
        while not self.events("start") and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.events("start"), "пробник не стартовал")
        self.assert_cut_by_real_wait(proc)

    def test_probe_started_after_first_clock_read_is_cut(self):
        """Пробник стартовал после первого чтения часов — настоящий `Popen._wait` обрывает быстро.

        Сценарий: первое чтение `subprocess._time` (срок `endtime` в
        `Popen.wait`) ставит флаг, и только по нему пробник пишет «start».
        Ожидается `TimeoutExpired` из `subprocess.Popen._wait` короче 5 с,
        отметки `clock_jump` и `cut` того же процесса.

        Ловит мутацию: перевод часов решён один раз на входе в обёртку
        (пробник к тому моменту ещё не стартовал) — часы стоят, обрыва нет,
        `wait` возвращается через `HOLD` секунд без `TimeoutExpired`.
        """
        clock = subprocess._time

        def first_read_releases_probe():
            value = clock()
            self.flag.touch()
            return value

        subprocess._time = first_read_releases_probe
        proc = self.spawn(self.flag)
        self.assert_cut_by_real_wait(proc)
        self.assertTrue(self.events("start"), "пробник не стартовал")
        self.assertFalse(self.stop_file.exists())

    def test_other_limit_releases_probe_without_cut(self):
        """Предел, отличный от N, — часы не переводятся, пробник отпущен файлом-стопом.

        Сценарий: `proc.wait(timeout=N + 1)`; пробник кончается сам по
        файлу-стопу, `wait` возвращает 0 короче 5 с, отметок `clock_jump` и
        `cut` нет.

        Ловит мутацию: обёртка обрывает при любом пределе (часы переводятся
        и при пределе config) — `TimeoutExpired` вместо кода 0, и мутация
        «фоновый прогон берёт предел config» не краснила бы метод `suite-run`.
        """
        proc = self.spawn(None)
        started = time.monotonic()
        self.assertEqual(proc.wait(timeout=self.LIMIT + 1), 0)
        self.assertLess(time.monotonic() - started, REAL_WAIT_CEILING_SEC)
        self.assertTrue(self.stop_file.exists())
        self.assertEqual(self.events("clock_jump"), [])
        self.assertEqual(self.events("cut"), [])


if __name__ == "__main__":
    unittest.main()
