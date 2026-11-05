"""Хостинг GitHub в гейте людей проекта: частичный успех открытия MR, «PR уже существует», снятие черновика и исполнитель на `approve`, черновой MR на входе в `verifying`, `mr-sync` по ответам `gh pr view`.

Группа: долгоживущий
Красен до реализации: у `forge._GitHub` нет `open_mr`/`mr_status`/`undraft_mr`/`assign_mr` — `approve` гейта мержа проекта `forge: github` + `target-human` получает «не реализовано для github» (MR не открыт, ссылки в БД нет), `mr-sync` — «неизвестно» вместо «MR не найден»/«влит этим MR»; частичного успеха (`iid` с причиной) и признака «уже существует» нет. Методы AC-16 зелены с рождения: они держат прежнее поведение (семь функций — «не реализовано для github», запись «сверка автора — после адаптера»).

Связка «команда пульта — FSM — база — git»: каждый сценарий доходит до
поведения через публичный вход (`fsm.cmd_approve`, `fsm.cmd_advance`,
`artel.main` с `sys.argv` команды `mr-sync`,
`github_adapter.ensure_forge_draft_mr`) в настоящем git песочницы
(`tests.sandbox.RealGitSandbox`): клон вымышленного проекта
(`tests.sandbox.make_project_repo`) с локальным голым `origin`, запись
проекта — в локальном слое (`targets.local_path()`), ссылка документов —
автокоммитом шага. Пара `github` + `target-human` включена подменой
`targets.SUPPORTED_PAIRS`.

`gh` — подделка `ci.gh` (`FakeGh`): пишет argv и именованные аргументы,
отвечает заготовкой сценария (код выхода, stdout, stderr); PR для `pr
view` — словарь полей сценария, `pr ready`/`pr edit` правят его. Цвет CI
ветки — подменённый `ci.branch_status` (зелёный), цвет CI base —
`ci.main_line_status`; `keychain.token` и `gitcmd.hosting_token`
подменены — связка ключей не читается. Прогон pytest у мест запуска
(`acceptance`, `two_sided`) отвечает зелёным прогоном.

Стенд (SPEC, «Материалы», «Стенд AC-3»): `url` записи на время
git-операций стенда (документы, публикация ветки) — путь голого `origin`
(белый список отправки сверяет `remote.origin.url` клона с `url` записи);
на время команды пульта, открывающей MR (`approve`, `advance`), — https-
адрес `https://localhost/<владелец>/<имя>`, разбираемый как адрес
GitHub: голова ветки и ссылка документов к этому моменту уже в `origin`,
недосланного нет, и пульт на пути к MR ничего не отправляет.

Имена, номера PR и тексты отказов — из `random`, зерно печатается и
входит в текст каждого провала.

Провалидировано временным стабом (удалён, не закоммичен): функции
`_GitHub`, сохранение ссылки при `iid` с причиной в `open_forge_mr`,
отдельная ветвь частичного успеха и эскалация по признаку «уже
существует» в `_deliver_mr`, проект в `_ready_existing_mr` — все методы
зелёные; мутации «ссылка только без причины» и «признак не читается
гейтом» краснят AC-3, AC-4 и AC-5.
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

from orchestrator import (acceptance, artel, catalog, checkpoint, ci, config,
                          fsm, github_adapter, idgen, keychain, store, targets,
                          workspace)
from orchestrator.advance_gates import two_sided
from tests.sandbox import make_project_repo

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
HEX = "0123456789abcdef"
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
MR_EXISTS = "MR ветки уже существует, ссылки в БД нет"
MR_NOT_OPENED = "MR не открыт"
DRAFT_REFUSAL = "черновой MR не открыт: "
STATE_UNKNOWN = "статус MR неизвестен"
AFTER_ADAPTER = "сверка автора — после адаптера"
NOT_FOUND = "MR не найден"
UNREAD = "не прочитан"
UNKNOWN = "неизвестно"
MERGED_THIS = "влит этим MR"
OTHER_WAY = "в базе, влит иначе"
CLOSED_THIS = "merged_upstream"
STATE = "awaiting_human"

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
      merge_gate: target-human
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: github
      url: "{url}"
      token_slot: {name}-token
{machine}"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
---

# SPEC: фикстура GitHub-MR

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
    """Подделка `ci.gh`: argv и именованные аргументы — в `calls`; ответ —
    по сценарию. `pr create` — заготовка `create`; `pr view` — `view`
    (заготовка отказа) либо JSON словаря `prs[<номер>]`; `pr ready` и `pr
    edit` — заготовки `ready`/`edit`, успех правит словарь PR."""

    def __init__(self):
        self.calls: list = []
        self.create = (1, "", "pr create вне сценария теста")
        self.view = None
        self.ready = (0, "", "")
        self.edit = (0, "", "")
        self.prs: dict = {}

    def __call__(self, *args, **kwargs):
        argv = [str(a) for a in args]
        self.calls.append((argv, dict(kwargs)))
        head = argv[:2]
        number = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else None
        if head == ["pr", "create"]:
            return subprocess.CompletedProcess(argv, *self.create)
        if head == ["pr", "view"]:
            if self.view is not None:
                return subprocess.CompletedProcess(argv, *self.view)
            if number not in self.prs:
                return subprocess.CompletedProcess(
                    argv, 1, "", "GraphQL: Could not resolve to a PullRequest "
                                 f"with the number of {number}. (repository.pullRequest)")
            return subprocess.CompletedProcess(argv, 0,
                                               json.dumps(self.prs[number]), "")
        if head == ["pr", "ready"]:
            code, out, err = self.ready
            if code == 0 and number in self.prs:
                self.prs[number]["isDraft"] = False
            return subprocess.CompletedProcess(argv, code, out, err)
        if head == ["pr", "edit"]:
            code, out, err = self.edit
            if code == 0 and number in self.prs and len(argv) > 3:
                self.prs[number]["assignees"].append(
                    {"login": argv[3].split("=", 1)[-1]})
            return subprocess.CompletedProcess(argv, code, out, err)
        return subprocess.CompletedProcess(argv, 1, "", "вызов gh вне сценария теста")

    def argvs(self) -> list:
        return [argv for argv, _kwargs in self.calls]

    def seen(self, *prefix) -> list:
        return [a for a in self.argvs() if a[:len(prefix)] == list(prefix)]


class Stand:
    """Пульт с клоном вымышленного проекта `forge: github` + `target-human`
    и локальным голым `origin`."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"proj{self.word()}"
        self.owner = f"own{self.word(4)}"
        self.https = f"https://localhost/{self.owner}/{self.ext}"
        self.gh = FakeGh()
        self.pushes: list = []
        self.policy: dict = {"draft_mr": "false"}
        self.machine = ""
        self.marks: dict = {}
        self._people = None

        def spy_run(*args, **kwargs):
            argv = args[0] if args else kwargs.get("args")
            if isinstance(argv, (list, tuple)) and argv and \
                    Path(str(argv[0])).name == "git":
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
        for patcher in (
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch.object(targets, "SUPPORTED_PAIRS",
                                  set(targets.SUPPORTED_PAIRS)
                                  | {("github", "target-human")}),
                mock.patch.object(ci, "main_line_status", main_line),
                mock.patch.object(ci, "branch_status", branch_status),
                mock.patch.object(ci, "gh", self.gh),
                mock.patch.object(keychain, "token", lambda *a, **k: "tok"),
                mock.patch("orchestrator.gitcmd.hosting_token",
                           lambda *a, **k: (None, None)),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: []),
                mock.patch.object(subprocess, "run", spy_run)):
            patcher.start()
            sb.addCleanup(patcher.stop)
        sb.add_synced_origin()
        self.clone = make_project_repo(self.ext)
        self.bare = config.PROJECTS / self.ext / "origin.git"
        self.record(https=False)
        capture_out(catalog.cmd_init)
        self.commit_to_main({"app.py": "VALUE = 1\n",
                             "conf/settings.yaml": "level: 1\n",
                             "docs/notes.md": "# Заметки\n\n- база\n"})

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def hexsha(self) -> str:
        return "".join(self.rng.choice(HEX) for _ in range(40))

    def login(self) -> str:
        return f"{self.word(3)}-{self.word(4)}"

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def git(self, *args) -> str:
        return self.sb.git(*[str(a) for a in args])

    def record(self, *, https: bool) -> None:
        """Запись проекта в локальном слое: `url` — https-адрес GitHub
        (`https`) либо путь голого `origin`; поля `policy` — `self.policy`
        (текст YAML), машинные — `self.machine`."""
        lines = "".join(f"      {key}: {value}\n"
                        for key, value in self.policy.items() if value is not None)
        url = self.https if https else str(self.bare)
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text("targets:\n" + ENTRY.format(
            name=self.ext, base=MAIN, policy=lines, url=url,
            machine=self.machine), encoding="utf-8")

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
        zones = "app.py, kod/, docs/"
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
            self.git("-C", self.clone, "push", "-q", "origin",
                     f"{branch}:refs/heads/{branch}")
            store.journal(self.conn, task, "orchestrator", SENT,
                          f"{self.head(task)} {branch}")
        return task

    def pr(self, task: str, number: int, *, draft: bool = False,
           state: str = "OPEN", **fields) -> dict:
        """PR задачи в подделке `gh` под номером `number`."""
        data = {"number": number, "url": f"{self.https}/pull/{number}",
                "title": f"MR {self.word()}", "state": state, "isDraft": draft,
                "assignees": [], "baseRefName": MAIN,
                "headRefName": self.branch(task), "headRefOid": self.head(task),
                "mergeCommit": None}
        data.update(fields)
        self.gh.prs[number] = data
        return data

    def created_ok(self, task: str, number: int) -> None:
        """`pr create` ответит адресом PR `number`, `pr view` — PR задачи."""
        self.gh.create = (0, f"{self.https}/pull/{number}\n", "")
        self.pr(task, number)

    def with_link(self, task: str, *, draft: bool = True) -> int:
        """Ссылка на MR задачи в БД и PR в подделке; номер."""
        number = self.rng.randrange(1, 10 ** 5)
        store.update_task(self.conn, task, mr_iid=number,
                          mr_url=f"{self.https}/pull/{number}")
        self.pr(task, number, draft=draft)
        return number

    def to_awaiting(self) -> tuple:
        """Задача доведена до `awaiting_human` настоящим `approve` (PR
        открывает подделка `gh`); (задача, номер PR)."""
        task = self.new_task()
        number = self.rng.randrange(1, 10 ** 5)
        self.created_ok(task, number)
        self.fork_at = self.main_sha()
        out = self.approve(task)
        assert self.state(task) == STATE, self.note(
            f"стенд: задача не дошла до awaiting_human\n{self.context(task, out)}")
        self.confirmed = self.head(task)
        return task, number

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

    def people(self) -> Path:
        if self._people is None:
            self._people = self.clone.parent.parent / f"people-{self.word()}"
            self.git("clone", "-q", self.bare, self._people)
        return self._people

    def pgit(self, *args) -> str:
        return self.git("-C", self.people(), "-c", "user.name=ljudi",
                        "-c", "user.email=ljudi@example.invalid", *args)

    def p_sync(self) -> None:
        self.pgit("fetch", "-q", "origin")
        self.pgit("checkout", "-q", "-B", MAIN, f"origin/{MAIN}")

    def p_commit(self, files: dict, message: str) -> str:
        for rel, text in files.items():
            path = self.people() / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.pgit("add", "-A")
        self.pgit("commit", "-q", "-m", message)
        return self.pgit("rev-parse", "HEAD").strip()

    def p_push_main(self) -> None:
        self.pgit("push", "-q", "origin", f"{MAIN}:{MAIN}")

    def foreign_main(self) -> None:
        self.p_sync()
        self.p_commit({f"chuzhoe/{self.word()}.py": f"C = {self.seed}\n"},
                      f"chuzhaya pravka {self.word()}")
        self.p_push_main()

    def merge_commit(self, task: str) -> str:
        """Вливание коммитом слияния; sha слияния в `origin/<base>`."""
        self.p_sync()
        self.pgit("merge", "-q", "--no-ff", "-m", f"Merge {self.word()}",
                  f"origin/{self.branch(task)}")
        sha = self.pgit("rev-parse", "HEAD").strip()
        self.p_push_main()
        return sha

    def squash(self, task: str) -> str:
        """Вливание сжатием одним коммитом; его sha."""
        self.p_sync()
        self.pgit("merge", "-q", "--squash", f"origin/{self.branch(task)}")
        sha = self.p_commit({}, f"squash {self.word()}")
        self.p_push_main()
        return sha

    def rebase_merge(self, task: str) -> str:
        """Вливание перебазированием поверх ушедшего вперёд `base`; новая
        голова ветки, на которую перемотан `base`."""
        self.foreign_main()
        self.p_sync()
        self.pgit("checkout", "-q", "-B", f"rb-{self.word()}",
                  f"origin/{self.branch(task)}")
        self.pgit("rebase", "-q", MAIN)
        head = self.pgit("rev-parse", "HEAD").strip()
        self.pgit("push", "-q", "-f", "origin",
                  f"HEAD:refs/heads/{self.branch(task)}")
        self.pgit("checkout", "-q", MAIN)
        self.pgit("merge", "-q", "--ff-only", head)
        self.p_push_main()
        return head

    def cherry_all(self, task: str) -> None:
        """Коммиты задачи перенесены в `base` поверх чужого коммита (MR
        закрыт без вливания)."""
        self.foreign_main()
        self.p_sync()
        commits = self.git("-C", self.clone, "rev-list", "--reverse",
                           f"{self.fork_at}..{self.confirmed}").split()
        self.pgit("fetch", "-q", "origin", self.branch(task))
        for sha in commits:
            self.pgit("cherry-pick", "--allow-empty", sha)
        self.p_push_main()

    # ------------------------------------------------------------ команды

    @contextlib.contextmanager
    def spy(self):
        spy = PytestSpy()
        with mock.patch.object(acceptance, "subprocess", spy), \
                mock.patch.object(two_sided, "subprocess", spy):
            yield spy

    def mark(self) -> None:
        self.pushes.clear()
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
        """`artel.py mr-sync <args>` через `artel.main`."""
        self.mark()
        argv = ["artel.py", "mr-sync", *[str(a) for a in args]]
        with self.spy(), mock.patch.object(sys, "argv", argv):
            return capture_out(artel.main)

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

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.rows(task))

    def head(self, task: str) -> str:
        return self.git("-C", self.clone, "rev-parse", self.branch(task)).strip()

    def context(self, task: str, out: str = "") -> str:
        calls = "\n".join(f"{argv} {kwargs}" for argv, kwargs in self.gh.calls)
        return self.note(f"\n--- вывод:\n{out}\n--- журнал:\n{self.journal(task)}"
                         f"\n--- gh:\n{calls}\n--- отправки:\n"
                         + "\n".join(map(" ".join, self.pushes)))


@pytest.fixture
def stand(real_git):
    return Stand(real_git)


# ------------------------------------------------------------------- AC-3


def test_ac3_partial_success_on_merge_gate_keeps_link(stand):
    """Частичный успех на гейте мержа: PR открыт, чтение отказало — ссылка в БД, задача на гейте, без «MR открыт» и без «MR не открыт»; повторный `approve` не эскалирует.

    Сценарий: задача на `merge_gate`, ссылки на MR нет; `pr create` отвечает
    адресом `<url записи>/pull/<n>`, `pr view` — кодом 1 со случайным текстом.
    После `approve`: ссылка на MR задачи — (n, адрес), задача на
    `merge_gate`, текст отказа чтения — в журнале, записи «MR открыт» нет,
    ни одна запись журнала этого `approve` не несёт «MR не открыт». Второй
    `approve` (чтение по-прежнему отказывает): задача не в `escalated`, в
    журнале нет «MR ветки уже существует, ссылки в БД нет».

    Ловит мутацию: `open_forge_mr` сохраняет ссылку только при результате
    без причины (ссылки нет, повторный `approve` открыл бы второй PR и
    получил «уже существует» — эскалация); частичный успех журналируется
    как «MR открыт» или прежним «MR не открыт: …»; задача уходит в
    `awaiting_human` при причине.
    """
    task = stand.new_task()
    number = stand.rng.randrange(1, 10 ** 5)
    stand.gh.create = (0, f"{stand.https}/pull/{number}\n", "")
    why = f"HTTP 502: Bad Gateway {stand.word()}"
    stand.gh.view = (1, "", why)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.gh.seen("pr", "create"), where
    assert stand.mr(task) == (number, f"{stand.https}/pull/{number}"), where
    assert stand.state(task) == "merge_gate", where
    assert why in stand.new_journal(task), where
    assert github_adapter.MR_OPENED_ACTION not in [
        r["action"] for r in stand.new_rows(task)], where
    assert MR_NOT_OPENED not in stand.new_journal(task), where
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == "merge_gate", where
    assert MR_EXISTS not in stand.journal(task), where


# ------------------------------------------------------------------- AC-4


def test_ac4_partial_success_on_verifying_entry(stand):
    """Частичный успех чернового MR на входе в `verifying`: причина, ссылка в БД, без «MR открыт», прежний текст отказа; следующий вызов не открывает PR снова.

    Сценарий: запись `draft_mr: true`, задача в `in_dev`, ветка на сервере;
    `pr create` — адрес `<url записи>/pull/<n>`, `pr view` — отказ. `advance`:
    задача в `in_dev`, текст отказа — `черновой MR не открыт: <причина>`,
    ссылка на MR в БД — (n, адрес), записи «MR открыт» нет. Затем
    `ensure_forge_draft_mr` той же задачи: `pr create` не вызван, ответ —
    без причины (не «уже существует»).

    Ловит мутацию: ссылка при частичном успехе не сохраняется (второй вызов
    снова зовёт `pr create`); текст отказа черновика сменён правилом
    гейта мержа; частичный успех пишет «MR открыт».
    """
    stand.policy["draft_mr"] = "true"
    task = stand.new_task(state="in_dev")
    number = stand.rng.randrange(1, 10 ** 5)
    stand.gh.create = (0, f"{stand.https}/pull/{number}\n", "")
    why = f"HTTP 502: Bad Gateway {stand.word()}"
    stand.gh.view = (1, "", why)
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "in_dev", where
    assert DRAFT_REFUSAL in out + stand.new_journal(task), where
    assert stand.mr(task) == (number, f"{stand.https}/pull/{number}"), where
    assert github_adapter.MR_OPENED_ACTION not in [
        r["action"] for r in stand.rows(task)], where
    stand.record(https=True)
    stand.mark()
    reason = github_adapter.ensure_forge_draft_mr(
        stand.conn, task, store.get_task(stand.conn, task))
    where = stand.context(task, str(reason))
    assert stand.gh.seen("pr", "create") == [], where
    assert reason is None, where


# ------------------------------------------------------------------- AC-5


@pytest.mark.parametrize("kind", ["gh", "422"])
def test_ac5_already_exists_escalates_without_link(stand, kind):
    """`pr create` «уже существует» (проверка `gh` с адресом PR, отказ сервера 422) — после `approve` ссылки нет, задача в эскалации «MR ветки уже существует, ссылки в БД нет».

    Сценарий: задача на `merge_gate`, ссылки нет; `pr create` — код 1,
    stderr `a pull request for branch "<ветка>" into branch "<база>"
    already exists:` с адресом `<url записи>/pull/<n>` либо `A pull request
    already exists`. `approve`: задача `escalated`, в журнале — «MR ветки
    уже существует, ссылки в БД нет», ссылка на MR пуста.

    Ловит мутацию: признак «уже существует» не читается гейтом (задача на
    гейте с прежним отказом); адрес из stderr сохранён ссылкой; эскалация
    только по коду 409 GitLab.
    """
    task = stand.new_task()
    number = stand.rng.randrange(1, 10 ** 5)
    branch = stand.branch(task)
    if kind == "gh":
        stderr = (f'a pull request for branch "{branch}" into branch "{MAIN}" '
                  f'already exists:\n{stand.https}/pull/{number}\n')
    else:
        stderr = ("pull request create failed: GraphQL: A pull request already "
                  f"exists for {stand.owner}:{branch}. (createPullRequest)\n")
    stand.gh.create = (1, "", stderr)
    stand.pr(task, number)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == "escalated", where
    assert MR_EXISTS in stand.new_journal(task), where
    assert stand.mr(task) == (None, None), where


# ------------------------------------------------------------------- AC-6


def test_ac6_other_create_refusal_keeps_gate(stand):
    """`pr create` отказал иным текстом — задача на гейте с причиной в журнале, ссылки нет, эскалации нет.

    Сценарий: задача на `merge_gate`, ссылки нет; `pr create` — код 1 со
    случайным отказом (нет коммитов, нет прав). `approve`: шпион видел `pr
    create`, задача на `merge_gate` (не `escalated`), текст отказа — в
    журнале, ссылка пуста.

    Ловит мутацию: любой отказ `pr create` эскалирует «уже существует»;
    отказ не проверяется (задача в `awaiting_human`); отказ без причины в
    журнале.
    """
    task = stand.new_task()
    why = stand.rng.choice([
        f"pull request create failed: GraphQL: No commits between {MAIN} and "
        f"{stand.branch(task)} (createPullRequest) {stand.word()}",
        f"GraphQL: {stand.word()} does not have the correct permissions to "
        f"execute `CreatePullRequest` {stand.word()}"])
    stand.gh.create = (1, "", why + "\n")
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.gh.seen("pr", "create"), where
    assert stand.state(task) == "merge_gate", where
    assert why in stand.new_journal(task), where
    assert stand.mr(task) == (None, None), where


# ------------------------------------------------------------------- AC-8


def test_ac8_unknown_pr_state_refuses_approve(stand):
    """`pr view` со `state` вне трёх известных — `approve` отказывает «статус MR неизвестен».

    Сценарий: задача на `merge_gate` со ссылкой на MR; `pr view` отдаёт PR
    со случайным `state` вне `OPEN`/`MERGED`/`CLOSED`. `approve`: шпион видел
    `pr view`, задача на `merge_gate`, в выводе или журнале — «статус MR
    неизвестен».

    Ловит мутацию: неизвестное `state` сопоставляется с `opened` (гейт идёт
    дальше снимать черновик) или пустой строкой с иным отказом.
    """
    task = stand.new_task()
    number = stand.with_link(task)
    stand.gh.prs[number]["state"] = stand.rng.choice(["LOCKED", "DRAFT", "QUEUED"])
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.gh.seen("pr", "view"), where
    assert stand.state(task) == "merge_gate", where
    assert STATE_UNKNOWN in out + stand.new_journal(task), where


# ------------------------------------------------------------------- AC-9


@pytest.mark.parametrize("case", ["404", "код 4", "код 2", "репозиторий",
                                  "авторизация", "сеть", "без baseRefName"])
def test_ac9_mr_sync_not_found_only_for_code1_pull_request(stand, case):
    """`mr-sync`: «MR не найден» — только код 1 и `Could not resolve to a PullRequest`; та же подстрока при кодах 4 и 2, репозиторий, авторизация, сеть — «не прочитан»; без `baseRefName` — «неизвестно».

    Сценарий: задача доведена до `awaiting_human` настоящим `approve`; затем
    `pr view` отвечает по параметру. «404»: код 1 и `GraphQL: Could not
    resolve to a PullRequest …` — `mr-sync` печатает «MR не найден»,
    `mr-sync --confirm` отказывает (задача в `awaiting_human`). Та же
    подстрока при коде 4 и 2, `Could not resolve to a Repository …`, код 4
    авторизации, сбой сети — вывод несёт «не прочитан», не «MR не найден».
    PR без `baseRefName` — вывод несёт «неизвестно».

    Ловит мутацию: «не найден» по одной подстроке без кода выхода (код 4 и 2
    дают «MR не найден»); отсутствие репозитория или сбой сети названы
    «не найден»; `baseRefName` по умолчанию — `base` проекта (итог не
    «неизвестно»).
    """
    task, number = stand.to_awaiting()
    pr_text = (f"GraphQL: Could not resolve to a PullRequest with the number "
               f"of {number}. (repository.pullRequest)")
    answers = {
        "404": (1, "", pr_text), "код 4": (4, "", pr_text),
        "код 2": (2, "", pr_text),
        "репозиторий": (1, "", f"GraphQL: Could not resolve to a Repository "
                               f"with the name '{stand.owner}/{stand.ext}'. "
                               f"(repository)"),
        "авторизация": (4, "", "To get started with GitHub CLI, please run:  "
                               "gh auth login"),
        "сеть": (1, "", "error connecting to api.localhost\ncheck your "
                        "internet connection")}
    if case == "без baseRefName":
        del stand.gh.prs[number]["baseRefName"]
    else:
        stand.gh.view = answers[case]
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert stand.gh.seen("pr", "view", str(number)), where
    if case == "404":
        assert NOT_FOUND in out, where
        out = stand.mr_sync(task, "--confirm")
        where = stand.context(task, out)
        assert stand.state(task) == STATE, where
        return
    assert NOT_FOUND not in out, where
    if case == "без baseRefName":
        assert UNKNOWN in out, where
        return
    assert UNREAD in out, where


# ------------------------------------------------------------------ AC-10


@pytest.mark.parametrize("way", ["слияние", "сжатие", "перебазирование"])
def test_ac10_mr_sync_merged_by_this_pr_confirm_done(stand, way):
    """`mr-sync`: PR влит коммитом слияния, сжатием или перебазированием, `state: MERGED` и `mergeCommit.oid` в `origin/<base>` — «влит этим MR»; `--confirm` — `done` с `merged_upstream`.

    Сценарий: задача в `awaiting_human` (настоящий `approve`, PR открыт
    подделкой); люди проекта вливают ветку git-командами способом по
    параметру; ответ `pr view` — `state: MERGED`, `mergeCommit.oid` —
    получившийся коммит в `origin/<base>`. `mr-sync <id>`: вывод несёт
    «влит этим MR»; `mr-sync <id> --confirm`: задача `done`, `closed_as` —
    `merged_upstream`.

    Ловит мутацию: `merge_commit_sha` не заполняется из `mergeCommit.oid`
    (признак (а) не срабатывает — итог «в базе, влит иначе» или иной);
    `MERGED` не сопоставлен с `merged`.
    """
    task, number = stand.to_awaiting()
    sha = {"слияние": stand.merge_commit, "сжатие": stand.squash,
           "перебазирование": stand.rebase_merge}[way](task)
    stand.gh.prs[number].update(state="MERGED", mergeCommit={"oid": sha})
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert MERGED_THIS in out, where
    out = stand.mr_sync(task, "--confirm")
    where = stand.context(task, out)
    assert stand.state(task) == "done", where
    assert store.get_task(stand.conn, task)["closed_as"] == CLOSED_THIS, where


def test_ac10_mr_sync_closed_pr_change_in_base_other_way(stand):
    """`mr-sync`: PR закрыт (`CLOSED`), правка внесена в `base` переносом коммитов — «в базе, влит иначе».

    Сценарий: задача в `awaiting_human`; люди переносят коммиты задачи в
    `base` поверх чужого коммита; ответ `pr view` — `state: CLOSED`,
    `mergeCommit: null`. `mr-sync <id>`: вывод несёт «в базе, влит иначе».

    Ловит мутацию: `CLOSED` сопоставлен с `merged` (итог «влит этим MR»
    без коммита вливания) либо отдан как есть (итог иной).
    """
    task, number = stand.to_awaiting()
    stand.cherry_all(task)
    stand.gh.prs[number].update(state="CLOSED", mergeCommit=None)
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert OTHER_WAY in out, where


# ------------------------------------------------------------------ AC-11


def test_ac11_ready_refusal_keeps_task_on_gate(stand):
    """Отказ `pr ready` у черновика по ссылке из БД — `_ready_existing_mr` оставляет задачу на гейте.

    Сценарий: задача на `merge_gate` со ссылкой на MR-черновик; `pr ready`
    — код 1 со случайным текстом. `approve`: шпион видел `pr ready <n>` с
    `repo` — `url` записи, задача на `merge_gate`, текст отказа — в выводе
    или журнале.

    Ловит мутацию: отказ `pr ready` не проверяется — задача в
    `awaiting_human` с черновиком.
    """
    task = stand.new_task()
    number = stand.with_link(task, draft=True)
    why = f"GraphQL: отказ снятия черновика {stand.word()}"
    stand.gh.ready = (1, "", why)
    out = stand.approve(task)
    where = stand.context(task, out)
    ready = [(a, k) for a, k in stand.gh.calls if a[:3] == ["pr", "ready", str(number)]]
    assert ready, where
    assert all(k.get("repo") == stand.https for _a, k in ready), where
    assert stand.state(task) == "merge_gate", where
    assert why in out + stand.new_journal(task), where


# ------------------------------------------------------------------ AC-12


def test_ac12_edit_refusal_keeps_task_on_gate(stand):
    """Отказ `pr edit` при назначении исполнителя — задача на гейте с причиной.

    Сценарий: запись `mr_assignee: alice`, задача на `merge_gate` со ссылкой
    на MR-черновик; `pr ready` успешен, `pr edit` — код 1 со случайным
    текстом. `approve`: шпион видел `pr edit <n> --add-assignee=alice`,
    задача на `merge_gate`, текст отказа — в выводе или журнале.

    Ловит мутацию: отказ `pr edit` не проверяется (задача в
    `awaiting_human` без исполнителя); исполнитель по имени для GitHub не
    назначается вовсе (`pr edit` не зван).
    """
    stand.policy["mr_assignee"] = "alice"
    task = stand.new_task()
    number = stand.with_link(task, draft=True)
    why = f"could not add assignee {stand.word()}"
    stand.gh.edit = (1, "", why)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.gh.seen("pr", "edit", str(number), "--add-assignee=alice"), where
    assert stand.state(task) == "merge_gate", where
    assert why in out + stand.new_journal(task), where


# ------------------------------------------------------------------ AC-15


def test_ac15_existing_pr_gets_add_assignee_by_name(stand):
    """GitHub и `mr_assignee: alice` на гейте с ссылкой — `pr edit <n> --add-assignee=alice`, задача в `awaiting_human`.

    Сценарий: запись `mr_assignee: alice`, задача на `merge_gate` со ссылкой
    на MR-черновик; `pr ready` и `pr edit` успешны. `approve`: шпион видел
    ровно `pr edit <n> --add-assignee=alice` с `repo` — `url` записи, задача
    в `awaiting_human`.

    Ловит мутацию: `_ready_existing_mr` зовёт `mr_assignee` без проекта
    (имя не принято — `pr edit` не зван, запись «не числовой id»).
    """
    stand.policy["mr_assignee"] = "alice"
    task = stand.new_task()
    number = stand.with_link(task, draft=True)
    out = stand.approve(task)
    where = stand.context(task, out)
    edit = [(a, k) for a, k in stand.gh.calls if a[:2] == ["pr", "edit"]]
    assert [a for a, _k in edit] == [
        ["pr", "edit", str(number), "--add-assignee=alice"]], where
    assert edit[0][1].get("repo") == stand.https, where
    assert stand.state(task) == STATE, where


# ------------------------------------------------------------------ AC-16


def test_ac16_author_check_record_after_adapter(stand):
    """Сверка автора для `forge: github` — прежняя запись «сверка автора — после адаптера», `gh` не зван ради `token_user`.

    Сценарий: запись с `commit_author`, `draft_mr: false`, задача в `in_dev`
    с коммитами, ветка ни разу не отправлена. `advance`: в журнале задачи —
    «сверка автора — после адаптера», шпион `gh` не видел ни одного `api`.

    Ловит мутацию: реализация GitHub получила `token_user` (запись пропуска
    исчезла, сверка идёт по `gh api user`).
    """
    stand.machine = (f"      commit_author:\n"
                     f"        name: avtor{stand.word(4)}\n"
                     f"        email: avtor@example.invalid\n")
    task = stand.new_task(state="in_dev", published=False)
    stand.mark()
    with stand.spy():
        out = capture_out(fsm.cmd_advance, task)
    where = stand.context(task, out)
    assert AFTER_ADAPTER in stand.journal(task), where
    assert not stand.gh.seen("api"), where
