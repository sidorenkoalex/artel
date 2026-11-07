"""Сценарий CI `scripts/plan_appendix_ci.py` публикует sha ссылки документов, исход и список sha256 диффов приложений и сверяет подтянутый коммит ссылки с `ls-remote`.

Группа: долгоживущий
Красен до реализации: сценарий не печатает аннотации `plan-appendix-docs` (AC-13) и при ссылке, сдвинутой между чтением и подтяжкой, завершается кодом 0 с «PLAN.md в ссылке документов нет» (AC-14).

Песочница — настоящий git (`RealGitSandbox`, клон артели — сам
репозиторий песочницы) с голым `origin` во временном каталоге: задача
артели с рабочей копией на ветке, отправленной в `origin`; PLAN и SPEC —
в ссылке документов задачи автокоммитом пульта
(`checkpoint.commit_step_artifacts`), ссылка отправлена в `origin`
(образец — `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`).
Сценарий этой рабочей копии кода запускается отдельным процессом (своя
группа процессов, предел времени) из корня «раннера» — клона `origin` на
ветке задачи — с переменными окружения Actions пуша ветки. Настоящие
файлы репозитория не меняются.

Публикация — по ANSWER-4 задачи, п. 1: ровно одна строка
`::notice title=plan-appendix-docs::ref=<sha X или пусто>;
outcome=<applied|no-plan|no-appendices|no-ref>; diffs=<h1,h2,… или пусто>`;
`h` — шестнадцатеричный sha256 байтов UTF-8 текста `PlanAppendix.diff`,
разбор `guard` пульта, в порядке PLAN (ANSWER-4, п. 2: тест считает
список сам по правилу требования 2 SPEC).

Зерно печатается и входит в текст каждого провала.

Валидировано временным стабом сценария (строка аннотации на четырёх
исходах, сверка `FETCH_HEAD` с sha `ls-remote`): оба теста зелёные;
хеш не байтов UTF-8 красит случай `applied`; стаб удалён.
"""
import hashlib
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from orchestrator import catalog, checkpoint, config, idgen, store, workspace
from scripts import guard
from tests.sandbox import artel_target_entry, capture

CODE_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = CODE_ROOT / "scripts" / "plan_appendix_ci.py"
DOCS_REF_PREFIX = "refs/artifacts/"
NOTICE = re.compile(r"^::notice title=plan-appendix-docs::ref=(?P<ref>[^;]*); "
                    r"outcome=(?P<outcome>[^;]*); diffs=(?P<diffs>.*)$")
NOTICE_START = "::notice title=plan-appendix-docs::"

PROTECTED_FILES = [p for p in config.PROTECTED_PATHS
                   if p.endswith(".md") and "*" not in p
                   and not p.startswith(("tests/", ".github"))]
BASE_LINES = [f"строка базы {n:02d} из 80" for n in range(1, 81)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
EDIT_LINES = BASE_LINES[::8]

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: feature.txt
---

# SPEC: фикстура

## Контекст

## Требования

## Критерии приёмки

AC-1. Фикстура.

## Не входит
"""


def run_group(cmd: list, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    """Дочерний процесс в своей группе с пределом времени; по пределу
    снимается вся группа."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        err += "\n(снят по пределу времени)"
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


class Runner:
    """Задача артели с рабочей копией и ссылкой документов в `origin`;
    раннер CI — клон `origin` на ветке задачи."""

    def __init__(self, sandbox):
        self.s = sandbox
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.case = ""
        self.lines = self.rng.sample(EDIT_LINES, len(EDIT_LINES))
        self.tmp = Path(tempfile.mkdtemp(prefix="artel-ci-publication-"))
        sandbox.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        config.TARGETS.write_text("targets:\n" + artel_target_entry(),
                                  encoding="utf-8")
        for rel in PROTECTED_FILES:
            path = sandbox.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
        sandbox.git("add", "-A")
        sandbox.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = sandbox.add_synced_origin()
        capture(catalog.cmd_init)

    def note(self, text: str = "") -> str:
        return f"{text} (зерно {self.seed}; {self.case or 'сценарий'})"

    def git(self, *args: str) -> str:
        return self.s.git(*args)

    def diff_of(self) -> tuple:
        """(путь, старая строка, новая строка, дифф) правки одной свободной
        строки защищённого файла к дереву `main`."""
        self.s.checkout(config.MAIN_BRANCH)
        rel = self.rng.choice(PROTECTED_FILES)
        path = self.s.root / rel
        text = path.read_text(encoding="utf-8")
        old, new = self.lines.pop(), f"правка {self.rng.randrange(10**9)}"
        path.write_text(text.replace(old, new), encoding="utf-8")
        diff = self.git("diff", "--", rel)
        self.git("checkout", "-q", "--", rel)
        return rel, old, new, diff

    @property
    def ref(self) -> str:
        return DOCS_REF_PREFIX + self.task

    def make_task(self, docs: str, appendices: int = 0) -> None:
        """Задача: ветка с кодом в `origin`; `docs` — `plan` (PLAN с
        `appendices` приложениями), `no_plan` (в ссылке только SPEC) или
        `no_ref` (ссылки документов в `origin` нет)."""
        self.task = idgen.new_task_id()
        self.branch = f"task/{self.task.lower()}-x"
        store.insert_task(store.db(), self.task, f"Задача {self.task}",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(self.task, self.branch,
                                     config.DEFAULT_TARGET)
        if error:
            raise RuntimeError(self.note(f"рабочая копия не заведена: {error}"))
        self.wt = Path(wt).resolve()
        (self.wt / "feature.txt").write_text(f"код задачи {self.task}\n",
                                             encoding="utf-8")
        self.git("-C", str(self.wt), "add", "feature.txt")
        self.git("-C", str(self.wt), "commit", "-q", "-m",
                 f"{self.task}: код задачи")
        self.git("-C", str(self.wt), "push", "-q", "origin", self.branch)
        self.edits = [self.diff_of() for _ in range(appendices)]
        sections = "".join(
            f"\n## Приложение {i}: правка {i}\n\n```diff\n{e[3]}```\n"
            for i, e in enumerate(self.edits, 1))
        self.plan = (f"---\ntask: {self.task}\ntype: plan\n"
                     f"author_role: developer\nstatus: ready\n"
                     f"schema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
                     f"Фикстура {self.rng.randrange(10**6)}.\n{sections}")
        tdir = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.task
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(SPEC_TEXT.format(task=self.task),
                                      encoding="utf-8")
        if docs == "plan":
            (tdir / "PLAN.md").write_text(self.plan, encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, store.db(), self.task,
                "developer")
        if docs != "no_ref":
            self.push_ref()
        elif self.git("ls-remote", "origin", self.ref).strip():
            # Автокоммит пульта отправляет ссылку сам — «ссылки нет»
            # моделируется её удалением из `origin`.
            self.git("push", "-q", "origin", f":{self.ref}")

    def push_ref(self) -> None:
        self.git("push", "-q", "origin", f"+{self.ref}:{self.ref}")

    def ref_head(self) -> str:
        return self.git("rev-parse", self.ref).strip()

    def passport(self) -> str:
        """Строка паспорта поверх ссылки документов, отправленная в
        `origin`: ссылка сдвинута. Возвращает новый sha."""
        tree = self.tmp / f"docs-{self.rng.randrange(10**9)}"
        self.git("worktree", "add", "-q", "--detach", str(tree), self.ref)
        path = tree / "tasks" / self.task / "PASSPORT.md"
        path.write_text(f"# Паспорт живой задачи\n\n{store.now()}  in_dev  "
                        f"actor=fsm\n", encoding="utf-8")
        self.git("-C", str(tree), "add", "-A")
        self.git("-C", str(tree), "commit", "-q", "-m", "паспорт")
        sha = self.git("-C", str(tree), "rev-parse", "HEAD").strip()
        self.git("worktree", "remove", "--force", str(tree))
        self.git("update-ref", self.ref, sha)
        self.push_ref()
        return sha

    def clone(self) -> Path:
        runner = self.tmp / f"runner-{self.rng.randrange(10**9)}"
        self.git("clone", "-q", "--depth", "1", "--branch", self.branch,
                 f"file://{self.origin}", str(runner))
        return runner

    def env(self, runner: Path) -> dict:
        env = dict(os.environ)
        env.update({"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
                    "GITHUB_REF": f"refs/heads/{self.branch}",
                    "GITHUB_REF_NAME": self.branch,
                    "GITHUB_REF_TYPE": "branch",
                    "GITHUB_WORKSPACE": str(runner),
                    "PYTHONDONTWRITEBYTECODE": "1"})
        return env

    def run_ci(self, runner: Path, cmd: list | None = None):
        cmd = cmd or [sys.executable, str(SCRIPT)]
        return run_group(cmd, runner, self.env(runner))


@pytest.fixture
def runner(real_git):
    """Песочница настоящего git с `origin`; задачу заводит тест."""
    return Runner(real_git)


def output(res) -> str:
    return f"код {res.returncode}\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}"


def notices(res) -> list:
    return [ln.rstrip() for ln in (res.stdout + "\n" + res.stderr).splitlines()
            if ln.startswith(NOTICE_START)]


def digests(plan: str) -> list:
    """sha256 диффов приложений по правилу требования 2 SPEC."""
    appendices, _errors = guard.plan_appendices(
        plan, tuple(config.PROTECTED_PATHS))
    return [hashlib.sha256(a.diff.encode("utf-8")).hexdigest()
            for a in appendices]


@pytest.mark.parametrize("docs,expected", [
    ("plan", "applied"),
    ("no_plan", "no-plan"),
    ("plan_without_appendices", "no-appendices"),
    ("no_ref", "no-ref"),
])
def test_ac13_script_publishes_ref_outcome_and_digests(runner, docs, expected):
    """Сценарий CI на голом `origin` печатает ровно одну аннотацию `plan-appendix-docs` с sha ссылки, исходом и списком sha256 диффов; наложение и код выхода прежние.

    Случаи: PLAN с 1–3 приложениями (от зерна) — `outcome=applied`,
    `ref` — sha ссылки в `origin`, `diffs` — список sha256 по правилу
    требования 2 SPEC в порядке PLAN, правки приложений в дереве раннера;
    ссылка без PLAN.md — `no-plan` с sha; PLAN без приложений —
    `no-appendices` с sha; ссылки нет — `no-ref` с пустым `ref`. У
    исходов, кроме `applied`, `diffs` пуст, дерево раннера не тронуто.
    Код выхода — 0 во всех случаях.

    Ловит мутацию: список диффов не публикуется — `diffs` пуст при
    `applied`; дайджест берётся не от байтов UTF-8 `PlanAppendix.diff`
    (текст с оградой, другая кодировка) или не шестнадцатеричный —
    список не совпадает; публикуется sha `FETCH_HEAD` или ветки вместо
    sha ссылки — `ref` не тот; исход «PLAN нет» и «приложений нет»
    перепутаны — `outcome` не тот.
    """
    r = runner
    r.case = f"AC-13 {docs}"
    r.make_task("no_plan" if docs == "no_plan" else
                "no_ref" if docs == "no_ref" else "plan",
                appendices=r.rng.randint(1, 3) if docs == "plan" else 0)
    tree = r.clone()
    res = r.run_ci(tree)
    out = output(res)
    assert res.returncode == 0, r.note(out)
    lines = notices(res)
    assert len(lines) == 1, r.note(f"аннотаций {len(lines)}\n{out}")
    match = NOTICE.match(lines[0])
    assert match, r.note(f"строка не в форме ANSWER-4: {lines[0]!r}")
    assert match["outcome"] == expected, r.note(out)
    ref = "" if docs == "no_ref" else r.ref_head()
    assert match["ref"] == ref, r.note(out)
    hashes = digests(r.plan) if docs == "plan" else []
    assert match["diffs"] == ",".join(hashes), r.note(
        f"ожидалось {hashes}\n{out}")
    status = r.git("-C", str(tree), "status", "--porcelain")
    if docs == "plan":
        for rel, old, new, _diff in r.edits:
            text = (tree / rel).read_text(encoding="utf-8")
            assert new in text and old not in text, r.note(
                f"приложение к {rel} не наложено\n{out}")
    else:
        assert status == "", r.note(f"дерево раннера тронуто: {status}\n{out}")


def test_ac14_fetch_head_differs_from_ls_remote(runner):
    """Ссылка документов сдвинута между чтением и подтяжкой (`ls-remote` дал X, `origin` уже на Y) — код 1 и причина одной строкой.

    Сдвиг моделируется подменой `remote_docs_refs` в процессе сценария:
    обёртка импортирует сценарий модулем и возвращает старый sha X
    (коммит ссылки до строки паспорта), когда в `origin` ссылка уже на
    Y. Процесс — в своей группе, с пределом времени.

    Ловит мутацию: подтянутый коммит (`FETCH_HEAD`) не сверяется с sha из
    `ls-remote` — PLAN.md ищется в X, которого нет в мелком клоне, и
    сценарий молча завершается кодом 0 «PLAN.md нет»; расхождение
    печатается многострочным отчётом — в stderr больше одной строки.
    """
    r = runner
    r.case = "AC-14"
    r.make_task("plan", appendices=r.rng.randint(1, 2))
    old = r.ref_head()
    new = r.passport()
    assert old != new, r.note()
    tree = r.clone()
    code = ("import sys\n"
            f"sys.path.insert(0, {str(CODE_ROOT)!r})\n"
            "from scripts import plan_appendix_ci as m\n"
            f"m.remote_docs_refs = lambda: {{{r.task!r}: {old!r}}}\n"
            "raise SystemExit(m.main([]))\n")
    res = r.run_ci(tree, [sys.executable, "-c", code])
    out = output(res)
    assert res.returncode == 1, r.note(out)
    reason = [ln for ln in res.stderr.splitlines() if ln.strip()]
    assert len(reason) == 1, r.note(f"причина не одной строкой\n{out}")
