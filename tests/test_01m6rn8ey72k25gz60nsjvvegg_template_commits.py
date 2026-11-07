"""Первая строка коммитов пульта в кодовой ветке задачи по `policy.commit_message_template`; опознание подтяжки рубежом «замечания ревью не отработаны».

Группа: долгоживущий
Красен до реализации: запись с полем `policy.commit_message_template` не загружается (отказ «неизвестное поле 'commit_message_template'»), контекст проекта задачи не разрешается — чекпоинт тестов не отбирает свои файлы, переход отказывает «репозиторий проекта задачи не найден», коммита по шаблону и записи «шаблон сообщения не применён» нет. Зелены и до реализации чекпоинты записи без поля (AC-3) и «коммит кода пульта» AC-8 (отказа рубежа нет: переход стоит раньше) — их различающую силу дали мутации на временном стабе реализации.

Провалидировано временным стабом корректной реализации (удалён, не
закоммичен): все методы зелёные; мутации «фильтр подтяжки только по
прежнему префиксу», «ветка подтяжки жёстко `main`», «отсев по началу темы
шаблона без `подтяжка `», «цепочка `str.replace` `{id}`, `{ref}`, `{text}`,
`{title}`», «шаблон не применён в авторазрешении конфликта» и «шаблон не
применён в чекпоинте тестов» красят названные в методах сценарии.

Связка «команда пульта — FSM — база — git»: каждый сценарий доходит до
коммита через публичный вход (`checkpoint.commit_success_checkpoint`,
`checkpoint.commit_step_artifacts`, `fsm.cmd_advance`,
`amend.cmd_amend_tests`) в настоящем git песочницы
(`tests.sandbox.RealGitSandbox`): клон вымышленного внешнего проекта
(`tests.sandbox.make_project_repo`) с bare `origin`, запись проекта — в
локальном слое (`targets.local_path()`), ссылка задачи — строкой
`external_refs`. Сообщение коммита читается целиком (`git cat-file
commit`): первая строка — до первого перевода строки, подпись — всё после
неё.

Подменены только внешние для песочницы ответы: цвет CI (`ci.*`), Draft MR
(`github_adapter.ensure_draft_mr`/`undraft_mr`), предпроверки доктора и
прогон pytest у мест запуска (`acceptance`, `two_sided` — подменённый
модуль `subprocess` отвечает зелёным прогоном). Рубеж ревью сравнивает
даты коммитов строго «позже вердикта», поэтому коммиты после вердикта
датированы будущим (`GIT_COMMITTER_DATE`, окружение git пульт передаёт
как есть) — иначе коммит в ту же секунду, что вердикт, не различал бы
мутацию.

Названия задач, ключи ссылок, система `ref_required`, соавтор, причины
`amend-tests` и файлы — из `random`, зерно печатается и входит в текст
каждого провала.
"""
import contextlib
import hashlib
import io
import os
import random
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (acceptance, amend, catalog, checkpoint, ci, config,
                          fsm, github_adapter, idgen, pull, store, targets,
                          workspace)
from orchestrator.advance_gates import two_sided
from scripts import guard
from tests.sandbox import make_project_repo

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
ALPHABET = "abcdefghijkmnopqrstuvwxyz"
TRAILER = "Artel-Actor: orchestrator"
TESTS_TEXT = ("долгоживущие тесты закоммичены пультом за роль test_author — "
              "шаг завершён")
CODE_TEXT = ("код закоммичен пультом за роль developer — шаг завершён с "
             "незакоммиченным кодом")
AMEND_TEXT = "правка долгоживущих тестов — {reason}"
PULL_TEXT = "подтяжка {base}"
NOT_APPLIED_ACTION = "шаблон сообщения не применён"
NOT_APPLIED_REASON = "нет ссылки системы {system}"
REWORK_ACTION = "переход отклонён: замечания ревью не отработаны"
PLACEHOLDER = re.compile(r"\{(id|ref|title|text)\}")
OUTPUT = "1 passed in 0.01s\n"
COLLECTED = "probe.py::test_probe\n\n1 test collected in 0.01s\n"
JUNIT = ('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite '
         'name="pytest" errors="0" failures="0" skipped="0" tests="1">'
         '<testcase classname="probe" name="test_probe" time="0.01"/>'
         '</testsuite></testsuites>')

ENTRY = """targets:
  {name}:
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
      forge: github
      url: https://localhost/grp/{name}
      token_slot: {name}-token
      commit_author:
        name: {author}
        email: {author}@pult.example
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

# SPEC: фикстура шаблона сообщения

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


def render(template: str, values: dict) -> str:
    """Ожидаемая первая строка: каждая подстановка шаблона раскрыта один
    раз, подставленные значения повторно не разбираются."""
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def dated(moment: datetime) -> dict:
    stamp = moment.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}


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
    отвечает зелёным прогоном (и пишет junit, если его просят); прочие
    процессы идут настоящими."""

    def __getattr__(self, name):
        return getattr(subprocess, name)

    def answer(self, argv, kwargs) -> str:
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


class Stand:
    """Пульт с клоном вымышленного внешнего проекта и bare `origin`; запись
    проекта — в локальном слое, поля — по сценарию. `base` — ветка
    подтяжки записи (`description.base`)."""

    def __init__(self, sb, base: str = config.MAIN_BRANCH):
        self.sb = sb
        self.base = base
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"proj{self.word()}"
        self.author = f"pult{self.word()}"
        self.co_author = (f"Co-authored-by: Соавтор {self.word()} "
                          f"<{self.word()}@co.example>")
        self.system = f"trk{self.word(4)}"
        self.key = f"ABC-{self.rng.randint(10, 99999)}"
        self.docs_files: dict = {}
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
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
                           lambda *args, **kwargs: [])):
            patcher.start()
            sb.addCleanup(patcher.stop)
        sb.add_synced_origin()
        self.clone = make_project_repo(self.ext)
        self.bare = config.PROJECTS / self.ext / "origin.git"
        if base != config.MAIN_BRANCH:
            self.git("-C", self.clone, "checkout", "-q", "-b", base)
            self.git("-C", self.clone, "push", "-q", "origin", f"{base}:{base}")
        self.record()
        capture_out(catalog.cmd_init)
        self.commit_to_base({"app.py": "VALUE = 1\n",
                             "docs/notes.md": "# Заметки\n\n- база\n"})

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def git(self, *args) -> str:
        return self.sb.git(*[str(a) for a in args])

    def record(self, *, template: str | None = None, ref_required: bool = True,
               squash_template: str | None = None) -> None:
        """Запись проекта в локальном слое: `ref_required` — система
        стенда, шаблон коммитов ветки — `template` (None — поля нет);
        `squash_template` — сжатие со своим `commit_template`."""
        policy = f'      co_author: "{self.co_author}"\n'
        if ref_required:
            policy += f"      ref_required: {self.system}\n"
        if template is not None:
            escaped = template.replace("\\", "\\\\").replace('"', '\\"')
            policy += f'      commit_message_template: "{escaped}"\n'
        if squash_template is not None:
            policy += ("      squash_before_mr: true\n"
                       f'      commit_template: "{squash_template}"\n')
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(ENTRY.format(name=self.ext, base=self.base,
                                      policy=policy, author=self.author),
                         encoding="utf-8")

    def commit_to_base(self, files: dict, moment: datetime | None = None) -> str:
        """Коммит в ветку подтяжки проекта и отправка в его `origin`;
        `moment` — дата автора и коммиттера."""
        for rel, text in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", self.clone, "add", "-A")
        env = dated(moment) if moment is not None else {}
        with mock.patch.dict(os.environ, env):
            self.git("-C", self.clone, "commit", "-q", "-m",
                     f"base {self.word()}")
        self.git("-C", self.clone, "push", "-q", "origin",
                 f"{self.base}:{self.base}")
        return self.base_sha()

    def base_sha(self) -> str:
        return self.git("--git-dir", self.bare, "rev-parse", self.base).strip()

    def base_ahead_code(self, moment: datetime | None = None) -> str:
        """Кодовый коммит в ветку подтяжки — в зоне задачи `kod/`: гейт
        зон считает дифф от `origin/main`, и у записи с `base` не `main`
        файл вне зон отказал бы переходу раньше рубежа ревью."""
        return self.commit_to_base({f"kod/base_{self.word()}.py":
                                    f"M = {self.seed}\n"}, moment=moment)

    # ------------------------------------------------------------ задача

    def new_task(self, *, title: str | None = None, ref: str | None = "own",
                 commits: int = 2, moment: datetime | None = None) -> str:
        """Задача проекта в `in_dev`: `commits` коммитов кода в ветке,
        SPEC/PLAN/планка в ссылке документов, лок планки. `ref`: «own» —
        ссылка системы стенда с ключом стенда, «other» — ссылка другой
        системы, None — ссылок нет."""
        task = idgen.new_task_id()
        branch = f"task/{task.lower()}-{self.word()}"
        self.title = title if title is not None else (
            f"Фикстура {self.word()} {self.word()}")
        store.insert_task(self.conn, task, self.title, "in_dev", branch,
                          self.ext, config.DEFAULT_BUDGET_USD)
        zones = "app.py, kod/, docs/"
        store.update_task(self.conn, task, zones=zones)
        if ref == "own":
            store.insert_external_ref(self.conn, store.REF_KIND_TASK, task,
                                      self.system, self.key, None, "test")
        elif ref == "other":
            store.insert_external_ref(self.conn, store.REF_KIND_TASK, task,
                                      f"oth{self.word(4)}", self.key, None,
                                      "test")
        wt, error = workspace.ensure(task, branch)
        assert error is None, self.note(f"рабочая копия не заведена: {error}")
        for _ in range(commits):
            self.commit_code(task, {f"kod/{self.word()}.py":
                                    f"A = {self.rng.randrange(10**6)}\n"},
                             moment=moment)
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
                    moment: datetime | None = None, subject: str = "") -> str:
        """Коммит в рабочей копии задачи мимо пульта (как коммит роли);
        `moment` — дата автора и коммиттера, `subject` — тема."""
        wt = self.wt(task)
        for rel, text in files.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        env = dated(moment) if moment is not None else {}
        with mock.patch.dict(os.environ, env):
            self.git("-C", wt, "add", "-A")
            self.git("-C", wt, "commit", "-q", "-m",
                     subject or f"код {self.word()}")
        return self.head(task)

    def set_state(self, task: str, state: str) -> None:
        store.set_state(self.conn, task, state, "test",
                        expected_state=self.state(task),
                        detail="фикстура шаблона сообщения")

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

    # ------------------------------------------------------------ команды

    @contextlib.contextmanager
    def spy(self):
        spy = PytestSpy()
        with mock.patch.object(acceptance, "subprocess", spy), \
                mock.patch.object(two_sided, "subprocess", spy):
            yield spy

    def advance(self, task: str) -> str:
        with self.spy():
            return capture_out(fsm.cmd_advance, task)

    def amend(self, task: str, rel: str, reason: str) -> str:
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
            return capture_out(amend.cmd_amend_tests, task, reason)

    def tests_checkpoint(self, task: str) -> tuple[str, str]:
        """Чекпоинт тестов пульта за test_author (задача в
        `tests_writing`, новый свой долгоживущий файл); (sha, detail)."""
        self.set_state(task, "tests_writing")
        rel = f"tests/test_{task.lower()}_{self.word()}.py"
        path = self.wt(task) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(LONG_LIVED_TEXT.format(cls=self.word().capitalize(),
                                               word=self.word()),
                        encoding="utf-8")
        before = self.head(task)
        detail = checkpoint.commit_success_checkpoint(self.conn, task,
                                                      "test_author")
        head = self.head(task)
        assert head != before, self.context(task, "чекпоинт тестов не сделан")
        self.set_state(task, "in_dev")
        return head, detail

    def code_checkpoint(self, task: str) -> tuple[str, str]:
        """Чекпоинт кода пульта за developer (незакоммиченный файл в
        `kod/`); (sha, detail)."""
        path = self.wt(task) / "kod" / f"wip_{self.word()}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"W = {self.seed}\n", encoding="utf-8")
        before = self.head(task)
        detail = checkpoint.commit_success_checkpoint(self.conn, task,
                                                      "developer")
        head = self.head(task)
        assert head != before, self.context(task, "чекпоинт кода не сделан")
        return head, detail

    # ------------------------------------------------------------ наблюдение

    def state(self, task: str) -> str:
        return store.get_task(self.conn, task)["state"]

    def rows(self, task: str) -> list:
        return list(store.task_steps(self.conn, task))

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.rows(task))

    def context(self, task: str, out: str = "") -> str:
        return self.note(f"\n--- вывод:\n{out}\n--- журнал:\n{self.journal(task)}")

    def head(self, task: str) -> str:
        return self.git("-C", self.clone, "rev-parse", self.branch(task)).strip()

    def parents(self, sha: str) -> list:
        return self.git("-C", self.clone, "rev-list", "--parents", "-n", "1",
                        sha).split()[1:]

    def raw_message(self, sha: str) -> str:
        """Сообщение коммита побайтно (после заголовков `cat-file`)."""
        raw = self.git("-C", self.clone, "cat-file", "commit", sha)
        return raw.split("\n\n", 1)[1]

    def first_line(self, sha: str) -> str:
        return self.raw_message(sha).split("\n", 1)[0]

    def signature(self, sha: str) -> str:
        """Всё сообщение после первой строки."""
        return self.raw_message(sha).split("\n", 1)[1]

    def old_signature(self) -> str:
        """Подпись коммита пульта у записи стенда: пустая строка, соавтор,
        трейлер пульта."""
        return f"\n{self.co_author}\n{TRAILER}\n"

    def values(self, task: str, text: str) -> dict:
        return {"id": task, "ref": self.key, "title": self.title, "text": text}


@pytest.fixture
def stand(real_git):
    return Stand(real_git)


def future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=1)


# ------------------------------------------------------------------- AC-1


def test_ac1_checkpoints_first_line_by_template_signature_unchanged(stand):
    """Чекпоинты тестов и кода по шаблону `{ref}: {title}`: первая строка — ключ и название, подпись — та же, что без поля.

    Сценарий: запись с `ref_required` (система стенда) без шаблона — задача
    со ссылкой стенда, чекпоинт тестов за test_author и чекпоинт кода за
    developer: их подписи — образец. Затем та же запись с
    `commit_message_template: "{ref}: {title}"` и новая задача со ссылкой
    `<система>:ABC-<n>` и случайным названием — те же два чекпоинта.
    Первая строка каждого из двух коммитов — `ABC-<n>: <название>`, всё
    после первой строки побайтно равно подписи того же коммита без поля
    (пустая строка, строка соавтора, трейлер пульта).

    Ловит мутацию: шаблон применяется только в чекпоинте разработчика (у
    коммита тестов первая строка `<id>: …`); либо шаблон подставлен в
    сообщение целиком вместе с подписью `pult_message` (подпись после
    первой строки потеряна или задвоена).
    """
    stand.record()
    plain = stand.new_task()
    plain_tests, _ = stand.tests_checkpoint(plain)
    plain_code, _ = stand.code_checkpoint(plain)

    stand.record(template="{ref}: {title}")
    task = stand.new_task()
    tests_sha, _ = stand.tests_checkpoint(task)
    code_sha, _ = stand.code_checkpoint(task)
    expected = f"{stand.key}: {stand.title}"
    for kind, sha, sample in (("тестов", tests_sha, plain_tests),
                              ("кода", code_sha, plain_code)):
        where = stand.context(task, f"чекпоинт {kind}: {stand.raw_message(sha)!r}")
        assert stand.first_line(sha) == expected, where
        assert stand.signature(sha) == stand.signature(sample), where
        assert stand.signature(sha) == stand.old_signature(), where


# ------------------------------------------------------------------- AC-2


def test_ac2_text_placeholder_is_service_text_without_id(stand):
    """Шаблон `{ref}: {text}`: первая строка чекпоинта тестов — ключ и служебный текст без префикса `<id>: `.

    Сценарий: запись с `ref_required` и `commit_message_template:
    "{ref}: {text}"`, задача со ссылкой `<система>:ABC-<n>`; чекпоинт тестов
    пульта за test_author. Первая строка — `ABC-<n>: долгоживущие тесты
    закоммичены пультом за роль test_author — шаг завершён`, id задачи в
    ней нет.

    Ловит мутацию: `{text}` раскрыт прежним сообщением целиком, с
    префиксом `<id>: ` (первая строка `ABC-<n>: <id>: долгоживущие …`);
    либо `{text}` раскрыт названием задачи, как в шаблоне сжатого коммита.
    """
    stand.record(template="{ref}: {text}")
    task = stand.new_task()
    sha, _ = stand.tests_checkpoint(task)
    where = stand.context(task, repr(stand.raw_message(sha)))
    assert stand.first_line(sha) == f"{stand.key}: {TESTS_TEXT}", where
    assert task not in stand.first_line(sha), where


def test_ac2_title_literals_not_expanded(stand):
    """Шаблон `{ref}: {title}` и название с литералами `{ref}`, `{text}`, `{id}`: первая строка — ключ и название как есть.

    Сценарий: запись с `ref_required` и `commit_message_template:
    "{ref}: {title}"`; название задачи — случайные слова вперемешку с
    литералами `{ref}`, `{text}` и `{id}` в порядке от зерна; чекпоинт
    тестов пульта. Первая строка — `ABC-<n>: ` и название побайтно, ни один
    литерал названия не раскрыт.

    Ловит мутацию: подстановка — цепочка `str.replace` в порядке `{title}`,
    затем `{ref}`/`{text}`/`{id}` (литералы названия раскрыты ключом,
    служебным текстом или id); либо `str.format_map` по уже подставленной
    строке (повторное раскрытие).
    """
    marks = ["{ref}", "{text}", "{id}"]
    stand.rng.shuffle(marks)
    title = " ".join(f"{stand.word(4)} {mark}" for mark in marks)
    stand.record(template="{ref}: {title}")
    task = stand.new_task(title=title)
    sha, _ = stand.tests_checkpoint(task)
    where = stand.context(task, repr(stand.raw_message(sha)))
    assert stand.first_line(sha) == f"{stand.key}: {title}", where


# ------------------------------------------------------------------- AC-3


def test_ac3_without_field_checkpoint_messages_unchanged(stand):
    """Запись без поля: сообщения чекпоинтов тестов и кода — прежние побайтно.

    Сценарий: запись с `ref_required` и ссылкой задачи, но без
    `commit_message_template`; чекпоинт тестов за test_author и чекпоинт
    кода за developer. Сообщение каждого коммита побайтно равно
    `<id>: <прежний служебный текст>`, пустой строке, строке соавтора и
    трейлеру пульта.

    Ловит мутацию: умолчание шаблона — не `{id}: {text}` (например
    `{ref}: {text}` или `{id}: {title}` — первая строка другая); либо
    сборка первой строки теряет перевод строки перед подписью.
    """
    stand.record()
    task = stand.new_task()
    tests_sha, _ = stand.tests_checkpoint(task)
    code_sha, _ = stand.code_checkpoint(task)
    for sha, text in ((tests_sha, TESTS_TEXT), (code_sha, CODE_TEXT)):
        where = stand.context(task, repr(stand.raw_message(sha)))
        assert stand.raw_message(sha) == (f"{task}: {text}\n"
                                          + stand.old_signature()), where


VALID_TEMPLATES = ["{ref}: {title}", "{ref}: {text}", "{text} ({ref})",
                   "{id}: {title}", "случайный"]


def random_template(stand) -> str:
    """Годный шаблон: все четыре подстановки в порядке от зерна между
    случайными словами."""
    marks = ["{id}", "{ref}", "{title}", "{text}"]
    stand.rng.shuffle(marks)
    return " ".join(f"{stand.word(3)} {mark}" for mark in marks)


def artifact_and_squash_messages(stand, template, title, squash_template):
    """(сообщение коммита ссылки документов, сообщение сжатого коммита)
    задачи под записью с шаблоном `template` (None — без поля); id задачи
    в обоих заменён на `<id>`."""
    stand.record(template=template, squash_template=squash_template)
    task = stand.new_task(title=title)
    before = stand.docs_head(task)
    stand.write_docs(task, {"PLAN.md": PLAN_TEXT.format(task=task)
                            + f"\nПравка {stand.word()}.\n"})
    docs = stand.docs_head(task)
    assert docs != before, stand.context(task, "коммита документов нет")
    out = stand.advance(task)
    assert stand.state(task) == "verifying", stand.context(task, out)
    head = stand.head(task)
    return (stand.raw_message(docs).replace(task, "<id>"),
            stand.raw_message(head).replace(task, "<id>"))


@pytest.mark.parametrize("template", VALID_TEMPLATES)
def test_ac3_artifact_and_squash_commits_unchanged_by_field(stand, template):
    """При годном шаблоне коммит ссылки документов `refs/artifacts/<id>` и сжатый коммит по `policy.commit_template` — прежние побайтно.

    Сценарий: запись со сжатием (`squash_before_mr: true`,
    `commit_template` со случайным префиксом и `{text}`) и `ref_required`.
    Задача без поля шаблона — коммит документа шага в ссылку документов и
    переход в `verifying` (сжатый коммит — голова ветки): их сообщения —
    образец. Та же запись с `commit_message_template` (по параметру;
    «случайный» — все четыре подстановки в порядке от зерна) и задача с тем
    же названием — те же два коммита. Сообщения с заменой id задачи на
    `<id>` побайтно равны образцу.

    Ловит мутацию: шаблон применён в общей точке подписи коммитов пульта
    (`pult_message`) — меняются и коммиты ссылки документов, и сжатый
    коммит; либо сжатый коммит собирается шаблоном коммитов ветки вместо
    `commit_template`.
    """
    if template == "случайный":
        template = random_template(stand)
    title = f"Фикстура {stand.word()} {stand.word()}"
    squash_template = f"сжато {stand.word(4)}: {{text}}"
    sample = artifact_and_squash_messages(stand, None, title, squash_template)
    got = artifact_and_squash_messages(stand, template, title, squash_template)
    where = stand.note(f"шаблон {template!r}: образец {sample!r}, есть {got!r}")
    assert got[0] == sample[0], where
    assert got[1] == sample[1], where
    assert got[1].split("\n", 1)[0] == squash_template.replace("{text}", title), \
        where


# ------------------------------------------------------------------- AC-5


@pytest.mark.parametrize("ref", [None, "other"])
@pytest.mark.parametrize("role", ["developer", "test_author"])
def test_ac5_no_ref_falls_back_to_default_and_journals(stand, role, ref):
    """Шаблон с `{ref}` без ссылки системы `ref_required`: коммит по умолчанию, запись журнала с причиной, шаг идёт дальше.

    Сценарий: запись с `ref_required: <случайная система>` и
    `commit_message_template: "{ref}: {text}"`; у задачи ссылок нет либо
    есть только ссылка другой системы; чекпоинт пульта за `role`. Коммит
    сделан (голова сдвинулась, чекпоинт вернул непустой итог), его
    сообщение — `<id>: <служебный текст>` с прежней подписью; в журнале
    задачи есть запись с действием `шаблон сообщения не применён`, чья
    деталь несёт `нет ссылки системы <система>`; задача в прежнем
    состоянии.

    Ловит мутацию: `{ref}` без ссылки раскрыт пустой строкой (первая
    строка `: <текст>`); либо ссылка берётся первой любой системы (у
    задачи со ссылкой другой системы — её ключ); либо запись журнала
    называет литерал `tracker` вместо системы записи; либо отсутствие
    ссылки бросает исключение и коммита нет.
    """
    stand.record(template="{ref}: {text}")
    task = stand.new_task(ref=ref)
    if role == "developer":
        sha, detail = stand.code_checkpoint(task)
        text = CODE_TEXT
    else:
        sha, detail = stand.tests_checkpoint(task)
        text = TESTS_TEXT
    where = stand.context(task, repr(stand.raw_message(sha)))
    assert detail, where
    assert stand.raw_message(sha) == f"{task}: {text}\n" + stand.old_signature(), \
        where
    reason = NOT_APPLIED_REASON.format(system=stand.system)
    assert any(r["action"] == NOT_APPLIED_ACTION and reason in (r["detail"] or "")
               for r in stand.rows(task)), where
    assert stand.state(task) == "in_dev", where


# ------------------------------------------------------------------- AC-7


def conflict_on_notes(stand, task: str, moment: datetime | None = None) -> None:
    """Обе стороны дописали разные строки в конец `docs/notes.md`;
    ветка подтяжки впереди и кодовым коммитом."""
    notes = stand.git("-C", stand.clone, "show", f"{stand.head(task)}:docs/notes.md")
    stand.commit_code(task, {"docs/notes.md": notes + f"- ветка {stand.word()}\n"},
                      moment=moment)
    stand.commit_to_base({"docs/notes.md": notes + f"- base {stand.word()}\n",
                          f"kod/base_{stand.word()}.py": "M = 1\n"},
                         moment=moment)


AC7_KINDS = ["подтяжка", "авторазрешение конфликта", "amend-tests",
             "amend-tests с литералом {title}"]


@pytest.mark.parametrize("kind", AC7_KINDS)
def test_ac7_pull_and_amend_commits_by_template(stand, kind):
    """Merge-коммит подтяжки, коммит авторазрешения конфликта и коммит `amend-tests` — первая строка по шаблону `{ref}: {text}`, подпись прежняя.

    Сценарий (запись с `ref_required` и `commit_message_template:
    "{ref}: {text}"`, задача со ссылкой `<система>:ABC-<n>`):
    «подтяжка» — ветка подтяжки впереди кодовым коммитом, переход
    `in_dev → verifying` сливает её; «авторазрешение конфликта» — обе
    стороны дописали `docs/notes.md`, пульт разрешает конфликт сам (запись
    журнала об аддитивном слиянии); в обоих голова — коммит с двумя
    родителями (второй — голова ветки подтяжки), первая строка
    `ABC-<n>: подтяжка <ветка>`. «amend-tests» — правка долгоживущего файла
    задачи, причина — случайные слова: первая строка `ABC-<n>: правка
    долгоживущих тестов — <причина>`; «amend-tests с литералом {title}» —
    в причине литерал `{title}`: он остаётся в первой строке буквально, не
    раскрыт названием. У всех — подпись после первой строки прежняя.

    Ловит мутацию: шаблон применяется только в чекпоинтах (первая строка
    подтяжки или `amend-tests` — `<id>: …`); шаблон не применён в
    авторазрешении конфликта (`<id>: подтяжка <ветка>` у этого коммита);
    подстановка — цепочка последовательных замен `{id}`, `{ref}`, `{text}`,
    `{title}` (литерал `{title}` причины раскрыт названием задачи).
    """
    stand.record(template="{ref}: {text}")
    task = stand.new_task()
    out = ""
    if kind.startswith("amend-tests"):
        rel = stand.with_long_lived(task)
        reason = f"правка {stand.word()} {stand.word()}"
        if kind != "amend-tests":
            reason = f"правка {stand.word()} {{title}} {stand.word()}"
        before = stand.head(task)
        out = stand.amend(task, rel, reason)
        head = stand.head(task)
        assert head != before, stand.context(task, out)
        text = AMEND_TEXT.format(reason=reason)
    else:
        if kind == "авторазрешение конфликта":
            conflict_on_notes(stand, task)
        else:
            stand.base_ahead_code()
        base = stand.base_sha()
        out = stand.advance(task)
        head = stand.head(task)
        where = stand.context(task, out)
        assert stand.state(task) == "verifying", where
        parents = stand.parents(head)
        assert len(parents) == 2 and parents[1] == base, where
        if kind == "авторазрешение конфликта":
            assert any(r["action"] == pull.ADDITIVE_CONFLICT_ACTION
                       for r in stand.rows(task)), where
        text = PULL_TEXT.format(base=stand.base)
    where = stand.context(task, f"{out}\n--- сообщение: {stand.raw_message(head)!r}")
    assert stand.first_line(head) == f"{stand.key}: {text}", where
    assert stand.signature(head) == stand.old_signature(), where
    if kind == "amend-tests с литералом {title}":
        assert "{title}" in stand.first_line(head), where
        assert stand.title not in stand.first_line(head), where


# ------------------------------------------------------------------- AC-8


AC8_CASES = ["подтяжка", "авторазрешение конфликта", "прежняя тема подтяжки",
             "коммит кода пульта"]


@pytest.mark.parametrize("case", AC8_CASES)
@pytest.mark.parametrize("base", [config.MAIN_BRANCH, "develop"])
@pytest.mark.parametrize("template", ["{ref}: {text}", "{text} ({ref})"])
def test_ac8_rework_gate_ignores_pull_by_template(real_git, template, base, case):
    """Рубеж «замечания ревью не отработаны» не засчитывает подтяжку ни по теме шаблона, ни по прежней теме; коммит кода пульта по шаблону засчитывает.

    Сценарий: запись с `ref_required`, `commit_message_template` по
    параметру и `base` по параметру (`main` либо `develop`); задача со
    ссылкой `<система>:ABC-<n>` в `in_dev`, коммиты разработчика — задним
    числом, как и коммиты ветки подтяжки, ушедшей вперёд (их подтяжка
    приносит в историю ветки задачи); после них — вердикт ревью
    `changes_requested` автокоммитом шага ревьювера и возврат в `in_dev`;
    всё после вердикта датировано будущим.
    «подтяжка» — ветка подтяжки впереди кодовым коммитом, переход сам
    делает merge-коммит подтяжки; «авторазрешение конфликта» — подтяжка с
    аддитивным конфликтом `docs/notes.md`, пульт разрешает его сам; в обоих
    голова ветки после перехода — коммит подтяжки с темой по шаблону
    (`ABC-<n>: подтяжка <ветка>` / `подтяжка <ветка> (ABC-<n>)`), и переход
    отказан рубежом, задача в `in_dev`. «прежняя тема подтяжки» — после
    вердикта в ветке только merge-коммит ветки подтяжки с темой
    `<id>: подтяжка <ветка>` — тоже отказ. «коммит кода пульта» (журнал без
    шага developer) — после вердикта коммит кода с темой шаблона для
    служебного текста `код закоммичен пультом за роль developer — …` —
    отказа рубежа нет.

    Ловит мутацию: фильтр подтяжки только по прежнему префиксу
    `"<id>: подтяжка "` (подтяжка по шаблону засчитана — отказа нет);
    отсев по началу темы шаблона без `подтяжка ` (коммит кода пульта
    отсеян — отказ в «коммит кода пульта»); рубеж всегда отказывает;
    сравнение начала темы только до `{text}` у шаблона `{text} ({ref})`;
    ветка подтяжки жёстко `main` (у `develop` тема подтяжки не опознана —
    отказа нет).
    """
    stand = Stand(real_git, base=base)
    stand.record(template=template)
    past = datetime.now(timezone.utc) - timedelta(hours=stand.rng.randint(2, 48))
    task = stand.new_task(moment=past)
    if case == "авторазрешение конфликта":
        conflict_on_notes(stand, task, moment=past)
    elif case in ("подтяжка", "прежняя тема подтяжки"):
        stand.base_ahead_code(moment=past)
    stand.write_docs(task, {"REVIEW.md": REVIEW_TEXT.format(
        task=task, word=stand.word())}, role="reviewer")
    store.journal(stand.conn, task, "fsm", "state -> in_dev",
                  "замечания ревью, итерация 1")
    later = future()
    pull_subject = render(template, stand.values(task, PULL_TEXT.format(base=base)))
    if case == "прежняя тема подтяжки":
        wt = stand.wt(task)
        stand.git("-C", wt, "fetch", "-q", "origin", base)
        pull_subject = f"{task}: {PULL_TEXT.format(base=base)}"
        with mock.patch.dict(os.environ, dated(later)):
            stand.git("-C", wt, "merge", "--no-ff", "-q", "FETCH_HEAD", "-m",
                      pull_subject)
    elif case == "коммит кода пульта":
        stand.commit_code(task, {f"kod/{stand.word()}.py": f"C = {stand.seed}\n"},
                          moment=later,
                          subject=render(template, stand.values(task, CODE_TEXT)))
    with mock.patch.dict(os.environ, dated(later)):
        out = stand.advance(task)
    where = stand.context(task, out)
    refused = any(r["action"] == REWORK_ACTION for r in stand.rows(task))
    if case == "коммит кода пульта":
        assert not refused, where
        return
    head = stand.head(task)
    assert len(stand.parents(head)) == 2, where
    assert stand.first_line(head) == pull_subject, where
    assert refused, where
    assert stand.state(task) == "in_dev", where
