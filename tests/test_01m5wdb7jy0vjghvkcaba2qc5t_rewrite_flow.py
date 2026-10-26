"""Коммиты пульта с автором, соавтором и трейлером; сжатие и перебазирование на входе в `verifying`; перезапись своей ветки и сверка автора с владельцем токена.

Группа: долгоживущий
Красен до реализации: поля записи `commit_author`, `co_author`, `squash_before_mr`, `commit_template`, `freshness` пульт не исполняет — ветка уходит на origin как есть (без сжатия, перебазирования и `--force-with-lease`), коммиты пульта пишутся служебной идентичностью без `Co-authored-by` и трейлера `Artel-Actor: orchestrator`, записей «коммит пульта», «ветка отправлена» и сверки `forge.token_user` нет, пакет ревью не знает перезаписи ветки; на сегодняшнем main запись с новыми полями даже не загружается.

Связка «команда пульта — FSM — база — git»: каждый сценарий доходит до
поведения через публичный вход (`fsm.cmd_advance`, `fsm.cmd_approve`,
`amend.cmd_amend_tests`, `pull_main.cmd_pull_main`, `checkpoint.
commit_step_artifacts`, `review.review_package`) в настоящем git песочницы
(`tests.sandbox.RealGitSandbox`): клон внешнего проекта
(`tests.sandbox.make_project_repo`) с bare `origin`, запись проекта — в
локальном слое (`targets.local_path()`), ссылка документов — автокоммитом
шага. Ветка задачи до первого перехода на сервер не отправлена.

Подменены только внешние для песочницы ответы: цвет CI (`ci.*` — итога CI
нет), Draft MR (`github_adapter.ensure_draft_mr`/`undraft_mr`), прогон
pytest у мест запуска (`acceptance`, `two_sided` — подменённый модуль
`subprocess` отвечает зелёным прогоном и запоминает голову рабочего
каталога и голову ветки на сервере в момент вызова), транспорт GitLab
(`gitlab_adapter.transport`, контракт — `(код, заголовки, тело bytes)`,
отказ сети — `urllib.error.URLError`) и слот связки ключей
(`keychain.token`). Отправки git наблюдаются обёрткой `subprocess.run`,
которая зовёт настоящий `subprocess.run`. Сеть недоступна — адрес
`origin` (или только адрес отправки) клона заменён на закрытый порт
`127.0.0.1`; отказ сервера не по сети — хук `pre-receive` bare `origin`.

Карта кодовой базы проекта-фикстуры — выход собственного
`scripts/codebase_map.py` проекта (пульт регенерирует карту им же,
интерпретатором процесса пульта в рабочей копии задачи); его заголовок
несёт число файлов — правки карты с двух сторон всегда конфликтуют.

Имена, файлы, автор, соавтор и пользователь токена — из `random`, зерно
печатается и входит в текст каждого провала.

Полный стаб реализации невозможен на сегодняшнем main: поля записи вводит
часть 1 деления (единая точка отправки и журнал «ветка отправлена» — тоже
она), а `forge.token_user` и `gitlab_adapter` — часть А1.1 (контракт
транспорта — ответ Оператора В-1 той задачи); обе — зависимости мержа.
Провалидировано временными стабами (удалены, не закоммичены): загрузка
полей записи — каждый сценарий доходит до перехода и краснеет только на
отсутствующем поведении задачи, места `merge` (AC-15) зелёные; подпись и
запись «коммит пульта» чекпоинта — зелёные AC-10/AC-11 этого вида; пакет
ревью с пометкой и базой `diff_base` — зелёный AC-14, мутация «полный дифф
от локальной основной ветки» его краснит.
"""
import contextlib
import dataclasses
import hashlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (acceptance, amend, catalog, checkpoint, ci, config,
                          fixation, fsm, github_adapter, idgen, keychain, pull,
                          pull_main, review, runner, snapshot, stack, store,
                          targets, workspace)
from orchestrator.advance_gates import two_sided
from scripts import guard
from tests.sandbox import (FakeProc, _stub_check_stack, is_claude_call,
                           make_project_repo)

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
TRAILER = "Artel-Actor: orchestrator"
SENT = re.compile(r"ветка отправлена: ([0-9a-f]{40})")
PULT_COMMIT = "коммит пульта: {sha}"
AFTER_ADAPTER = "сверка автора — после адаптера"
REWORK_ACTION = "переход отклонён: замечания ревью не отработаны"
STRAY_REFUSAL = "посторонние файлы в worktree"
REWRITTEN_MARK = "ветка перезаписана — дифф полный"
DEAD_URL = "https://127.0.0.1:9/team/unreachable.git"
IDENTITY = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")
REPO = Path(__file__).resolve().parent.parent
OUTPUT = "1 passed in 0.01s\n"
COLLECTED = "probe.py::test_probe\n\n1 test collected in 0.01s\n"
JUNIT = ('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite '
         'name="pytest" errors="0" failures="0" skipped="0" tests="1">'
         '<testcase classname="probe" name="test_probe" time="0.01"/>'
         '</testsuite></testsuites>')

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
      merge_gate: operator
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: {forge}
      url: https://localhost/grp/{name}
      token_slot: {name}-token
{machine}"""

MAP_SCRIPT = '''"""Карта кода проекта-фикстуры: заголовок с числом файлов и список."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
files = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py")
               if p.relative_to(ROOT).parts[0] not in (".git", "tasks"))
lines = [f"# Карта кода: {len(files)} файлов", ""]
lines += [f"- {rel}" for rel in files]
(ROOT / "docs" / "codebase-map.md").write_text("\\n".join(lines) + "\\n",
                                               encoding="utf-8")
'''

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
---

# SPEC: фикстура перезаписи ветки

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

REVIEW_TEXT = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 1
---

# REVIEW: фикстура

## Замечания
1. Почини {word}.
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


def is_git_push(argv) -> bool:
    parts = [str(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    return bool(parts) and Path(parts[0]).name == "git" and git_sub(parts) == "push"


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


def swap_text(value, old: str, new: str):
    """Значение с заменой `old` на `new` во всех строках на любой глубине."""
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, tuple):
        items = [swap_text(v, old, new) for v in value]
        return type(value)(*items) if hasattr(value, "_fields") else tuple(items)
    if isinstance(value, list):
        return [swap_text(v, old, new) for v in value]
    if isinstance(value, dict):
        return {k: swap_text(v, old, new) for k, v in value.items()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.replace(value, **{
            f.name: swap_text(getattr(value, f.name), old, new)
            for f in dataclasses.fields(value) if f.init})
    return value


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
    запоминает рабочий каталог, голову его git и голову ветки задачи на
    сервере в момент вызова и отвечает зелёным прогоном; прочие процессы
    идут настоящими."""

    def __init__(self, stand):
        self.stand = stand
        self.calls: list = []

    def __getattr__(self, name):
        return getattr(subprocess, name)

    def record(self, argv, kwargs) -> str:
        argv = [str(a) for a in argv]
        cwd = kwargs.get("cwd")
        here = Path(cwd) if cwd is not None else Path.cwd()
        head = REAL_RUN(["git", "-C", str(here), "rev-parse", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
        self.calls.append({"argv": argv, "cwd": str(here), "head": head,
                           "origin": self.stand.origin_heads()})
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
        text = self.record(argv, kwargs)
        return subprocess.CompletedProcess(argv, 0, text, "")

    def Popen(self, argv, *args, **kwargs):
        if not is_pytest(argv):
            return REAL_POPEN(argv, *args, **kwargs)
        text = self.record(argv, kwargs)
        out = kwargs.get("stdout")
        if hasattr(out, "write"):
            out.write(text.encode("utf-8") if "b" in getattr(out, "mode", "")
                      else text)
            out.flush()
        return SpyProc(argv, text)


class GitLabFake:
    """Поддельный транспорт GitLab: ответ `GET /user` по исходу сценария,
    прочие пары — 404."""

    def __init__(self):
        self.user = None
        self.status = 200
        self.exc = None
        self.calls: list = []

    def transport(self, method, url, headers=None, body=None, timeout=None,
                  *args, **kwargs):
        self.calls.append((str(method).upper(), str(url)))
        if self.exc is not None:
            raise self.exc
        if str(url).split("?")[0].rstrip("/").endswith("/user"):
            payload = self.user if self.user is not None else {}
            return (self.status, {"Content-Type": "application/json"},
                    json.dumps(payload).encode("utf-8"))
        return 404, {"Content-Type": "application/json"}, b'{"message": "404"}'


class Stand:
    """Пульт с клоном внешнего проекта и bare `origin`; запись проекта —
    в локальном слое, поля — по сценарию."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"proj{self.word()}"
        self.author = f"pult{self.word()}"
        self.email = f"{self.author}@{self.word(5)}.example"
        self.co_author = (f"Co-authored-by: Соавтор {self.word()} "
                          f"<{self.word()}@co.example>")
        self.template = f"сжато {self.word(4)}: {{text}}"
        self.pushes: list = []
        self.docs_files: dict = {}
        self.gitlab = GitLabFake()
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")

        self.git_calls: list = []

        def spy_run(*args, **kwargs):
            argv = args[0] if args else kwargs.get("args")
            if isinstance(argv, (list, tuple)) and argv and \
                    Path(str(argv[0])).name == "git":
                self.git_calls.append([str(a) for a in argv])
            if is_git_push(argv):
                self.pushes.append([str(a) for a in argv])
            return REAL_RUN(*args, **kwargs)

        for name in IDENTITY:
            os.environ.pop(name, None)
        for patcher in (
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch.object(ci, "branch_status",
                                  lambda branch, repo=None:
                                  (True, "зелёный (тест)")),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main),
                mock.patch.object(ci, "head_sha",
                                  lambda branch, repo=None: ("", "нет CI (тест)")),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: []),
                mock.patch.object(subprocess, "run", spy_run)):
            patcher.start()
            sb.addCleanup(patcher.stop)
        sb.add_synced_origin()
        self.clone = make_project_repo(self.ext)
        self.bare = config.PROJECTS / self.ext / "origin.git"
        self.record()
        capture_out(catalog.cmd_init)
        self.commit_to_main({"app.py": "VALUE = 1\n",
                             "scripts/codebase_map.py": MAP_SCRIPT,
                             "docs/notes.md": "# Заметки\n\n- база\n"},
                            regen_map=True)
        self.fork = self.main_sha()

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def git(self, *args) -> str:
        return self.sb.git(*[str(a) for a in args])

    def record(self, *, author: bool = True, co_author: bool = True,
               squash: bool = False, freshness: str = "merge",
               template: bool = False, forge: str = "github") -> None:
        """Запись проекта в локальном слое с полями сценария."""
        policy = ""
        if co_author:
            policy += f'      co_author: "{self.co_author}"\n'
        if squash:
            policy += "      squash_before_mr: true\n"
        if freshness != "merge":
            policy += f"      freshness: {freshness}\n"
        if template:
            policy += f'      commit_template: "{self.template}"\n'
        machine = ""
        if author:
            machine = (f"      commit_author:\n"
                       f"        name: {self.author}\n"
                       f"        email: {self.email}\n")
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text("targets:\n" + ENTRY.format(
            name=self.ext, base=config.MAIN_BRANCH, policy=policy,
            forge=forge, machine=machine), encoding="utf-8")

    def commit_to_main(self, files: dict, regen_map: bool = False) -> str:
        """Коммит в основную ветку проекта и отправка в его `origin`."""
        for rel, text in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        if regen_map:
            self.regen_map(self.clone)
        self.git("-C", self.clone, "add", "-A")
        self.git("-C", self.clone, "commit", "-q", "-m", f"main {self.word()}")
        self.git("-C", self.clone, "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        return self.main_sha()

    def main_sha(self) -> str:
        return self.git("--git-dir", self.bare, "rev-parse",
                        config.MAIN_BRANCH).strip()

    def regen_map(self, tree: Path) -> None:
        REAL_RUN([sys.executable, "scripts/codebase_map.py"], cwd=tree,
                 check=True, capture_output=True)

    def main_ahead_code(self) -> str:
        return self.commit_to_main({f"kod_main/{self.word()}.py":
                                    f"M = {self.seed}\n"})

    def main_ahead_docs(self) -> str:
        return self.commit_to_main({f"docs/main_{self.word()}.md":
                                    f"# {self.word()}\n"})

    # ------------------------------------------------------------ задача

    def new_task(self, state: str = "in_dev", commits: int = 2,
                 zones: str = "app.py, kod/, docs/",
                 dated: datetime | None = None) -> str:
        """Задача проекта: `commits` коммитов кода в ветке (не отправлена),
        SPEC/PLAN/планка в ссылке документов, лок планки."""
        task = idgen.new_task_id()
        branch = f"task/{task.lower()}-{self.word()}"
        self.title = f"Фикстура {self.word()} {self.word()}"
        store.insert_task(self.conn, task, self.title, state, branch, self.ext,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task, zones=zones)
        wt, error = workspace.ensure(task, branch)
        assert error is None, self.note(f"рабочая копия не заведена: {error}")
        for _ in range(commits):
            self.commit_code(task, {f"kod/{self.word()}.py":
                                    f"A = {self.rng.randrange(10**6)}\n"},
                             dated=dated)
        self.write_docs(task, {
            "SPEC.md": SPEC_TEXT.format(task=task, zones=zones),
            "PLAN.md": PLAN_TEXT.format(task=task),
            f"acceptance_tests/test_ac1_{self.word()}.py":
                PLANK_TEXT.format(word=self.word())})
        self.lock(task)
        return task

    def branch(self, task: str) -> str:
        return store.get_task(self.conn, task)["branch"]

    def wt(self, task: str) -> Path:
        return workspace.path(task, self.ext)

    def docs_dir(self, task: str) -> Path:
        return config.PROJECTS / self.ext / "tasks" / task

    def write_docs(self, task: str, files: dict, role: str = "developer") -> str:
        self.docs_files.setdefault(task, {}).update(files)
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

    def commit_code(self, task: str, files: dict,
                    dated: datetime | None = None) -> str:
        wt = self.wt(task)
        for rel, text in files.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        env = {}
        if dated is not None:
            stamp = dated.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            env = {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
        with mock.patch.dict(os.environ, env):
            self.git("-C", wt, "add", "-A")
            self.git("-C", wt, "commit", "-q", "-m", f"код {self.word()}")
        return self.head(task)

    # ------------------------------------------------------------ команды

    @contextlib.contextmanager
    def spy(self):
        spy = PytestSpy(self)
        with mock.patch.object(acceptance, "subprocess", spy), \
                mock.patch.object(two_sided, "subprocess", spy):
            yield spy

    def advance(self, task: str) -> str:
        with self.spy() as spy:
            out = capture_out(fsm.cmd_advance, task)
        self.plank_calls = spy.calls
        return out

    def back_to_in_dev(self, task: str) -> None:
        store.set_state(self.conn, task, "in_dev", "test",
                        expected_state=self.state(task),
                        detail="фикстура: следующая итерация")

    def publish_first(self, task: str) -> str:
        """Первый переход в `verifying` (первая отправка) и возврат в
        `in_dev` с новым коммитом разработчика; голова сервера после
        первой отправки."""
        out = self.advance(task)
        assert self.state(task) == "verifying", self.context(task, out)
        first = self.origin_head(task)
        assert first == self.head(task), self.context(task, out)
        self.back_to_in_dev(task)
        self.commit_code(task, {f"kod/{self.word()}.py": f"B = {self.seed}\n"})
        return first

    # ------------------------------------------------------------ наблюдение

    def state(self, task: str) -> str:
        return store.get_task(self.conn, task)["state"]

    def rows(self, task: str) -> list:
        return list(store.task_steps(self.conn, task))

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.rows(task))

    def context(self, task: str, out: str = "") -> str:
        return self.note(f"\n--- вывод:\n{out}\n--- журнал:\n{self.journal(task)}"
                         f"\n--- отправки:\n" + "\n".join(map(" ".join,
                                                                self.pushes)))

    def head(self, task: str) -> str:
        return self.git("-C", self.clone, "rev-parse", self.branch(task)).strip()

    def origin_head(self, task: str) -> str:
        return self.git("--git-dir", self.bare, "for-each-ref",
                        "--format=%(objectname)",
                        f"refs/heads/{self.branch(task)}").strip()

    def origin_heads(self) -> dict:
        out = self.git("--git-dir", self.bare, "for-each-ref",
                       "--format=%(refname) %(objectname)", "refs/heads/")
        return dict(line.split(" ", 1) for line in out.splitlines() if line)

    def parents(self, sha: str) -> list:
        return self.git("-C", self.clone, "rev-list", "--parents", "-n", "1",
                        sha).split()[1:]

    def count_over(self, base: str, sha: str) -> int:
        return int(self.git("-C", self.clone, "rev-list", "--count",
                            f"{base}..{sha}").strip())

    def is_ancestor(self, older: str, newer: str) -> bool:
        res = REAL_RUN(["git", "-C", str(self.clone), "merge-base",
                        "--is-ancestor", older, newer], capture_output=True)
        return res.returncode == 0

    def message(self, sha: str) -> list:
        return self.git("-C", self.clone, "log", "-1", "--format=%B",
                        sha).splitlines()

    def identity(self, sha: str) -> tuple:
        return tuple(self.git("-C", self.clone, "log", "-1",
                              "--format=%an%x00%ae%x00%cn%x00%ce",
                              sha).strip().split("\x00"))

    def dirty(self, task: str) -> str:
        return self.git("-C", self.wt(task), "status", "--porcelain").strip()

    def file_at(self, sha: str, rel: str) -> str:
        return self.git("-C", self.clone, "show", f"{sha}:{rel}")

    def sent_shas(self, task: str) -> list:
        return [m.group(1) for r in self.rows(task)
                for m in [SENT.search(f"{r['action']} {r['detail'] or ''}")] if m]

    def assert_signed(self, sha: str, where: str) -> None:
        """Автор и коммиттер — `commit_author`, строки `Co-authored-by` и
        трейлера пульта — в сообщении."""
        assert self.identity(sha) == (self.author, self.email, self.author,
                                      self.email), self.note(
            f"{where}: идентичность {self.identity(sha)}")
        lines = [line.strip() for line in self.message(sha)]
        assert self.co_author in lines, self.note(f"{where}: нет соавтора: {lines}")
        assert TRAILER in lines, self.note(f"{where}: нет трейлера: {lines}")

    def with_long_lived(self, task: str) -> str:
        """Долгоживущий файл задачи в ветке и перечень его суммы в планке;
        лок — на новой голове ссылки документов. Путь файла."""
        rel = f"tests/test_{task.lower()}_{self.word()}.py"
        self.commit_code(task, {rel: LONG_LIVED_TEXT.format(
            cls=self.word().capitalize(), word=self.word())})
        digest = hashlib.sha256((self.wt(task) / rel).read_bytes()).hexdigest()
        self.write_docs(task, {
            f"acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}":
                guard.render_long_lived_manifest({rel: digest})})
        self.lock(task)
        return rel

    def amend(self, task: str, rel: str) -> str:
        """`amend-tests` с правкой долгоживущего файла в рабочей копии:
        планка лока выложена в рабочую копию, долгоживущий файл дописан."""
        task_dir = self.wt(task) / "tasks" / task
        for name, text in self.docs_files[task].items():
            if not name.startswith("acceptance_tests/"):
                continue
            path = task_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        path = self.wt(task) / rel
        path.write_text(path.read_text(encoding="utf-8")
                        + f"# правка Оператора {self.word()}\n", encoding="utf-8")
        with self.spy():
            return capture_out(amend.cmd_amend_tests, task,
                               f"правка планки {self.seed}")

    def pult_commit_rows(self, task: str, sha: str) -> list:
        mark = PULT_COMMIT.format(sha=sha)
        return [r for r in self.rows(task)
                if mark in f"{r['action']} {r['detail'] or ''}"]

    def rebase_in_progress(self, task: str) -> bool:
        wt = self.wt(task)
        for name in ("rebase-merge", "rebase-apply"):
            rel = self.git("-C", wt, "rev-parse", "--git-path", name).strip()
            path = Path(rel) if Path(rel).is_absolute() else wt / rel
            if path.exists():
                return True
        return False

    # ------------------------------------------------------------ GitLab

    @contextlib.contextmanager
    def token_user(self, outcome: str):
        """Исход `forge.token_user` для записи `forge: gitlab` (кроме
        «github»): подменённый транспорт GitLab или слот связки ключей."""
        fake = self.gitlab
        fake.exc, fake.status, fake.user = None, 200, None
        patches = [mock.patch("orchestrator.gitlab_adapter.transport",
                              fake.transport)]
        if outcome == "совпадение":
            fake.user = {"id": 7, "username": self.author, "name": self.author,
                         "email": self.email}
        elif outcome == "несовпадение":
            self.stranger = f"chuzhoy{self.word()}"
            fake.user = {"id": 8, "username": self.stranger,
                         "name": self.stranger,
                         "email": f"{self.stranger}@other.example"}
        elif outcome == "сбой сети":
            fake.exc = urllib.error.URLError(
                ConnectionRefusedError(61, "Connection refused"))
        elif outcome == "отказ токена":
            patches.append(mock.patch.object(keychain, "token",
                                             lambda *a, **k: None))
        elif outcome in ("ответ 401", "ответ 403"):
            fake.status = int(outcome.split()[1])
            fake.user = {"message": f"{fake.status} Unauthorized"}
        elif outcome == "пустой ответ":
            fake.user = {"id": 9, "username": ""}
        elif outcome == "не реализовано":
            from orchestrator import forge
            real = forge.token_user
            sample = real(config.DEFAULT_TARGET)
            patches.append(mock.patch(
                "orchestrator.forge.token_user",
                lambda target, *a, **k: swap_text(sample, "github", "gitlab")))
        with contextlib.ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            yield fake


@pytest.fixture
def stand(real_git):
    return Stand(real_git)


# ------------------------------------------------------------------- AC-1


def test_ac1_lease_carries_sha_of_last_sent_record(stand):
    """Первая отправка — без перезаписи; перезапись — `--force-with-lease` с sha журнала.

    Сценарий: запись со сжатием и перебазированием; первый переход в
    `verifying` отправляет ветку, которой на сервере нет, без
    `--force-with-lease`, журнал несёт «ветка отправлена: <sha>». Задача
    возвращается в `in_dev`, разработчик добавляет коммит; второй переход
    сжимает ветку заново и отправляет её
    `--force-with-lease=refs/heads/<ветка>:<sha>` с sha последней записи
    «ветка отправлена» — голова сервера равна новой голове.

    Ловит мутацию: перезапись обычным `push` без lease (отказ сервера по
    non-fast-forward, задача не в `verifying`) или lease с sha
    отслеживающей ветки клона вместо записи журнала — в argv нет пары
    ветки и sha записи.
    """
    stand.record(squash=True, freshness="rebase", template=True)
    task = stand.new_task()
    out = stand.advance(task)
    assert stand.state(task) == "verifying", stand.context(task, out)
    first_pushes = [p for p in stand.pushes if stand.branch(task) in " ".join(p)]
    assert first_pushes, stand.context(task, out)
    assert not any(a.startswith("--force-with-lease") for p in first_pushes
                   for a in p), stand.context(task, out)
    first = stand.origin_head(task)
    assert first == stand.head(task), stand.context(task, out)
    sent = stand.sent_shas(task)
    assert sent and sent[-1] == first, stand.context(task, out)

    stand.back_to_in_dev(task)
    stand.commit_code(task, {f"kod/{stand.word()}.py": f"B = {stand.seed}\n"})
    stand.pushes.clear()
    out = stand.advance(task)
    assert stand.state(task) == "verifying", stand.context(task, out)
    lease = f"--force-with-lease=refs/heads/{stand.branch(task)}:{sent[-1]}"
    assert any(lease in p for p in stand.pushes), stand.context(task, out)
    assert stand.origin_head(task) == stand.head(task), stand.context(task, out)
    assert stand.count_over(stand.fork, stand.head(task)) == 1, \
        stand.context(task, out)


REFUSALS = ["чужой коммит", "сеть: чтение головы", "сеть: отправка",
            "ветка на сервере без записи отправки",
            "перезапись отвергнута сервером", "отказ сверки автора"]


@pytest.mark.parametrize("case", REFUSALS)
def test_ac1_refusal_keeps_server_and_restores_local_head(stand, case):
    """Отказ или эскалация отправки после сжатия: сервер не тронут, локальная ветка — голова до сжатия, копия чистая.

    Сценарий по `case` (запись со сжатием и перебазированием):
    «чужой коммит» — после первой отправки на сервер лёг чужой коммит
    поверх отправленного sha → `escalated`; «сеть: чтение головы» —
    адрес `origin` клона недоступен (закрытый порт) → переход отклонён
    «сеть», задача в `in_dev`; «сеть: отправка» — недоступен только адрес
    отправки → то же; «ветка на сервере без записи отправки» — ветку
    отправили на сервер мимо пульта до первого перехода → `escalated` с
    этой причиной; «перезапись отвергнута сервером» — хук `pre-receive`
    отвергает ветку с текстом → `escalated` с этой причиной и текстом
    хука, повторной отправки нет; «отказ сверки автора» — `forge:
    gitlab`, владелец токена — другой пользователь → отказ (`escalated`).
    Во всех исходах голова ветки на сервере прежняя, локальная ветка
    задачи равна голове до сжатия, рабочая копия чистая.

    Ловит мутацию: после отказа отправки локальная ветка остаётся сжатой
    (голова — сжатый коммит, не коммит разработчика); либо сбой сети
    классифицирован как «чужой коммит» (задача в `escalated` вместо
    `in_dev`); либо отказ сервера повторяется обычной отправкой (две
    отправки ветки).
    """
    forge = "gitlab" if case == "отказ сверки автора" else "github"
    stand.record(squash=True, freshness="rebase", template=True, forge=forge)
    task = stand.new_task()
    branch = stand.branch(task)
    hook_text = f"хук отказал {stand.word()}"
    ctx = contextlib.nullcontext()
    if case == "ветка на сервере без записи отправки":
        stand.git("-C", stand.clone, "push", "-q", "origin",
                  f"{branch}:refs/heads/{branch}")
    elif case == "отказ сверки автора":
        ctx = stand.token_user("несовпадение")
    else:
        stand.publish_first(task)
        if case == "чужой коммит":
            head = stand.origin_head(task)
            tree = stand.git("-C", stand.clone, "rev-parse",
                             f"{head}^{{tree}}").strip()
            foreign = stand.git("-C", stand.clone, "commit-tree", tree, "-p",
                                head, "-m", "чужой коммит").strip()
            stand.git("-C", stand.clone, "push", "-q", "origin",
                      f"{foreign}:refs/heads/{branch}")
        elif case == "сеть: чтение головы":
            stand.git("-C", stand.clone, "remote", "set-url", "origin", DEAD_URL)
        elif case == "сеть: отправка":
            stand.git("-C", stand.clone, "remote", "set-url", "--push",
                      "origin", DEAD_URL)
        elif case == "перезапись отвергнута сервером":
            hook = stand.bare / "hooks" / "pre-receive"
            hook.write_text(
                "#!/bin/sh\nwhile read old new ref; do\n"
                f"  if [ \"$ref\" = \"refs/heads/{branch}\" ]; then\n"
                f"    echo '{hook_text}' >&2; exit 1\n  fi\ndone\nexit 0\n",
                encoding="utf-8")
            hook.chmod(0o755)
    before_server = stand.origin_head(task)
    before_local = stand.head(task)
    stand.pushes.clear()
    with ctx:
        out = stand.advance(task)
    text = out + "\n" + stand.journal(task)
    where = stand.context(task, out)
    if case.startswith("сеть"):
        assert stand.state(task) == "in_dev", where
        assert "сеть" in text, where
    else:
        assert stand.state(task) == "escalated", where
    if case == "ветка на сервере без записи отправки":
        assert "ветка на сервере без записи отправки" in text, where
    if case == "перезапись отвергнута сервером":
        assert "перезапись отвергнута сервером" in text, where
        assert hook_text in text, where
        branch_pushes = [p for p in stand.pushes
                         if any(branch in a for a in p)]
        assert len(branch_pushes) == 1, where
    if case == "отказ сверки автора":
        assert stand.stranger in text and stand.author in text, where
    assert stand.origin_head(task) == before_server, where
    assert stand.head(task) == before_local, where
    assert stand.dirty(task) == "", where


# ------------------------------------------------------------------- AC-2


def test_ac2_squash_rebase_single_signed_commit_over_origin(stand):
    """Сжатие и перебазирование: один коммит поверх `origin/<base>` по шаблону, подписанный пультом.

    Сценарий: `squash_before_mr: true`, `freshness: rebase`, шаблон
    `commit_template` со случайным префиксом; в ветке задачи несколько
    коммитов разработчика, `origin/<base>` впереди кодовым коммитом.
    После перехода в `verifying` ветка задачи — ровно один коммит, чей
    родитель — голова `origin/<base>`; первая строка сообщения — шаблон
    с названием задачи; автор и коммиттер — `commit_author`; в сообщении
    строки `Co-authored-by` и `Artel-Actor: orchestrator`; основная
    ветка на сервере и `base` записи не изменились.

    Ловит мутацию: перебазирование вместо сжатия (в ветке столько же
    коммитов, сколько было) либо сжатый коммит пишется идентичностью
    клона, а не `commit_author` (автор не тот); либо `{text}` шаблона не
    подставлен (первая строка не совпадает).
    """
    stand.record(squash=True, freshness="rebase", template=True)
    task = stand.new_task(commits=3)
    main = stand.main_ahead_code()
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    head = stand.head(task)
    assert stand.parents(head) == [main], where
    assert stand.message(head)[0] == stand.template.replace(
        "{text}", stand.title), where
    stand.assert_signed(head, "сжатый коммит")
    assert stand.main_sha() == main, where
    assert targets.target(stand.ext)["base"] == config.MAIN_BRANCH, where


# ------------------------------------------------------------------- AC-3


@pytest.mark.parametrize("case", ["подтяжка", "авторазрешение конфликта"])
def test_ac3_merge_commit_signed_by_commit_author(stand, case):
    """Подтяжка `merge`: merge-коммит и коммит авторазрешения конфликта подписаны `commit_author`.

    Сценарий: `freshness: merge`, без сжатия; `origin/<base>` впереди
    кодовым коммитом. «подтяжка» — без конфликта; «авторазрешение
    конфликта» — обе стороны дописали разные строки в конец одного
    документа `docs/notes.md`, пульт разрешает конфликт сам. Голова
    ветки после перехода — коммит подтяжки с двумя родителями (второй —
    голова `origin/<base>`), автор и коммиттер — `commit_author`, строки
    `Co-authored-by` и трейлера пульта — в сообщении.

    Ловит мутацию: `merge` подтяжки идёт идентичностью клона
    (`workspace.inherit_identity`) — автор не `commit_author`; либо
    коммит авторазрешения (`git commit` завершения слияния) без
    `-c user.*` и без строки соавтора.
    """
    stand.record()
    task = stand.new_task()
    if case == "авторазрешение конфликта":
        notes = stand.file_at(stand.head(task), "docs/notes.md")
        stand.commit_code(task, {"docs/notes.md": notes + f"- ветка {stand.word()}\n"})
        stand.commit_to_main({"docs/notes.md": notes + f"- main {stand.word()}\n",
                              f"kod_main/{stand.word()}.py": "M = 1\n"})
    else:
        stand.main_ahead_code()
    main = stand.main_sha()
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    head = stand.head(task)
    parents = stand.parents(head)
    assert len(parents) == 2 and parents[1] == main, where
    stand.assert_signed(head, case)


# ------------------------------------------------------------------- AC-4


def test_ac4_merge_then_squash_single_commit_over_origin(stand):
    """`freshness: merge` со сжатием: после перехода в ветке один подписанный коммит поверх `origin/<base>`.

    Сценарий: `squash_before_mr: true`, `freshness: merge`, шаблон
    коммита; `origin/<base>` впереди кодовым коммитом. После перехода в
    `verifying` ветка — один коммит, родитель — голова `origin/<base>`;
    автор и коммиттер — `commit_author`, строки `Co-authored-by` и
    трейлера пульта есть; дерево несёт и код задачи, и код main.

    Ловит мутацию: сжатие от старой точки ответвления, а не от
    `origin/<base>` (родитель — прежний main, а не его новая голова);
    либо сжатие пропущено при `merge` (голова — merge-коммит с двумя
    родителями).
    """
    stand.record(squash=True, template=True)
    task = stand.new_task()
    rel = f"kod_main/{stand.word()}.py"
    main = stand.commit_to_main({rel: "M = 2\n"})
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    head = stand.head(task)
    assert stand.parents(head) == [main], where
    stand.assert_signed(head, "сжатый коммит после merge")
    assert stand.file_at(head, rel) == "M = 2\n", where


# ------------------------------------------------------------------- AC-5


def test_ac5_doc_lag_squashes_without_pull(stand):
    """Документное отставание: подтяжки и перебазирования нет, коммиты задачи сжаты по шаблону.

    Сценарий: `squash_before_mr: true`, `freshness: rebase`;
    `origin/<base>` впереди только документным коммитом, не задевающим
    файлы ветки. После перехода в `verifying` голова ветки — один коммит
    поверх прежней точки ответвления (новая голова main не предок ветки),
    первая строка сообщения — по шаблону `commit_template`.

    Ловит мутацию: при `Fresh` сжатие пропущено (в ветке прежние коммиты
    разработчика) либо ветка всё же перебазирована на новую голову main
    (она — предок головы).
    """
    stand.record(squash=True, freshness="rebase", template=True)
    task = stand.new_task(commits=3)
    main = stand.main_ahead_docs()
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    head = stand.head(task)
    assert stand.parents(head) == [stand.fork], where
    assert not stand.is_ancestor(main, head), where
    assert stand.message(head)[0] == stand.template.replace(
        "{text}", stand.title), where


def test_ac5_doc_lag_with_uncommitted_change_refused(stand):
    """Документное отставание и незакоммиченная правка: переход отклонён, ветка и правка не тронуты.

    Сценарий: та же запись и то же документное отставание; в рабочей
    копии — незакоммиченная правка отслеживаемого файла зоны. `advance`
    отклоняет переход: задача в `in_dev`, голова ветки прежняя, правка
    по-прежнему не закоммичена (есть в рабочей копии, нет в голове).
    Контроль: правка отменена — повторный `advance` переводит задачу в
    `verifying` со сжатием поверх прежней точки ответвления.

    Ловит мутацию: при `Fresh` правка коммитится пультом перед сжатием
    (голова сменилась, правка в ней) либо сжатие идёт на грязной копии.
    """
    stand.record(squash=True, freshness="rebase", template=True)
    task = stand.new_task()
    stand.main_ahead_docs()
    before = stand.head(task)
    marker = f"ПРАВКА = {stand.seed}\n"
    (stand.wt(task) / "app.py").write_text(marker, encoding="utf-8")
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "in_dev", where
    assert stand.head(task) == before, where
    assert stand.file_at(before, "app.py") != marker, where
    assert (stand.wt(task) / "app.py").read_text(encoding="utf-8") == marker, where
    # Контроль: отказ — из-за правки; без неё тот же переход состоится.
    stand.git("-C", stand.wt(task), "checkout", "--", "app.py")
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    assert stand.parents(stand.head(task)) == [stand.fork], where


# ------------------------------------------------------------------- AC-6


@pytest.mark.parametrize("case", ["карта", "документ", "прочий"])
def test_ac6_rebase_conflicts(stand, case):
    """Конфликт перебазирования: карта — регенерацией, документ — по правилу `merge`, прочий — эскалация.

    Сценарий (`squash_before_mr: true`, `freshness: rebase`):
    «карта» — обе стороны добавили код и перегенерировали
    `docs/codebase-map.md` (заголовок с числом файлов конфликтует) →
    переход в `verifying`, карта итоговой головы равна выходу
    `scripts/codebase_map.py` на её дереве, журнал называет регенерацию;
    «документ» — обе стороны дописали разные строки в конец
    `docs/notes.md` → переход в `verifying`, файл итоговой головы несёт
    строку main перед строкой ветки, журнал называет порядок «main, затем
    ветка задачи»; «прочий» — обе стороны по-разному правят `app.py` →
    задача в `escalated`, в журнале метка
    `pull.PULL_CONFLICT_ROLE_STEP_MARKER`. Во всех исходах незавершённого
    перебазирования в рабочей копии задачи нет; у разрешённых конфликтов
    итоговая голова — один коммит поверх головы `origin/<base>`.

    Ловит мутацию: карта разрешается объединением сторон (`--theirs`
    без регенерации — заголовок не совпадает с выходом генератора);
    либо порядок добавок документа перевёрнут; либо прочий конфликт
    оставляет перебазирование незавершённым; либо вместо перебазирования
    идёт подтяжка `merge` (голова — merge-коммит с двумя родителями).
    """
    stand.record(squash=True, freshness="rebase", template=True)
    task = stand.new_task()
    wt = stand.wt(task)
    notes = stand.file_at(stand.fork, "docs/notes.md")
    mine, theirs = f"- ветка {stand.word()}", f"- main {stand.word()}"
    if case == "карта":
        (wt / "kod" / f"{stand.word()}.py").write_text("C = 1\n", encoding="utf-8")
        stand.regen_map(wt)
        stand.commit_code(task, {})
        stand.commit_to_main({f"kod_main/{stand.word()}.py": "M = 3\n"},
                             regen_map=True)
    elif case == "документ":
        stand.commit_code(task, {"docs/notes.md": notes + mine + "\n"})
        stand.commit_to_main({"docs/notes.md": notes + theirs + "\n",
                              f"kod_main/{stand.word()}.py": "M = 4\n"})
    else:
        stand.commit_code(task, {"app.py": f"VALUE = {stand.word()}\n"})
        stand.commit_to_main({"app.py": f"VALUE = {stand.word()}x\n"})
    out = stand.advance(task)
    where = stand.context(task, out)
    assert not stand.rebase_in_progress(task), where
    journal = stand.journal(task)
    if case == "прочий":
        assert stand.state(task) == "escalated", where
        assert any(r["action"] == pull.PULL_CONFLICT_ROLE_STEP_MARKER
                   for r in stand.rows(task)), where
        return
    assert stand.state(task) == "verifying", where
    head = stand.head(task)
    assert stand.parents(head) == [stand.main_sha()], where
    if case == "карта":
        committed = stand.file_at(head, "docs/codebase-map.md")
        stand.regen_map(wt)
        assert (wt / "docs" / "codebase-map.md").read_text(
            encoding="utf-8") == committed, where
        assert "регенерац" in journal, where
    else:
        text = stand.file_at(head, "docs/notes.md")
        assert theirs in text and mine in text, where
        assert text.index(theirs) < text.index(mine), where
        assert "main, затем ветка задачи" in journal, where


# ------------------------------------------------------------------- AC-7


@pytest.mark.parametrize("case", ["вне зон", "в зонах", "посторонний файл"])
def test_ac7_wip_checkpoint_before_gates_on_rebase(stand, case):
    """Кодовое отставание при `rebase`: правка рабочей копии — чекпоинтом до рубежей.

    Сценарий (`squash_before_mr: true`, `freshness: rebase`,
    `origin/<base>` впереди кодовым коммитом, зоны задачи — `app.py`,
    `kod/`, `docs/`): «вне зон» — незакоммиченная правка нового файла
    `tests/…` (общая зона чекпоинта, но не зона задачи внешнего проекта)
    → она закоммичена чекпоинтом WIP (есть в голове ветки), переход
    отказан гейтом зон, задача в `in_dev`, сжатия нет (голова —
    коммит чекпоинта поверх прежней головы), ветки на сервере нет;
    «в зонах» — правка в `kod/` → переход в `verifying`, правка есть в
    итоговой голове; «посторонний файл» — файл вне всех зон → переход
    отклонён «посторонние файлы в worktree», задача в `in_dev`, голова
    ветки прежняя, новая голова main ей не предок.

    Ловит мутацию: при `rebase` узел подтяжки пропущен целиком вместе с
    чекпоинтом — правка «вне зон» не закоммичена и гейт зон её не видит
    (переход идёт дальше), правка «в зонах» не попадает в итоговую
    голову, посторонний файл не отклоняет переход.
    """
    stand.record(squash=True, freshness="rebase", template=True)
    task = stand.new_task()
    main = stand.main_ahead_code()
    before = stand.head(task)
    rel = {"вне зон": f"tests/helper_{stand.word()}.py",
           "в зонах": f"kod/wip_{stand.word()}.py",
           "посторонний файл": f"zz{stand.word()}/stray.txt"}[case]
    body = f"WIP = {stand.seed}\n"
    path = stand.wt(task) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    out = stand.advance(task)
    where = stand.context(task, out)
    head = stand.head(task)
    if case == "в зонах":
        assert stand.state(task) == "verifying", where
        assert stand.file_at(head, rel) == body, where
        return
    assert stand.state(task) == "in_dev", where
    assert stand.origin_head(task) == "", where
    if case == "вне зон":
        assert stand.parents(head) == [before], where
        assert stand.file_at(head, rel) == body, where
        assert any(r["action"] == "переход отклонён: гейт зон"
                   for r in stand.rows(task)), where
    else:
        assert head == before, where
        assert not stand.is_ancestor(main, head), where
        assert any(STRAY_REFUSAL in (r["action"] or "")
                   and r["action"].startswith("переход отклонён")
                   for r in stand.rows(task)), where


# ------------------------------------------------------------------- AC-8


def test_ac8_rework_gate_sees_role_commits(stand):
    """После `changes_requested` без коммита разработчика переход отказан рубежом переделки до сжатия.

    Сценарий: `squash_before_mr: true`, `freshness: rebase`,
    `origin/<base>` впереди кодовым коммитом; коммиты разработчика —
    задним числом, после них — вердикт ревью `changes_requested`
    автокоммитом шага ревьювера и возврат в `in_dev`. `advance` пишет
    отказ «замечания ревью не отработаны», задача в `in_dev`, голова
    ветки прежняя.

    Ловит мутацию: сжатие и перебазирование до рубежей — сжатый коммит
    пульта свежей датой коммиттера проходит рубеж переделки (отказа нет)
    или голова ветки сменилась до отказа.
    """
    stand.record(squash=True, freshness="rebase", template=True)
    past = datetime.now(timezone.utc) - timedelta(hours=stand.rng.randint(2, 48))
    task = stand.new_task(dated=past)
    stand.write_docs(task, {"REVIEW.md": REVIEW_TEXT.format(
        task=task, word=stand.word())}, role="reviewer")
    store.journal(stand.conn, task, "fsm", "state -> in_dev",
                  "замечания ревью, итерация 1")
    stand.main_ahead_code()
    before = stand.head(task)
    out = stand.advance(task)
    where = stand.context(task, out)
    assert any(r["action"] == REWORK_ACTION for r in stand.rows(task)), where
    assert stand.state(task) == "in_dev", where
    assert stand.head(task) == before, where


# ------------------------------------------------------------------ AC-10


PULT_KINDS = ["чекпоинт шага", "чекпоинт подтяжки", "документ", "паспорт",
              "amend-tests", "закрытие"]


def make_pult_commit(stand, task: str, kind: str) -> str:
    """Коммит пульта вида `kind` у задачи; sha коммита. Коммиты кодовой
    ветки — в рабочей копии задачи, прочие — в `refs/artifacts/<id>`."""
    if kind in ("чекпоинт шага", "чекпоинт подтяжки"):
        before = stand.head(task)
        path = stand.wt(task) / "kod" / f"wip_{stand.word()}.py"
        path.write_text(f"W = {stand.seed}\n", encoding="utf-8")
        if kind == "чекпоинт шага":
            capture_out(checkpoint.commit_success_checkpoint, stand.conn, task,
                        "developer")
        else:
            capture_out(checkpoint.commit_pull_checkpoint, stand.conn, task,
                        stand.wt(task))
        head = stand.head(task)
        assert head != before, stand.context(task, f"{kind}: коммита нет")
        return head
    if kind == "amend-tests":
        rel = stand.with_long_lived(task)
        before = stand.head(task)
        out = stand.amend(task, rel)
        head = stand.head(task)
        assert head != before, stand.context(task, out)
        return head
    before = stand.docs_head(task)
    if kind == "документ":
        stand.write_docs(task, {"PLAN.md": PLAN_TEXT.format(task=task)
                                + f"\nПравка {stand.word()}.\n"})
    elif kind == "паспорт":
        store.set_state(stand.conn, task, "review", "test",
                        expected_state="in_dev", detail="фикстура паспорта")
    else:
        store.set_state(stand.conn, task, "killed", "test",
                        expected_state="in_dev", detail="фикстура закрытия")
        before = stand.docs_head(task)
        capture_out(snapshot.commit_closing, stand.conn, task, "killed")
    head = stand.docs_head(task)
    assert head != before, stand.context(task, f"{kind}: коммита нет")
    return head


@pytest.mark.parametrize("author", [True, False])
@pytest.mark.parametrize("kind", PULT_KINDS)
def test_ac10_pult_commits_carry_author_and_trailer(stand, kind, author):
    """Коммиты пульта: автор `commit_author`, соавтор и трейлер; без `commit_author` — трейлер при прежнем авторе.

    Сценарий по `kind`: чекпоинт шага (`checkpoint.
    commit_success_checkpoint`) и чекпоинт подтяжки (`checkpoint.
    commit_pull_checkpoint`) незакоммиченного кода — в кодовой ветке;
    документ шага (`checkpoint.commit_step_artifacts`), коммит паспорта
    (смена состояния `store.set_state`) и коммит закрытия
    (`snapshot.commit_closing`) — в `refs/artifacts/<id>`; коммит
    `amend-tests` правки долгоживущего файла — в кодовой ветке. Коммит
    закрытия — `RETRO.md` по закрытии задачи (`snapshot.commit_closing`;
    строка `snapshot.py:272`, названная в SPEC, — соседний коммит
    исторического снимка, не закрытия). Запись с
    `commit_author` и `co_author`: автор и коммиттер — `commit_author`,
    в сообщении строки `Co-authored-by` и `Artel-Actor: orchestrator`.
    Запись без них: автор и коммиттер — служебная идентичность
    (`fixation.FIXATION_AUTHOR_*`), трейлер — есть.

    Ловит мутацию: подпись добавлена только части точек записи (например,
    `artifact_branch.write_commit` с собственным окружением `GIT_*`
    остался с `FIXATION_AUTHOR_*`) — коммит этого вида несёт не того
    автора или без трейлера; либо трейлер ставится только при
    `commit_author` — у записи без поля трейлера нет.
    """
    stand.record(author=author, co_author=author)
    task = stand.new_task()
    sha = make_pult_commit(stand, task, kind)
    if author:
        stand.assert_signed(sha, kind)
        return
    assert stand.identity(sha) == (
        fixation.FIXATION_AUTHOR_NAME, fixation.FIXATION_AUTHOR_EMAIL,
        fixation.FIXATION_AUTHOR_NAME, fixation.FIXATION_AUTHOR_EMAIL), \
        stand.note(f"{kind}: идентичность {stand.identity(sha)}")
    lines = [line.strip() for line in stand.message(sha)]
    assert TRAILER in lines, stand.note(f"{kind}: нет трейлера: {lines}")


# ------------------------------------------------------------------ AC-11


JOURNAL_KINDS = ["чекпоинт", "amend-tests", "подтяжка",
                 "авторазрешение конфликта", "сжатие"]


@pytest.mark.parametrize("author", [True, False])
@pytest.mark.parametrize("kind", JOURNAL_KINDS)
def test_ac11_pult_commit_journal_record(stand, kind, author):
    """Запись «коммит пульта: <sha> (<вид>)» с `actor` `orchestrator` — только при `commit_author`.

    Сценарий по `kind`: чекпоинт шага; `amend-tests` с правкой
    долгоживущего файла; подтяжка `merge` (`origin/<base>` впереди
    кодовым коммитом); подтяжка с авторазрешением конфликта документа;
    сжатие на переходе в `verifying`. Запись с `commit_author`: в
    журнале задачи есть запись с sha этого коммита («коммит пульта:
    <sha>») и `actor` `orchestrator`. Запись без `commit_author`: ни
    одной записи «коммит пульта»; у `amend-tests` запись
    `amend.AMEND_ACTION` — с `actor` `operator`.

    Ловит мутацию: запись «коммит пульта» пишется безусловно (журнал
    задач без `commit_author` меняется) либо несёт sha до коммита
    (голову ветки до подтяжки/сжатия), а не sha самого коммита.
    """
    squash = kind == "сжатие"
    stand.record(author=author, co_author=author, squash=squash,
                 template=squash)
    task = stand.new_task()
    if kind == "чекпоинт":
        sha = make_pult_commit(stand, task, "чекпоинт шага")
        out = ""
    elif kind == "amend-tests":
        sha = make_pult_commit(stand, task, "amend-tests")
        out = ""
    else:
        if kind == "авторазрешение конфликта":
            notes = stand.file_at(stand.head(task), "docs/notes.md")
            stand.commit_code(task, {"docs/notes.md":
                                     notes + f"- ветка {stand.word()}\n"})
            stand.commit_to_main({"docs/notes.md":
                                  notes + f"- main {stand.word()}\n",
                                  f"kod_main/{stand.word()}.py": "M = 5\n"})
        else:
            stand.main_ahead_code()
        out = stand.advance(task)
        assert stand.state(task) == "verifying", stand.context(task, out)
        sha = stand.head(task)
        if kind != "сжатие":
            assert len(stand.parents(sha)) == 2, stand.context(task, out)
    where = stand.context(task, out)
    if author:
        rows = stand.pult_commit_rows(task, sha)
        assert rows, where
        assert all(r["actor"] == "orchestrator" for r in rows), where
        return
    assert not any("коммит пульта" in f"{r['action']} {r['detail'] or ''}"
                   for r in stand.rows(task)), where
    if kind == "amend-tests":
        amend_rows = [r for r in stand.rows(task)
                      if r["action"] == amend.AMEND_ACTION]
        assert amend_rows and all(r["actor"] == "operator"
                                  for r in amend_rows), where


# ------------------------------------------------------------------ AC-12


OUTCOMES = ["совпадение", "несовпадение", "сбой сети", "отказ токена",
            "ответ 401", "ответ 403", "не реализовано", "пустой ответ"]
REASON_MARK = {"сбой сети": "сеть", "отказ токена": "токен",
               "ответ 401": "401", "ответ 403": "403",
               "не реализовано": "не реализовано", "пустой ответ": "пуст"}


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_ac12_author_check_on_transition(stand, outcome):
    """Сверка автора на переходе `in_dev → verifying` до первой отправки — по исходу `forge.token_user`.

    Сценарий: запись `forge: gitlab` с `commit_author`, записи «ветка
    отправлена» нет; исход `forge.token_user` задан подменённым
    транспортом GitLab (`GET /user`), слотом связки ключей (отказ
    токена) или подменой самой функции («не реализовано» для GitLab).
    «совпадение» — ветка отправлена, задача в `verifying`;
    «несовпадение» — отправки нет, задача в `escalated`, отказ называет
    оба значения; прочие исходы — отправки нет, отказ называет причину
    (сеть, токен, 401, 403, «не реализовано», пустой ответ); при «не
    реализовано» для не-`github` записи «сверка автора — после
    адаптера» нет.

    Ловит мутацию: сверка открыта по умолчанию — любой исход, кроме
    несовпадения, пропускает отправку (ветка оказывается на сервере);
    либо «не реализовано» без проверки `forge` записи трактуется как
    пропуск «после адаптера».
    """
    stand.record(forge="gitlab")
    task = stand.new_task()
    with stand.token_user(outcome):
        out = stand.advance(task)
    text = out + "\n" + stand.journal(task)
    where = stand.context(task, out)
    if outcome == "совпадение":
        assert stand.state(task) == "verifying", where
        assert stand.origin_head(task) == stand.head(task), where
        return
    assert stand.origin_head(task) == "", where
    if outcome == "несовпадение":
        assert stand.state(task) == "escalated", where
        assert stand.author in text and stand.stranger in text, where
        return
    assert REASON_MARK[outcome] in text, where
    if outcome == "не реализовано":
        assert AFTER_ADAPTER not in text, where


def test_ac12_github_skips_check_after_adapter(stand):
    """`forge: github` — сверка пропущена записью «сверка автора — после адаптера», отправка состоялась.

    Сценарий: запись `forge: github` с `commit_author`, записи «ветка
    отправлена» нет; адаптер GitHub отвечает «не реализовано для
    github». Переход в `verifying` состоялся, ветка на сервере равна
    локальной голове, в журнале задачи — «сверка автора — после
    адаптера».

    Ловит мутацию: ответ «не реализовано для github» трактуется как
    любой иной исход — отправки нет, задача не в `verifying`; либо пропуск
    без записи журнала.
    """
    stand.record(forge="github")
    task = stand.new_task()
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    assert stand.origin_head(task) == stand.head(task), where
    assert AFTER_ADAPTER in stand.journal(task), where


def test_ac12_without_commit_author_no_check(stand):
    """Запись без `commit_author`: `forge.token_user` не вызывается, журнала сверки нет, отправка прежняя.

    Сценарий: запись `forge: gitlab` без `commit_author`; переход в
    `verifying` отправляет ветку, `forge.token_user` (подменён шпионом)
    не вызван, в журнале ни одной записи со словами «сверка автора».

    Ловит мутацию: сверка выполняется при любой записи (шпион вызван,
    отправка отказана ответом подменённой функции).
    """
    stand.record(author=False, co_author=False, forge="gitlab")
    task = stand.new_task()
    with mock.patch("orchestrator.forge.token_user",
                    side_effect=AssertionError("token_user вызван")) as spy:
        out = stand.advance(task)
    where = stand.context(task, out)
    assert spy.call_count == 0, where
    assert "сверка автора" not in stand.journal(task), where
    assert stand.state(task) == "verifying", where
    assert stand.origin_head(task) == stand.head(task), where


def test_ac12_no_check_after_sent_record(stand):
    """С записью «ветка отправлена» `forge.token_user` не вызывается.

    Сценарий: запись `forge: gitlab` с `commit_author`, владелец токена
    совпадает; первый переход отправляет ветку (запись «ветка
    отправлена» есть). Задача возвращается в `in_dev`, разработчик
    добавляет коммит; на втором переходе шпион `forge.token_user` не
    вызван, а новая голова отправлена.

    Ловит мутацию: сверка выполняется на каждой отправке, а не только до
    первой (шпион вызван на втором переходе).
    """
    stand.record(forge="gitlab")
    task = stand.new_task()
    with stand.token_user("совпадение"):
        stand.publish_first(task)
    assert stand.sent_shas(task), stand.context(task)
    with mock.patch("orchestrator.forge.token_user",
                    side_effect=AssertionError("token_user вызван")) as spy:
        out = stand.advance(task)
    where = stand.context(task, out)
    assert spy.call_count == 0, where
    assert stand.state(task) == "verifying", where
    assert stand.origin_head(task) == stand.head(task), where


@pytest.mark.parametrize("path", ["amend-tests", "pull-main"])
def test_ac12_mismatch_blocks_other_push_paths(stand, path):
    """Несовпадение владельца токена: отправки нет и из `amend-tests`, и из `pull-main`; отказ называет оба значения.

    Сценарий: запись `forge: gitlab` с `commit_author`, ветка ни разу не
    отправлена; владелец токена — другой пользователь. «amend-tests» —
    правка долгоживущего файла задачи в `in_dev` (коммит в кодовой ветке
    и отправка его головы); «pull-main» — задача в `verifying`,
    `origin/<base>` впереди кодовым коммитом. Ветки на сервере нет, текст
    вывода и журнала называет `commit_author` и пользователя токена.

    Ловит мутацию: сверка стоит только на рубеже перехода, а не в единой
    точке отправки — `amend-tests`/`pull-main` отправляют ветку.
    """
    stand.record(forge="gitlab")
    task = stand.new_task(state="in_dev" if path == "amend-tests" else "verifying")
    with stand.token_user("несовпадение"):
        if path == "amend-tests":
            rel = stand.with_long_lived(task)
            out = stand.amend(task, rel)
        else:
            stand.main_ahead_code()
            with stand.spy():
                out = capture_out(pull_main.cmd_pull_main, task)
    text = out + "\n" + stand.journal(task)
    where = stand.context(task, out)
    assert stand.origin_head(task) == "", where
    assert stand.author in text and stand.stranger in text, where


# ------------------------------------------------------------------ AC-13


@pytest.mark.parametrize("freshness", ["rebase", "merge"])
def test_ac13_acceptance_runs_on_pushed_final_head(stand, freshness):
    """Переход со сжатием: приёмка прогнана после отправки на итоговой голове.

    Сценарий: `squash_before_mr: true` и `freshness` по параметру,
    `origin/<base>` впереди кодовым коммитом. После перехода в
    `verifying` итоговая голова — один коммит поверх головы
    `origin/<base>` (переход со сжатием состоялся), последний прогон
    pytest планки шёл в рабочем каталоге,
    чья голова равна итоговой голове ветки, и в момент прогона голова
    ветки на сервере уже была ею же; голова на сервере сейчас — она же.

    Ловит мутацию: приёмка прогоняется до сжатия (на коммитах роли) или
    до отправки — голова прогона не равна итоговой либо сервер в момент
    прогона ещё не нёс её.
    """
    stand.record(squash=True, freshness=freshness, template=True)
    task = stand.new_task()
    main = stand.main_ahead_code()
    out = stand.advance(task)
    where = stand.context(task, out)
    assert stand.state(task) == "verifying", where
    runs = [c for c in stand.plank_calls
            if any("acceptance_tests" in a for a in c["argv"])]
    assert runs, where
    final = stand.head(task)
    assert stand.parents(final) == [main], where
    last = runs[-1]
    assert last["head"] == final, where
    assert last["origin"].get(f"refs/heads/{stand.branch(task)}") == final, where
    assert stand.origin_head(task) == final, where


# ------------------------------------------------------------------ AC-14


@pytest.mark.parametrize("rewritten", [True, False])
def test_ac14_review_package_after_rewrite(stand, rewritten):
    """Пакет ревью следующей итерации: перезаписанная ветка — полный дифф с пометкой, иначе — прежний инкремент.

    Сценарий: у задачи коммит итерации 1 (файл с меткой T1), sha
    прошлого вердикта — его голова. `origin/<base>` уходит вперёд
    кодовым коммитом (метка M), локальная основная ветка клона остаётся
    позади. «перезаписана»: ветка перебазирована на `origin/<base>` и
    сжата вместе с новым коммитом (метка T2) — sha вердикта больше не
    предок головы; пакет итерации 2 несёт пометку «ветка перезаписана —
    дифф полный», метки T1 и T2, но не M (база — merge-base с
    `origin/<base>`). «не перезаписана»: новый коммит T2 поверх — пакета
    без пометки, с T2 и без T1 (инкремент от sha вердикта).

    Ловит мутацию: инкрементальный дифф от sha вердикта и после
    перезаписи (нет пометки, нет T1 или есть M — дифф от не-предка);
    либо полный дифф от локальной основной ветки клона (в нём M).
    """
    stand.record(squash=True, freshness="rebase", template=True)
    task = stand.new_task(commits=0)
    t1, t2, m = (f"metka_{stand.word(10)}" for _ in range(3))
    prev = stand.commit_code(task, {f"kod/{stand.word()}.py": f"{t1} = 1\n"})
    old_main = stand.git("-C", stand.clone, "rev-parse",
                         config.MAIN_BRANCH).strip()
    stand.commit_to_main({f"kod_main/{stand.word()}.py": f"{m} = 1\n"})
    stand.git("-C", stand.clone, "update-ref",
              f"refs/heads/{config.MAIN_BRANCH}", old_main)
    stand.git("-C", stand.clone, "fetch", "-q", "origin")
    wt = stand.wt(task)
    if rewritten:
        stand.git("-C", wt, "rebase", "-q", f"origin/{config.MAIN_BRANCH}")
        stand.commit_code(task, {f"kod/{stand.word()}.py": f"{t2} = 2\n"})
        stand.git("-C", wt, "reset", "-q", "--soft",
                  f"origin/{config.MAIN_BRANCH}")
        stand.git("-C", wt, "commit", "-q", "-m", "сжато")
        assert not stand.is_ancestor(prev, stand.head(task)), stand.note("стенд")
    else:
        stand.commit_code(task, {f"kod/{stand.word()}.py": f"{t2} = 2\n"})
    package = review.review_package(stand.conn, task, stand.title,
                                    stand.branch(task), iteration=2,
                                    prev_sha=prev)
    text = package["text"]
    where = stand.note(f"перезаписана: {rewritten}\n{text[:4000]}")
    assert t2 in text, where
    if rewritten:
        assert REWRITTEN_MARK in text, where
        assert t1 in text, where
        assert m not in text, where
    else:
        assert REWRITTEN_MARK not in text, where
        assert t1 not in text, where


# ------------------------------------------------------------------ AC-15


CALLERS = ["шаг разработчика", "pull-main", "approve приёмки", "гейт мержа"]


def run_caller(stand, caller: str) -> tuple:
    """Задача в состоянии места `caller`, `origin/<base>` впереди кодовым
    коммитом; место вызвано публичным входом. (задача, новая голова
    `origin/<base>`, вывод, голова ветки на старте агента или после
    вызова)."""
    state = {"шаг разработчика": "in_dev", "pull-main": "verifying",
             "approve приёмки": "acceptance", "гейт мержа": "merge_gate"}[caller]
    task = stand.new_task(state=state)
    main = stand.main_ahead_code()
    stand.git_calls.clear()
    seen = {}
    if caller == "шаг разработчика":
        # Скилы роли шаг читает из основной ветки клона артели.
        for name in ("skills", "templates"):
            shutil.copytree(REPO / name, config.ROOT / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
        stand.git("add", "-A", "skills", "templates")
        stand.git("commit", "-q", "-m", "скилы и шаблоны пульта")
        stand.git("push", "-q", "origin",
                  f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        stand.sb.use_role_map()

        def spawn(cmd, *args, **kwargs):
            if not is_claude_call(cmd):
                return REAL_POPEN(cmd, *args, **kwargs)
            seen["head"] = stand.git("-C", kwargs.get("cwd"), "rev-parse",
                                     "HEAD").strip()
            return FakeProc(["готово\n"])

        with mock.patch.object(stack, "check_stack", _stub_check_stack), \
                mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                stand.spy():
            out = capture_out(runner.cmd_run, task)
        return task, main, out, seen.get("head", "")
    with stand.spy():
        if caller == "pull-main":
            out = capture_out(pull_main.cmd_pull_main, task)
        else:
            store.record_fixation(stand.conn, task)
            out = capture_out(fsm.cmd_approve, task)
    return task, main, out, ""


@pytest.mark.parametrize("caller", CALLERS)
def test_ac15_rebase_freshness_keeps_merge_elsewhere(stand, caller):
    """`freshness: rebase` вне перехода `in_dev → verifying` — прежняя подтяжка `merge`.

    Сценарий: запись `squash_before_mr: true`, `freshness: rebase`;
    `origin/<base>` впереди кодовым коммитом. Место по параметру —
    подтяжка перед шагом разработчика (`runner.cmd_run` с подменённым
    агентом), `pull-main`, `approve` приёмки, гейт мержа (`approve` на
    `merge_gate`) — сливает голову `origin/<base>` в ветку задачи
    `git merge --no-ff`, `git rebase` не вызывается; у шага
    разработчика, `pull-main` и `approve` приёмки голова ветки (у шага —
    на старте агента) — merge-коммит, второй родитель которого — голова
    `origin/<base>`. Приёмка канарейки (`canary.py`, только для чтения в
    этой задаче) зовёт тот же узел подтяжки тем же вызовом, что `approve`
    приёмки (`fsm._pull_main_or_escalate(..., "acceptance")`), и
    покрыта случаем «approve приёмки».

    Ловит мутацию: узел подтяжки читает `freshness` записи сам и
    перебазирует на любом вызове (или на любом вызове в `in_dev`, включая
    шаг разработчика) — `git merge` не вызван, голова — не merge-коммит.
    """
    stand.record(squash=True, freshness="rebase", template=True)
    task, main, out, start = run_caller(stand, caller)
    where = stand.context(task, out) + "\n--- git:\n" + "\n".join(
        " ".join(c) for c in stand.git_calls if git_sub(c) in ("merge", "rebase"))
    merges = [c for c in stand.git_calls
              if git_sub(c) == "merge" and "--no-ff" in c and main in c]
    assert merges, where
    assert not any(git_sub(c) == "rebase" for c in stand.git_calls), where
    if caller == "гейт мержа":
        return
    head = start if caller == "шаг разработчика" else stand.head(task)
    parents = stand.parents(head) if head else []
    assert len(parents) == 2 and parents[1] == main, where
