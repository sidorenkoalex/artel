"""Профиль проекта задачи у вызывающих прогон pytest: argv, `cwd` и окружение каждого места.

Группа: долгоживущий
Красен до реализации: вызывающие вне `acceptance.py` не передают профиль `pytest-own` — гейт мержа, `suite-run`, прогон планки и повторы `in_dev`, сухой сбор `tests_writing` передают список команды профиля (интерпретатор пульта вместо `python3`, `-p timeout`, корень дерева, окружение пульта), `plank-run`, `amend-tests`, `pull` и двусторонний прогон — ничего, ключ итога базы `suite-run` считается по списку; автогейт и `approve` на acceptance (AC-1, AC-2, механика `acceptance_suite` части 2), артель и внешний `pult-pytest` (AC-10) и прогон без задачи (AC-11) держат сегодняшнее поведение и зелёны с рождения.

Связка «команда пульта — FSM — база — git — место запуска»: каждое место
доходит до прогона через публичный вход (`fsm.cmd_advance`,
`fsm.cmd_approve`, `suite_run.cmd_suite_run` + `suite_run.background`,
`plank_run.cmd_plank_run`, `amend.cmd_amend_tests`,
`pull_main.cmd_pull_main`) в настоящем git песочницы
(`tests.sandbox.RealGitSandbox`): клон артели и клон внешнего проекта
(`tests.sandbox.make_project_repo`) с bare `origin`; ссылка документов —
автокоммитом шага (`checkpoint.commit_step_artifacts`). Профиль внешнего
проекта в `targets.yaml` песочницы — `runner: pytest-own` со случайными
`workdir` (под `tests/`: раздел SPEC «Меняемое поведение» называет только
файлы `tests/…`) и переменной `env`, либо `pult-pytest` с командой
`python3 -m pytest` и добавочным флагом — чтобы команда профиля была
отличима от команды пульта.

Наблюдение — подмена модуля `subprocess` у мест запуска (`acceptance`,
`two_sided`): вызов pytest запоминает argv, `cwd`, окружение и содержимое
каталогов вокруг `cwd` и отвечает зелёным прогоном; git и прочие процессы
идут настоящими. Подменены только внешние для песочницы ответы: цвет CI
(`ci.branch_status`, `ci.main_line_status`, `ci.head_sha` — итога CI нет,
приёмка идёт локально), Draft MR и отправка головы форджа
(`github_adapter`), политика гейта acceptance у автогейта (`gates.policy`),
отвязанный фон `suite-run` (фон зовётся в этом же процессе). Объявление
смены поведения теста `approve` гейта SPEC пишет только задаче артели —
сценарий гейта двустороннего прогона кладёт запись «объявлена смена
поведения тестов» в журнал сам, тем же текстом строки раздела.

В окружении пульта на время теста — случайная переменная; имена каталогов,
файлов, значения `env` и ожиданий — из `random`, зерно печатается и входит
в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
профиль `pytest-own` передан каналом `command`/`profile` в каждой точке
требования 1, у `amend-tests` без долгоживущих файлов — с `cwd` рабочей
копии, у `pult-pytest` и артели — прежние вызовы; все методы зелёные.
Мутации стаба «`cwd` не передан в amend без долгоживущих файлов», «ключ
базы `suite-run` по списку команды» и «профиль в `pull` безусловно» дают
красные AC-6, AC-4 и AC-10 соответственно.
"""
import contextlib
import hashlib
import io
import os
import random
import subprocess
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, amend, catalog, checkpoint, ci, config,
                          fsm, gates, github_adapter, idgen, plank_run,
                          project_profile, pull_main, stack, store,
                          suite_run, workspace)
from orchestrator.advance_gates import test_integrity, two_sided
from scripts import guard
from tests.sandbox import RealGitSandbox, make_project_repo

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
OUTPUT = "1 passed in 0.01s\n"
COLLECTED = "probe.py::test_probe\n\n1 test collected in 0.01s\n"
JUNIT = ('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite '
         'name="pytest" errors="0" failures="0" skipped="0" tests="1">'
         '<testcase classname="probe" name="test_probe" time="0.01"/>'
         '</testsuite></testsuites>')
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
DOCS_REF = "refs/artifacts/"

OWN = "pytest-own"
EXT_PULT = "pult-pytest внешнего проекта"
ARTEL_PULT = "артель"
KINDS = (OWN, EXT_PULT, ARTEL_PULT)

ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [{command}]
      long_lived_dir: {lld}
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [{lld}/**/*.py]
      mutation_claim_scope: [{lld}/test_*.py]
{extra}"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
---

# SPEC: фикстура вызывающих прогон

## Контекст

Фикстура песочницы.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстурный критерий.
{section}
## Не входит

Ничего.
"""

CHANGE_SECTION = """
## Меняемое поведение

Смена ожидания фикстуры.

- `{node}`: `{old}` → `{new}` (требование 1)
"""

REVIEW_TEXT = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: фикстура

## Соответствие SPEC

Фикстура.

## Замечания

Нет.

## Реестр замечаний
| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
Фикстура песочницы — прогон не нужен.
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
{appendices}"""

APPENDIX = """
## Приложение {number}: {heading}

```diff
{diff}```
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

BASE_TEST_TEXT = '''import unittest

import app


class BaseTest(unittest.TestCase):

    def test_value(self):
        """Существующий тест проекта.

        Ловит мутацию: фикстура песочницы.
        """
        self.assertEqual(app.VALUE, {value})
'''


def is_pytest(argv) -> bool:
    parts = [str(a) for a in argv]
    return any(Path(p).name in ("pytest", "py.test") for p in parts) or any(
        a == "-m" and b == "pytest" for a, b in zip(parts, parts[1:]))


def has_pair(argv: list, first: str, second: str) -> bool:
    return any(argv[i] == first and argv[i + 1] == second
               for i in range(len(argv) - 1))


def new_file_diff(rel: str, line: str) -> str:
    return (f"diff --git a/{rel} b/{rel}\n"
            f"new file mode 100644\n"
            f"--- /dev/null\n"
            f"+++ b/{rel}\n"
            f"@@ -0,0 +1 @@\n"
            f"+{line}\n")


def is_full_suite(call: dict) -> bool:
    """Вызов pytest — прогон полного набора, а не планки, сбора, повтора
    или стороны двустороннего прогона."""
    argv = call["argv"]
    return not any("acceptance_tests" in a or a.startswith("--junitxml=")
                   for a in argv) and "--collect-only" not in argv \
        and two_sided.PLUGIN_MODULE not in argv


class Detached:
    """Замена `subprocess` у `suite_run`: отвязанный фоновый процесс не
    запускается, замок машины передаётся этому процессу (его pid), а сам
    фон зовёт сценарий — `suite_run.background` в этом же процессе."""

    class Child:
        def __init__(self):
            self.pid = os.getpid()

    def __getattr__(self, name):
        return getattr(subprocess, name)

    def Popen(self, *args, **kwargs):
        return self.Child()


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
    """Замена модуля `subprocess` у мест запуска (`acceptance`,
    `two_sided`): вызов pytest запоминается (argv, `cwd`, окружение,
    содержимое `cwd` и его родителя в момент вызова) и отвечает зелёным
    прогоном; прочие вызовы (git, ps) идут настоящим `subprocess`."""

    def __init__(self, depth: int = 1):
        self.calls: list = []
        self.depth = depth

    def __getattr__(self, name):
        return getattr(subprocess, name)

    def record(self, argv, kwargs) -> str:
        argv = [str(a) for a in argv]
        env = kwargs.get("env")
        cwd = kwargs.get("cwd")
        here = Path(cwd) if cwd is not None else Path.cwd()
        listing = sorted(os.listdir(here)) if here.is_dir() else []
        up = here.parents[self.depth - 1]
        above = sorted(os.listdir(up)) if up.is_dir() else []
        self.calls.append({"argv": argv, "cwd": str(here),
                           "real_cwd": os.path.realpath(here),
                           "env": dict(os.environ if env is None else env),
                           "listing": listing, "above": above})
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


class ProfileCallersSandbox(RealGitSandbox):
    """Клон артели и клон внешнего проекта с bare `origin`; профиль тестов
    внешнего проекта — `pytest-own` либо `pult-pytest` по сценарию."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"proj{self.word()}"
        # Под `tests/`: раздел SPEC «Меняемое поведение» называет только
        # файлы `tests/…` — иначе гейт двустороннего прогона недостижим.
        self.workdir = f"tests/wd_{self.word()}"
        self.lld = f"{self.workdir}/checks_{self.word()}"
        self.prot = f"zp{self.word()}"
        self.marker = f"marker_{self.word()}.txt"
        self.env_name = f"PROBE_ENV_{self.word().upper()}"
        self.env_value = self.word(12)
        self.leak_name = f"ARTEL_LEAK_{self.word().upper()}"
        self.leak_value = self.word(12)
        self.pult_flag = "-rN"
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                             self.leak_name: self.leak_value}),
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
            self.addCleanup(patcher.stop)
        self.kind = OWN
        self.artel_origin = self.add_synced_origin()
        self.write_targets(OWN)
        self.ext_clone = make_project_repo(self.ext)
        capture_out(catalog.cmd_init)
        self.base_name = f"test_base_{self.word()}.py"
        self.old_value = self.rng.randrange(10, 1000)
        self.new_value = self.old_value + self.rng.randrange(1, 9)
        base = {self.marker: "метка дерева\n",
                "app.py": f"VALUE = {self.old_value}\n",
                f"tests/{self.base_name}": BASE_TEST_TEXT.format(
                    value=self.old_value)}
        self.commit_to_main(self.ext_clone, {
            **base, f"{self.lld}/{self.base_name}": BASE_TEST_TEXT.format(
                value=self.old_value)})
        self.commit_to_main(self.root, base)
        self.docs_files: dict = {}

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def write_targets(self, kind: str) -> None:
        """`targets.yaml` песочницы: артель со своим профилем и внешний
        проект с профилем вида `kind` (при `ARTEL_PULT` — `pytest-own`)."""
        self.kind = kind
        artel = ENTRY.format(name=ARTEL, url="http://localhost/artel",
                             base=config.MAIN_BRANCH,
                             no_paths=", ".join(config.PROTECTED_PATHS),
                             command="python3, -m, pytest", lld="tests",
                             extra="      report: junit-xml\n      install: []\n")
        # Задача артели — при внешнем проекте с `pytest-own` рядом.
        if kind in (OWN, ARTEL_PULT):
            command, lld = "python3, -m, pytest", self.lld
            extra = (f"      runner: pytest-own\n"
                     f"      workdir: {self.workdir}\n"
                     f"      env:\n        {self.env_name}: {self.env_value}\n")
        else:
            command, lld, extra = f"python3, -m, pytest, {self.pult_flag}", \
                "tests", ""
        ext = ENTRY.format(name=self.ext, url=f"file:///nonexistent/{self.ext}",
                           base=config.MAIN_BRANCH, no_paths=f"{self.prot}/",
                           command=command, lld=lld, extra=extra)
        config.TARGETS.write_text("targets:\n" + artel + ext, encoding="utf-8")

    def target(self) -> str:
        return ARTEL if self.kind == ARTEL_PULT else self.ext

    def clone(self, target: str | None = None) -> Path:
        return self.root if (target or self.target()) == ARTEL else self.ext_clone

    def commit_to_main(self, clone: Path, files: dict) -> None:
        # Гейт мержа прошлого сценария мог сдвинуть main в origin.
        self.git("-C", str(clone), "pull", "-q", "--ff-only", "origin",
                 config.MAIN_BRANCH)
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    # ------------------------------------------------------------ задача

    def new_task(self, state: str, code: dict | None = None,
                 appendices: list = (), plank: bool = True,
                 section: str = "") -> str:
        """Задача проекта сценария в состоянии `state`: код `code` в ветке,
        SPEC/PLAN/планка в ссылке документов."""
        target = self.target()
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, target, config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        if code:
            self.commit_code(task_id, code)
        sections = "".join(
            APPENDIX.format(number=n, heading=self.word(), diff=diff)
            for n, diff in enumerate(appendices, 1))
        docs = {"SPEC.md": SPEC_TEXT.format(task=task_id, zones=self.zones(),
                                            section=section),
                "PLAN.md": PLAN_TEXT.format(task=task_id, appendices=sections)}
        if plank:
            docs[f"acceptance_tests/test_ac1_{self.word()}.py"] = \
                PLANK_TEXT.format(word=self.word())
        self.write_docs(task_id, docs)
        return task_id

    def zones(self) -> str:
        return "app.py, kod/, tests/, " + (f"{self.lld}/" if self.kind == OWN else "tests/")

    def docs_dir(self, task_id: str) -> Path:
        return config.PROJECTS / store.task_target(self.conn, task_id) / \
            "tasks" / task_id

    def write_docs(self, task_id: str, files: dict) -> None:
        self.docs_files.setdefault(task_id, {}).update(files)
        docs = self.docs_dir(task_id)
        for rel, text in files.items():
            path = docs / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        capture_out(checkpoint.commit_step_artifacts, self.conn, task_id,
                    "developer")

    def docs_head(self, task_id: str) -> str:
        clone = self.clone(store.task_target(self.conn, task_id))
        return self.git("-C", str(clone), "for-each-ref",
                        "--format=%(objectname)", DOCS_REF + task_id).strip()

    def wt(self, task_id: str) -> Path:
        return workspace.path(task_id, store.task_target(self.conn, task_id))

    def commit_code(self, task_id: str, files: dict, push: bool = True) -> None:
        wt = self.wt(task_id)
        for rel, text in files.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: код задачи")
        if push:
            branch = store.get_task(self.conn, task_id)["branch"]
            self.git("-C", str(wt), "push", "-q", "-f", "origin",
                     f"{branch}:{branch}")

    def code(self) -> dict:
        return {f"kod/{self.word()}.py": f"A = {self.seed}\n"}

    def project_tests_dir(self) -> str:
        """Каталог тестов проекта по профилю сценария."""
        return self.lld if self.kind == OWN else "tests"

    def lock(self, task_id: str, long_lived: bool = False) -> str:
        """Лок планки на голове ссылки документов; `long_lived` — ещё
        долгоживущий файл с зерном в ветке и перечень его суммы в планке.
        Возвращает путь долгоживущего файла (или пусто)."""
        rel = ""
        if long_lived:
            rel = (f"{self.project_tests_dir()}/test_{task_id.lower()}_"
                   f"{self.word()}.py")
            self.commit_code(task_id, {rel: LONG_LIVED_TEXT.format(
                cls=self.word().capitalize(), word=self.word())})
            digest = hashlib.sha256(
                (self.wt(task_id) / rel).read_bytes()).hexdigest()
            self.write_docs(task_id, {
                f"acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}":
                    guard.render_long_lived_manifest({rel: digest})})
        store.update_task(self.conn, task_id,
                          tests_locked_sha=self.docs_head(task_id),
                          draft_mr_created=1)
        store.record_fixation(self.conn, task_id)
        return rel

    # ---------------------------------------------------- места вызова

    def run_autogate(self) -> tuple:
        """Автогейт приёмки: `advance` из `review` с одобренным REVIEW.md
        при политике гейта acceptance `auto` — полный набор перед мержем."""
        task = self.new_task("review", self.code())
        self.write_docs(task, {"REVIEW.md": REVIEW_TEXT.format(task=task)})
        store.update_task(self.conn, task, draft_mr_created=1)
        store.record_fixation(self.conn, task)
        real_policy = gates.policy
        with mock.patch.object(gates, "policy", lambda gate: gates.AUTO
                               if gate == "acceptance" else real_policy(gate)), \
                self.spy() as spy:
            out = capture_out(fsm.cmd_advance, task)
        return task, out, [c for c in spy.calls if is_full_suite(c)]

    def run_approve(self, fresh: bool) -> tuple:
        """`approve` на acceptance — полный набор приёмки."""
        task = self.new_task("acceptance", self.code())
        store.record_fixation(self.conn, task)
        with self.spy() as spy:
            out = capture_out(fsm.cmd_approve, task, fresh_suite=fresh)
        return task, out, [c for c in spy.calls if is_full_suite(c)]

    def run_merge_gate(self, fresh: bool) -> tuple:
        """`approve` на `merge_gate` задачи с приложением PLAN — полный набор
        после применённого приложения, со свежим прогоном и без."""
        rel = (f"{self.prot}/{self.word()}.cfg" if self.kind != ARTEL_PULT
               else f"zd{self.word()}/conftest.py")
        task = self.new_task("merge_gate", self.code(),
                             [new_file_diff(rel, f"# {self.word()}")])
        store.record_fixation(self.conn, task)
        with self.spy() as spy:
            out = capture_out(fsm.cmd_approve, task, fresh_suite=fresh)
        return task, out, [c for c in spy.calls if is_full_suite(c)]

    def run_suite_run(self) -> tuple:
        """`suite-run` задачи: прогон ветки и прогон базы в фоне (в процессе)."""
        task = self.new_task("in_dev", self.code())
        with self.spy() as spy:
            with mock.patch.object(suite_run, "subprocess", Detached()):
                out = capture_out(suite_run.cmd_suite_run, [task])
            out += capture_out(suite_run.background, task, "1",
                               suite_run.MODE_FULL)
        return task, out, [c for c in spy.calls if is_full_suite(c)]

    def run_plank_run(self) -> tuple:
        """`plank-run` черновика планки задачи в `tests_writing`."""
        task = self.new_task("tests_writing", self.code())
        draft = self.docs_dir(task) / "acceptance_tests"
        draft.mkdir(parents=True, exist_ok=True)
        (draft / f"test_ac1_{self.word()}.py").write_text(
            PLANK_TEXT.format(word=self.word()), encoding="utf-8")
        with self.spy() as spy:
            out = capture_out(plank_run.cmd_plank_run, task)
        return task, out, list(spy.calls)

    def run_amend(self, long_lived: bool) -> tuple:
        """`amend-tests` правки планки лока: с долгоживущими файлами
        (сбор и прогон с ними) и без них (сбор и прогон одной планки)."""
        task = self.new_task("in_dev", self.code())
        self.lock(task, long_lived=long_lived)
        task_dir = self.wt(task) / "tasks" / task
        for rel, text in self.docs_files[task].items():
            if not rel.startswith("acceptance_tests/"):
                continue
            if Path(rel).name.startswith("test_"):
                text += f"\n# правка Оператора {self.word()}\n"
            path = task_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        with self.spy() as spy:
            out = capture_out(amend.cmd_amend_tests, task,
                              f"правка планки {self.seed}")
        return task, out, list(spy.calls)

    def run_pull(self, long_lived: bool) -> tuple:
        """`pull-main` задачи в `verifying`, отставшей от main проекта, —
        прогон планки (с долгоживущими файлами и без) после подтяжки."""
        task = self.new_task("verifying", self.code())
        self.lock(task, long_lived=long_lived)
        self.commit_to_main(self.clone(), {f"kod_main/{self.word()}.py":
                                           f"B = {self.seed}\n"})
        with self.spy() as spy, \
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda conn, task_id, branch: (True, "")):
            out = capture_out(pull_main.cmd_pull_main, task)
        return task, out, list(spy.calls)

    def run_two_sided(self, observation: bool) -> tuple:
        """`advance` из `in_dev` с изменённым ожиданием существующего теста
        проекта: двусторонний прогон гейта (смена объявлена в SPEC) либо
        наблюдения (смена не объявлена, наблюдение включено)."""
        rel = f"{self.project_tests_dir()}/{self.base_name}"
        node = f"{rel}::BaseTest::test_value"
        section = "" if observation else CHANGE_SECTION.format(
            node=node, old=self.old_value, new=self.new_value)
        task = self.new_task("in_dev", section=section)
        if section:
            # Запись объявления пишет `approve` гейта SPEC только задаче
            # артели; узел неослабления читает объявленное из неё у любой
            # задачи — сценарий кладёт её тем же текстом строк раздела.
            store.journal(self.conn, task, "operator",
                          test_integrity.DECLARED_CHANGE_ACTION,
                          section.strip().splitlines()[-1])
        self.lock(task)
        self.commit_code(task, {rel: BASE_TEST_TEXT.format(value=self.new_value),
                                "app.py": f"VALUE = {self.new_value}\n"})
        store.record_fixation(self.conn, task)
        with self.spy() as spy, \
                mock.patch.object(config, "TWO_SIDED_OBSERVATION", observation):
            out = capture_out(fsm.cmd_advance, task)
        return task, out, [c for c in spy.calls
                           if two_sided.PLUGIN_MODULE in c["argv"]]

    def run_tests_writing(self, long_lived: bool) -> tuple:
        """`advance` из `tests_writing` — сухой сбор планки (с долгоживущим
        файлом задачи в кодовой ветке и без него)."""
        task = self.new_task("tests_writing")
        if long_lived:
            self.commit_code(task, {
                f"{self.project_tests_dir()}/test_{task.lower()}_{self.word()}.py":
                    LONG_LIVED_TEXT.format(cls=self.word().capitalize(),
                                           word=self.word())})
        store.record_fixation(self.conn, task)
        with self.spy() as spy:
            out = capture_out(fsm.cmd_advance, task)
        return task, out, [c for c in spy.calls if "--collect-only" in c["argv"]]

    def run_in_dev(self) -> tuple:
        """`advance` из `in_dev` с долгоживущим файлом, несущим зерно, —
        прогон планки и повторы долгоживущего файла."""
        task = self.new_task("in_dev", self.code())
        rel = self.lock(task, long_lived=True)
        with self.spy() as spy:
            out = capture_out(fsm.cmd_advance, task)
        plank = [c for c in spy.calls if any("acceptance_tests" in a
                                             for a in c["argv"])]
        repeats = [c for c in spy.calls if c not in plank
                   and any(a.endswith(Path(rel).name) for a in c["argv"])]
        return task, out, plank, repeats

    # ------------------------------------------------------------ наблюдение

    @contextlib.contextmanager
    def spy(self):
        spy = PytestSpy(len(Path(self.workdir).parts))
        with mock.patch.object(acceptance, "subprocess", spy), \
                mock.patch.object(two_sided, "subprocess", spy):
            yield spy

    def state(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    def journal(self, task_id: str) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in store.task_steps(self.conn, task_id))

    def context(self, task_id: str, out: str, calls: list) -> str:
        return self.note(f"профиль {self.kind}\n--- вывод:\n{out}\n--- журнал:\n"
                         f"{self.journal(task_id)}\n--- вызовы pytest:\n"
                         + "\n".join(f"{c['argv']} @ {c['cwd']}" for c in calls))

    # ------------------------------------------------------------ проверки

    def assert_own(self, call: dict, where: str) -> None:
        """Вызов идёт по профилю `pytest-own`: команда профиля как есть,
        `cwd` — `workdir` в дереве прогона, чистое окружение с `env`."""
        argv = call["argv"]
        self.assertEqual(argv[:3], ["python3", "-m", "pytest"],
                         f"{where}: голова argv не команда профиля: {argv}")
        self.assertFalse(has_pair(argv, "-p", "timeout"),
                         f"{where}: флаги пульта в argv: {argv}")
        self.assertTrue(Path(call["cwd"]).as_posix().endswith("/" + self.workdir),
                        f"{where}: cwd {call['cwd']} — не workdir профиля")
        self.assertIn(self.marker, call["above"],
                      f"{where}: cwd {call['cwd']} — не workdir в дереве проекта")
        env = call["env"]
        self.assertEqual(env.get(self.env_name), self.env_value,
                         f"{where}: нет переменной test_profile.env")
        self.assertNotIn(self.leak_name, env,
                         f"{where}: окружение пульта в прогоне")

    def assert_pult(self, call: dict, where: str, profile_head: bool,
                    cwd: Path | None = None) -> None:
        """Вызов идёт как на main: интерпретатор пульта, `-p timeout`,
        окружение пульта; голова — команда профиля (`profile_head`) либо
        команда пульта; `cwd` — `cwd` либо корень дерева проекта."""
        argv = call["argv"]
        python = stack.pytest_python_executable()
        self.assertEqual(argv[:3], [python, "-m", "pytest"],
                         f"{where}: голова argv не команда пульта: {argv}")
        if self.kind == EXT_PULT:
            if profile_head:
                self.assertEqual(argv[3], self.pult_flag,
                                 f"{where}: не команда профиля: {argv}")
            else:
                self.assertNotEqual(argv[3], self.pult_flag,
                                    f"{where}: команда профиля вместо команды "
                                    f"пульта: {argv}")
        self.assertTrue(has_pair(argv, "-p", "timeout"),
                        f"{where}: нет таймаута пульта: {argv}")
        if cwd is not None:
            self.assertEqual(call["real_cwd"], os.path.realpath(cwd),
                             f"{where}: cwd")
        else:
            self.assertIn(self.marker, call["listing"],
                          f"{where}: cwd {call['cwd']} — не корень дерева")
        env = call["env"]
        self.assertEqual(env.get(self.leak_name), self.leak_value,
                         f"{where}: окружение не пульта")
        self.assertNotIn(self.env_name, env, f"{where}: env профиля")

    def calls_of(self, label: str, run: tuple) -> list:
        """Вызовы pytest сценария `run`; место обязано дойти до прогона."""
        task, out, calls = run[:3]
        self.assertTrue(calls, f"{label}: pytest не запускался\n"
                               + self.context(task, out, calls))
        return calls

    def check_own(self, label: str, run: tuple, cwd: Path | None = None) -> None:
        """Каждый вызов места — по профилю `pytest-own`; `cwd` — точный
        рабочий каталог, если назван."""
        calls = self.calls_of(label, run)
        where = self.context(*run[:3]) + f"\n--- место: {label}"
        for call in calls:
            self.assert_own(call, where)
            if cwd is not None:
                self.assertEqual(call["real_cwd"], os.path.realpath(cwd), where)

    def places(self) -> list:
        """(место, сценарий, голова команды на main у внешнего `pult-pytest`
        — команда профиля, `cwd` на main — точный путь либо корень дерева)
        каждого места AC-1 — AC-9 и AC-12."""
        def in_dev(index):
            def run():
                task, out, plank, repeats = self.run_in_dev()
                return task, out, (plank, repeats)[index]
            return run
        return [
            ("автогейт приёмки", self.run_autogate, False, None),
            ("approve на acceptance", lambda: self.run_approve(False),
             False, None),
            ("гейт мержа без свежего прогона",
             lambda: self.run_merge_gate(False), True, None),
            ("гейт мержа со свежим прогоном",
             lambda: self.run_merge_gate(True), True, None),
            ("suite-run", self.run_suite_run, True, None),
            ("plank-run", self.run_plank_run, False, None),
            ("amend-tests с долгоживущими файлами",
             lambda: self.run_amend(True), False, None),
            ("amend-tests без долгоживущих файлов",
             lambda: self.run_amend(False), False, config.ROOT),
            ("pull с долгоживущими файлами", lambda: self.run_pull(True),
             False, None),
            ("pull без долгоживущих файлов", lambda: self.run_pull(False),
             False, None),
            ("двусторонний прогон наблюдения",
             lambda: self.run_two_sided(True), False, None),
            ("двусторонний прогон гейта", lambda: self.run_two_sided(False),
             False, None),
            ("сухой сбор tests_writing без долгоживущих файлов",
             lambda: self.run_tests_writing(False), True, None),
            ("сухой сбор tests_writing с долгоживущим файлом",
             lambda: self.run_tests_writing(True), True, None),
            ("прогон планки in_dev -> verifying", in_dev(0), True, None),
            ("повторы долгоживущих файлов с зерном", in_dev(1), True, None),
        ]


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


class AutogateTest(ProfileCallersSandbox):

    def test_ac1_autogate_full_suite_by_own_profile(self):
        """Автогейт приёмки гоняет полный набор учебного проекта по профилю `pytest-own`.

        Сценарий: задача внешнего проекта с `runner: pytest-own` (случайные
        `workdir` и переменная `env`) в `review` с одобренным REVIEW.md,
        политика гейта acceptance — `auto`, итога CI нет. `advance` уводит
        задачу в `acceptance`, автогейт запускает полный набор: argv —
        команда профиля как есть (`python3 -m pytest` без интерпретатора и
        таймаута пульта), `cwd` — `workdir` в дереве ветки, окружение
        несёт переменную `env` и не несёт переменной пульта.

        Ловит мутацию: автогейт зовёт `acceptance.full_suite` мимо
        `acceptance.acceptance_suite` или `acceptance_suite` не передаёт
        профиль проекта задачи — полный набор идёт интерпретатором пульта с
        `-p timeout` в корне дерева с окружением пульта.
        """
        self.check_own("автогейт приёмки", self.run_autogate())


class ApproveAcceptanceTest(ProfileCallersSandbox):

    def test_ac2_approve_acceptance_full_suite_by_own_profile(self):
        """`approve` на acceptance гоняет полный набор учебного проекта по профилю `pytest-own`.

        Сценарий: задача внешнего проекта с `runner: pytest-own` в
        `acceptance`, итога CI нет; `approve` без флага и с флагом свежего
        прогона. В обоих случаях полный набор: argv — команда профиля как
        есть, `cwd` — `workdir` в дереве ветки, окружение — `env` профиля
        без переменных пульта.

        Ловит мутацию: `approve` зовёт полный набор без профиля проекта
        задачи (в одной из ветвей `fresh`) — прогон идёт командой и в
        окружении пульта в корне дерева.
        """
        for fresh in (False, True):
            with self.subTest(fresh=fresh, seed=self.seed):
                self.check_own(f"approve на acceptance, fresh={fresh}",
                               self.run_approve(fresh))


class MergeGateTest(ProfileCallersSandbox):

    def test_ac3_merge_gate_full_suite_by_own_profile_both_points(self):
        """Гейт мержа после применённого приложения гоняет полный набор по профилю `pytest-own` — со свежим прогоном и без.

        Сценарий: задача внешнего проекта с `runner: pytest-own` на
        `merge_gate`, PLAN несёт приложение — новый файл под `no_paths`
        проекта. `approve` без флага и с флагом свежего прогона: полный
        набор в scratch-дереве мержа идёт командой профиля как есть, в
        `workdir` этого дерева, с `env` профиля и без переменных пульта.

        Ловит мутацию: гейт мержа передаёт `list(profile.command)` вместо
        профиля или профиль передан только в одной из ветвей
        `fresh_suite` — прогон идёт интерпретатором пульта с `-p timeout`
        в корне scratch-дерева с окружением пульта.
        """
        for fresh in (False, True):
            with self.subTest(fresh=fresh, seed=self.seed):
                self.check_own(f"гейт мержа, fresh={fresh}",
                               self.run_merge_gate(fresh))


class SuiteRunTest(ProfileCallersSandbox):

    def test_ac4_suite_run_by_own_profile_and_result_key(self):
        """`suite-run` гоняет полный набор ветки и базы по профилю `pytest-own`; итог базы сохранён под ключом этого профиля.

        Сценарий: задача внешнего проекта с `runner: pytest-own` в `in_dev`;
        `suite-run` (фон — в этом же процессе). Оба прогона — ветки и базы —
        идут командой профиля как есть, в `workdir` своего дерева, с `env`
        профиля. Итог базы лежит в каталоге сохранённых итогов под ключом
        `acceptance.suite_result_key(<дерево базы>, <профиль>, base=True)`.

        Ловит мутацию: `suite-run` по-прежнему берёт из профиля только
        список команды — прогон идёт интерпретатором пульта в корне дерева;
        прогон по профилю, а ключ итога базы считается по списку команды —
        файла итога под ключом профиля нет.
        """
        run = self.run_suite_run()
        self.check_own("suite-run", run)
        self.assertGreaterEqual(len(run[2]), 2, self.context(*run))
        branch = store.get_task(self.conn, run[0])["branch"]
        base = self.git("-C", str(self.ext_clone), "merge-base", branch,
                        f"origin/{config.MAIN_BRANCH}").strip()
        tree = acceptance.suite_tree_hash(self.ext_clone, ref=base, base=True,
                                          worktree=False)
        profile = project_profile.decide(self.ext).profile
        key = acceptance.suite_result_key(tree, profile, base=True)
        saved = sorted(p.name for p in acceptance.suite_results_dir().glob("*"))
        self.assertIn(f"base-{key}.json", saved,
                      self.context(*run) + f"\n--- итоги: {saved}")


class PlankRunTest(ProfileCallersSandbox):

    def test_ac5_plank_run_by_own_profile(self):
        """`plank-run` гоняет черновик планки по профилю `pytest-own`.

        Сценарий: задача внешнего проекта с `runner: pytest-own` в
        `tests_writing`, черновик планки в каталоге документов. `plank-run`
        запускает pytest командой профиля как есть, в `workdir` рабочей
        копии кода, с `env` профиля и без переменных пульта.

        Ловит мутацию: `plank-run` зовёт `acceptance.run_plank` без
        профиля — прогон идёт интерпретатором пульта в корне рабочей копии с
        окружением пульта.
        """
        self.check_own("plank-run", self.run_plank_run())


class AmendTestsTest(ProfileCallersSandbox):

    def test_ac6_amend_tests_by_own_profile_both_points(self):
        """`amend-tests` собирает и гоняет планку по профилю `pytest-own` — с долгоживущими файлами и без; без них `cwd` — `workdir` рабочей копии.

        Сценарий: задача внешнего проекта с `runner: pytest-own` в `in_dev`
        с локом планки; Оператор правит файл планки в рабочей копии.
        `amend-tests` при перечне долгоживущих файлов (сбор и прогон с ними)
        и без перечня (сбор и прогон одной планки): каждый вызов — командой
        профиля как есть, с `env` профиля, без переменных пульта; без
        перечня `cwd` — ровно `<рабочая копия>/<workdir>`.

        Ловит мутацию: профиль передан только в одной из точек; в точке без
        долгоживущих файлов профиль передан, но `cwd` не передан — `workdir`
        отсчитан от корня пульта, а не от рабочей копии задачи.
        """
        for long_lived in (True, False):
            with self.subTest(long_lived=long_lived, seed=self.seed):
                run = self.run_amend(long_lived)
                cwd = None if long_lived else self.wt(run[0]) / self.workdir
                self.check_own(f"amend-tests, долгоживущие={long_lived}", run,
                               cwd=cwd)


class PullTest(ProfileCallersSandbox):

    def test_ac7_pull_plank_by_own_profile_both_points(self):
        """Прогон планки после подтяжки main идёт по профилю `pytest-own` — с долгоживущими файлами и без.

        Сценарий: задача внешнего проекта с `runner: pytest-own` в
        `verifying` с локом планки (с перечнем долгоживущих файлов и без);
        main проекта ушёл вперёд; `pull-main` подтягивает его и гоняет
        планку: командой профиля как есть, в `workdir` рабочей копии, с
        `env` профиля, без переменных пульта.

        Ловит мутацию: `pull` зовёт `acceptance.run` без профиля в одной из
        ветвей (с долгоживущими файлами или без) — прогон идёт
        интерпретатором пульта в корне рабочей копии с окружением пульта.
        """
        for long_lived in (True, False):
            with self.subTest(long_lived=long_lived, seed=self.seed):
                self.check_own(f"pull, долгоживущие={long_lived}",
                               self.run_pull(long_lived))


class TwoSidedTest(ProfileCallersSandbox):

    def test_ac8_two_sided_by_own_profile_both_callers(self):
        """Двусторонний прогон наблюдения и гейта неослабления идёт по профилю `pytest-own`.

        Сценарий: задача внешнего проекта с `runner: pytest-own` в `in_dev`
        меняет ожидание существующего теста проекта. Наблюдение включено,
        смена не объявлена — двусторонний прогон наблюдения; наблюдение
        выключено, смена объявлена записью «объявлена смена поведения
        тестов» — двусторонний прогон гейта. Каждая сторона — командой
        профиля как есть, в `workdir` дерева стороны, с `env` профиля, без
        переменных пульта.

        Ловит мутацию: профиль передан в `two_sided.run` только у одного из
        вызывающих (наблюдение или гейт) — сторона другого идёт
        интерпретатором пульта в корне дерева стороны с окружением пульта.
        """
        for observation in (True, False):
            with self.subTest(observation=observation, seed=self.seed):
                self.check_own(f"двусторонний прогон, наблюдение={observation}",
                               self.run_two_sided(observation))


class TestsWritingCollectTest(ProfileCallersSandbox):

    def test_ac9_tests_writing_dry_collect_by_own_profile(self):
        """Сухой сбор на выходе `tests_writing` идёт по профилю `pytest-own` — без долгоживущих файлов и с ними.

        Сценарий: задача внешнего проекта с `runner: pytest-own` в
        `tests_writing`; кодовая ветка пуста либо несёт долгоживущий файл
        задачи. `advance` собирает планку `--collect-only` командой профиля
        как есть, в `workdir` рабочей копии, с `env` профиля, без
        переменных пульта.

        Ловит мутацию: `fsm_advance` по-прежнему передаёт
        `list(profile.command)` (или узел сбора сворачивает профиль в
        список) — сбор идёт интерпретатором пульта в корне рабочей копии с
        окружением пульта.
        """
        for long_lived in (False, True):
            with self.subTest(long_lived=long_lived, seed=self.seed):
                self.check_own(f"сухой сбор, долгоживущие={long_lived}",
                               self.run_tests_writing(long_lived))


class InDevPlankTest(ProfileCallersSandbox):

    def test_ac12_in_dev_plank_and_seed_repeats_by_own_profile(self):
        """Прогон планки на `in_dev -> verifying` и повторы долгоживущего файла с зерном идут по профилю `pytest-own`.

        Сценарий: задача внешнего проекта с `runner: pytest-own` в `in_dev`
        с локом планки и долгоживущим файлом задачи, импортирующим
        `random`. `advance`: прогон планки с долгоживущим файлом и
        `config.LONG_LIVED_SEED_REPEATS` повторов файла — каждый командой
        профиля как есть, в `workdir` рабочей копии, с `env` профиля, без
        переменных пульта.

        Ловит мутацию: рубеж по-прежнему берёт `list(decision.profile.command)`
        — прогон и повторы идут интерпретатором пульта в корне рабочей
        копии; профиль передан в прогон планки, но не в повторы с зерном.
        """
        task, out, plank, repeats = self.run_in_dev()
        self.check_own("прогон планки in_dev", (task, out, plank))
        self.assertEqual(len(repeats), config.LONG_LIVED_SEED_REPEATS,
                         self.context(task, out, plank + repeats))
        self.check_own("повторы с зерном", (task, out, repeats))


class PultUnchangedTest(ProfileCallersSandbox):

    # Места `places()` делятся на доли `[i::PLACE_SHARES]` по сортировке
    # метки — по методу на долю: один тест не проходит все места подряд
    # (SPEC 01M5H1A4GS19TPR4RJ8XRVVYZQ).
    PLACE_SHARES = 8

    def share(self, kind: str, index: int) -> list:
        """Доля `index` мест AC-1 — AC-9 и AC-12 для профиля `kind`:
        `targets.yaml` песочницы под `kind`, перечень `places()` по
        сортировке метки, срез `[index::PLACE_SHARES]`."""
        self.write_targets(kind)
        ordered = sorted(self.places(), key=lambda place: place[0])
        return ordered[index::self.PLACE_SHARES]

    def test_ac10_external_pult_pytest_unchanged(self):
        """У внешнего проекта с `pult-pytest` каждое место запускается как на main.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи внешнего
        проекта с `runner: pult-pytest`, чья команда профиля — `python3 -m
        pytest` с добавочным флагом. argv — с интерпретатором пульта и `-p
        timeout`; голова — команда профиля с флагом там, где на main её
        брал вызывающий (гейт мержа, `suite-run`, сухой сбор, прогон
        планки и повторы `in_dev`), и команда пульта без флага в остальных
        местах; `cwd` — корень дерева прогона (у `amend-tests` без
        долгоживущих файлов — корень пульта); окружение — окружение пульта.

        Ловит мутацию: профиль передаётся безусловно — у `pult-pytest`
        `pull`, `amend-tests`, `plank-run`, двусторонний прогон, автогейт и
        `approve` пойдут командой профиля с её флагом; `cwd` рабочей копии
        в `amend-tests` выставлен и без `pytest-own` — `cwd` перестаёт быть
        корнем пульта; окружение `pytest-own` применено к `pult-pytest` —
        переменной пульта в прогоне нет.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        0 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = EXT_PULT
        share = self.share(kind, 0)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_external_pult_pytest_unchanged_share1(self):
        """У внешнего проекта с `pult-pytest` каждое место запускается как на main.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи внешнего
        проекта с `runner: pult-pytest`, чья команда профиля — `python3 -m
        pytest` с добавочным флагом. argv — с интерпретатором пульта и `-p
        timeout`; голова — команда профиля с флагом там, где на main её
        брал вызывающий (гейт мержа, `suite-run`, сухой сбор, прогон
        планки и повторы `in_dev`), и команда пульта без флага в остальных
        местах; `cwd` — корень дерева прогона (у `amend-tests` без
        долгоживущих файлов — корень пульта); окружение — окружение пульта.

        Ловит мутацию: профиль передаётся безусловно — у `pult-pytest`
        `pull`, `amend-tests`, `plank-run`, двусторонний прогон, автогейт и
        `approve` пойдут командой профиля с её флагом; `cwd` рабочей копии
        в `amend-tests` выставлен и без `pytest-own` — `cwd` перестаёт быть
        корнем пульта; окружение `pytest-own` применено к `pult-pytest` —
        переменной пульта в прогоне нет.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        1 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = EXT_PULT
        share = self.share(kind, 1)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_external_pult_pytest_unchanged_share2(self):
        """У внешнего проекта с `pult-pytest` каждое место запускается как на main.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи внешнего
        проекта с `runner: pult-pytest`, чья команда профиля — `python3 -m
        pytest` с добавочным флагом. argv — с интерпретатором пульта и `-p
        timeout`; голова — команда профиля с флагом там, где на main её
        брал вызывающий (гейт мержа, `suite-run`, сухой сбор, прогон
        планки и повторы `in_dev`), и команда пульта без флага в остальных
        местах; `cwd` — корень дерева прогона (у `amend-tests` без
        долгоживущих файлов — корень пульта); окружение — окружение пульта.

        Ловит мутацию: профиль передаётся безусловно — у `pult-pytest`
        `pull`, `amend-tests`, `plank-run`, двусторонний прогон, автогейт и
        `approve` пойдут командой профиля с её флагом; `cwd` рабочей копии
        в `amend-tests` выставлен и без `pytest-own` — `cwd` перестаёт быть
        корнем пульта; окружение `pytest-own` применено к `pult-pytest` —
        переменной пульта в прогоне нет.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        2 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = EXT_PULT
        share = self.share(kind, 2)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_external_pult_pytest_unchanged_share3(self):
        """У внешнего проекта с `pult-pytest` каждое место запускается как на main.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи внешнего
        проекта с `runner: pult-pytest`, чья команда профиля — `python3 -m
        pytest` с добавочным флагом. argv — с интерпретатором пульта и `-p
        timeout`; голова — команда профиля с флагом там, где на main её
        брал вызывающий (гейт мержа, `suite-run`, сухой сбор, прогон
        планки и повторы `in_dev`), и команда пульта без флага в остальных
        местах; `cwd` — корень дерева прогона (у `amend-tests` без
        долгоживущих файлов — корень пульта); окружение — окружение пульта.

        Ловит мутацию: профиль передаётся безусловно — у `pult-pytest`
        `pull`, `amend-tests`, `plank-run`, двусторонний прогон, автогейт и
        `approve` пойдут командой профиля с её флагом; `cwd` рабочей копии
        в `amend-tests` выставлен и без `pytest-own` — `cwd` перестаёт быть
        корнем пульта; окружение `pytest-own` применено к `pult-pytest` —
        переменной пульта в прогоне нет.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        3 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = EXT_PULT
        share = self.share(kind, 3)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_external_pult_pytest_unchanged_share4(self):
        """У внешнего проекта с `pult-pytest` каждое место запускается как на main.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи внешнего
        проекта с `runner: pult-pytest`, чья команда профиля — `python3 -m
        pytest` с добавочным флагом. argv — с интерпретатором пульта и `-p
        timeout`; голова — команда профиля с флагом там, где на main её
        брал вызывающий (гейт мержа, `suite-run`, сухой сбор, прогон
        планки и повторы `in_dev`), и команда пульта без флага в остальных
        местах; `cwd` — корень дерева прогона (у `amend-tests` без
        долгоживущих файлов — корень пульта); окружение — окружение пульта.

        Ловит мутацию: профиль передаётся безусловно — у `pult-pytest`
        `pull`, `amend-tests`, `plank-run`, двусторонний прогон, автогейт и
        `approve` пойдут командой профиля с её флагом; `cwd` рабочей копии
        в `amend-tests` выставлен и без `pytest-own` — `cwd` перестаёт быть
        корнем пульта; окружение `pytest-own` применено к `pult-pytest` —
        переменной пульта в прогоне нет.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        4 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = EXT_PULT
        share = self.share(kind, 4)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_external_pult_pytest_unchanged_share5(self):
        """У внешнего проекта с `pult-pytest` каждое место запускается как на main.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи внешнего
        проекта с `runner: pult-pytest`, чья команда профиля — `python3 -m
        pytest` с добавочным флагом. argv — с интерпретатором пульта и `-p
        timeout`; голова — команда профиля с флагом там, где на main её
        брал вызывающий (гейт мержа, `suite-run`, сухой сбор, прогон
        планки и повторы `in_dev`), и команда пульта без флага в остальных
        местах; `cwd` — корень дерева прогона (у `amend-tests` без
        долгоживущих файлов — корень пульта); окружение — окружение пульта.

        Ловит мутацию: профиль передаётся безусловно — у `pult-pytest`
        `pull`, `amend-tests`, `plank-run`, двусторонний прогон, автогейт и
        `approve` пойдут командой профиля с её флагом; `cwd` рабочей копии
        в `amend-tests` выставлен и без `pytest-own` — `cwd` перестаёт быть
        корнем пульта; окружение `pytest-own` применено к `pult-pytest` —
        переменной пульта в прогоне нет.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        5 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = EXT_PULT
        share = self.share(kind, 5)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_external_pult_pytest_unchanged_share6(self):
        """У внешнего проекта с `pult-pytest` каждое место запускается как на main.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи внешнего
        проекта с `runner: pult-pytest`, чья команда профиля — `python3 -m
        pytest` с добавочным флагом. argv — с интерпретатором пульта и `-p
        timeout`; голова — команда профиля с флагом там, где на main её
        брал вызывающий (гейт мержа, `suite-run`, сухой сбор, прогон
        планки и повторы `in_dev`), и команда пульта без флага в остальных
        местах; `cwd` — корень дерева прогона (у `amend-tests` без
        долгоживущих файлов — корень пульта); окружение — окружение пульта.

        Ловит мутацию: профиль передаётся безусловно — у `pult-pytest`
        `pull`, `amend-tests`, `plank-run`, двусторонний прогон, автогейт и
        `approve` пойдут командой профиля с её флагом; `cwd` рабочей копии
        в `amend-tests` выставлен и без `pytest-own` — `cwd` перестаёт быть
        корнем пульта; окружение `pytest-own` применено к `pult-pytest` —
        переменной пульта в прогоне нет.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        6 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = EXT_PULT
        share = self.share(kind, 6)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_external_pult_pytest_unchanged_share7(self):
        """У внешнего проекта с `pult-pytest` каждое место запускается как на main.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи внешнего
        проекта с `runner: pult-pytest`, чья команда профиля — `python3 -m
        pytest` с добавочным флагом. argv — с интерпретатором пульта и `-p
        timeout`; голова — команда профиля с флагом там, где на main её
        брал вызывающий (гейт мержа, `suite-run`, сухой сбор, прогон
        планки и повторы `in_dev`), и команда пульта без флага в остальных
        местах; `cwd` — корень дерева прогона (у `amend-tests` без
        долгоживущих файлов — корень пульта); окружение — окружение пульта.

        Ловит мутацию: профиль передаётся безусловно — у `pult-pytest`
        `pull`, `amend-tests`, `plank-run`, двусторонний прогон, автогейт и
        `approve` пойдут командой профиля с её флагом; `cwd` рабочей копии
        в `amend-tests` выставлен и без `pytest-own` — `cwd` перестаёт быть
        корнем пульта; окружение `pytest-own` применено к `pult-pytest` —
        переменной пульта в прогоне нет.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        7 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = EXT_PULT
        share = self.share(kind, 7)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_artel_unchanged(self):
        """У задачи артели каждое место запускается как на main — командой пульта.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи артели (её
        профиль — `python3 -m pytest`), в то время как внешний проект
        объявлен с `runner: pytest-own`. argv — интерпретатор пульта, `-m
        pytest`, `-p timeout`; `cwd` — корень дерева прогона (у
        `amend-tests` без долгоживущих файлов — корень пульта); окружение —
        окружение пульта, без `env` профиля внешнего проекта.

        Ловит мутацию: профиль для места берётся не по проекту задачи (у
        первого проекта с `pytest-own` в `targets.yaml`) или `cwd`
        рабочей копии в `amend-tests` выставлен безусловно — у артели
        меняются argv, `cwd` или окружение.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        0 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = ARTEL_PULT
        share = self.share(kind, 0)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_artel_unchanged_share1(self):
        """У задачи артели каждое место запускается как на main — командой пульта.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи артели (её
        профиль — `python3 -m pytest`), в то время как внешний проект
        объявлен с `runner: pytest-own`. argv — интерпретатор пульта, `-m
        pytest`, `-p timeout`; `cwd` — корень дерева прогона (у
        `amend-tests` без долгоживущих файлов — корень пульта); окружение —
        окружение пульта, без `env` профиля внешнего проекта.

        Ловит мутацию: профиль для места берётся не по проекту задачи (у
        первого проекта с `pytest-own` в `targets.yaml`) или `cwd`
        рабочей копии в `amend-tests` выставлен безусловно — у артели
        меняются argv, `cwd` или окружение.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        1 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = ARTEL_PULT
        share = self.share(kind, 1)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_artel_unchanged_share2(self):
        """У задачи артели каждое место запускается как на main — командой пульта.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи артели (её
        профиль — `python3 -m pytest`), в то время как внешний проект
        объявлен с `runner: pytest-own`. argv — интерпретатор пульта, `-m
        pytest`, `-p timeout`; `cwd` — корень дерева прогона (у
        `amend-tests` без долгоживущих файлов — корень пульта); окружение —
        окружение пульта, без `env` профиля внешнего проекта.

        Ловит мутацию: профиль для места берётся не по проекту задачи (у
        первого проекта с `pytest-own` в `targets.yaml`) или `cwd`
        рабочей копии в `amend-tests` выставлен безусловно — у артели
        меняются argv, `cwd` или окружение.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        2 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = ARTEL_PULT
        share = self.share(kind, 2)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_artel_unchanged_share3(self):
        """У задачи артели каждое место запускается как на main — командой пульта.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи артели (её
        профиль — `python3 -m pytest`), в то время как внешний проект
        объявлен с `runner: pytest-own`. argv — интерпретатор пульта, `-m
        pytest`, `-p timeout`; `cwd` — корень дерева прогона (у
        `amend-tests` без долгоживущих файлов — корень пульта); окружение —
        окружение пульта, без `env` профиля внешнего проекта.

        Ловит мутацию: профиль для места берётся не по проекту задачи (у
        первого проекта с `pytest-own` в `targets.yaml`) или `cwd`
        рабочей копии в `amend-tests` выставлен безусловно — у артели
        меняются argv, `cwd` или окружение.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        3 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = ARTEL_PULT
        share = self.share(kind, 3)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_artel_unchanged_share4(self):
        """У задачи артели каждое место запускается как на main — командой пульта.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи артели (её
        профиль — `python3 -m pytest`), в то время как внешний проект
        объявлен с `runner: pytest-own`. argv — интерпретатор пульта, `-m
        pytest`, `-p timeout`; `cwd` — корень дерева прогона (у
        `amend-tests` без долгоживущих файлов — корень пульта); окружение —
        окружение пульта, без `env` профиля внешнего проекта.

        Ловит мутацию: профиль для места берётся не по проекту задачи (у
        первого проекта с `pytest-own` в `targets.yaml`) или `cwd`
        рабочей копии в `amend-tests` выставлен безусловно — у артели
        меняются argv, `cwd` или окружение.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        4 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = ARTEL_PULT
        share = self.share(kind, 4)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_artel_unchanged_share5(self):
        """У задачи артели каждое место запускается как на main — командой пульта.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи артели (её
        профиль — `python3 -m pytest`), в то время как внешний проект
        объявлен с `runner: pytest-own`. argv — интерпретатор пульта, `-m
        pytest`, `-p timeout`; `cwd` — корень дерева прогона (у
        `amend-tests` без долгоживущих файлов — корень пульта); окружение —
        окружение пульта, без `env` профиля внешнего проекта.

        Ловит мутацию: профиль для места берётся не по проекту задачи (у
        первого проекта с `pytest-own` в `targets.yaml`) или `cwd`
        рабочей копии в `amend-tests` выставлен безусловно — у артели
        меняются argv, `cwd` или окружение.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        5 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = ARTEL_PULT
        share = self.share(kind, 5)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_artel_unchanged_share6(self):
        """У задачи артели каждое место запускается как на main — командой пульта.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи артели (её
        профиль — `python3 -m pytest`), в то время как внешний проект
        объявлен с `runner: pytest-own`. argv — интерпретатор пульта, `-m
        pytest`, `-p timeout`; `cwd` — корень дерева прогона (у
        `amend-tests` без долгоживущих файлов — корень пульта); окружение —
        окружение пульта, без `env` профиля внешнего проекта.

        Ловит мутацию: профиль для места берётся не по проекту задачи (у
        первого проекта с `pytest-own` в `targets.yaml`) или `cwd`
        рабочей копии в `amend-tests` выставлен безусловно — у артели
        меняются argv, `cwd` или окружение.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        6 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = ARTEL_PULT
        share = self.share(kind, 6)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)

    def test_ac10_artel_unchanged_share7(self):
        """У задачи артели каждое место запускается как на main — командой пульта.

        Сценарий: каждое место AC-1 — AC-9 и AC-12 для задачи артели (её
        профиль — `python3 -m pytest`), в то время как внешний проект
        объявлен с `runner: pytest-own`. argv — интерпретатор пульта, `-m
        pytest`, `-p timeout`; `cwd` — корень дерева прогона (у
        `amend-tests` без долгоживущих файлов — корень пульта); окружение —
        окружение пульта, без `env` профиля внешнего проекта.

        Ловит мутацию: профиль для места берётся не по проекту задачи (у
        первого проекта с `pytest-own` в `targets.yaml`) или `cwd`
        рабочей копии в `amend-tests` выставлен безусловно — у артели
        меняются argv, `cwd` или окружение.

        Сценарий доли: места `places()` по сортировке метки делятся на
        `PLACE_SHARES` долей `[i::PLACE_SHARES]`; метод проходит долю
        7 (её непустоту утверждает `assertTrue`), прочие доли — у
        метода без суффикса и методов с суффиксом `_share<i>`.
        """
        kind = ARTEL_PULT
        share = self.share(kind, 7)
        self.assertTrue(share)
        for label, run, profile_head, cwd in share:
            with self.subTest(kind=kind, place=label, seed=self.seed):
                result = run()
                calls = self.calls_of(f"{kind}: {label}", result)
                where = self.context(*result) + f"\n--- место: {label}"
                for call in calls:
                    self.assert_pult(call, where, profile_head, cwd)


class NoTaskRunTest(ProfileCallersSandbox):

    def test_ac11_run_without_task_unchanged(self):
        """Прогон полного набора без задачи идёт командой и в окружении пульта, как на main.

        Сценарий: в окружении пульта — случайная переменная; внешний проект
        объявлен с `runner: pytest-own`. `acceptance.run_full_suite` по
        дереву артели без команды (так зовёт его `doc-commit`): argv —
        интерпретатор пульта, `-m pytest`, цель `tests`, `-p timeout`,
        параллель `-p xdist`; `cwd` — переданный корень; окружение —
        окружение пульта со случайной переменной, без `env` профиля.

        Ловит мутацию: прогон без задачи берёт профиль проекта (например,
        первого `pytest-own` из `targets.yaml`) — argv, `cwd` или окружение
        расходятся с командой пульта.
        """
        with self.spy() as spy:
            acceptance.run_full_suite(self.root)
        self.assertTrue(spy.calls, self.note("прогон не запускался"))
        for call in spy.calls:
            where = self.note(f"{call['argv']} @ {call['cwd']}")
            self.assert_pult(call, where, False, self.root)
            self.assertIn("tests", call["argv"], where)
            self.assertTrue(has_pair(call["argv"], "-p", "xdist"), where)


