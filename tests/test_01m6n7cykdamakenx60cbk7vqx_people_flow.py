"""Проект людей на GitHub (`forge: github` + `merge_gate: target-human`): полный цикл до `done` и `kill` после отправки без закрытия PR, запрет повтора CI пультом (`ci.trigger_rerun`, гейт мержа на красном CI, команда `ci-rerun`); GitLab с `target-human` и `github` + `operator` — прежние.

Группа: долгоживущий
Красен до реализации: пара `github` + `target-human` не в `targets.SUPPORTED_PAIRS` — `approve` на `merge_gate` отказывает причиной поддержки (до `awaiting_human`, до записи `flake-rate`), а `ci.trigger_rerun` и `ci-rerun` для клона проекта людей зовут `gh` (поиск прогона, `run rerun`, `run watch`, чтение статуса); методы `gitlab` + `target-human` и `github` + `operator` зелены с рождения — они держат прежнее поведение.

Связка «команда пульта — FSM — база — git»: каждый сценарий идёт через
публичный вход (`fsm.cmd_advance`, `fsm.cmd_approve`, `artel.main` с
`sys.argv` команды `mr-sync`, `ci_rerun.cmd_ci_rerun`, `cleanup.cmd_kill`,
`ci.trigger_rerun`) в настоящем git песочницы (`tests.sandbox.RealGitSandbox`):
клон вымышленного проекта (`tests.sandbox.make_project_repo`) с локальным
голым `origin`, запись проекта — в локальном слое (`targets.local_path()`),
ссылка документов — автокоммитом шага. Пара НЕ включается подменой
`targets.SUPPORTED_PAIRS`: её поддержка — предмет задачи.

`gh` — подделка `ci.gh` (`FakeGh`): пишет argv и именованные аргументы в
два журнала (`calls` — с последней отметки команды, `all` — за весь тест),
отвечает заготовкой сценария; PR для `pr view` — словарь полей сценария,
`pr ready`/`pr edit` правят его; `api`-чтения check-runs и прогонов
отвечают по режиму CI сценария (зелёный, красный, зависший). Цвет CI ветки
— подменённый `ci.branch_status` (зелёный), кроме сценариев, где краснота
CI — предмет (`real_ci=True`): там `ci.branch_status` настоящий и читает
подделку. Цвет CI base — `ci.main_line_status`; `keychain.token` и
`gitcmd.hosting_token` подменены — связка ключей не читается. Прогон pytest
у мест запуска (`acceptance`, `two_sided`) отвечает зелёным прогоном.
Настоящего `gh` и GitHub тест не трогает, ссылок на реальные проекты нет.

Стенд: `url` записи на время git-операций стенда — путь голого `origin`;
на время команды, открывающей MR (`approve`, `advance`), — https-адрес
`https://localhost/<владелец>/<имя>`: голова ветки и ссылка документов к
этому моменту уже в `origin`. Отправки (`push`) пульта пишет шпион
`subprocess.run`; отправки людей проекта (их клон) шпион не считает.

Имена, номера PR, id прогонов — из `random`, зерно печатается и входит в
текст каждого провала.
"""
import contextlib
import io
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (acceptance, artel, catalog, checkpoint, ci, ci_rerun,
                          cleanup, config, fsm, idgen, keychain, store,
                          targets, workspace)
from orchestrator.advance_gates import two_sided
from tests.sandbox import make_project_repo

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
IDENTITY = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")
OUTPUT = "1 passed in 0.01s\n"
COLLECTED = "probe.py::test_probe\n\n1 test collected in 0.01s\n"
JUNIT = ('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite '
         'name="pytest" errors="0" failures="0" skipped="0" tests="1">'
         '<testcase classname="probe" name="test_probe" time="0.01"/>'
         '</testsuite></testsuites>')
MAIN = config.MAIN_BRANCH
SENT = "ветка отправлена:"
PUSH_SUBCOMMANDS = ("push", "send-pack")
NOT_STARTED = "ре-ран CI не запущен: "
RERUN_NOT_STARTED = "повтор не запущен"
MERGE_REFUSED = "merge отклонён: "
PR_UNTOUCHED = "PR не тронут: MR вливают люди проекта"
SERVER_LEFT = "сервер проекта не тронут: ветка {branch} отправлена"
BRANCH_OUTCOME = "ветка origin {branch}: "
CLEANUP = "уборка"
MERGED_THIS = "влит этим MR"
CLOSED_THIS = "merged_upstream"
AWAITING = "awaiting_human"
FORBIDDEN_GH = (["pr", "merge"], ["pr", "close"], ["pr", "comment"],
                ["run", "rerun"], ["run", "watch"])

ENTRY = """  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
    policy:
      no_paths: [conf/settings.yaml]
      project_skills: []
      merge_gate: {gate}
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: {forge}
      url: "{url}"
      token_slot: {name}-token
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
---

# SPEC: фикстура проекта людей

## Контекст

Фикстура песочницы.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстурный критерий.

## Не входит

Ничего.
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: фикстура

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

Нет.
"""

PLANK_TEXT = '''"""Фикстура планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_fixture_{word}(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''


def is_pytest(argv) -> bool:
    parts = [str(a) for a in argv]
    return any(Path(p).name in ("pytest", "py.test") for p in parts) or any(
        a == "-m" and b == "pytest" for a, b in zip(parts, parts[1:]))


def git_sub(argv: list) -> str:
    """Подкоманда git-вызова после глобальных опций `-C`/`-c`."""
    i = 1
    while i + 1 < len(argv) and argv[i] in ("-C", "-c"):
        i += 2
    return argv[i] if i < len(argv) else ""


def capture_out(fn, *args, **kwargs) -> str:
    """Вывод вызова вместе с текстом ненулевого `SystemExit`."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue()


class SpyProc:
    """Процесс подменённого pytest: зелёный, вывод — текст прогона."""
    pid = 2_000_000_000
    returncode = 0
    stdin = stdout = stderr = None

    def __init__(self, argv, text):
        self.args = argv
        self.text = text

    def communicate(self, input=None, timeout=None):
        return self.text, ""

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0

    def kill(self):
        pass

    terminate = kill

    def send_signal(self, sig):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class PytestSpy:
    """Замена модуля `subprocess` у мест запуска pytest: вызов pytest
    отвечает зелёным прогоном; прочие процессы идут настоящими."""

    def __getattr__(self, name):
        return getattr(subprocess, name)

    @staticmethod
    def answer(argv, kwargs) -> str:
        argv = [str(a) for a in argv]
        cwd = kwargs.get("cwd")
        here = Path(cwd) if cwd is not None else Path.cwd()
        for arg in argv:
            if arg.startswith("--junitxml="):
                path = Path(arg.split("=", 1)[1])
                if not path.is_absolute():
                    path = here / path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(JUNIT, encoding="utf-8")
        return COLLECTED if "--collect-only" in argv else OUTPUT

    def run(self, argv, *args, **kwargs):
        if not is_pytest(argv):
            return REAL_RUN(argv, *args, **kwargs)
        return subprocess.CompletedProcess(argv, 0, self.answer(argv, kwargs), "")

    def Popen(self, argv, *args, **kwargs):
        if not is_pytest(argv):
            return REAL_POPEN(argv, *args, **kwargs)
        text = self.answer(argv, kwargs)
        out = kwargs.get("stdout")
        if hasattr(out, "write"):
            out.write(text.encode("utf-8") if "b" in getattr(out, "mode", "")
                      else text)
            out.flush()
        return SpyProc(argv, text)


class FakeGh:
    """Подделка `ci.gh`. `pr create` — заготовка `create`; `pr view` — JSON
    словаря `prs[<номер>]`; `pr ready`/`pr edit` правят словарь PR;
    `api …/check-runs` — по режиму `ci` (`green`, `red`, `stuck`), `api
    …/actions/runs` — один упавший прогон `run_id`, `api …/actions/jobs/<id>`
    — `run_id`; `run rerun`/`run watch` — успех. Прочее — отказ."""

    def __init__(self, rng: random.Random):
        self.calls: list = []
        self.all: list = []
        self.create = (1, "", "pr create вне сценария теста")
        self.prs: dict = {}
        self.ci = "green"
        self.check_id = rng.randrange(10 ** 6, 10 ** 7)
        self.run_id = rng.randrange(10 ** 6, 10 ** 7)

    def check_runs(self) -> dict:
        check = {"id": self.check_id, "name": "tests", "head_sha": "x"}
        if self.ci == "red":
            check.update(status="completed", conclusion="failure",
                         started_at="2026-01-01T00:00:00Z",
                         completed_at="2026-01-01T00:05:00Z")
        elif self.ci == "stuck":
            check.update(status="in_progress", conclusion=None,
                         started_at="2001-01-01T00:00:00Z")
        else:
            check.update(status="completed", conclusion="success",
                         started_at="2026-01-01T00:00:00Z",
                         completed_at="2026-01-01T00:05:00Z")
        return {"total_count": 1, "check_runs": [check]}

    def __call__(self, *args, **kwargs):
        argv = [str(a) for a in args]
        self.calls.append((argv, dict(kwargs)))
        self.all.append((argv, dict(kwargs)))
        head = argv[:2]
        number = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else None
        if argv[:1] == ["api"] and len(argv) > 1:
            path = argv[1]
            if "/check-runs" in path:
                return subprocess.CompletedProcess(argv, 0,
                                                   json.dumps(self.check_runs()), "")
            if "/actions/runs" in path:
                run = {"id": self.run_id, "status": "completed",
                       "conclusion": "failure", "event": "push"}
                return subprocess.CompletedProcess(
                    argv, 0, json.dumps({"total_count": 1, "workflow_runs": [run]}), "")
            if "/actions/jobs/" in path:
                return subprocess.CompletedProcess(
                    argv, 0, json.dumps({"run_id": self.run_id}), "")
        if head in (["run", "rerun"], ["run", "watch"]):
            return subprocess.CompletedProcess(argv, 0, "", "")
        if head == ["pr", "create"]:
            return subprocess.CompletedProcess(argv, *self.create)
        if head == ["pr", "view"]:
            if number not in self.prs:
                return subprocess.CompletedProcess(
                    argv, 1, "", "GraphQL: Could not resolve to a PullRequest "
                                 f"with the number of {number}. (repository.pullRequest)")
            return subprocess.CompletedProcess(argv, 0,
                                               json.dumps(self.prs[number]), "")
        if head == ["pr", "ready"]:
            if number in self.prs:
                self.prs[number]["isDraft"] = False
            return subprocess.CompletedProcess(argv, 0, "", "")
        if head == ["pr", "edit"]:
            if number in self.prs and len(argv) > 3:
                self.prs[number]["assignees"].append(
                    {"login": argv[3].split("=", 1)[-1]})
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 1, "", "вызов gh вне сценария теста")

    @staticmethod
    def heads(log: list) -> list:
        return [argv for argv, _kwargs in log]

    def seen(self, *prefix, log=None) -> list:
        log = self.calls if log is None else log
        return [a for a in self.heads(log) if a[:len(prefix)] == list(prefix)]


class Stand:
    """Пульт с клоном вымышленного проекта (`forge`, `merge_gate` — по
    параметрам) и локальным голым `origin`."""

    def __init__(self, sb, *, forge_name: str = "github",
                 gate: str = "target-human", real_ci: bool = False):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.forge = forge_name
        self.gate = gate
        self.ext = f"proj{self.word()}"
        self.owner = f"own{self.word(4)}"
        self.https = f"https://localhost/{self.owner}/{self.ext}"
        self.gh = FakeGh(self.rng)
        self.pushes: list = []
        self.recording = True
        self.policy: dict = {"draft_mr": "false"}
        self.marks: dict = {}
        self._people = None

        def spy_run(*args, **kwargs):
            argv = args[0] if args else kwargs.get("args")
            if (self.recording and isinstance(argv, (list, tuple)) and argv
                    and Path(str(argv[0])).name == "git"):
                argv = [str(a) for a in argv]
                if git_sub(argv) in PUSH_SUBCOMMANDS:
                    self.pushes.append(argv)
            return REAL_RUN(*args, **kwargs)

        def main_line(sha, repo=None):
            return ci.MainLineStatus(ci.MAIN_GREEN, sha, [], [], "",
                                     "CI base (тест): green")

        def branch_status(branch, repo=None):
            return True, f"CI ветки {branch} (тест): зелёный"

        for name in IDENTITY:
            os.environ.pop(name, None)
        patchers = [
            mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
            mock.patch.object(ci, "main_line_status", main_line),
            mock.patch.object(ci, "gh", self.gh),
            mock.patch.object(keychain, "token", lambda *a, **k: "tok"),
            mock.patch("orchestrator.gitcmd.hosting_token",
                       lambda *a, **k: (None, None)),
            mock.patch("orchestrator.doctor.preflight_checks",
                       lambda *args, **kwargs: []),
            mock.patch.object(subprocess, "run", spy_run)]
        if not real_ci:
            patchers.append(mock.patch.object(ci, "branch_status", branch_status))
        for patcher in patchers:
            patcher.start()
            sb.addCleanup(patcher.stop)
        sb.add_synced_origin()
        self.clone = make_project_repo(self.ext)
        self.bare = config.PROJECTS / self.ext / "origin.git"
        self.record(https=False)
        capture_out(catalog.cmd_init)
        self.commit_to_main({"app.py": "VALUE = 1\n",
                             "conf/settings.yaml": "level: 1\n"})

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def git(self, *args) -> str:
        return self.sb.git(*[str(a) for a in args])

    def record(self, *, https: bool) -> None:
        """Запись проекта в локальном слое: `url` — https-адрес (`https`)
        либо путь голого `origin`; поля `policy` — `self.policy`."""
        lines = "".join(f"      {key}: {value}\n"
                        for key, value in self.policy.items() if value is not None)
        url = self.https if https else str(self.bare)
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text("targets:\n" + ENTRY.format(
            name=self.ext, base=MAIN, policy=lines, url=url, gate=self.gate,
            forge=self.forge), encoding="utf-8")

    def commit_to_main(self, files: dict) -> str:
        for rel, text in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", self.clone, "add", "-A")
        self.git("-C", self.clone, "commit", "-q", "-m", f"main {self.word()}")
        self.git("-C", self.clone, "push", "-q", "origin", f"{MAIN}:{MAIN}")
        return self.main_sha()

    def main_sha(self) -> str:
        return self.git("--git-dir", self.bare, "rev-parse", MAIN).strip()

    # ------------------------------------------------------------ задачи

    def new_task(self, state: str = "merge_gate", published: bool = True) -> str:
        """Задача проекта: 2 коммита кода, SPEC/PLAN/планка в ссылке
        документов (отправлена в `origin`), лок планки; `published` — ветка
        на сервере с записью «ветка отправлена»."""
        self.record(https=False)
        task = idgen.new_task_id()
        branch = f"task/{task.lower()}-{self.word()}"
        zones = "app.py, kod/"
        store.insert_task(self.conn, task, f"Фикстура {self.word()}", state,
                          branch, self.ext, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task, zones=zones)
        wt, error = workspace.ensure(task, branch)
        assert error is None, self.note(f"рабочая копия не заведена: {error}")
        for _ in range(2):
            self.commit_code(task, {f"kod/{self.word()}.py":
                                    f"A = {self.rng.randrange(10 ** 6)}\n"})
        self.write_docs(task, {
            "SPEC.md": SPEC_TEXT.format(task=task, zones=zones),
            "PLAN.md": PLAN_TEXT.format(task=task),
            f"acceptance_tests/test_ac1_{self.word()}.py":
                PLANK_TEXT.format(word=self.word())})
        store.update_task(self.conn, task, tests_locked_sha=self.docs_head(task),
                          draft_mr_created=1)
        store.record_fixation(self.conn, task)
        if published:
            self.publish_branch(task)
            store.journal(self.conn, task, "orchestrator", SENT,
                          f"{self.head(task)} {branch}")
        return task

    def publish_branch(self, task: str) -> None:
        """Ветка задачи в `origin` git-командой стенда, без записи
        журнала «ветка отправлена»."""
        branch = self.branch(task)
        self.git("-C", self.clone, "push", "-q", "origin",
                 f"{branch}:refs/heads/{branch}")

    def pr(self, task: str, number: int, *, draft: bool = False) -> dict:
        data = {"number": number, "url": f"{self.https}/pull/{number}",
                "title": f"MR {self.word()}", "state": "OPEN", "isDraft": draft,
                "assignees": [], "baseRefName": MAIN,
                "headRefName": self.branch(task), "headRefOid": self.head(task),
                "mergeCommit": None}
        self.gh.prs[number] = data
        return data

    def created_ok(self, task: str, number: int, *, draft: bool = False) -> None:
        self.gh.create = (0, f"{self.https}/pull/{number}\n", "")
        self.pr(task, number, draft=draft)

    def to_awaiting(self) -> tuple:
        """Задача доведена до `awaiting_human` настоящим `approve`; (задача,
        номер PR, вывод)."""
        task = self.new_task()
        number = self.rng.randrange(1, 10 ** 5)
        self.created_ok(task, number)
        out = self.approve(task)
        return task, number, out

    def branch(self, task: str) -> str:
        return store.get_task(self.conn, task)["branch"]

    def wt(self, task: str) -> Path:
        return workspace.path(task, self.ext)

    def write_docs(self, task: str, files: dict, role: str = "developer") -> str:
        docs = config.PROJECTS / self.ext / "tasks" / task
        for rel, text in files.items():
            path = docs / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return capture_out(checkpoint.commit_step_artifacts, self.conn, task,
                           role)

    def docs_head(self, task: str) -> str:
        return self.git("-C", self.clone, "for-each-ref",
                        "--format=%(objectname)",
                        f"refs/artifacts/{task}").strip()

    def commit_code(self, task: str, files: dict) -> str:
        wt = self.wt(task)
        for rel, text in files.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", wt, "add", "-A")
        self.git("-C", wt, "commit", "-q", "-m", f"код {self.word()}")
        return self.head(task)

    # ------------------------------------------------------ люди проекта

    def pgit(self, *args) -> str:
        if self._people is None:
            self._people = self.clone.parent.parent / f"people-{self.word()}"
            self.git("clone", "-q", self.bare, self._people)
        return self.git("-C", self._people, "-c", "user.name=ljudi",
                        "-c", "user.email=ljudi@example.invalid", *args)

    def merge_commit(self, task: str) -> str:
        """Люди проекта вливают ветку коммитом слияния (их отправки шпион
        пульта не считает); sha слияния в `origin/<base>`."""
        self.recording = False
        try:
            self.pgit("fetch", "-q", "origin")
            self.pgit("checkout", "-q", "-B", MAIN, f"origin/{MAIN}")
            self.pgit("merge", "-q", "--no-ff", "-m", f"Merge {self.word()}",
                      f"origin/{self.branch(task)}")
            sha = self.pgit("rev-parse", "HEAD").strip()
            self.pgit("push", "-q", "origin", f"{MAIN}:{MAIN}")
        finally:
            self.recording = True
        return sha

    # ------------------------------------------------------------ команды

    @contextlib.contextmanager
    def spy(self):
        spy = PytestSpy()
        with mock.patch.object(acceptance, "subprocess", spy), \
                mock.patch.object(two_sided, "subprocess", spy):
            yield spy

    def mark(self) -> None:
        self.gh.calls.clear()
        self.marks = {r["id"]: len(self.rows(r["id"]))
                      for r in store.all_tasks(self.conn)}

    def approve(self, task: str) -> str:
        """`approve` гейта мержа sha фиксации; `url` записи — https."""
        store.record_fixation(self.conn, task)
        sha = store.get_task(self.conn, task)["fixed_sha"]
        self.record(https=True)
        self.mark()
        try:
            with self.spy():
                return capture_out(fsm.cmd_approve, task, sha)
        finally:
            self.record(https=False)

    def advance(self, task: str) -> str:
        self.record(https=True)
        self.mark()
        try:
            with self.spy():
                return capture_out(fsm.cmd_advance, task)
        finally:
            self.record(https=False)

    def mr_sync(self, *args) -> str:
        self.mark()
        argv = ["artel.py", "mr-sync", *[str(a) for a in args]]
        with self.spy(), mock.patch.object(sys, "argv", argv):
            return capture_out(artel.main)

    def kill(self, task: str) -> str:
        self.record(https=False)
        self.mark()
        return capture_out(cleanup.cmd_kill, task)

    def ci_rerun(self, task: str, reason: str) -> str:
        self.mark()
        return capture_out(ci_rerun.cmd_ci_rerun, task, reason)

    # ------------------------------------------------------------ наблюдение

    def state(self, task: str) -> str:
        return store.get_task(self.conn, task)["state"]

    def mr(self, task: str) -> tuple:
        return store.mr_link(store.get_task(self.conn, task))

    def rows(self, task: str) -> list:
        return list(store.task_steps(self.conn, task))

    def new_rows(self, task: str) -> list:
        return self.rows(task)[self.marks.get(task, 0):]

    def new_journal(self, task: str) -> str:
        return "\n".join(f"{r['action']} {r['detail'] or ''}"
                         for r in self.new_rows(task))

    def cleanup_records(self, task: str) -> list:
        return [r["detail"] or "" for r in self.rows(task) if r["action"] == CLEANUP]

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.rows(task))

    def head(self, task: str) -> str:
        return self.git("-C", self.clone, "rev-parse", self.branch(task)).strip()

    def origin_has(self, branch: str) -> bool:
        return bool(self.git("--git-dir", self.bare, "for-each-ref",
                             f"refs/heads/{branch}").strip())

    def context(self, task: str, out: str = "") -> str:
        calls = "\n".join(f"{argv} {kwargs}" for argv, kwargs in self.gh.all)
        return self.note(f"\n--- вывод:\n{out}\n--- журнал:\n{self.journal(task)}"
                         f"\n--- gh (весь тест):\n{calls}\n--- отправки:\n"
                         + "\n".join(map(" ".join, self.pushes)))


def refspec_targets(argv: list) -> list:
    """Цели refspec'ов отправки: часть после `:` (или весь refspec)."""
    words = argv[argv.index(git_sub(argv)) + 1:] if git_sub(argv) in argv else []
    found = []
    for word in words:
        if word.startswith("-"):
            continue
        found.append(word.rpartition(":")[2] if ":" in word else word)
    return found


def pushes_to(pushes: list, branch: str) -> list:
    names = {branch, f"refs/heads/{branch}"}
    return [p for p in pushes if names & set(refspec_targets(p))]


@pytest.fixture
def stand(real_git):
    return Stand(real_git)


@pytest.fixture
def red_stand(real_git):
    return Stand(real_git, real_ci=True)


# ------------------------------------------------------------------- AC-6


def test_ac6_full_cycle_github_people_to_done(stand):
    """Полный цикл задачи `github` + `target-human`: черновой PR на входе в `verifying`, `approve` → `awaiting_human`, вливание людьми, `mr-sync` «влит этим MR», `--confirm` → `done`.

    Сценарий: запись `draft_mr: true`, `mr_assignee: <имя>`; задача в
    `in_dev`, ветка на сервере. `advance`: задача в `verifying`, шпион `gh`
    видел `pr create … --draft`, ссылка на MR в БД — номер PR. Переход
    `verifying → merge_gate` в путь требования 5 не входит — стенд ставит
    состояние сам. `approve` на `merge_gate`: задача в `awaiting_human`, PR
    в подделке не черновик, исполнитель — имя из записи. Люди проекта
    вливают ветку коммитом слияния; PR — `MERGED` с этим коммитом. `mr-sync
    <id>` — «влит этим MR»; `mr-sync <id> --confirm` — `done`, `closed_as`
    `merged_upstream`. За весь тест шпион `gh` не видел `pr merge`, `pr
    close`, `pr comment`, `run rerun`, `run watch`; после входа в
    `awaiting_human` пульт не отправлял ни в `base`, ни в ветку задачи.

    Ловит мутацию: пара `github` + `target-human` не добавлена в
    `SUPPORTED_PAIRS` — `approve` отказывает причиной поддержки, задача
    остаётся на `merge_gate`; гейт людей для GitHub вливает PR сам (`pr
    merge`) или отправляет в `base` — шпион видит вызов или отправку;
    черновик не снимается (`isDraft` истинно) либо исполнитель не
    назначается.
    """
    login = f"{stand.word(3)}-{stand.word(4)}"
    stand.policy.update(draft_mr="true", mr_assignee=login)
    task = stand.new_task(state="in_dev")
    number = stand.rng.randrange(1, 10 ** 5)
    stand.created_ok(task, number, draft=True)
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    created = stand.gh.seen("pr", "create")
    assert created and "--draft" in created[0], where
    assert stand.mr(task)[0] == number, where

    store.set_state(stand.conn, task, "merge_gate", "fsm",
                    expected_state="verifying", detail="стенд теста")
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == AWAITING, where
    assert stand.gh.prs[number]["isDraft"] is False, where
    assert login in [a["login"] for a in stand.gh.prs[number]["assignees"]], where
    after_awaiting = len(stand.pushes)

    sha = stand.merge_commit(task)
    stand.gh.prs[number].update(state="MERGED", mergeCommit={"oid": sha})
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert MERGED_THIS in out, where
    out = stand.mr_sync(task, "--confirm")
    where = stand.context(task, out)
    assert stand.state(task) == "done", where
    assert store.get_task(stand.conn, task)["closed_as"] == CLOSED_THIS, where

    for prefix in FORBIDDEN_GH:
        assert stand.gh.seen(*prefix, log=stand.gh.all) == [], where + f"\n{prefix}"
    later = stand.pushes[after_awaiting:]
    assert pushes_to(later, MAIN) == [], where
    assert pushes_to(later, stand.branch(task)) == [], where


def test_ac6_kill_after_send_keeps_branch_and_pr(stand):
    """`kill` задачи `github` + `target-human` в `awaiting_human` (ветка отправлена): ветка в `origin` цела, `gh pr close` не вызван.

    Сценарий: задача доведена настоящим `approve` до `awaiting_human` (PR
    открыт подделкой); `kill`. Задача `killed`, ветка задачи в голом
    `origin` есть, шпион `gh` за `kill` не видел `pr close`.

    Ловит мутацию: пара не поддержана — задача не доходит до
    `awaiting_human`; уборка закрывает PR проекта людей после отправки
    (`gh pr close`) или удаляет ветку из `origin`.
    """
    task, _number, out = stand.to_awaiting()
    where = stand.context(task, out)
    assert stand.state(task) == AWAITING, where
    out = stand.kill(task)
    where = stand.context(task, out)
    assert stand.state(task) == "killed", where
    assert stand.origin_has(stand.branch(task)), where
    assert stand.gh.seen("pr", "close") == [], where


# ------------------------------------------------------------------- AC-7


@pytest.mark.parametrize("with_run_id", [True, False], ids=["run_id", "без run_id"])
def test_ac7_trigger_rerun_refuses_people_clone_without_gh(stand, with_run_id):
    """`ci.trigger_rerun` для клона проекта `github` + `target-human` — «ре-ран CI не запущен: …», шпион `gh` пуст.

    Сценарий: задача проекта с веткой в клоне; прямой вызов
    `ci.trigger_rerun(<ветка>, repo=<клон>)` со случайным `run_id` и без
    него. Ответ начинается с «ре-ран CI не запущен: » и несёт причину после
    префикса; шпион `gh` не видел ни одного вызова.

    Ловит мутацию: отказ проекта людей стоит после поиска прогона
    (`gh api …/actions/runs`) или только на пути без `run_id` — шпион видит
    `api`/`run rerun`/`run watch`; отказ решается по хостингу
    (`ci_by_pipeline`), а не по `merged_by_project_people`.
    """
    task = stand.new_task(state="verifying")
    stand.mark()
    kwargs = {"run_id": str(stand.gh.run_id)} if with_run_id else {}
    note = ci.trigger_rerun(stand.branch(task), repo=stand.clone, **kwargs)
    where = stand.context(task, note)
    assert note.startswith(NOT_STARTED), where
    assert note[len(NOT_STARTED):].strip(), where
    assert stand.gh.calls == [], where


def test_ac7_red_ci_on_merge_gate_no_rerun(red_stand):
    """Красный CI ветки задачи `github` + `target-human` на `approve` `merge_gate`: без `run rerun`/`run watch`, `flake-rate` «повтор не запущен», «merge отклонён: », задача на гейте.

    Сценарий: `ci.branch_status` настоящий; подделка `gh` отвечает на
    `api`-чтение check-runs головы ветки упавшей проверкой, на поиск
    прогонов — упавшим прогоном (повтор нашёл бы, что перезапускать).
    `approve`: шпион не видел `run rerun` и `run watch`; в журнале — запись
    `flake-rate` с «повтор не запущен»; вывод несёт «merge отклонён: »;
    задача на `merge_gate`.

    Ловит мутацию: `trigger_rerun` не отказывает проекту людей — гейт
    перезапускает CI (`run rerun … --failed`, `run watch`), запись
    `flake-rate` — «подтверждённый красный»; пара не поддержана —
    `approve` отказывает причиной поддержки до CI, записи `flake-rate` нет.
    """
    stand = red_stand
    stand.gh.ci = "red"
    task = stand.new_task()
    number = stand.rng.randrange(1, 10 ** 5)
    stand.created_ok(task, number)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.gh.seen("run", "rerun") == [], where
    assert stand.gh.seen("run", "watch") == [], where
    flake = [r["detail"] or "" for r in stand.new_rows(task)
             if r["action"] == "flake-rate"]
    assert any(RERUN_NOT_STARTED in d for d in flake), where
    assert MERGE_REFUSED in out, where
    assert stand.state(task) == "merge_gate", where


@pytest.mark.parametrize("case", ["verifying-красный", "verifying-зависший",
                                  "не verifying"])
def test_ac7_ci_rerun_command_refuses_people_without_gh(red_stand, case):
    """`ci-rerun` задачи `github` + `target-human` с непустым новым `--reason` — отказ с «ре-ран CI не запущен: », шпион `gh` пуст.

    Сценарий по параметру: задача в `verifying` при красном CI (в журнале —
    запись статуса verifying о красном CI головы, подделка отвечает
    упавшей проверкой) либо при зависшей проверке (подделка — проверка
    `in_progress` без исхода с давним стартом), либо задача на
    `merge_gate`. `ci_rerun.cmd_ci_rerun(<id>, <случайное основание>)`:
    вывод несёт «ре-ран CI не запущен: », шпион `gh` не видел ни одного
    вызова.

    Ловит мутацию: отказ проекта людей стоит после чтения статуса
    (`ci.verifying_status` зовёт `gh api …/check-runs`) или после проверки
    состояния — вне `verifying` прежний отказ «задача в состоянии …»;
    отказ только на красном пути — путь зависшей проверки зовёт `gh api
    …/actions/jobs/<id>` и `run rerun`.
    """
    stand = red_stand
    stand.gh.ci = "stuck" if case == "verifying-зависший" else "red"
    task = stand.new_task(state="merge_gate" if case == "не verifying" else "verifying")
    if case == "verifying-красный":
        short = stand.head(task)[:8]
        store.journal(stand.conn, task, "orchestrator", fsm.VERIFYING_STATUS_ACTION,
                      f"CI коммита {short} не зелёный: tests=failure")
    reason = f"флейк {stand.word()} {stand.rng.randrange(10 ** 6)}"
    out = stand.ci_rerun(task, reason)
    where = stand.context(task, out)
    assert NOT_STARTED in out, where
    assert stand.gh.calls == [], where


def test_ac7_github_operator_trigger_rerun_keeps_failed_rerun(real_git):
    """`ci.trigger_rerun` для клона проекта `github` + `operator` — прежний вызов `gh run rerun <id> --failed`.

    Сценарий: стенд `github` + `operator`; задача с веткой в клоне;
    подделка `gh` находит упавший прогон со случайным id. Прямой вызов
    `ci.trigger_rerun(<ветка>, repo=<клон>)`: шпион видел ровно `run rerun
    <id> --failed`.

    Ловит мутацию: запрет повтора поставлен по хостингу GitHub или для
    любой внешней записи (не по `merged_by_project_people`) — `run rerun`
    не вызван, ответ «ре-ран CI не запущен».
    """
    stand = Stand(real_git, gate="operator")
    task = stand.new_task(state="verifying")
    stand.mark()
    note = ci.trigger_rerun(stand.branch(task), repo=stand.clone)
    where = stand.context(task, note)
    assert stand.gh.seen("run", "rerun") == [
        ["run", "rerun", str(stand.gh.run_id), "--failed"]], where


# ------------------------------------------------------------------- AC-9
# Критерий AC-9 эскалирован (пометка в планке задачи): тесты `kill`
# проекта людей на GitHub — после ответа Оператора.


# ------------------------------------------------------------------ AC-10


@pytest.mark.parametrize("published", [False, True], ids=["до отправки", "после отправки"])
def test_ac10_gitlab_people_kill_records_unchanged(real_git, published):
    """`kill` задачи `gitlab` + `target-human` до и после отправки: записи уборки прежние, без «PR не тронут», `gh` не вызван.

    Сценарий: стенд `gitlab` + `target-human`; задача в `in_dev` с веткой в
    `origin` — без записи «ветка отправлена» (до отправки) и с ней (после).
    `kill`: шпион `gh` не видел ни одного вызова; ни одна запись «уборка»
    не несёт «PR не тронут»; до отправки — запись с прежним исходом
    удаления ветки «ветка origin <ветка>: …»; после — прежняя запись
    «сервер проекта не тронут: ветка <ветка> отправлена», ветка в `origin`
    цела.

    Ловит мутацию: фраза «PR не тронут» пишется для любой записи проекта
    людей, а не только хостинга без конвейеров; уборка GitLab зовёт `gh`;
    исход удаления ветки до отправки или прежний текст после отправки
    пропал.
    """
    stand = Stand(real_git, forge_name="gitlab")
    task = stand.new_task(state="in_dev", published=published)
    if not published:
        stand.publish_branch(task)
    branch = stand.branch(task)
    out = stand.kill(task)
    where = stand.context(task, out)
    records = stand.cleanup_records(task)
    assert stand.state(task) == "killed", where
    assert stand.gh.calls == [], where
    assert records and all(PR_UNTOUCHED not in r for r in records), where
    if published:
        assert any(SERVER_LEFT.format(branch=branch) in r for r in records), where
        assert stand.origin_has(branch), where
    else:
        assert any(BRANCH_OUTCOME.format(branch=branch) in r for r in records), where
