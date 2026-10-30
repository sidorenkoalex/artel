"""Доставка через MR для проекта с `merge_gate: target-human`: гейт мержа открывает MR через `forge`, черновой MR на входе в `verifying`, пределы `max_awaiting` и `max_in_flight`.

Группа: долгоживущий
Красен до реализации: состояния `awaiting_human`, столбцов задачи `mr_iid`/`mr_url`, полей `policy.max_awaiting` и целого `mr_assignee` (часть Б2.1а) и самой доставки этой части нет — запись с `max_awaiting` или `mr_assignee: 42` не загружается, гейт мержа `target-human` вливает ветку в `base` сам и не зовёт `forge.open_mr`, черновой MR заводит только `gh` для GitHub, предела отправок в точке отправки `gitcmd` нет.

Связка «команда пульта — FSM — база — git»: каждый сценарий доходит до
поведения через публичный вход (`fsm.cmd_approve`, `fsm.cmd_advance`,
`amend.cmd_amend_tests`, `github_adapter.ensure_draft_mr`,
`catalog.cmd_status`) в настоящем git песочницы
(`tests.sandbox.RealGitSandbox`): клон внешнего проекта
(`tests.sandbox.make_project_repo`) с bare `origin`, запись проекта — в
локальном слое (`targets.local_path()`), ссылка документов — автокоммитом
шага. Поддержка `target-human` и `gitlab` — подменой
`targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES` (SPEC, «Контекст»).

Хостинг подменён целиком реестром `forge.IMPLEMENTATIONS` (ключ записи
`gitlab`): подделка записывает каждый вызов (`open_mr`, `undraft_mr`,
`assign_mr` и любой иной) и отвечает по сценарию; цвет CI ветки — её же
`pipeline_status` по sha (у GitLab итог CI даёт `forge.pipeline_status`).
Прочие внешние ответы: `ci.main_line_status` (цвет CI base), `ci.gh`
(шпион `gh`, отвечает успехом), `keychain.token` (слот токена хостинга),
прогон pytest у мест запуска (`acceptance`, `two_sided` — подменённый
модуль `subprocess` отвечает зелёным прогоном). Отправки и прочие вызовы
git наблюдаются обёрткой `subprocess.run`, которая зовёт настоящий
`subprocess.run`. Задачи-«соседи» для счёта пределов заводятся прямо в БД
(`store.insert_task`) с записью журнала «ветка отправлена» там, где она
нужна.

Имена, числа пределов и число соседей — из `random`, зерно печатается и
входит в текст каждого провала.

Провалидировано временным стабом (удалён, не закоммичен): столбцы
`mr_iid`/`mr_url`, состояние `awaiting_human` и поля `max_awaiting`/целый
`mr_assignee` (вместо части Б2.1а), ветвь `target-human` в теле гейта
мержа после публикации головы, черновой MR за отправкой на входе в
`verifying`, предел `max_in_flight` в `gitcmd._push_plan` и суффиксы
строки `status` — все методы зелёные; мутация «счёт `max_awaiting` до
захвата мьютекса» краснит AC-20. На сегодняшнем коде гейт мержа доходит
до слияния в `base` (его отказывает белый список отправок), переход
`in_dev -> verifying`, `amend-tests` и `ensure_draft_mr` отправляют ветку
без предела — краснота приходится на отсутствующее поведение задачи, а не
на стенд.
"""
import contextlib
import hashlib
import inspect
import io
import os
import random
import subprocess
import threading
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (acceptance, amend, catalog, checkpoint, ci, config,
                          forge, fsm, github_adapter, idgen, keychain,
                          canary, merge_lock, store, targets, workspace)
from orchestrator.advance_gates import two_sided
from scripts import guard
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

# Записи журнала «ветка отправлена» новой и старой формы и подкоманды
# отправки — значения `gitcmd.PUSH_SENT_ACTION`, `PUSH_SENT_LEGACY_ACTION`
# и `PUSH_SUBCOMMANDS` (SPEC, требование 7).
SENT = "ветка отправлена:"
SENT_LEGACY = "ветка отправлена"
PUSH_SUBCOMMANDS = ("push", "send-pack")
NOT_NUMERIC = "исполнитель не числовой id — не назначен"
BASE_MOVED = "base сдвинулся — подготовка ветки заново"
APPENDIX_REFUSAL = ("приложения не применяются в проекте с target-human — "
                    "правку вносят люди проекта")
MR_EXISTS = "MR ветки уже существует, ссылки в БД нет"
AWAITING_QUEUE = "очередь: предел awaiting_human"
PROTECTED_UNCHANGED = "conf/settings.yaml"
# Разговор с хостингом о MR — функции интерфейса `forge` с «mr» в имени.
MR_CALLS = tuple(name for name in forge.RESULT_TYPES if "mr" in name)

ENTRY = """  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
    policy:
      no_paths: [{protected}]
      project_skills: []
      merge_gate: {gate}
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: {forge}
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

# SPEC: фикстура доставки через MR

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

APPENDIX_TEXT = """
## Приложение: правка conf/settings.yaml

```diff
diff --git a/conf/settings.yaml b/conf/settings.yaml
--- a/conf/settings.yaml
+++ b/conf/settings.yaml
@@ -1 +1,2 @@
 level: 1
+extra: {value}
```
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

LONG_LIVED_TEXT = '''"""Фикстура долгоживущего файла песочницы.

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

POST_RECEIVE = """#!/bin/sh
while read old new ref; do
  if [ "$ref" = "refs/heads/{branch}" ]; then
    tree=$(git rev-parse "$new^{{tree}}")
    foreign=$(GIT_AUTHOR_NAME=chuzhoy GIT_AUTHOR_EMAIL=c@example.invalid \\
      GIT_COMMITTER_NAME=chuzhoy GIT_COMMITTER_EMAIL=c@example.invalid \\
      git commit-tree "$tree" -p "$new" -m "chuzhoy kommit")
    git update-ref "$ref" "$foreign"
  fi
done
exit 0
"""


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
    каждый вызов — в `calls` (имя и аргументы по сигнатуре интерфейса
    `forge`), ответ — по сценарию (`fail` — имя функции → причина отказа,
    `red` — sha с красным CI)."""

    CI_BY_PIPELINE = True

    def __init__(self, stand):
        self.stand = stand
        self.calls: list = []
        self.fail: dict = {}
        self.red: set = set()
        self.opened: list = []

    def _record(self, name: str, args: tuple) -> dict:
        params = list(inspect.signature(getattr(forge, name)).parameters)
        call = dict(zip(params, args))
        call["name"] = name
        self.calls.append(call)
        self.stand.events.append((name, call.get("branch")))
        return call

    def pipeline_status(self, target, sha):
        self._record("pipeline_status", (target, sha))
        if sha in self.red:
            return forge.PipelineStatus(forge.RED, "задание unit упало (failed)",
                                        [forge.Job("unit", "failed")], ["unit"])
        return forge.PipelineStatus(forge.GREEN, "", [forge.Job("unit", "success")])

    def open_mr(self, target, branch, base, title, body, draft, assignee):
        self._record("open_mr", (target, branch, base, title, body, draft,
                                 assignee))
        if "open_mr" in self.fail:
            return forge.MergeRequest(reason=self.fail["open_mr"])
        iid = self.stand.rng.randrange(100, 10 ** 6)
        url = f"https://localhost/grp/{target}/-/merge_requests/{iid}"
        self.opened.append((iid, url))
        return forge.MergeRequest(iid=iid, url=url, title=title, state="opened",
                                  draft=bool(draft))

    def undraft_mr(self, target, mr):
        self._record("undraft_mr", (target, mr))
        if "undraft_mr" in self.fail:
            return forge.MergeRequest(reason=self.fail["undraft_mr"])
        return forge.MergeRequest(iid=mr, state="opened", draft=False)

    def assign_mr(self, target, mr, assignee):
        self._record("assign_mr", (target, mr, assignee))
        if "assign_mr" in self.fail:
            return forge.MergeRequest(reason=self.fail["assign_mr"])
        return forge.MergeRequest(iid=mr, state="opened", assignee=str(assignee))

    def __getattr__(self, name):
        if name.startswith("__") or name not in forge.RESULT_TYPES:
            raise AttributeError(name)

        def other(*args):
            self._record(name, args)
            return forge.RESULT_TYPES[name](
                reason=f"подделка хостинга: {name} не отвечает")
        return other

    def named(self, name: str) -> list:
        return [c for c in self.calls if c["name"] == name]


class Stand:
    """Пульт с клонами двух внешних проектов (свой и «другой») и bare
    `origin`; записи проектов — в локальном слое, поля — по сценарию."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"proj{self.word()}"
        self.other = f"drug{self.word()}"
        self.pushes: list = []
        self.git_calls: list = []
        self.gh_calls: list = []
        self.events: list = []
        self.main_kind = ci.MAIN_GREEN
        self.fake = FakeForge(self)
        self.real_acquire = merge_lock.acquire

        def spy_run(*args, **kwargs):
            argv = args[0] if args else kwargs.get("args")
            if isinstance(argv, (list, tuple)) and argv and \
                    Path(str(argv[0])).name == "git":
                argv = [str(a) for a in argv]
                self.git_calls.append(argv)
                if git_sub(argv) in PUSH_SUBCOMMANDS:
                    self.pushes.append(argv)
            return REAL_RUN(*args, **kwargs)

        def spy_gh(*args, **kwargs):
            self.gh_calls.append([str(a) for a in args])
            return subprocess.CompletedProcess(
                list(args), 0, f"https://localhost/grp/{self.ext}/pull/1\n", "")

        def main_line(sha, repo=None):
            return ci.MainLineStatus(self.main_kind, sha,
                                     [] if self.main_kind != ci.MAIN_RED
                                     else ["unit"], [], "",
                                     f"CI base (тест): {self.main_kind}")

        def acquire(conn, task_id, session_id, *args, **kwargs):
            self.events.append(("acquire", task_id))
            return self.real_acquire(conn, task_id, session_id, *args, **kwargs)

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
                mock.patch.object(ci, "gh", spy_gh),
                mock.patch.object(keychain, "token", lambda *a, **k: "tok"),
                mock.patch.object(merge_lock, "acquire", acquire),
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
                             PROTECTED_UNCHANGED: "level: 1\n",
                             "docs/notes.md": "# Заметки\n\n- база\n"})
        self.fork = self.main_sha()

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def pick(self, low: int, high: int) -> int:
        return self.rng.randint(low, high)

    def hexsha(self) -> str:
        return "".join(self.rng.choice(HEX) for _ in range(40))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def git(self, *args) -> str:
        return self.sb.git(*[str(a) for a in args])

    def record(self, *, gate: str = "target-human", forge_name: str = "gitlab",
               **policy) -> None:
        """Записи своего и «другого» проектов в локальном слое; `policy` —
        поля раздела `policy` (значение — текст YAML, `None` — поля нет)."""
        lines = "".join(f"      {key}: {value}\n" for key, value in policy.items()
                        if value is not None)
        text = "targets:\n"
        for name in (self.ext, self.other):
            text += ENTRY.format(name=name, base=config.MAIN_BRANCH,
                                 protected=PROTECTED_UNCHANGED, gate=gate,
                                 policy=lines, forge=forge_name)
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(text, encoding="utf-8")

    def commit_to_main(self, files: dict) -> str:
        """Коммит в основную ветку проекта и отправка в его `origin`."""
        for rel, text in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", self.clone, "add", "-A")
        self.git("-C", self.clone, "commit", "-q", "-m", f"main {self.word()}")
        self.git("-C", self.clone, "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        return self.main_sha()

    def main_sha(self) -> str:
        return self.git("--git-dir", self.bare, "rev-parse",
                        config.MAIN_BRANCH).strip()

    # ------------------------------------------------------------ задачи

    def new_task(self, state: str = "in_dev", commits: int = 2,
                 published: bool = False, appendix: bool = False) -> str:
        """Задача проекта: `commits` коммитов кода в ветке, SPEC/PLAN/планка в
        ссылке документов, лок планки; `published` — ветка уже на сервере с
        записью «ветка отправлена» (так на гейте мержа после `verifying`)."""
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
        plan = PLAN_TEXT.format(task=task)
        if appendix:
            plan += APPENDIX_TEXT.format(value=self.rng.randrange(10 ** 6))
        self.write_docs(task, {
            "SPEC.md": SPEC_TEXT.format(task=task, zones=zones),
            "PLAN.md": plan,
            f"acceptance_tests/test_ac1_{self.word()}.py":
                PLANK_TEXT.format(word=self.word())})
        self.lock(task)
        if published:
            self.publish_raw(task)
        return task

    def ghost(self, state: str, project: str | None = None,
              record: str | None = SENT) -> str:
        """Задача-сосед прямо в БД: состояние `state`, проект `project`
        (по умолчанию свой), запись журнала `record` («ветка отправлена»
        новой или старой формы; `None` — записи нет)."""
        task = idgen.new_task_id()
        branch = f"task/{task.lower()}-{self.word()}"
        store.insert_task(self.conn, task, f"Сосед {self.word()}", state, branch,
                          project or self.ext, config.DEFAULT_BUDGET_USD)
        if record is not None:
            store.journal(self.conn, task, "orchestrator", record,
                          f"{self.hexsha()} {branch}")
        return task

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

    def lock(self, task: str) -> None:
        store.update_task(self.conn, task, tests_locked_sha=self.docs_head(task),
                          draft_mr_created=1)
        store.record_fixation(self.conn, task)

    def commit_code(self, task: str, files: dict) -> str:
        wt = self.wt(task)
        for rel, text in files.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", wt, "add", "-A")
        self.git("-C", wt, "commit", "-q", "-m", f"код {self.word()}")
        return self.head(task)

    def publish_raw(self, task: str) -> None:
        """Ветка на сервере мимо пульта и запись «ветка отправлена» о ней."""
        branch = self.branch(task)
        self.git("-C", self.clone, "push", "-q", "origin",
                 f"{branch}:refs/heads/{branch}")
        store.journal(self.conn, task, "orchestrator", SENT,
                      f"{self.head(task)} {branch}")

    def with_long_lived(self, task: str) -> str:
        """Долгоживущий файл задачи в ветке и перечень его суммы в планке;
        лок — на новой голове ссылки документов. Путь файла."""
        rel = f"tests/test_{task.lower()}_{self.word()}.py"
        self.commit_code(task, {rel: LONG_LIVED_TEXT.format(
            cls=self.word().capitalize(), word=self.word())})
        digest = hashlib.sha256((self.wt(task) / rel).read_bytes()).hexdigest()
        self.plank_name = f"acceptance_tests/test_ac1_{self.word()}.py"
        self.plank_text = PLANK_TEXT.format(word=self.word())
        self.write_docs(task, {
            self.plank_name: self.plank_text,
            f"acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}":
                guard.render_long_lived_manifest({rel: digest})})
        self.lock(task)
        return rel

    # ------------------------------------------------------------ команды

    @contextlib.contextmanager
    def spy(self):
        spy = PytestSpy()
        with mock.patch.object(acceptance, "subprocess", spy), \
                mock.patch.object(two_sided, "subprocess", spy):
            yield spy

    def reset_spies(self) -> None:
        self.pushes.clear()
        self.git_calls.clear()
        self.gh_calls.clear()
        self.events.clear()
        self.fake.calls.clear()

    def approve(self, task: str, sha: str | None = None,
                refix: bool = True) -> str:
        """`approve` гейта мержа подтверждённым sha (по умолчанию — sha
        фиксации, как его называет Оператору пульт); `refix` — фиксация
        заново перед вызовом."""
        if refix:
            store.record_fixation(self.conn, task)
        sha = sha or store.get_task(self.conn, task)["fixed_sha"]
        self.reset_spies()
        self.before = len(self.rows(task))
        with self.spy():
            return capture_out(fsm.cmd_approve, task, sha)

    def advance(self, task: str) -> str:
        self.reset_spies()
        self.before = len(self.rows(task))
        with self.spy():
            return capture_out(fsm.cmd_advance, task)

    def amend(self, task: str, rel: str) -> str:
        """`amend-tests` с правкой долгоживущего файла в рабочей копии:
        планка лока выложена в рабочую копию, долгоживущий файл дописан."""
        task_dir = self.wt(task) / "tasks" / task
        path = task_dir / self.plank_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.plank_text, encoding="utf-8")
        path = self.wt(task) / rel
        path.write_text(path.read_text(encoding="utf-8")
                        + f"# правка Оператора {self.word()}\n", encoding="utf-8")
        self.reset_spies()
        self.before = len(self.rows(task))
        with self.spy():
            return capture_out(amend.cmd_amend_tests, task,
                               f"правка планки {self.seed}")

    def to_merge_gate(self, task: str) -> None:
        store.set_state(self.conn, task, "merge_gate", "test",
                        expected_state=self.state(task),
                        detail="фикстура: ревью и приёмка пройдены")

    # ------------------------------------------------------------ наблюдение

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
                         for r in self.rows(task)[self.before:])

    def status_block(self, task: str) -> str:
        """Строки вывода `status` о задаче `task` — от строки с её id до
        строки с id другой задачи."""
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
        calls = "\n".join(f"{c['name']}: " + ", ".join(
            f"{k}={v!r}" for k, v in c.items() if k not in ("name", "body"))
            for c in self.fake.calls)
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


@pytest.fixture
def stand(real_git):
    return Stand(real_git)


def opened_ok(stand, task: str, out: str) -> dict:
    """Утверждения успешного открытия MR на гейте; вызов `open_mr`."""
    where = stand.context(task, out)
    calls = stand.fake.named("open_mr")
    assert len(calls) == 1, where
    assert stand.state(task) == "awaiting_human", where
    return calls[0]


# ------------------------------------------------------------------- AC-1


@pytest.mark.parametrize("value, expected", [
    ('"42"', 42), ("42", 42), ("alice", None), (None, None)])
def test_ac1_assignee_numeric_id_or_unassigned(stand, value, expected):
    """Исполнитель MR на гейте: строка цифр и целое — `int` 42, иное и отсутствие поля — без исполнителя.

    Сценарий: запись `target-human` с `policy.mr_assignee` по параметру
    (`"42"` — строка цифр, `42` — целое, `alice`, поля нет), задача на
    `merge_gate`, ссылки на MR в БД нет. `approve` открывает MR: в
    `forge.open_mr` исполнитель — ровно `int` 42 (не строка `"42"`) либо
    `None`; при `alice` в журнале задачи — «исполнитель не числовой id — не
    назначен»; без поля — запись журнала об исполнителе.

    Ловит мутацию: строка `policy.mr_assignee` уходит в `forge` как есть
    (`assignee` — `"42"`, тип `str`); либо `alice` уходит исполнителем
    (GitLab получил бы нечисловой `assignee_id`); либо отказ назначения
    молчит — записи журнала нет.
    """
    stand.record(draft_mr="false", mr_assignee=value)
    task = stand.new_task(state="merge_gate", published=True)
    out = stand.approve(task)
    call = opened_ok(stand, task, out)
    where = stand.context(task, out)
    assert call["assignee"] == expected, where
    assert type(call["assignee"]) is type(expected), where
    text = stand.new_journal(task)
    if value == "alice":
        assert NOT_NUMERIC in text, where
    if value is None:
        assert "исполнител" in text, where


# ------------------------------------------------------------------- AC-2


def test_ac2_gate_opens_mr_and_records_link(stand):
    """`approve` гейта мержа: публикация головы, мьютекс, MR ветки в `base`, ссылка в столбцах и журнале, `awaiting_human`.

    Сценарий: запись `target-human`, `draft_mr: false`; ветка задачи на
    `merge_gate` на сервер ещё не отправлена. После `approve` голова ветки
    на сервере равна подтверждённому sha; мьютекс merge-окна взят этой
    задачей раньше вызова `open_mr`; `open_mr` звана для ветки задачи и
    `base` записи; задача в `awaiting_human`; `mr_iid`/`mr_url` задачи —
    `iid` и адрес ответа `open_mr`; адрес MR — в журнале задачи.

    Ловит мутацию: ссылка MR не записана в столбцы (пусты) или записана
    только в журнал; либо MR открыт до захвата мьютекса (порядок событий
    обратный); либо голова не опубликована до MR (сервер её не видит);
    либо MR открыт в ветку, отличную от `base`.
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate")
    head = stand.head(task)
    out = stand.approve(task)
    call = opened_ok(stand, task, out)
    where = stand.context(task, out)
    assert call["branch"] == stand.branch(task), where
    assert call["base"] == config.MAIN_BRANCH, where
    assert stand.origin_head(task) == head, where
    iid, url = stand.fake.opened[0]
    assert stand.mr(task) == (iid, url), where
    assert url in stand.new_journal(task), where
    names = [e for e in stand.events if e[0] in ("acquire", "open_mr")]
    assert ("acquire", task) in names, where
    assert names.index(("acquire", task)) < [e[0] for e in names].index(
        "open_mr"), where


def test_ac2_live_canary_refuses_before_open_mr(stand):
    """Живая канарейка: `approve` записи `target-human` отказывает, `open_mr` не зван.

    Сценарий: запись `target-human`, задача на `merge_gate`, ветка на
    сервере; `canary.live_run_note` отвечает живым прогоном набора по
    умолчанию. `approve` отказывает, задача на `merge_gate`, ни одного
    вызова `open_mr`, ссылки на MR в БД нет.

    Ловит мутацию: сверка канарейки оставлена только для артели (как
    сегодня `_refuse_during_canary`) — для `target-human` MR открыт, задача
    в `awaiting_human`.
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True)
    note = f"идёт канарейка {stand.word()} на {stand.hexsha()[:7]}"
    with mock.patch.object(canary, "live_run_note",
                           lambda default_set_only=False: note):
        out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.fake.named("open_mr") == [], where
    assert stand.state(task) == "merge_gate", where
    assert stand.mr(task) == (None, None), where


# ------------------------------------------------------------------- AC-3


def test_ac3_no_merge_no_base_push_no_closing(stand):
    """Гейт `target-human` не сливает, не отправляет `base`, не закрывает и не убирает задачу.

    Сценарий: успешный `approve` записи `target-human` (MR открыт). Шпион
    git не видит ни одного `git merge` и ни одной отправки в `base`;
    голова `base` на сервере прежняя; в ссылке документов задачи нет
    `RETRO.md` (коммита закрытия не было); рабочая копия, локальная ветка и
    ветка на сервере на месте; записи «CI main после мержа» (ожидание CI
    base) нет; задача не `done`.

    Ловит мутацию: ветвление по гейту стоит после плотницкого слияния (в
    журнале шпиона `git merge --no-ff`, голова `base` сдвинута); либо после
    открытия MR выполняются закрытие и уборка прежнего пути (`RETRO.md` в
    ссылке, рабочей копии нет).
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True)
    base_before = stand.main_sha()
    out = stand.approve(task)
    opened_ok(stand, task, out)
    where = stand.context(task, out)
    assert not [c for c in stand.git_calls if git_sub(c) == "merge"], where
    base_pushes = [p for p in stand.pushes
                   if any(a.endswith(f":{config.MAIN_BRANCH}")
                          or a.endswith(f"refs/heads/{config.MAIN_BRANCH}")
                          for a in p)]
    assert base_pushes == [], where
    assert stand.main_sha() == base_before, where
    assert not any(f.endswith("RETRO.md") for f in stand.artifact_files(task)), \
        where
    assert stand.wt(task).is_dir(), where
    assert REAL_RUN(["git", "-C", str(stand.clone), "rev-parse", "--verify",
                     f"refs/heads/{stand.branch(task)}"],
                    capture_output=True).returncode == 0, where
    assert stand.origin_head(task) == stand.head(task), where
    assert "CI main после мержа" not in stand.journal(task), where
    assert stand.state(task) != "done", where


# ------------------------------------------------------------------- AC-4


@pytest.mark.parametrize("red", ["base", "голова ветки"])
def test_ac4_base_ci_ignored_branch_ci_required(stand, red):
    """Красный CI base не держит MR; красный CI головы ветки — отказ без MR.

    Сценарий: запись `target-human`, задача на `merge_gate`, ветка на
    сервере. «base»: цвет CI base (`ci.main_line_status`) красный и
    конвейер головы `base` красный — `approve` открывает MR, задача в
    `awaiting_human`. «голова ветки»: конвейер подтверждённой головы
    красный — отказ, `open_mr` не зван, задача на `merge_gate`.

    Ловит мутацию: `_refuse_if_main_red` (или сверка CI base через `forge`)
    исполняется и для `target-human` — красный base отказывает; либо зелёный
    CI головы ветки не требуется — MR открыт при красной голове.
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True)
    if red == "base":
        stand.main_kind = ci.MAIN_RED
        stand.fake.red.add(stand.main_sha())
    else:
        stand.fake.red.add(stand.head(task))
    out = stand.approve(task)
    where = stand.context(task, out)
    if red == "base":
        opened_ok(stand, task, out)
        return
    assert stand.fake.named("open_mr") == [], where
    assert stand.state(task) == "merge_gate", where


# ------------------------------------------------------------------- AC-5


@pytest.mark.parametrize("case", ["sha не голова", "сервер другой"])
def test_ac5_confirmed_sha_must_match_head_and_server(stand, case):
    """Подтверждённый sha обязан совпасть с головой, уходящей в MR, и с головой на сервере.

    Сценарий: запись `target-human`, задача на `merge_gate`. «sha не
    голова» — Оператор получил sha фиксации, после неё в ветку лёг новый
    коммит (голова, которая ушла бы в MR, другая), `approve` прежним sha.
    «сервер другой» — `approve` sha свежей фиксации, ветки на сервере ещё
    нет; хук `post-receive` bare `origin` при публикации перевешивает ветку
    на чужой коммит поверх отправленного (отправка успешна, голова сервера
    другая). В обоих — отказ, `open_mr` не зван, задача на `merge_gate`.

    Ловит мутацию: после публикации голова сервера не сверяется с
    подтверждённым sha (MR открыт, хотя сервер несёт чужой коммит); либо в
    MR уходит голова ветки, не сверенная с подтверждённой фиксацией.
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", commits=2)
    if case == "sha не голова":
        stand.publish_raw(task)
        store.record_fixation(stand.conn, task)
        sha = store.get_task(stand.conn, task)["fixed_sha"]
        stand.commit_code(task, {f"kod/{stand.word()}.py": f"P = {stand.seed}\n"})
        out = stand.approve(task, sha, refix=False)
    else:
        hook = stand.bare / "hooks" / "post-receive"
        hook.write_text(POST_RECEIVE.format(branch=stand.branch(task)),
                        encoding="utf-8")
        hook.chmod(0o755)
        out = stand.approve(task)
    where = stand.context(task, out)
    if case == "сервер другой":
        assert stand.origin_head(task) not in ("", stand.head(task)), \
            stand.note(f"стенд: хук не перевесил ветку\n{where}")
    assert stand.fake.named("open_mr") == [], where
    assert stand.state(task) == "merge_gate", where


# ------------------------------------------------------------------- AC-6


def test_ac6_base_moved_returns_to_in_dev(stand):
    """Сдвиг `base` на `approve`: без подтяжки на гейте, задача в `in_dev` с причиной, MR не открыт.

    Сценарий: запись `target-human`, задача на `merge_gate`, ветка на
    сервере; после ответвления ветки `base` на сервере ушёл вперёд кодовым
    коммитом. `approve`: шпион git не видит ни `git merge`, ни отправки
    ветки задачи; голова ветки прежняя; задача в `in_dev`; в журнале —
    «base сдвинулся — подготовка ветки заново»; `open_mr` не зван.

    Ловит мутацию: прежняя подтяжка на гейте (`_sync_main_or_wait`) для
    `target-human` — в журнале шпиона `git merge` и отправка ветки, задача
    остаётся на `merge_gate`.
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True)
    head = stand.head(task)
    stand.commit_to_main({f"kod_main/{stand.word()}.py": f"M = {stand.seed}\n"})
    out = stand.approve(task)
    where = stand.context(task, out)
    assert not [c for c in stand.git_calls if git_sub(c) == "merge"], where
    assert stand.branch_pushes(task) == [], where
    assert stand.head(task) == head, where
    assert stand.state(task) == "in_dev", where
    assert BASE_MOVED in stand.new_journal(task), where
    assert stand.fake.named("open_mr") == [], where


# ------------------------------------------------------------------- AC-7


def test_ac7_plan_appendix_refused(stand):
    """Задача с приложением PLAN в проекте `target-human` — отказ `approve` с причиной, MR не открыт.

    Сценарий: запись `target-human`, PLAN задачи несёт приложение к
    защищённому пути проекта (`conf/settings.yaml` из `no_paths`), дифф
    применим к `base`. `approve`: в выводе или журнале — «приложения не
    применяются в проекте с target-human — правку вносят люди проекта»,
    `open_mr` не зван, задача на `merge_gate`.

    Ловит мутацию: приложения PLAN для `target-human` не проверяются — MR
    открыт, правка Оператора теряется (задача в `awaiting_human`).
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True, appendix=True)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert APPENDIX_REFUSAL in out + stand.new_journal(task), where
    assert stand.fake.named("open_mr") == [], where
    assert stand.state(task) == "merge_gate", where


# ------------------------------------------------------------------- AC-8


def test_ac8_open_mr_refusal_keeps_gate(stand):
    """Отказ `forge` при открытии MR — задача на `merge_gate` с причиной, ссылки на MR нет.

    Сценарий: запись `target-human`, задача на `merge_gate`, ссылки на MR
    в БД нет; подделка отвечает на `open_mr` отказом с причиной хостинга
    (5xx). Задача на `merge_gate`, текст причины хостинга — в выводе или
    журнале, `mr_iid`/`mr_url` пусты.

    Ловит мутацию: результат `open_mr` не проверяется на `reason` — задача
    уходит в `awaiting_human` без MR (или с пустой ссылкой).
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True)
    reason = (f"ошибка сервера GitLab (502) на POST /projects/grp%2F{stand.ext}"
              f"/merge_requests после 3 попыток {stand.word()}")
    stand.fake.fail["open_mr"] = reason
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == "merge_gate", where
    assert reason in out + stand.new_journal(task), where
    assert stand.mr(task) == (None, None), where


# ------------------------------------------------------------------- AC-9


def test_ac9_existing_link_undrafts_and_assigns(stand):
    """Заполненный `mr_iid`: без `open_mr`, `undraft_mr` и `assign_mr` по этому `mr_iid`, задача в `awaiting_human`.

    Сценарий: запись `target-human` с `mr_assignee: "42"`, у задачи на
    `merge_gate` в БД уже ссылка на черновой MR (случайный `mr_iid`).
    `approve`: `open_mr` не зван, `undraft_mr` и `assign_mr` званы с этим
    `mr_iid`, задача в `awaiting_human`, ссылка в БД прежняя.

    Ловит мутацию: наличие ссылки не читается — открыт второй MR
    (`open_mr` зван); либо черновик не снят (`undraft_mr` не зван) или
    исполнитель не назначен.
    """
    stand.record(mr_assignee='"42"')
    task = stand.new_task(state="merge_gate", published=True)
    iid = stand.rng.randrange(100, 10 ** 6)
    url = f"https://localhost/grp/{stand.ext}/-/merge_requests/{iid}"
    store.update_task(stand.conn, task, mr_iid=iid, mr_url=url)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.fake.named("open_mr") == [], where
    assert [c["mr"] for c in stand.fake.named("undraft_mr")] == [iid], where
    assert [c["mr"] for c in stand.fake.named("assign_mr")] == [iid], where
    assert stand.state(task) == "awaiting_human", where
    assert stand.mr(task) == (iid, url), where


# ------------------------------------------------------------------ AC-10


@pytest.mark.parametrize("code", [409, 403])
def test_ac10_conflict_409_escalates_other_codes_stay(stand, code):
    """409 от `open_mr` без ссылки в БД — эскалация без второго MR; иной код — задача на гейте.

    Сценарий: запись `target-human`, задача на `merge_gate`, ссылки в БД
    нет; подделка отвечает на `open_mr` причиной в тексте адаптера GitLab:
    409 — «GitLab ответил кодом 409 на POST …», 403 — «доступ запрещён
    (403) на POST …». 409: задача `escalated`, в журнале — «MR ветки уже
    существует, ссылки в БД нет», `open_mr` зван ровно один раз. 403:
    задача на `merge_gate`, не эскалирована, причина хостинга — в выводе
    или журнале, `open_mr` зван один раз.

    Ловит мутацию: 409 не отличается от прочих отказов (задача на
    `merge_gate`, не `escalated`); либо отказ любого кода эскалирует (403 —
    `escalated`); либо после 409 открытие повторяется (два вызова `open_mr`).
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True)
    pair = f"POST /projects/grp%2F{stand.ext}/merge_requests"
    reason = (f"GitLab ответил кодом 409 на {pair}" if code == 409
              else f"доступ запрещён (403) на {pair}")
    stand.fake.fail["open_mr"] = reason
    out = stand.approve(task)
    where = stand.context(task, out)
    assert len(stand.fake.named("open_mr")) == 1, where
    if code == 409:
        assert stand.state(task) == "escalated", where
        assert MR_EXISTS in stand.new_journal(task), where
        return
    assert stand.state(task) == "merge_gate", where
    assert reason in out + stand.new_journal(task), where


# ------------------------------------------------------------------ AC-11


@pytest.mark.parametrize("failing", ["undraft_mr", "assign_mr"])
def test_ac11_undraft_or_assign_refusal_no_second_mr(stand, failing):
    """Отказ `undraft_mr`/`assign_mr` — задача на гейте с причиной; повторный `approve` не открывает второй MR.

    Сценарий: запись `target-human` с `mr_assignee: "42"`, у задачи на
    `merge_gate` ссылка на MR в БД; подделка отказывает функцией по
    параметру. Задача на `merge_gate`, причина хостинга — в выводе или
    журнале. Отказ снят, повторный `approve`: `open_mr` не зван ни разу,
    задача в `awaiting_human`.

    Ловит мутацию: отказ `undraft_mr`/`assign_mr` не проверяется (задача в
    `awaiting_human` после первого же `approve`); либо отказ стирает ссылку
    из БД и повторный `approve` открывает второй MR.
    """
    stand.record(mr_assignee='"42"')
    task = stand.new_task(state="merge_gate", published=True)
    iid = stand.rng.randrange(100, 10 ** 6)
    store.update_task(stand.conn, task, mr_iid=iid,
                      mr_url=f"https://localhost/mr/{iid}")
    reason = (f"доступ запрещён (403) на PUT /projects/grp%2F{stand.ext}"
              f"/merge_requests/{iid} {stand.word()}")
    stand.fake.fail[failing] = reason
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == "merge_gate", where
    assert reason in out + stand.new_journal(task), where
    assert stand.fake.named("open_mr") == [], where
    stand.fake.fail.clear()
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.fake.named("open_mr") == [], where
    assert stand.state(task) == "awaiting_human", where


# ------------------------------------------------------------------ AC-12


@pytest.mark.parametrize("full", [True, False])
def test_ac12_max_awaiting_counts_own_project(stand, full):
    """Предел `max_awaiting`: N задач своего проекта в `awaiting_human` — отказ и строка `status`; N−1 — проход при любом числе чужих.

    Сценарий: запись `target-human` с `max_awaiting` = N (случайное 1–3).
    «полно»: N задач этого проекта в `awaiting_human` — `approve` (N+1)-й
    задачи отказывает с причиной (в выводе или журнале — `awaiting_human`),
    задача на `merge_gate`, `open_mr` не зван, строка `status` задачи
    несёт «очередь: предел awaiting_human». «не полно»: N−1 задач этого
    проекта и случайное число задач другого проекта в `awaiting_human` —
    `approve` открывает MR.

    Ловит мутацию: счёт по всем проектам (чужие задачи заполняют предел —
    «не полно» отказывает); либо сравнение `>` вместо `>=` (при N задачах
    MR открыт); либо отказ без строки очереди в `status`.
    """
    limit = stand.pick(1, 3)
    stand.record(draft_mr="false", max_awaiting=str(limit))
    task = stand.new_task(state="merge_gate", published=True)
    own = limit if full else limit - 1
    for _ in range(own):
        stand.ghost("awaiting_human", record=None)
    if not full:
        for _ in range(stand.pick(1, 4)):
            stand.ghost("awaiting_human", project=stand.other, record=None)
    out = stand.approve(task)
    where = stand.context(task, out) + f"\nпредел {limit}, своих {own}"
    if not full:
        opened_ok(stand, task, out)
        return
    assert stand.fake.named("open_mr") == [], where
    assert stand.state(task) == "merge_gate", where
    assert "awaiting_human" in out + stand.new_journal(task), where
    block = stand.status_block(task)
    assert AWAITING_QUEUE in block, where + f"\n--- status:\n{block}"


# ------------------------------------------------------------------ AC-13


def test_ac13_draft_on_verifying_undraft_on_gate(stand):
    """`draft_mr: true`: черновой MR через `forge` на входе в `verifying`, ссылка сразу; на гейте снят черновик, второго MR нет.

    Сценарий: запись `target-human`, `draft_mr: true`; задача в `in_dev`
    с коммитами, ветка не отправлена. Переход в `verifying`: `open_mr`
    зван один раз с `draft=True` для ветки задачи, шпион `gh` не видит `pr
    create`, `mr_iid`/`mr_url` — ответ `open_mr`. Задача переведена на
    `merge_gate`; `approve`: `undraft_mr` зван с тем же `mr_iid`, `open_mr`
    больше не зван, задача в `awaiting_human`.

    Ловит мутацию: черновик заводится прежним `gh pr create` (шпион видит
    `pr create`, `open_mr` не зван); либо ссылка не записана на входе в
    `verifying` и гейт открывает второй MR.
    """
    stand.record(draft_mr="true")
    task = stand.new_task()
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    calls = stand.fake.named("open_mr")
    assert len(calls) == 1 and calls[0]["draft"] is True, where
    assert calls[0]["branch"] == stand.branch(task), where
    assert not [c for c in stand.gh_calls if c[:2] == ["pr", "create"]], where
    iid, url = stand.fake.opened[0]
    assert stand.mr(task) == (iid, url), where
    stand.to_merge_gate(task)
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.fake.named("open_mr") == [], where
    assert [c["mr"] for c in stand.fake.named("undraft_mr")] == [iid], where
    assert stand.state(task) == "awaiting_human", where


def test_ac13_amend_tests_first_push_opens_no_mr(stand):
    """Первая отправка ветки на пути `amend-tests` записи с `draft_mr: true` не зовёт `open_mr`.

    Сценарий: запись `target-human`, `draft_mr: true`; задача в `in_dev`
    с долгоживущим файлом, ветка ни разу не отправлена. `amend-tests` с
    правкой долгоживущего файла коммитит и отправляет ветку (голова на
    сервере — голова ветки), `open_mr` не зван.

    Ловит мутацию: черновой MR открывается в общей точке первой отправки
    (`ensure_head_in_origin`) — путь `amend-tests` зовёт `open_mr`.
    """
    stand.record(draft_mr="true")
    task = stand.new_task()
    rel = stand.with_long_lived(task)
    out = stand.amend(task, rel)
    where = stand.context(task, out)
    assert stand.origin_head(task) == stand.head(task), \
        stand.note(f"стенд: amend-tests не отправил ветку\n{where}")
    assert stand.fake.named("open_mr") == [], where


# ------------------------------------------------------------------ AC-14


def test_ac14_no_draft_mr_opens_only_on_gate(stand):
    """`draft_mr: false`: на входе в `verifying` MR нет, MR открывается на `approve` гейта.

    Сценарий: запись `target-human`, `draft_mr: false`; задача в `in_dev`.
    Переход в `verifying` состоялся, ветка на сервере, `open_mr` не зван,
    ссылки в БД нет. Задача на `merge_gate`, `approve` открывает MR —
    `open_mr` зван один раз, задача в `awaiting_human`.

    Ловит мутацию: `draft_mr` не читается и черновик открывается всегда
    (`open_mr` зван на входе в `verifying`); либо при `false` MR не
    открывается и на гейте.
    """
    stand.record(draft_mr="false")
    task = stand.new_task()
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    assert stand.origin_head(task) == stand.head(task), where
    assert stand.fake.named("open_mr") == [], where
    assert stand.mr(task) == (None, None), where
    stand.to_merge_gate(task)
    out = stand.approve(task)
    opened_ok(stand, task, out)


# ------------------------------------------------------------------ AC-15
# Положительная половина AC-15 («называет изменённые веткой защищённые
# пути») недостижима при действующих гейтах: ветку с правкой пути из
# `no_paths` гейт зон на выходе из `in_dev` отклоняет до отправки, гейт
# мержа эскалирует до открытия MR. Решение Оператора (ANSWER-1, вариант
# (а)): проверяются отрицательная половина и последняя фраза критерия.


@pytest.mark.parametrize("draft", [True, False])
def test_ac15_description_omits_unchanged_protected_paths(stand, draft):
    """Описание MR не называет защищённые пути проекта, веткой не изменённые.

    Сценарий: запись `target-human` с `no_paths: [conf/settings.yaml]` (файл
    есть в `base`, ветка его не трогает). «черновик» (`draft_mr: true`) —
    описание `open_mr` на входе в `verifying`; «гейт» (`draft_mr: false`)
    — описание `open_mr` на `approve` гейта мержа. В описании нет
    `conf/settings.yaml`.

    Ловит мутацию: в описании перечислены все защищённые пути проекта
    (`repo_context.protected_paths`), а не изменённые веткой — в теле
    `open_mr` есть `conf/settings.yaml`.
    """
    stand.record(draft_mr="true" if draft else "false")
    task = stand.new_task()
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    if not draft:
        stand.to_merge_gate(task)
        out = stand.approve(task)
        where = stand.context(task, out)
    calls = stand.fake.named("open_mr")
    assert len(calls) == 1, where
    assert PROTECTED_UNCHANGED not in str(calls[0]["body"]), \
        where + f"\n--- описание:\n{calls[0]['body']}"


def test_ac15_gate_with_link_talks_to_mr_only_by_undraft_and_assign(stand):
    """На `approve` задачи с заполненным `mr_iid` к MR — только `undraft_mr` и `assign_mr`.

    Сценарий: запись `target-human` с `mr_assignee: "42"`, ссылка на MR
    в БД. За весь `approve` подделка хостинга не видит ни одного вызова о
    MR (функции интерфейса `forge` с «mr» в имени), кроме `undraft_mr` и
    `assign_mr`; задача в `awaiting_human`.

    Ловит мутацию: гейт перечитывает или правит MR (`mr_status`, повторный
    `open_mr` ради обновления описания) — в журнале подделки вызов вне
    `undraft_mr`/`assign_mr`.
    """
    stand.record(mr_assignee='"42"')
    task = stand.new_task(state="merge_gate", published=True)
    iid = stand.rng.randrange(100, 10 ** 6)
    store.update_task(stand.conn, task, mr_iid=iid,
                      mr_url=f"https://localhost/mr/{iid}")
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.state(task) == "awaiting_human", where
    talked = {c["name"] for c in stand.fake.calls if c["name"] in MR_CALLS}
    assert talked <= {"undraft_mr", "assign_mr"}, where


# ------------------------------------------------------------------ AC-16


IN_FLIGHT_STATES = ["review", "in_dev", "escalated", "awaiting_human"]


@pytest.mark.parametrize("case", ["предел", "другой проект", "закрытые"])
def test_ac16_max_in_flight_on_verifying_entry(stand, case):
    """`max_in_flight` на входе в `verifying`: N незакрытых своих с «ветка отправлена» — отправки нет; N−1 — отправка при любом числе чужих и закрытых.

    Сценарий: запись `target-human`, `draft_mr: false`, `max_in_flight` = N
    (случайное 4–6). «предел»: N задач этого проекта с записью «ветка
    отправлена» — среди них `review`, `in_dev`, `escalated`,
    `awaiting_human` — задача без записи на переходе в `verifying` ветку не
    отправляет (шпион не видит её отправки, на сервере ветки нет),
    остаётся в `in_dev`, причина предела (`max_in_flight` или «предел»)
    — в журнале и в строке `status`. «другой проект»: N−1 своих и
    случайное число таких задач другого проекта — ветка отправлена, задача
    в `verifying`. «закрытые»: N−1 своих и случайное число своих `done`/
    `killed` с записью — ветка отправлена.

    Ловит мутацию: счёт без отбора по проекту (чужие задачи заполняют
    предел); либо счёт без отбора по состоянию (закрытые заполняют
    предел); либо счёт только по `verifying`/`review` (задачи `in_dev`,
    `escalated`, `awaiting_human` не считаются — при «предел» ветка
    отправлена).
    """
    limit = stand.pick(4, 6)
    stand.record(draft_mr="false", max_in_flight=str(limit))
    states = list(IN_FLIGHT_STATES)
    states += [stand.rng.choice(IN_FLIGHT_STATES) for _ in range(limit - 4)]
    stand.rng.shuffle(states)
    own = states if case == "предел" else states[:-1]
    for state in own:
        stand.ghost(state)
    if case == "другой проект":
        for _ in range(stand.pick(1, 4)):
            stand.ghost(stand.rng.choice(IN_FLIGHT_STATES), project=stand.other)
    if case == "закрытые":
        for _ in range(stand.pick(1, 4)):
            stand.ghost(stand.rng.choice(["done", "killed"]))
    task = stand.new_task()
    out = stand.advance(task)
    where = stand.context(task, out) + f"\nпредел {limit}, своих {len(own)}"
    if case != "предел":
        assert stand.state(task) == "verifying", where
        assert stand.origin_head(task) == stand.head(task), where
        return
    assert stand.branch_pushes(task) == [], where
    assert stand.origin_head(task) == "", where
    assert stand.state(task) == "in_dev", where
    assert limit_named(stand.new_journal(task)), where
    block = stand.status_block(task)
    assert limit_named(block), where + f"\n--- status:\n{block}"


def limit_named(text: str) -> bool:
    """Текст называет предел отправок: имя поля или слово «предел»."""
    return "max_in_flight" in text or "предел" in text


# ------------------------------------------------------------------ AC-17


def test_ac17_max_in_flight_on_amend_tests(stand):
    """`max_in_flight` на пути `amend-tests`: при N своих задачах с «ветка отправлена» ветка без записи не отправлена, причина в журнале.

    Сценарий: запись `target-human`, `max_in_flight` = N (случайное 1–4),
    N задач этого проекта с записью «ветка отправлена» в незакрытых
    состояниях; задача в `in_dev` с долгоживущим файлом, ветка ни разу не
    отправлена. `amend-tests` с правкой долгоживущего файла: шпион argv git
    не видит отправки её ветки, на сервере ветки нет, причина предела — в
    журнале задачи.

    Ловит мутацию: предел проверяется только на переходе `in_dev ->
    verifying`, а не в единой точке отправки `gitcmd` — `amend-tests`
    отправляет ветку.
    """
    limit = stand.pick(1, 4)
    stand.record(draft_mr="false", max_in_flight=str(limit))
    for _ in range(limit):
        stand.ghost(stand.rng.choice(IN_FLIGHT_STATES))
    task = stand.new_task()
    rel = stand.with_long_lived(task)
    out = stand.amend(task, rel)
    where = stand.context(task, out) + f"\nпредел {limit}"
    assert stand.branch_pushes(task) == [], where
    assert stand.origin_head(task) == "", where
    assert limit_named(stand.new_journal(task)), where


# ------------------------------------------------------------------ AC-18


@pytest.mark.parametrize("sent", [False, True])
def test_ac18_max_in_flight_on_github_draft_mr(stand, sent):
    """`max_in_flight` на черновом MR GitHub (`ensure_draft_mr`): первая отправка отказана до git, повторная — без отказа.

    Сценарий: запись `forge: github`, гейт `operator`, `max_in_flight` = N
    (случайное 1–4), N задач этого проекта с записью «ветка отправлена».
    Задача в `in_dev` с коммитами, черновик не заведён; вызван
    `github_adapter.ensure_draft_mr`. Без записи у задачи: шпион не видит
    отправки её ветки, на сервере ветки нет, причина предела — в журнале.
    С записью «ветка отправлена» у задачи: ветка отправлена (голова на
    сервере — голова ветки), причины предела в журнале нет.

    Ловит мутацию: предел стоит только на переходах FSM, а
    `ensure_draft_mr` отправляет мимо него; либо предел отказывает и
    повторной отправке задачи, у которой запись уже есть.
    """
    limit = stand.pick(1, 4)
    stand.record(gate="operator", forge_name="github", max_in_flight=str(limit))
    for _ in range(limit):
        stand.ghost(stand.rng.choice(["in_dev", "review", "escalated"]))
    task = stand.new_task()
    store.update_task(stand.conn, task, draft_mr_created=0)
    if sent:
        store.journal(stand.conn, task, "orchestrator", SENT,
                      f"{stand.hexsha()} {stand.branch(task)}")
    stand.reset_spies()
    stand.before = len(stand.rows(task))
    out = capture_out(github_adapter.ensure_draft_mr, stand.conn, task,
                      store.get_task(stand.conn, task))
    where = stand.context(task, out) + f"\nпредел {limit}"
    if sent:
        assert stand.origin_head(task) == stand.head(task), where
        assert not limit_named(stand.new_journal(task)), where
        return
    assert stand.branch_pushes(task) == [], where
    assert stand.origin_head(task) == "", where
    assert limit_named(stand.new_journal(task)), where


# ------------------------------------------------------------------ AC-20


def test_ac20_max_awaiting_counted_under_merge_mutex(stand):
    """Два параллельных `approve` при N−1 задачах в `awaiting_human`: проходит ровно один.

    Сценарий: запись `target-human`, `max_awaiting` = N (случайное 1–3),
    N−1 задач этого проекта в `awaiting_human`; задачи A и B на
    `merge_gate`. `approve` B идёт в отдельном потоке и останавливается
    перед захватом мьютекса merge-окна (`merge_lock.acquire`), пока
    `approve` A проходит целиком; затем B продолжает. A — в
    `awaiting_human` с MR; B — на `merge_gate`, причина предела
    (`awaiting_human`) в её журнале, MR для ветки B не открыт.

    Ловит мутацию: счёт `max_awaiting` до захвата мьютекса — B сосчитала
    N−1 до ожидания и открыла второй MR (обе задачи в `awaiting_human`).
    """
    limit = stand.pick(1, 3)
    stand.record(draft_mr="false", max_awaiting=str(limit))
    for _ in range(limit - 1):
        stand.ghost("awaiting_human", record=None)
    first = stand.new_task(state="merge_gate", published=True)
    second = stand.new_task(state="merge_gate", published=True)
    for task in (first, second):
        store.record_fixation(stand.conn, task)
    shas = {task: store.get_task(stand.conn, task)["fixed_sha"]
            for task in (first, second)}
    main = threading.current_thread()
    at_mutex, first_done = threading.Event(), threading.Event()
    blocked: list = []
    spied = merge_lock.acquire

    def acquire(conn, task_id, session_id, *args, **kwargs):
        if task_id == second and threading.current_thread() is not main:
            blocked.append(task_id)
            at_mutex.set()
            first_done.wait(timeout=60)
        return spied(conn, task_id, session_id, *args, **kwargs)

    exits: list = []

    def run_second():
        try:
            fsm.cmd_approve(second, shas[second])
        except SystemExit as exc:
            exits.append(exc.code)
        except BaseException as exc:  # noqa: BLE001 — текст провала потока
            exits.append(f"{type(exc).__name__}: {exc}")
        finally:
            at_mutex.set()

    stand.reset_spies()
    with stand.spy(), mock.patch.object(merge_lock, "acquire", acquire):
        worker = threading.Thread(target=run_second, daemon=True)
        worker.start()
        at_mutex.wait(timeout=60)
        out = capture_out(fsm.cmd_approve, first, shas[first])
        first_done.set()
        worker.join(timeout=60)
    where = (stand.context(first, out) + "\n--- журнал B:\n"
             + stand.journal(second) + f"\nвыходы B: {exits}\nпредел {limit}")
    assert blocked, stand.note(f"стенд: approve B не дошёл до мьютекса\n{where}")
    assert not worker.is_alive(), where
    assert stand.state(first) == "awaiting_human", where
    assert stand.state(second) == "merge_gate", where
    branches = [c["branch"] for c in stand.fake.named("open_mr")]
    assert branches == [stand.branch(first)], where
    assert "awaiting_human" in stand.journal(second) + " ".join(
        str(e) for e in exits), where


# ------------------------------------------------------------------ AC-21


def test_ac21_draft_refusal_keeps_in_dev_and_retries(stand):
    """Отказ `open_mr(draft=True)` на входе в `verifying` — задача в `in_dev` с причиной; следующий `advance` открывает черновик снова.

    Сценарий: запись `target-human`, `draft_mr: true`; задача в `in_dev`.
    Подделка отказывает `open_mr` причиной хостинга: переход не выполнен,
    задача в `in_dev`, причина хостинга — в журнале, строка `status`
    называет причину про MR (сегодня строка задачи слова «MR» не несёт),
    `mr_iid` пуст, голова ветки уже на сервере. Отказ снят, второй
    `advance`: `open_mr` зван снова с `draft=True`, задача в `verifying`,
    `mr_iid`/`mr_url` — ответ второго вызова.

    Ловит мутацию: отказ чернового MR не останавливает переход (задача в
    `verifying` без ссылки); либо повтор открытия идёт только после
    успешной отправки (как `_ensure_draft_mr_after_publish`) — голова уже
    на сервере, второй `advance` `open_mr` не зовёт.
    """
    stand.record(draft_mr="true")
    task = stand.new_task()
    reason = (f"доступ запрещён (403) на POST /projects/grp%2F{stand.ext}"
              f"/merge_requests {stand.word()}")
    stand.fake.fail["open_mr"] = reason
    out = stand.advance(task)
    where = stand.context(task, out)
    assert len(stand.fake.named("open_mr")) == 1, where
    assert stand.state(task) == "in_dev", where
    assert reason in stand.new_journal(task), where
    block = stand.status_block(task)
    assert "MR" in block, where + f"\n--- status:\n{block}"
    assert stand.mr(task)[0] is None, where
    assert stand.origin_head(task) == stand.head(task), where
    stand.fake.fail.clear()
    out = stand.advance(task)
    where = stand.context(task, out)
    calls = stand.fake.named("open_mr")
    assert len(calls) == 1 and calls[0]["draft"] is True, where
    assert stand.state(task) == "verifying", where
    assert stand.mr(task) == stand.fake.opened[-1], where


# ------------------------------------------------------------------ AC-22


def test_ac22_legacy_sent_record_is_not_first_push(stand):
    """Только старая запись «ветка отправлена» у задачи — отправка без отказа пределом.

    Сценарий: запись `target-human`, `draft_mr: false`, `max_in_flight` =
    N (случайное 1–4), N задач этого проекта с записью «ветка
    отправлена»; у задачи в `in_dev` в журнале только
    `gitcmd.PUSH_SENT_LEGACY_ACTION`. Переход в `verifying` отправляет
    ветку (голова на сервере — голова ветки), задача в `verifying`,
    причины предела в журнале нет.

    Ловит мутацию: признак первой отправки читает только
    `PUSH_SENT_ACTION` — задача со старой записью считается новой и
    отказана пределом.
    """
    limit = stand.pick(1, 4)
    stand.record(draft_mr="false", max_in_flight=str(limit))
    for _ in range(limit):
        stand.ghost(stand.rng.choice(IN_FLIGHT_STATES))
    task = stand.new_task()
    store.journal(stand.conn, task, "orchestrator",
                  SENT_LEGACY,
                  f"{stand.hexsha()} {stand.branch(task)}")
    out = stand.advance(task)
    where = stand.context(task, out) + f"\nпредел {limit}"
    assert stand.state(task) == "verifying", where
    assert stand.origin_head(task) == stand.head(task), where
    assert not limit_named(stand.new_journal(task)), where
