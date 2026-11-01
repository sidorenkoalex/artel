"""Команда `mr-sync`: сверка MR и нахождения правки в `base`, закрытие `done` по `--confirm`, инциденты на `approve` и в сверке, показ итога.

Группа: долгоживущий
Красен до реализации: команды `mr-sync` нет — `artel.main` выходит «Неизвестная команда mr-sync», итога сверки нет ни в выводе, ни в журнале, `--confirm` не закрывает задачу; `approve` гейта мержа не читает статус MR и не сверяет голову ветки на сервере с последней своей отправкой — снимает черновик и переводит задачу в `awaiting_human`; переход в `awaiting_human` не записывает точку ответвления.

Связка «команда пульта — FSM — база — git»: каждый сценарий доходит до
поведения через публичный вход (`artel.main` с `sys.argv` команды
`mr-sync`, `fsm.cmd_approve`, `answer.cmd_answer`, `catalog.cmd_status`,
`board.build_model`) в настоящем git песочницы
(`tests.sandbox.RealGitSandbox`): клон внешнего проекта
(`tests.sandbox.make_project_repo`) с bare `origin`, запись проекта — в
локальном слое (`targets.local_path()`). Поддержка `target-human` и
`gitlab` — подменой `targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES`
(SPEC, «Критерии приёмки»). Задача доходит до `awaiting_human` настоящим
`approve` гейта мержа (MR открывает подделка хостинга).

Люди проекта действуют в отдельном клоне того же bare `origin`: вливают
ветку задачи коммитом слияния, сжатием вместе с чужой правкой, переносом
коммитов (cherry-pick) или перебазированием, правят `base` после
вливания, кладут чужой коммит в ветку задачи, удаляют её на сервере.

Хостинг подменён целиком реестром `forge.IMPLEMENTATIONS` (ключ записи
`gitlab`): подделка записывает каждый вызов и отвечает на `mr_status`
ответом сценария (статус MR, `target_branch`, `sha`, `merge_commit_sha`,
`squash_commit_sha`) либо отказом с причиной. Отправки и прочие вызовы
git наблюдаются обёрткой `subprocess.run`, которая зовёт настоящий
`subprocess.run`.

«MR не найден» разыгрывается задачей без ссылки на MR в БД (`mr_iid`
пуст): ответ хостинга 404 — это отказ `forge`, а он по строке 1 таблицы
итогов SPEC даёт «неизвестно».

Имена, файлы задачи и причины отказа — из `random`, зерно печатается и
входит в текст каждого провала.

Провалидировано временным стабом (удалён, не закоммичен): поля
`MergeRequest`, запись точки ответвления на переходе в `awaiting_human`,
инциденты на `approve` (статус MR, чужой коммит), принятая голова при
возврате из эскалации, модуль сверки с таблицей итогов, `--confirm`
(сверка ссылки документов, `done`, `closed_as`, коммит закрытия, уборка
рабочей копии) и показ итога в `status`/доске — все методы зелёные;
мутации «точка пересчитывается в сверке», «принятая голова не читается»,
«`--confirm` без `--by-content` по (в)», «пометка ставится всегда»,
«статус merged сам даёт «влит этим MR»» краснят свои методы.
"""
import contextlib
import io
import os
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (acceptance, answer, artel, board, catalog,
                          checkpoint, ci, config, forge, fsm, idgen, keychain,
                          merge_after, store, targets, workspace, zone_lock)
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
SENT = "ветка отправлена:"
PUSH_SUBCOMMANDS = ("push", "send-pack")
# Вызовы `forge`, меняющие MR (SPEC, требование 4: «ни вызовов `forge`,
# меняющих MR»).
MR_WRITES = ("open_mr", "undraft_mr", "assign_mr")
STATE = "awaiting_human"
MAIN = config.MAIN_BRANCH

# Итоги сверки — тексты таблицы требования 3 SPEC.
MERGED_THIS = "влит этим MR"
CHANGED_AFTER = "после вливания файлы менялись"
OTHER_WAY = "в базе, влит иначе"
PARTIAL = "в базе частично"
ABSENT = "нет в базе"
NOT_FOUND = "MR не найден"
RETARGETED = "MR переведён на другую ветку"
UNKNOWN = "неизвестно"
BY_CONTENT = "по содержимому"
CLOSED_THIS = "merged_upstream"
CLOSED_OTHER = "merged_upstream_other"
# Подсказка отказа `--confirm` (требование 4: `kill`, новая задача,
# ожидание) — хотя бы одно из этих слов.
CONFIRM_HINT_WORDS = ("kill", "нов", "ожид", "жд")
# Столбцы задачи, которые сверка без `--confirm` не меняет (AC-16).
KEPT_COLUMNS = ("state", "branch", "target", "zones", "mr_iid", "mr_url",
                "closed_as", "escalated_from", "fixed_sha", "merge_after",
                "tests_locked_sha", "title")

ENTRY = """  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
    policy:
      no_paths: []
      project_skills: []
      merge_gate: {gate}
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: gitlab
      url: https://localhost/grp/{name}
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

# SPEC: фикстура сверки MR

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

REJECT_DOCS_REFS = ("#!/bin/sh\n"
                    "while read old new ref; do\n"
                    "  case \"$ref\" in refs/artifacts/*) exit 1;; esac\n"
                    "done\n"
                    "exit 0\n")


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


class FakeForge:
    """Подделка реализации хостинга `gitlab` в реестре `forge.IMPLEMENTATIONS`:
    каждый вызов — в `calls`; `mr_status` отвечает словарём `replies[iid]`
    (поля `forge.MergeRequest`), `fail` — имя функции → причина отказа."""

    CI_BY_PIPELINE = True

    def __init__(self, stand):
        self.stand = stand
        self.calls: list = []
        self.fail: dict = {}
        self.replies: dict = {}
        self.opened: list = []

    def _record(self, name: str, args: tuple) -> None:
        self.calls.append((name, args))

    def pipeline_status(self, target, sha):
        self._record("pipeline_status", (target, sha))
        return forge.PipelineStatus(forge.GREEN, "", [forge.Job("unit", "success")])

    def open_mr(self, target, branch, base, title, body, draft, assignee):
        self._record("open_mr", (target, branch, base, title, body, draft,
                                 assignee))
        iid = self.stand.rng.randrange(100, 10 ** 6)
        url = f"https://localhost/grp/{target}/-/merge_requests/{iid}"
        self.opened.append((iid, url))
        return forge.MergeRequest(iid=iid, url=url, title=title, state="opened",
                                  draft=bool(draft))

    def undraft_mr(self, target, mr):
        self._record("undraft_mr", (target, mr))
        return forge.MergeRequest(iid=mr, state="opened", draft=False)

    def assign_mr(self, target, mr, assignee):
        self._record("assign_mr", (target, mr, assignee))
        return forge.MergeRequest(iid=mr, state="opened", assignee=str(assignee))

    def mr_status(self, target, mr):
        self._record("mr_status", (target, mr))
        if "mr_status" in self.fail:
            return forge.MergeRequest(reason=self.fail["mr_status"])
        return forge.MergeRequest(**self.replies[mr])

    def __getattr__(self, name):
        if name.startswith("__") or name not in forge.RESULT_TYPES:
            raise AttributeError(name)

        def other(*args):
            self._record(name, args)
            return forge.RESULT_TYPES[name](
                reason=f"подделка хостинга: {name} не отвечает")
        return other

    def names(self) -> list:
        return [name for name, _args in self.calls]


class Stand:
    """Пульт с клоном внешнего проекта `target-human` (и вторым проектом),
    bare `origin` и клоном «людей проекта»."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"proj{self.word()}"
        self.other = f"drug{self.word()}"
        self.pushes: list = []
        self.fake = FakeForge(self)
        self.marks: dict = {}
        self.fork_at: dict = {}
        self.confirmed: dict = {}
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

        for name in IDENTITY:
            os.environ.pop(name, None)
        for patcher in (
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch.object(targets, "SUPPORTED_FORGES",
                                  ("github", "gitlab")),
                mock.patch.object(targets, "SUPPORTED_MERGE_GATES",
                                  ("operator", "target-human")),
                mock.patch.dict(forge.IMPLEMENTATIONS, {"gitlab": self.fake}),
                mock.patch.object(ci, "main_line_status", main_line),
                mock.patch.object(ci, "gh", lambda *a, **k:
                                  subprocess.CompletedProcess(list(a), 0, "", "")),
                mock.patch.object(keychain, "token", lambda *a, **k: "tok"),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: []),
                mock.patch.object(subprocess, "run", spy_run)):
            patcher.start()
            sb.addCleanup(patcher.stop)
        sb.add_synced_origin()
        self.clone = make_project_repo(self.ext)
        make_project_repo(self.other)
        self.bare = config.PROJECTS / self.ext / "origin.git"
        self.record()
        capture_out(catalog.cmd_init)
        self.commit_to_main({"app.py": "VALUE = 1\n",
                             "docs/notes.md": "# Заметки\n\n- база\n"})

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def hexsha(self) -> str:
        return "".join(self.rng.choice(HEX) for _ in range(40))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def git(self, *args) -> str:
        return self.sb.git(*[str(a) for a in args])

    def record(self, other_gate: str = "operator", **policy) -> None:
        """Записи своего проекта (`target-human`) и второго проекта
        (`other_gate`) в локальном слое; `policy` — поля раздела `policy`
        своего проекта (значение — текст YAML)."""
        policy.setdefault("draft_mr", "false")
        lines = "".join(f"      {key}: {value}\n" for key, value in policy.items()
                        if value is not None)
        text = "targets:\n"
        text += ENTRY.format(name=self.ext, base=MAIN, gate="target-human",
                             policy=lines)
        text += ENTRY.format(name=self.other, base=MAIN, gate=other_gate,
                             policy="      draft_mr: false\n")
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(text, encoding="utf-8")

    def commit_to_main(self, files: dict) -> str:
        """Коммит в основную ветку проекта клоном пульта и отправка в `origin`."""
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

    def new_task(self, state: str = "merge_gate", commits: int = 2) -> str:
        """Задача проекта: `commits` коммитов кода в ветке (каждый — свой
        новый файл), SPEC/PLAN/планка в ссылке документов, лок планки,
        ветка на сервере с записью «ветка отправлена»."""
        task = idgen.new_task_id()
        branch = f"task/{task.lower()}-{self.word()}"
        zones = "app.py, kod/, docs/"
        store.insert_task(self.conn, task, f"Фикстура {self.word()}", state,
                          branch, self.ext, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task, zones=zones)
        wt, error = workspace.ensure(task, branch)
        assert error is None, self.note(f"рабочая копия не заведена: {error}")
        for _ in range(commits):
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
        self.git("-C", self.clone, "push", "-q", "origin",
                 f"{branch}:refs/heads/{branch}")
        store.journal(self.conn, task, "orchestrator", SENT,
                      f"{self.head(task)} {branch}")
        return task

    def to_awaiting(self, commits: int = 2) -> str:
        """Задача доведена до `awaiting_human` настоящим `approve` гейта
        мержа (MR открывает подделка); ответ `mr_status` по умолчанию —
        открытый MR головы ветки в `base`."""
        task = self.new_task(commits=commits)
        self.fork_at[task] = self.main_sha()
        out = self.approve(task)
        assert self.state(task) == STATE, self.note(
            f"стенд: задача не дошла до awaiting_human\n{self.context(task, out)}")
        iid, url = self.mr(task)
        self.confirmed[task] = self.head(task)
        self.fake.replies[iid] = dict(
            iid=iid, url=url, title=f"MR {self.word()}", state="opened",
            draft=False, target_branch=MAIN, source_branch=self.branch(task),
            sha=self.head(task))
        return task

    def ghost(self, state: str, project: str | None = None,
              zones: str | None = None) -> str:
        """Задача прямо в БД: состояние `state`, проект `project` (по
        умолчанию свой), ссылка на MR."""
        task = idgen.new_task_id()
        branch = f"task/{task.lower()}-{self.word()}"
        store.insert_task(self.conn, task, f"Сосед {self.word()}", state, branch,
                          project or self.ext, config.DEFAULT_BUDGET_USD)
        iid = self.rng.randrange(100, 10 ** 6)
        store.update_task(self.conn, task, mr_iid=iid,
                          mr_url=f"https://localhost/mr/{iid}")
        if zones is not None:
            store.update_task(self.conn, task, zones=zones)
        self.fake.replies[iid] = dict(iid=iid, state="opened", draft=False,
                                      target_branch=MAIN, source_branch=branch,
                                      sha=self.hexsha())
        return task

    def iid(self, task: str) -> int:
        return self.mr(task)[0]

    def reply(self, task: str, **fields) -> None:
        """Правка ответа `mr_status` для MR задачи."""
        self.fake.replies[self.iid(task)].update(fields)

    def branch(self, task: str) -> str:
        return store.get_task(self.conn, task)["branch"]

    def wt(self, task: str) -> Path:
        return workspace.path(task, self.ext)

    def docs_dir(self, task: str) -> Path:
        return config.PROJECTS / self.ext / "tasks" / task

    def write_docs(self, task: str, files: dict, role: str = "developer") -> str:
        docs = self.docs_dir(task)
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

    def task_files(self, task: str) -> list:
        """Файлы диффа задачи от точки ответвления до подтверждённой головы."""
        return self.git("-C", self.clone, "diff", "--name-only",
                        self.fork_at[task], self.confirmed[task]).split()

    def task_commits(self, task: str) -> list:
        return self.git("-C", self.clone, "rev-list", "--reverse",
                        f"{self.fork_at[task]}..{self.confirmed[task]}").split()

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

    def p_push_main(self) -> str:
        self.pgit("push", "-q", "origin", f"{MAIN}:{MAIN}")
        return self.main_sha()

    def foreign_main(self) -> str:
        """Чужой коммит в `base` на сервере."""
        self.p_sync()
        self.p_commit({f"chuzhoe/{self.word()}.py": f"C = {self.seed}\n"},
                      f"chuzhaya pravka {self.word()}")
        return self.p_push_main()

    def merge_commit(self, task: str) -> str:
        """Люди проекта вливают ветку задачи коммитом слияния; sha слияния."""
        self.p_sync()
        self.pgit("merge", "-q", "--no-ff", "-m", f"Merge {self.word()}",
                  f"origin/{self.branch(task)}")
        merge = self.pgit("rev-parse", "HEAD").strip()
        self.p_push_main()
        return merge

    def squash_with_other(self, task: str) -> str:
        """Правка задачи влита сжатием одним коммитом вместе с чужой правкой."""
        self.p_sync()
        self.pgit("merge", "-q", "--squash", f"origin/{self.branch(task)}")
        sha = self.p_commit({f"chuzhoe/{self.word()}.py": f"S = {self.seed}\n"},
                            f"squash {self.word()}")
        self.p_push_main()
        return sha

    def cherry(self, task: str, count: int | None = None) -> list:
        """Коммиты задачи (первые `count`) перенесены в другую ветку и
        влиты в `base` поверх чужого коммита; sha перенесённых коммитов."""
        self.foreign_main()
        self.p_sync()
        commits = self.task_commits(task)[:count]
        self.pgit("fetch", "-q", "origin", self.branch(task))
        self.pgit("checkout", "-q", "-B", f"perenos-{self.word()}", MAIN)
        for sha in commits:
            self.pgit("cherry-pick", "--allow-empty", sha)
        picked = self.pgit("rev-list", f"{MAIN}..HEAD").split()
        self.pgit("checkout", "-q", MAIN)
        self.pgit("merge", "-q", "--ff-only", picked[0])
        self.p_push_main()
        return picked

    def modify_task_file(self, task: str) -> str:
        """После вливания люди меняют в `base` файл правки задачи."""
        self.p_sync()
        rel = self.rng.choice(self.task_files(task))
        path = self.people() / rel
        path.write_text(path.read_text(encoding="utf-8")
                        + f"B = {self.seed}\n", encoding="utf-8")
        self.p_commit({}, f"pravka posle {self.word()}")
        return self.p_push_main()

    def foreign_branch_commit(self, task: str) -> str:
        """Чужой коммит поверх ветки задачи на сервере; его sha."""
        self.pgit("fetch", "-q", "origin")
        self.pgit("checkout", "-q", "-B", f"chuzh-{self.word()}",
                  f"origin/{self.branch(task)}")
        sha = self.p_commit({f"kod/chuzh_{self.word()}.py": f"F = {self.seed}\n"},
                            f"chuzhoy kommit {self.word()}")
        self.pgit("push", "-q", "origin", f"HEAD:refs/heads/{self.branch(task)}")
        return sha

    def rebase_merge(self, task: str) -> str:
        """Вливание с перебазированием: `base` ушёл вперёд, ветка задачи
        перебазирована на него и переписана на сервере, `base` перемотан
        на неё; новая голова ветки."""
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

    def delete_branch(self, task: str) -> None:
        self.pgit("push", "-q", "origin", "--delete", self.branch(task))

    def reset_main(self, sha: str) -> None:
        """`base` на сервере возвращён на `sha` (силой)."""
        self.pgit("push", "-q", "-f", "origin", f"{sha}:refs/heads/{MAIN}")

    # ------------------------------------------------------------ команды

    @contextlib.contextmanager
    def spy(self):
        spy = PytestSpy()
        with mock.patch.object(acceptance, "subprocess", spy), \
                mock.patch.object(two_sided, "subprocess", spy):
            yield spy

    def mark(self) -> None:
        """Начало команды стенда: шпионы очищены, длина журналов запомнена."""
        self.pushes.clear()
        self.fake.calls.clear()
        self.marks = {r["id"]: len(self.rows(r["id"]))
                      for r in store.all_tasks(self.conn)}

    def approve(self, task: str) -> str:
        store.record_fixation(self.conn, task)
        sha = store.get_task(self.conn, task)["fixed_sha"]
        self.mark()
        with self.spy():
            return capture_out(fsm.cmd_approve, task, sha)

    def mr_sync(self, *args) -> str:
        """`artel.py mr-sync <args>` через `artel.main`."""
        self.mark()
        argv = ["artel.py", "mr-sync", *[str(a) for a in args]]
        with self.spy(), mock.patch.object(sys, "argv", argv):
            return capture_out(artel.main)

    def to_merge_gate_with_mr(self) -> str:
        """Задача на `merge_gate` с уже заведённым (черновым) MR в БД."""
        task = self.new_task()
        iid = self.rng.randrange(100, 10 ** 6)
        store.update_task(self.conn, task, mr_iid=iid,
                          mr_url=f"https://localhost/grp/{self.ext}/-/merge_requests/{iid}")
        self.fake.replies[iid] = dict(
            iid=iid, state="opened", draft=True, target_branch=MAIN,
            source_branch=self.branch(task), sha=self.head(task))
        return task

    # ------------------------------------------------------------ наблюдение

    def row(self, task: str) -> dict:
        return dict(store.get_task(self.conn, task))

    def state(self, task: str) -> str:
        return store.get_task(self.conn, task)["state"]

    def mr(self, task: str) -> tuple:
        row = store.get_task(self.conn, task)
        return row["mr_iid"], row["mr_url"]

    def rows(self, task: str) -> list:
        return list(store.task_steps(self.conn, task))

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.rows(task))

    def new_journal(self, task: str) -> str:
        """Записи журнала задачи после начала последней команды стенда."""
        return "\n".join(f"{r['action']} {r['detail'] or ''}"
                         for r in self.rows(task)[self.marks.get(task, 0):])

    def status_block(self, task: str) -> str:
        out = capture_out(catalog.cmd_status)
        others = [r["id"] for r in store.all_tasks(self.conn) if r["id"] != task]
        block, inside = [], False
        for line in out.splitlines():
            if task in line:
                inside = True
            elif inside and any(o in line for o in others):
                break
            if inside:
                block.append(line)
        return "\n".join(block)

    def context(self, task: str, out: str = "") -> str:
        calls = "\n".join(f"{name}: {args!r}" for name, args in self.fake.calls
                          if name != "open_mr")
        return self.note(f"\n--- вывод:\n{out}\n--- журнал:\n{self.journal(task)}"
                         f"\n--- forge:\n{calls}\n--- отправки:\n"
                         + "\n".join(map(" ".join, self.pushes)))

    def head(self, task: str) -> str:
        return self.git("-C", self.clone, "rev-parse", self.branch(task)).strip()

    def origin_head(self, task: str) -> str:
        return self.git("--git-dir", self.bare, "for-each-ref",
                        "--format=%(objectname)",
                        f"refs/heads/{self.branch(task)}").strip()

    def branch_pushes(self, task: str) -> list:
        branch = self.branch(task)
        return [p for p in self.pushes if any(branch in a for a in p)]

    def artifact_files(self, task: str) -> list:
        return self.git("-C", self.clone, "ls-tree", "-r", "--name-only",
                        f"refs/artifacts/{task}").split()

    def retro(self, task: str) -> str | None:
        """Текст RETRO.md из ссылки документов задачи; None — его нет."""
        names = [f for f in self.artifact_files(task) if f.endswith("RETRO.md")]
        if not names:
            return None
        return self.git("-C", self.clone, "show",
                        f"refs/artifacts/{task}:{names[0]}")

    def closed_as(self, task: str):
        return store.get_task(self.conn, task)["closed_as"]


@pytest.fixture
def stand(real_git):
    return Stand(real_git)


def confirmed_done(stand, task: str, out: str, closed: str) -> str:
    """Утверждения успешного `--confirm`; текст RETRO."""
    where = stand.context(task, out)
    assert stand.state(task) == "done", where
    assert stand.closed_as(task) == closed, where
    retro = stand.retro(task)
    assert retro is not None, where + "\n--- RETRO нет в ссылке документов"
    return retro


def confirm_refused(stand, task: str, out: str) -> None:
    """Утверждения отказа `--confirm`: задача ждёт людей, не закрыта."""
    where = stand.context(task, out)
    assert stand.state(task) == STATE, where
    assert stand.closed_as(task) in (None, ""), where
    assert stand.retro(task) is None, where


# ------------------------------------------------------------------- AC-2


def test_ac2_sync_without_ids_takes_only_target_human_awaiting(stand):
    """`mr-sync` без id сверяет задачи `target-human` в `awaiting_human` и только их.

    Сценарий: своя задача доведена до `awaiting_human` настоящим
    `approve`, ещё случайное число задач своего проекта в `awaiting_human`
    заведено в БД; задача своего проекта на `merge_gate`; задача проекта с
    `merge_gate: operator` в `awaiting_human`. После `mr-sync` без id у
    каждой задачи `target-human` в `awaiting_human` новые записи журнала, а
    её id — в выводе; у задачи на `merge_gate` и у задачи проекта
    `operator` новых записей журнала нет, их id в выводе нет.

    Ловит мутацию: отбор без условия на проект (задача `operator` сверена
    — в её журнале запись сверки) или без условия на состояние (задача на
    `merge_gate` сверена); либо сверяется только первая подходящая задача
    — у остальных записей нет.
    """
    own = [stand.to_awaiting()]
    own += [stand.ghost(STATE) for _ in range(stand.rng.randint(1, 3))]
    gate = stand.ghost("merge_gate")
    foreign = stand.ghost(STATE, project=stand.other)
    out = stand.mr_sync()
    where = stand.context(own[0], out)
    for task in own:
        assert stand.new_journal(task), where + f"\nне сверена {task}"
        assert task in out, where + f"\nне названа {task}"
    for task in (gate, foreign):
        assert stand.new_journal(task) == "", where + f"\nсверена {task}"
        assert task not in out, where + f"\nназвана {task}"


@pytest.mark.parametrize("case", ["merge_gate", "operator", "нет задачи"])
def test_ac2_sync_by_id_refuses_foreign_or_wrong_state(stand, case):
    """`mr-sync <id>` по задаче не в `awaiting_human`, проекта не `target-human` или неизвестной — отказ с причиной.

    Сценарий: «merge_gate» — задача своего проекта на `merge_gate`;
    «operator» — задача проекта с `merge_gate: operator` в
    `awaiting_human`; «нет задачи» — случайный id, которого нет в БД.
    `mr-sync <id>`: вывод называет id; причина называет
    `awaiting_human` (состояние), `target-human` (проект) — для своих
    случаев; хостинг о MR не спрошен (`mr_status` не зван); журнала
    сверки у задачи нет, её состояние прежнее.

    Ловит мутацию: `mr-sync <id>` сверяет названную задачу без проверки
    состояния или проекта — `mr_status` зван, в журнале запись сверки;
    либо отказ молчит о причине (нет `awaiting_human`/`target-human` в
    тексте).
    """
    if case == "merge_gate":
        task = stand.ghost("merge_gate")
    elif case == "operator":
        task = stand.ghost(STATE, project=stand.other)
    else:
        task = idgen.new_task_id()
    out = stand.mr_sync(task)
    where = stand.context(task, out) if case != "нет задачи" else stand.note(out)
    assert task in out, where
    assert "mr_status" not in stand.fake.names(), where
    if case == "нет задачи":
        return
    assert stand.new_journal(task) == "", where
    if case == "merge_gate":
        assert STATE in out and stand.state(task) == "merge_gate", where
    else:
        assert "target-human" in out and stand.state(task) == STATE, where


# ------------------------------------------------------------------- AC-3


def test_ac3_fork_point_recorded_and_used_after_base_moves(stand):
    """Точка ответвления записана в БД и журнал на переходе в `awaiting_human`; сверка после сдвига `base` берёт её.

    Сценарий: на `approve` голова `base` на сервере — точка ответвления
    (`git merge-base` подтверждённой головы и `origin/<base>`). После
    перехода в `awaiting_human` один из столбцов строки задачи, не
    содержавший её до `approve`, содержит её sha, и журнал за `approve`
    называет его. Люди вливают ветку коммитом слияния и кладут сверху
    случайное число чужих коммитов в `base`. `mr-sync <id>`: журнал сверки
    называет записанную точку; доказательство признака (в) по файлам
    называет каждый файл правки задачи (дифф `<точка>..<голова>`).

    Ловит мутацию: точка не записана (нет ни столбца, ни записи журнала);
    либо сверка вычисляет её заново — после вливания коммитом слияния
    `merge-base` равен голове, журнал называет голову, а дифф пуст и
    доказательство (в) не называет файлы задачи.
    """
    task = stand.new_task()
    fork = stand.main_sha()
    stand.fork_at[task] = fork
    before = stand.row(task)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == STATE, stand.note(f"стенд: {where}")
    head = stand.head(task)
    stand.confirmed[task] = head
    assert stand.git("-C", stand.clone, "merge-base", head, fork).strip() == fork, \
        where
    after = stand.row(task)
    columns = [k for k in after if fork in str(after[k] or "")
               and fork not in str(before.get(k) or "")]
    assert columns, where + f"\nточки {fork} нет в строке задачи: {after}"
    assert fork[:7] in stand.new_journal(task), where
    iid, url = stand.mr(task)
    stand.fake.replies[iid] = dict(iid=iid, url=url, state="opened", draft=False,
                                   target_branch=MAIN,
                                   source_branch=stand.branch(task), sha=head)
    merge = stand.merge_commit(task)
    for _ in range(stand.rng.randint(1, 3)):
        stand.foreign_main()
    stand.reply(task, state="merged", merge_commit_sha=merge)
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert fork[:7] in stand.new_journal(task), where
    for rel in stand.task_files(task):
        assert rel in out, where + f"\nфайл {rel} не назван"


# ------------------------------------------------------------------- AC-4


def test_ac4_merged_by_this_mr_confirm_closes_without_touching_mr(stand):
    """«влит этим MR» по коммиту слияния: признак (а) в выводе и журнале; `--confirm` — `done`, `merged_upstream`, RETRO с sha слияния, рабочая копия убрана, ветка и MR не тронуты.

    Сценарий: задача в `awaiting_human`; люди влили ветку коммитом
    слияния, `mr_status` — «merged» с `merge_commit_sha` этого слияния.
    `mr-sync <id>`: вывод и журнал несут «влит этим MR» и sha коммита
    слияния. `mr-sync <id> --confirm`: задача `done`, `closed_as` —
    `merged_upstream`, RETRO в ссылке документов называет sha слияния,
    рабочей копии нет, lease снят; шпион git не видит ни одной отправки,
    называющей ветку задачи (ни отправки, ни удаления), голова ветки на
    сервере прежняя; подделка хостинга не видит `open_mr`/`undraft_mr`/
    `assign_mr`.

    Ловит мутацию: закрытие идёт прежней уборкой гейта мержа — ветка на
    сервере удалена (отправка `--delete`, ветки нет); либо RETRO несёт
    голову задачи, а не коммит слияния; либо `closed_as` пуст или
    `merged_upstream_other`; либо рабочая копия оставлена.
    """
    task = stand.to_awaiting()
    merge = stand.merge_commit(task)
    stand.reply(task, state="merged", merge_commit_sha=merge)
    server = stand.origin_head(task)
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert MERGED_THIS in out and MERGED_THIS in stand.new_journal(task), where
    assert merge[:7] in out and merge[:7] in stand.new_journal(task), where
    assert stand.state(task) == STATE, where
    out = stand.mr_sync(task, "--confirm")
    retro = confirmed_done(stand, task, out, CLOSED_THIS)
    where = stand.context(task, out) + f"\n--- RETRO:\n{retro}"
    assert merge[:8] in retro, where
    assert not stand.wt(task).exists(), where
    assert store.lease_row(stand.conn, task) is None, where
    assert stand.branch_pushes(task) == [], where
    assert stand.origin_head(task) == server != "", where
    assert not set(stand.fake.names()) & set(MR_WRITES), where


# ------------------------------------------------------------------- AC-5


@pytest.mark.parametrize("changed", [True, False])
def test_ac5_changed_after_merge_mark(stand, changed):
    """Пометка «после вливания файлы менялись» — только когда правка задачи изменена в `base` после вливания.

    Сценарий: задача в `awaiting_human`, люди влили её коммитом слияния
    (`mr_status` — «merged» с `merge_commit_sha`). При `changed` затем
    в `base` изменён случайный файл правки задачи (обратное наложение
    диффа задачи не проходит). `mr-sync <id>`: итог «влит этим MR»; пометка
    «после вливания файлы менялись» в выводе — ровно при `changed`.

    Ловит мутацию: пометка ставится всегда при (а) (контрольный случай
    без правки несёт её) или не ставится никогда (провал (в) не
    проверяется); либо провал (в) отменяет признак (а) — итог не «влит
    этим MR».
    """
    task = stand.to_awaiting()
    merge = stand.merge_commit(task)
    if changed:
        stand.modify_task_file(task)
    stand.reply(task, state="merged", merge_commit_sha=merge)
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert MERGED_THIS in out, where
    assert (CHANGED_AFTER in out) is changed, where


# ------------------------------------------------------------------- AC-6


def test_ac6_commits_moved_to_other_branch_confirm_other(stand):
    """MR закрыт, коммиты задачи перенесены в другую ветку и влиты — признак (б), «в базе, влит иначе»; `--confirm` закрывает `merged_upstream_other` sha найденного коммита.

    Сценарий: задача в `awaiting_human` (случайно 1–3 коммита); люди
    закрыли MR (`mr_status` — «closed», без коммитов слияния и сжатия,
    `sha` — голова ветки) и перенесли все коммиты задачи cherry-pick'ом в
    другую ветку, влитую в `base` поверх чужого коммита. `mr-sync <id>`:
    итог «в базе, влит иначе». `--confirm`: `done`, `closed_as` —
    `merged_upstream_other`, RETRO называет sha одного из перенесённых в
    `base` коммитов.

    Ловит мутацию: признак (б) не считается (перенос по содержимому не
    найден) — итог «нет в базе» или «в базе, влит иначе» только по (в) и
    отказ без `--by-content`; либо `closed_as` — `merged_upstream`; либо
    RETRO несёт голову задачи или `base`, а не найденный коммит.
    """
    task = stand.to_awaiting(commits=stand.rng.randint(1, 3))
    picked = stand.cherry(task)
    stand.reply(task, state="closed")
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert OTHER_WAY in out, where
    out = stand.mr_sync(task, "--confirm")
    retro = confirmed_done(stand, task, out, CLOSED_OTHER)
    where = stand.context(task, out) + f"\n--- RETRO:\n{retro}\nперенесены {picked}"
    assert any(sha[:8] in retro for sha in picked), where


# ------------------------------------------------------------------- AC-7


def test_ac7_squashed_with_other_needs_by_content(stand):
    """Правка влита сжатием вместе с чужой — только признак (в) с доказательством по файлам; `--confirm` требует `--by-content`.

    Сценарий: задача в `awaiting_human`; люди закрыли MR
    (`mr_status` — «closed») и влили правку задачи одним сжатым коммитом
    вместе с чужим файлом. `mr-sync <id>`: итог «в базе, влит иначе»,
    доказательство называет каждый файл правки задачи. `--confirm` без
    `--by-content` — отказ: задача в `awaiting_human`, `closed_as` пуст,
    RETRO нет. `--confirm --by-content`: `done`, `closed_as` —
    `merged_upstream_other`, RETRO называет голову `origin/<base>` и несёт
    «по содержимому».

    Ловит мутацию: `--confirm` закрывает по одному признаку (в) без
    `--by-content`; либо доказательство не перечисляет файлы; либо RETRO
    без пометки «по содержимому» или с головой ветки задачи вместо
    головы `base`.
    """
    task = stand.to_awaiting()
    stand.squash_with_other(task)
    stand.reply(task, state="closed")
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert OTHER_WAY in out, where
    for rel in stand.task_files(task):
        assert rel in out, where + f"\nфайл {rel} не назван"
    out = stand.mr_sync(task, "--confirm")
    confirm_refused(stand, task, out)
    base_head = stand.main_sha()
    out = stand.mr_sync(task, "--confirm", "--by-content")
    retro = confirmed_done(stand, task, out, CLOSED_OTHER)
    where = stand.context(task, out) + f"\n--- RETRO:\n{retro}"
    assert base_head[:8] in retro, where
    assert BY_CONTENT in retro, where


# ------------------------------------------------------------------- AC-8


OUTCOMES = ["частично", "нет в базе", "не найден", "другая ветка", "отказ forge"]


def arrange_outcome(stand, case: str) -> tuple:
    """Задача в `awaiting_human` под итог `case`; (задача, ожидаемый
    текст итога, причина отказа хостинга или "")."""
    task = stand.to_awaiting(commits=2 if case != "частично"
                             else stand.rng.randint(2, 3))
    reason = ""
    if case == "частично":
        stand.cherry(task, count=1)
        stand.reply(task, state="closed")
        return task, PARTIAL, reason
    if case == "нет в базе":
        stand.reply(task, state=stand.rng.choice(["opened", "closed"]))
        return task, ABSENT, reason
    if case == "не найден":
        store.update_task(stand.conn, task, mr_iid=None, mr_url=None)
        return task, NOT_FOUND, reason
    if case == "другая ветка":
        stand.reply(task, target_branch=f"release-{stand.word()}")
        return task, RETARGETED, reason
    reason = (f"ошибка сервера GitLab (502) на GET /projects/grp%2F{stand.ext}"
              f"/merge_requests {stand.word()}")
    stand.fake.fail["mr_status"] = reason
    return task, UNKNOWN, reason


@pytest.mark.parametrize("case", OUTCOMES)
def test_ac8_non_closing_outcomes_named_and_refuse_confirm(stand, case):
    """Итоги «в базе частично», «нет в базе», «MR не найден», «MR переведён на другую ветку», «неизвестно» печатаются своим текстом; `--confirm` отказывает с итогом и подсказкой.

    Сценарий по параметру: «частично» — из 2–3 коммитов задачи в `base`
    перенесён только первый, MR закрыт; «нет в базе» — правки в `base`
    нет, MR открыт или закрыт; «не найден» — ссылки на MR в БД нет;
    «другая ветка» — `target_branch` MR не `base`; «отказ forge» —
    `mr_status` отвечает отказом 5xx. `mr-sync <id>`: вывод несёт текст
    своего итога (при отказе — «неизвестно» и причину хостинга).
    `--confirm`: отказ — вывод несёт тот же итог и подсказку (`kill`,
    новая задача или ожидание), задача в `awaiting_human`, `closed_as`
    пуст, RETRO нет.

    Ловит мутацию: два итога печатаются одним текстом (например
    «частично» как «нет в базе»); либо отказ `forge` даёт зелёный итог
    или молчит о причине; либо `--confirm` закрывает задачу при одном из
    этих итогов; либо отказ без подсказки.
    """
    task, text, reason = arrange_outcome(stand, case)
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert text in out, where
    if reason:
        assert reason in out, where
    out = stand.mr_sync(task, "--confirm")
    where = stand.context(task, out)
    confirm_refused(stand, task, out)
    assert text in out, where
    assert any(w in out for w in CONFIRM_HINT_WORDS), where


# ------------------------------------------------------------------- AC-9


@pytest.mark.parametrize("case", ["не найден при (б)", "другая ветка при (а)",
                                  "влит, только (б)", "влит без признаков"])
def test_ac9_outcome_order_follows_table(stand, case):
    """Порядок итогов по таблице требования 3: верхняя подошедшая строка решает итог и исход `--confirm`.

    Сценарий по параметру: «не найден при (б)» — коммиты задачи
    перенесены в `base`, ссылки на MR в БД нет → «MR не найден», `--confirm`
    отказывает; «другая ветка при (а)» — коммит слияния в `base`, но
    `target_branch` MR не `base` → «MR переведён на другую ветку»,
    `--confirm` отказывает; «влит, только (б)» — MR «merged» без коммитов
    слияния и сжатия, `sha` MR не в `base`, коммиты перенесены → «в базе,
    влит иначе», `--confirm` закрывает `merged_upstream_other`; «влит без
    признаков» — MR «merged», правки в `base` нет → «нет в базе»,
    `--confirm` отказывает.

    Ловит мутацию: строки таблицы переставлены — признак (б) проверен
    раньше «MR не найден» (итог «в базе, влит иначе», `--confirm`
    закрывает); (а) раньше `target_branch` (закрытие `merged_upstream`);
    статус «merged» сам по себе даёт «влит этим MR» (`--confirm`
    закрывает задачу без правки в `base`).
    """
    task = stand.to_awaiting()
    if case == "не найден при (б)":
        stand.cherry(task)
        store.update_task(stand.conn, task, mr_iid=None, mr_url=None)
        text = NOT_FOUND
    elif case == "другая ветка при (а)":
        merge = stand.merge_commit(task)
        stand.reply(task, state="merged", merge_commit_sha=merge,
                    target_branch=f"release-{stand.word()}")
        text = RETARGETED
    elif case == "влит, только (б)":
        stand.cherry(task)
        stand.reply(task, state="merged")
        text = OTHER_WAY
    else:
        stand.reply(task, state="merged")
        text = ABSENT
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert text in out, where
    out = stand.mr_sync(task, "--confirm")
    if text == OTHER_WAY:
        confirmed_done(stand, task, out, CLOSED_OTHER)
        return
    confirm_refused(stand, task, out)


# ------------------------------------------------------------------ AC-10


def test_ac10_confirm_recomputes_outcome(stand):
    """`--confirm` пересчитывает итог: прошлый «влит этим MR», затем `base` и ответ хостинга изменены — отказ.

    Сценарий: задача в `awaiting_human`, влита коммитом слияния;
    `mr-sync <id>` даёт «влит этим MR». Затем `base` на сервере силой
    возвращён на точку до слияния, ответ `mr_status` — «closed» без
    коммита слияния. `mr-sync <id> --confirm`: отказ, задача в
    `awaiting_human`, `closed_as` пуст, RETRO нет.

    Ловит мутацию: `--confirm` берёт итог прошлого запуска из БД — задача
    закрыта `merged_upstream` при правке, которой в `base` нет.
    """
    task = stand.to_awaiting()
    before_merge = stand.main_sha()
    merge = stand.merge_commit(task)
    stand.reply(task, state="merged", merge_commit_sha=merge)
    out = stand.mr_sync(task)
    assert MERGED_THIS in out, stand.context(task, out)
    stand.reset_main(before_merge)
    stand.reply(task, state="closed", merge_commit_sha=None)
    out = stand.mr_sync(task, "--confirm")
    confirm_refused(stand, task, out)


@pytest.mark.parametrize("ids", ["два id", "без id"])
def test_ac10_confirm_needs_exactly_one_id(stand, ids):
    """`mr-sync --confirm` с двумя id или без id — отказ, ни одна задача не закрыта.

    Сценарий: задача A в `awaiting_human` влита коммитом слияния (итог
    «влит этим MR»), задача B своего проекта в `awaiting_human`.
    `mr-sync --confirm A B` либо `mr-sync --confirm` без id: обе задачи в
    `awaiting_human`, `closed_as` пуст, RETRO у A нет.

    Ловит мутацию: `--confirm` применяется к каждой названной (или каждой
    отобранной) задаче — A закрыта `merged_upstream`.
    """
    task = stand.to_awaiting()
    merge = stand.merge_commit(task)
    stand.reply(task, state="merged", merge_commit_sha=merge)
    second = stand.ghost(STATE)
    args = ["--confirm", task, second] if ids == "два id" else ["--confirm"]
    out = stand.mr_sync(*args)
    confirm_refused(stand, task, out)
    assert stand.state(second) == STATE, stand.context(second, out)
    assert stand.closed_as(second) in (None, ""), stand.context(second, out)


# ------------------------------------------------------------------ AC-11


def test_ac11_confirm_refuses_when_docs_ref_unsynced(stand):
    """`--confirm` при «влит этим MR», когда ссылка документов задачи расходится с `origin`, — отказ, коммита закрытия нет.

    Сценарий: задача в `awaiting_human`, влита коммитом слияния
    (`mr_status` — «merged»). `origin` проекта отвергает запись в
    `refs/artifacts/*` (хук `pre-receive`), локальная ссылка документов
    задачи ушла вперёд на коммит, которого в `origin` нет.
    `mr-sync <id> --confirm`: задача в `awaiting_human`, `closed_as` пуст,
    RETRO в ссылке нет.

    Ловит мутацию: `--confirm` не сверяет ссылку документов с `origin`
    перед переходом — задача закрыта, RETRO лёг поверх истории, которой в
    `origin` нет.
    """
    task = stand.to_awaiting()
    merge = stand.merge_commit(task)
    stand.reply(task, state="merged", merge_commit_sha=merge)
    hook = stand.bare / "hooks" / "pre-receive"
    hook.write_text(REJECT_DOCS_REFS, encoding="utf-8")
    hook.chmod(0o755)
    ref = f"refs/artifacts/{task}"
    tree = stand.git("-C", stand.clone, "rev-parse", f"{ref}^{{tree}}").strip()
    ahead = stand.git("-C", stand.clone, "commit-tree", tree, "-p", ref,
                      "-m", f"lokalno {stand.word()}").strip()
    stand.git("-C", stand.clone, "update-ref", ref, ahead)
    remote = stand.git("--git-dir", stand.bare, "for-each-ref",
                       "--format=%(objectname)", ref).strip()
    assert remote != ahead, stand.note("стенд: ссылка совпала с origin")
    out = stand.mr_sync(task, "--confirm")
    confirm_refused(stand, task, out)


# ------------------------------------------------------------------ AC-12


def test_ac12_confirm_frees_zone_and_merge_after(stand):
    """После `--confirm` зона задачи свободна, а зависимый по `merge_after` больше ею не держится.

    Сценарий: запись проекта с `awaiting_holds_zones: true`; задача в
    `awaiting_human` держит зону (до закрытия `zone_lock.blocking_conflict`
    задачи той же зоны называет её); задача-соседка той же зоны в
    `in_dev`; задача на `merge_gate` с `merge_after` на неё
    (`merge_after.merge_gate_refuses` до закрытия — отказ). Задача влита
    коммитом слияния, `mr-sync <id> --confirm` закрывает её. После:
    `zone_lock.blocking_conflict` соседки — None,
    `merge_after.merge_gate_refuses` зависимой — False.

    Ловит мутацию: закрытие ставит нетерминальное состояние или не
    `done` (зона держится, зависимый ждёт); либо `closed_as` выставлен без
    перехода `state -> done`.
    """
    stand.record(awaiting_holds_zones="true")
    task = stand.new_task()
    store.journal(stand.conn, task, "system", "state -> in_dev", "")
    store.journal(stand.conn, task, "developer", "agent run started", "")
    stand.fork_at[task] = stand.main_sha()
    out = stand.approve(task)
    assert stand.state(task) == STATE, stand.note(f"стенд: {stand.context(task, out)}")
    stand.confirmed[task] = stand.head(task)
    iid, url = stand.mr(task)
    stand.fake.replies[iid] = dict(iid=iid, url=url, state="opened", draft=False,
                                   target_branch=MAIN,
                                   source_branch=stand.branch(task),
                                   sha=stand.head(task))
    zone = store.get_task(stand.conn, task)["zones"]
    neighbour = stand.ghost("in_dev", zones=zone)
    dependent = stand.ghost("merge_gate")
    store.update_task(stand.conn, dependent, merge_after=merge_after.column([task]))
    with contextlib.redirect_stdout(io.StringIO()):
        held = zone_lock.blocking_conflict(
            stand.conn, neighbour, store.get_task(stand.conn, neighbour))
        waits = merge_after.merge_gate_refuses(
            stand.conn, dependent, store.get_task(stand.conn, dependent))
    assert held is not None and waits, stand.note(
        f"стенд: до закрытия зона {held}, merge_after {waits}")
    merge = stand.merge_commit(task)
    stand.reply(task, state="merged", merge_commit_sha=merge)
    out = stand.mr_sync(task, "--confirm")
    confirmed_done(stand, task, out, CLOSED_THIS)
    where = stand.context(task, out)
    with contextlib.redirect_stdout(io.StringIO()):
        assert zone_lock.blocking_conflict(
            stand.conn, neighbour, store.get_task(stand.conn, neighbour)) is None, where
        assert not merge_after.merge_gate_refuses(
            stand.conn, dependent, store.get_task(stand.conn, dependent)), where


# ------------------------------------------------------------------ AC-13


@pytest.mark.parametrize("mr_state", ["merged", "closed"])
def test_ac13_mr_merged_before_awaiting_escalates_on_approve(stand, mr_state):
    """MR задачи влит или закрыт до `awaiting_human` — `approve` гейта мержа эскалирует, черновик не снят, исполнитель не назначен.

    Сценарий: задача на `merge_gate` с `mr_iid` (черновой MR заведён
    раньше), `mr_status` отвечает статусом по параметру. `approve`:
    задача `escalated` (не `awaiting_human`), подделка хостинга не видит
    `undraft_mr` и `assign_mr`.

    Ловит мутацию: статус MR на `approve` не читается — черновик снят,
    задача в `awaiting_human`; либо проверяется только «merged», и
    закрытый MR проходит.
    """
    task = stand.to_merge_gate_with_mr()
    stand.reply(task, state=mr_state)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == "escalated", where
    assert "undraft_mr" not in stand.fake.names(), where
    assert "assign_mr" not in stand.fake.names(), where


# ------------------------------------------------------------------ AC-14


def test_ac14_foreign_commit_escalates_approve_without_push(stand):
    """Чужой коммит в ветке задачи на сервере при открытом MR — `approve` на `merge_gate` эскалирует без отправки ветки.

    Сценарий: задача на `merge_gate` с открытым MR в БД, ветка отправлена
    пультом (запись «ветка отправлена»); люди положили поверх неё на
    сервере чужой коммит. `approve`: задача `escalated`, шпион git не
    видит отправки ветки задачи, голова ветки на сервере — чужой коммит
    (не перезаписана).

    Ловит мутацию: голова на сервере не сверяется с последней своей
    отправкой — `approve` перезаписывает ветку (отправка в шпионе) или
    уходит в `awaiting_human`/остаётся на гейте без эскалации.
    """
    task = stand.to_merge_gate_with_mr()
    foreign = stand.foreign_branch_commit(task)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == "escalated", where
    assert stand.branch_pushes(task) == [], where
    assert stand.origin_head(task) == foreign, where


def test_ac14_foreign_commit_sync_escalates_then_accepted_head(stand):
    """Чужой коммит при открытом MR — `mr-sync` эскалирует; после `answer` + `approve` голова сервера принята, следующая сверка не эскалирует.

    Сценарий: задача в `awaiting_human`, MR открыт; люди положили чужой
    коммит поверх ветки задачи на сервере. `mr-sync <id>` (без
    `--confirm`): задача `escalated`, отправки ветки нет, голова на
    сервере — чужой коммит. Оператор отвечает (`answer` случайным файлом)
    и подтверждает (`approve`): задача снова в `awaiting_human`, журнал за
    этот `approve` называет sha чужого коммита. Второй `mr-sync <id>` при
    той же голове: задача в `awaiting_human`.

    Ловит мутацию: `mr-sync` не проверяет чужой коммит (задача остаётся
    в `awaiting_human` после первой сверки); либо принятая голова не
    записывается и сравнение снова идёт с последней своей отправкой —
    вторая сверка эскалирует.
    """
    task = stand.to_awaiting()
    foreign = stand.foreign_branch_commit(task)
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert stand.state(task) == "escalated", where
    assert stand.branch_pushes(task) == [], where
    assert stand.origin_head(task) == foreign, where
    path = stand.clone.parent.parent / f"answer-{stand.word()}.md"
    path.write_text(f"Ответ Оператора: чужой коммит принят {stand.word()}\n",
                    encoding="utf-8")
    stand.mark()
    out = capture_out(answer.cmd_answer, task, str(path))
    out += stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == STATE, where
    assert foreign[:7] in stand.new_journal(task), where
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert stand.state(task) == STATE, where


# ------------------------------------------------------------------ AC-15


@pytest.mark.parametrize("case", ["перебазирование", "ветка удалена"])
def test_ac15_merged_or_deleted_branch_is_not_incident(stand, case):
    """MR влит с перебазированием или ветка задачи удалена на сервере — не инцидент: итог по признакам, задача ждёт людей.

    Сценарий: задача в `awaiting_human`. «перебазирование» — `base` ушёл
    вперёд, люди перебазировали ветку задачи, переписали её на сервере и
    перемотали на неё `base`; `mr_status` — «merged», `sha` — новая
    голова, коммита слияния нет. «ветка удалена» — люди влили ветку
    коммитом слияния и удалили её на сервере; `mr_status` — «merged» с
    `merge_commit_sha`. `mr-sync <id>`: задача в `awaiting_human` (не
    `escalated`), итог «влит этим MR», отправок ветки нет.

    Ловит мутацию: проверка чужого коммита идёт при любом статусе MR —
    переписанная вливанием или удалённая ветка эскалирует задачу.
    """
    task = stand.to_awaiting()
    if case == "перебазирование":
        head = stand.rebase_merge(task)
        stand.reply(task, state="merged", sha=head)
    else:
        merge = stand.merge_commit(task)
        stand.delete_branch(task)
        stand.reply(task, state="merged", merge_commit_sha=merge)
    out = stand.mr_sync(task)
    where = stand.context(task, out)
    assert stand.state(task) == STATE, where
    assert MERGED_THIS in out, where
    assert stand.branch_pushes(task) == [], where


# ------------------------------------------------------------------ AC-16


@pytest.mark.parametrize("merged", [True, False])
def test_ac16_plain_sync_changes_only_outcome_fields(stand, merged):
    """`mr-sync` без `--confirm` меняет в строке задачи только последний итог и время сверки.

    Сценарий: задача в `awaiting_human`; при `merged` влита коммитом
    слияния, иначе MR открыт и правки в `base` нет. Снимок строки задачи
    до и после `mr-sync <id>`: изменились не больше двух столбцов; столбцы
    состояния, ветки, ссылки на MR, `closed_as`, `escalated_from`,
    фиксации, `merge_after`, лока планки — прежние; в журнале задачи есть
    новые записи.

    Ловит мутацию: сверка без `--confirm` двигает состояние, правит
    ссылку MR или `closed_as` (столбец из перечня изменён); либо пишет
    сверх итога и времени (изменено больше двух столбцов); либо не пишет
    журнал.
    """
    task = stand.to_awaiting()
    if merged:
        merge = stand.merge_commit(task)
        stand.reply(task, state="merged", merge_commit_sha=merge)
    before = stand.row(task)
    out = stand.mr_sync(task)
    after = stand.row(task)
    where = stand.context(task, out)
    changed = sorted(k for k in after if after[k] != before.get(k))
    assert len(changed) <= 2, where + f"\nизменены {changed}"
    for column in KEPT_COLUMNS:
        if column in before:
            assert after[column] == before[column], where + f"\nизменён {column}"
    assert stand.new_journal(task), where


# ------------------------------------------------------------------ AC-19


@pytest.mark.parametrize("view", ["status", "--md", "--json", "--html"])
def test_ac19_status_and_board_show_last_outcome_and_time(stand, view):
    """`status` и доска у задачи в `awaiting_human` после `mr-sync` показывают последний итог и время сверки.

    Сценарий: задача в `awaiting_human`, влита коммитом слияния; часы
    пульта (`store.now`) на время сверки подменены случайной датой
    2031 года. После `mr-sync <id>` блок задачи в выводе `status` или вид
    доски проекта (`board.RENDERERS` над `board.build_model`) несёт итог
    «влит этим MR» и время сверки (часы и минуты подменённого времени
    либо его дату); до сверки итога там нет.

    Ловит мутацию: итог сохраняется, но не показывается (в `status` или в
    модели доски нет); либо показывается итог без времени сверки.
    """
    task = stand.to_awaiting()
    merge = stand.merge_commit(task)
    stand.reply(task, state="merged", merge_commit_sha=merge)

    def shown() -> str:
        if view == "status":
            return stand.status_block(task)
        return board.RENDERERS[view](board.build_model(stand.conn, stand.ext))

    assert MERGED_THIS not in shown(), stand.note(f"стенд: итог до сверки\n{shown()}")
    minute = stand.rng.randrange(60)
    hour = stand.rng.randrange(24)
    day = stand.rng.randint(1, 28)
    fixed = f"2031-07-{day:02d} {hour:02d}:{minute:02d}:05Z"
    with mock.patch.object(store, "now", lambda: fixed):
        out = stand.mr_sync(task)
    text = shown()
    where = stand.context(task, out) + f"\n--- показ ({view}):\n{text}\nвремя {fixed}"
    assert MERGED_THIS in text, where
    assert f"{hour:02d}:{minute:02d}" in text or f"2031-07-{day:02d}" in text, where
