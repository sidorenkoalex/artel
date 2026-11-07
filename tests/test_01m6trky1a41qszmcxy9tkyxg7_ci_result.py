"""Приёмка принимает итог CI без условия свежести при `merge_gate: operator` и для дерева с приложениями PLAN, доказанными публикацией CI.

Группа: долгоживущий
Красен до реализации: приёмка проверяет свежесть головы при любом `merge_gate` и не принимает итог CI при дереве с приложениями PLAN — тесты принятия (AC-1, AC-2 случаи (1), AC-4, AC-12 режим `ci`, AC-15) видят локальный прогон или «неизвестно»; тесты отказа (AC-3, AC-5…AC-11, AC-16…AC-18) зелены и до кода: прежний путь и сегодня отказывает, они держат отказ после появления принятия.

Две связки.

Режим `full_suite: local` (проект артели): настоящий git
(`RealGitSandbox`, клон артели — сам репозиторий песочницы) с голым
`origin`; задача с рабочей копией (`workspace.ensure`) на ветке,
отправленной в `origin`; PLAN — в ссылке документов задачи
автокоммитом пульта (`checkpoint.commit_step_artifacts`), ссылка
отправлена в `origin`. Узел — `appendix_tree.suite_tree` на голове ветки
и `acceptance.acceptance_suite` на его корне, как у `approve` и
автогейта. Подменены только граница CI `ci.gh` (проверки коммита,
прогоны, аннотации проверки) и шпион локального полного прогона
`acceptance.full_suite`; деревья, свежесть, ссылка документов и её
`origin` — настоящие.

Публикация CI — по ANSWER-4 задачи, п. 1: у проверки `FULL_SUITE_JOB`
одна аннотация с заголовком `plan-appendix-docs` и текстом
`ref=<sha X>; outcome=<applied|no-plan|no-appendices|no-ref>;
diffs=<h1,h2,…>`, `h` — шестнадцатеричный sha256 байтов UTF-8 текста
`PlanAppendix.diff` в порядке PLAN; читается ответом
`check-runs/<id>/annotations`. Поддельные варианты — правка полей этой
строки. Рядом с ней всегда лежит посторонняя аннотация другого заголовка.

Режим `full_suite: ci` (внешний проект): лёгкая песочница переходов
(`light_transition`) с подменённым хостингом `forge.IMPLEMENTATIONS` и
подменёнными источниками условий принятия — образец
`tests/test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py`.

Зерно печатается и входит в текст каждого провала.

Валидировано временным стабом реализации (чтение аннотации у
`FULL_SUITE_JOB` в `ci.py`, условия 3а–3з и снятие свежести при
`operator` в `acceptance.py`, публикация в сценарии CI): все тесты файла
зелёные; поочерёдное снятие каждого условия стаба (предок, равенство
ссылок, PLAN.md в X, источник, чистота, исход, сценарий, список как
множество, чтение любой проверки, непрочитанный `merge_gate` как
`operator`) и иная форма хеша в сценарии красят названные тесты; стаб
удалён.
"""
import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (acceptance, appendix_tree, artifact_source,
                          catalog, checkpoint, ci, config, forge, idgen,
                          store, workspace)
from scripts import guard
from tests.sandbox import artel_target_entry, capture, make_project_repo

CODE_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_REL = "scripts/plan_appendix_ci.py"
DOCS_REF_PREFIX = "refs/artifacts/"
TITLE = "plan-appendix-docs"
ACCEPTED_PREFIX = "полный набор: принят итог CI"
LOCAL_ACTION = "полный набор локально"
BASIS_APPENDICES = "для дерева с приложениями PLAN"
BASIS_FRESHNESS = "без проверки свежести: её держит merge_gate"
OTHER_BASES = ("develop", "trunk", "stable", "release")

# Защищённые markdown-файлы — от `config.PROTECTED_PATHS`, не литералом:
# перечень меняет Оператор (тот же отбор, что у образца
# `tests/test_01m4jd3srn66sd6bm63xaghb11_suite_tree_ci_in_base.py`).
PROTECTED_FILES = [p for p in config.PROTECTED_PATHS
                   if p.endswith(".md") and "*" not in p
                   and not p.startswith(("tests/", ".github"))]
BASE_LINES = [f"строка базы {n:02d} из 120" for n in range(1, 121)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
# Строки правок — через восемь: контекст хунка соседней правки их не задевает.
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

LOCAL_GREEN = acceptance.FullSuiteRun(
    True, acceptance.FULL_SUITE_GREEN, "12 passed", None,
    "локальный полный набор зелёный")


def plan_text(task: str, diffs: list, note: str) -> str:
    """PLAN.md задачи с приложениями `diffs` в порядке списка."""
    sections = "".join(
        f"\n## Приложение {i}: правка {i}\n\n```diff\n{diff}```\n"
        for i, diff in enumerate(diffs, 1))
    return (f"---\ntask: {task}\ntype: plan\nauthor_role: developer\n"
            f"status: ready\nschema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
            f"{note}\n{sections}")


def digests(plan: str) -> list:
    """Список sha256 диффов приложений PLAN по правилу требования 2 SPEC:
    шестнадцатеричный дайджест байтов UTF-8 `PlanAppendix.diff`, разбор
    `guard` пульта, в порядке PLAN."""
    appendices, _errors = guard.plan_appendices(
        plan, tuple(config.PROTECTED_PATHS))
    return [hashlib.sha256(a.diff.encode("utf-8")).hexdigest()
            for a in appendices]


def annotation(message: str, title: str = TITLE,
               level: str = "notice") -> dict:
    """Аннотация проверки в форме ответа GitHub `check-runs/<id>/annotations`."""
    return {"path": ".github", "blob_href": "", "start_line": 1,
            "end_line": 1, "start_column": None, "end_column": None,
            "annotation_level": level, "title": title, "message": message,
            "raw_details": None}


def publication(ref: str, outcome: str, diffs: list) -> dict:
    return annotation(f"ref={ref}; outcome={outcome}; diffs={','.join(diffs)}")


def noise() -> dict:
    return annotation("Node.js 16 actions are deprecated.",
                      title="Deprecation", level="warning")


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


# ------------------------------------------------------------ стенд local


class Stand:
    """Задача артели в `acceptance` на настоящем git; по умолчанию все
    условия принятия итога CI выполнены."""

    def __init__(self, sandbox):
        self.s = sandbox
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.case = ""
        self.lines = self.rng.sample(EDIT_LINES, len(EDIT_LINES))
        self.tmp = Path(tempfile.mkdtemp(prefix="artel-ci-result-"))
        sandbox.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.write_targets("operator")
        root = sandbox.root
        for rel in PROTECTED_FILES:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
        script = root / SCRIPT_REL
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_bytes((CODE_ROOT / SCRIPT_REL).read_bytes())
        sandbox.git("add", "-A")
        sandbox.git("commit", "-q", "-m", "защищённые файлы и сценарий CI")
        self.origin = sandbox.add_synced_origin()
        capture(catalog.cmd_init)
        self.local = mock.Mock(return_value=LOCAL_GREEN)
        self.check_ids = {}
        self.annotations = {}
        self.annotations_fail = False
        self.ci_sha = ""
        self.run_id = self.rng.randrange(10000, 1000000)
        self.task = ""
        for target, name, kwargs in (
                (ci, "gh", {"side_effect": self.fake_gh}),
                (acceptance, "full_suite", {"side_effect": self.local}),
        ):
            patcher = mock.patch.object(target, name, **kwargs)
            patcher.start()
            sandbox.addCleanup(patcher.stop)

    # ---------------------------------------------------------- обвязка

    def note(self, text: str = "") -> str:
        return f"{text} (зерно {self.seed}; {self.case or 'сценарий'})"

    def git(self, *args: str) -> str:
        return self.s.git(*args)

    def write_targets(self, gate: str, base: str = config.MAIN_BRANCH) -> None:
        entry = artel_target_entry(base=base).replace(
            "merge_gate: operator", f"merge_gate: {gate}")
        config.TARGETS.write_text("targets:\n" + entry, encoding="utf-8")

    def free_line(self) -> str:
        return self.lines.pop()

    def diff_of(self, rel: str) -> str:
        """Unified-дифф правки одной свободной строки `rel` к дереву
        `main` — настоящим `git diff`, правка затем откатывается."""
        self.s.checkout(config.MAIN_BRANCH)
        path = self.s.root / rel
        text = path.read_text(encoding="utf-8")
        line = self.free_line()
        path.write_text(text.replace(line, f"правка {self.rng.randrange(10**9)}"),
                        encoding="utf-8")
        diff = self.git("diff", "--", rel)
        self.git("checkout", "-q", "--", rel)
        return diff

    def diffs(self, count: int) -> list:
        return [self.diff_of(self.rng.choice(PROTECTED_FILES))
                for _ in range(count)]

    @property
    def ref(self) -> str:
        return DOCS_REF_PREFIX + self.task

    def make_task(self, appendices: int) -> None:
        """Задача артели: рабочая копия на ветке с кодом задачи (ветка в
        `origin`), PLAN с `appendices` приложениями в ссылке документов (и
        в `origin`). CI прогнан на голове ветки."""
        self.task = idgen.new_task_id()
        self.branch = f"task/{self.task.lower()}-x"
        store.insert_task(store.db(), self.task, f"Задача {self.task}",
                          "acceptance", self.branch, config.DEFAULT_TARGET,
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
        self.ci_sha = self.head()
        self.plan = plan_text(self.task, self.diffs(appendices),
                              f"Фикстура {self.rng.randrange(10**6)}.")
        docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=self.task),
                                      encoding="utf-8")
        (docs / "PLAN.md").write_text(self.plan, encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, store.db(), self.task,
                "developer")
        self.push_ref()
        self.x = self.ref_head()
        self.set_checks()
        self.publish(self.good())

    def head(self) -> str:
        return self.git("-C", str(self.wt), "rev-parse", "HEAD").strip()

    def ref_head(self) -> str:
        return self.git("rev-parse", self.ref).strip()

    def push_ref(self) -> None:
        self.git("push", "-q", "origin", f"+{self.ref}:{self.ref}")

    def docs_commit(self, files: dict, push: bool = True) -> str:
        """Коммит поверх локальной ссылки документов с файлами `files`
        ({имя файла каталога задачи: текст}); `push` — отправить в
        `origin`. Возвращает sha нового коммита."""
        tree = self.tmp / f"docs-{self.rng.randrange(10**9)}"
        self.git("worktree", "add", "-q", "--detach", str(tree), self.ref)
        for name, text in files.items():
            path = tree / "tasks" / self.task / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(tree), "add", "-A")
        self.git("-C", str(tree), "commit", "-q", "--allow-empty", "-m",
                 f"{self.task}: документы")
        sha = self.git("-C", str(tree), "rev-parse", "HEAD").strip()
        self.git("worktree", "remove", "--force", str(tree))
        self.git("update-ref", self.ref, sha)
        if push:
            self.push_ref()
        return sha

    def passport(self, push: bool = True) -> str:
        """Строка паспорта поверх ссылки документов — сдвиг ссылки сменой
        состояния."""
        return self.docs_commit({"PASSPORT.md": (
            "# Паспорт живой задачи\n\n"
            f"{store.now()}  acceptance  actor=fsm\n")}, push=push)

    def orphan_like_ref(self) -> str:
        """Коммит с деревом головы ссылки, но без родителя — не предок её
        головы; PLAN.md в нём тот же."""
        tree = self.git("rev-parse", f"{self.ref}^{{tree}}").strip()
        return self.git("commit-tree", tree, "-m", "переписанная ссылка").strip()

    def move_base(self) -> None:
        """База ушла одним коммитом: голова ветки не содержит `origin/main`."""
        self.s.checkout(config.MAIN_BRANCH)
        name = f"later-{self.rng.randrange(10**9)}.txt"
        (self.s.root / name).write_text("новый main\n", encoding="utf-8")
        self.git("add", name)
        self.git("commit", "-q", "-m", "новый main")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def change_script_on_branch(self) -> None:
        path = self.wt / SCRIPT_REL
        path.write_text(path.read_text(encoding="utf-8")
                        + "# правка сценария в ветке\n", encoding="utf-8")
        self.git("-C", str(self.wt), "add", SCRIPT_REL)
        self.git("-C", str(self.wt), "commit", "-q", "-m",
                 f"{self.task}: правка сценария CI")
        self.git("-C", str(self.wt), "push", "-q", "origin", self.branch)
        self.ci_sha = self.head()

    # ------------------------------------------------------------- CI

    def set_checks(self) -> None:
        names = sorted(ci.FULL_SUITE_CHECKS) + ["Сторож защищённых путей"]
        ids = self.rng.sample(range(10**9, 10**10), len(names))
        self.check_ids = dict(zip(names, ids))
        self.annotations = {}

    def other_check(self) -> str:
        return self.rng.choice(sorted(n for n in self.check_ids
                                      if n != ci.FULL_SUITE_JOB))

    def good(self) -> dict:
        return publication(self.x, "applied", digests(self.plan))

    def publish(self, *items: dict, check: str = ci.FULL_SUITE_JOB) -> None:
        """Аннотации проверки `check`: посторонняя и `items`."""
        self.annotations[self.check_ids[check]] = [noise(), *items]

    def fake_gh(self, *args, **kwargs) -> subprocess.CompletedProcess:
        text = " ".join(str(a) for a in args)
        found = re.search(r"check-runs/(\d+)/annotations", text)
        if found:
            if self.annotations_fail:
                return subprocess.CompletedProcess(args, 1, "", "HTTP 502")
            body = self.annotations.get(int(found.group(1)), [])
            return subprocess.CompletedProcess(args, 0, json.dumps(body), "")
        found = re.search(r"commits/([0-9a-f]{40})/check-runs", text)
        if found:
            checks = [] if found.group(1) != self.ci_sha else [
                {"id": check_id, "name": name, "head_sha": self.ci_sha,
                 "status": "completed", "conclusion": "success",
                 "details_url": (f"http://localhost/actions/runs/"
                                 f"{self.run_id}/job/{check_id}"),
                 "check_suite": {"id": self.run_id}}
                for name, check_id in self.check_ids.items()]
            body = {"total_count": len(checks), "check_runs": checks}
            return subprocess.CompletedProcess(args, 0, json.dumps(body), "")
        if "actions/runs" in text:
            body = {"total_count": 1, "workflow_runs": [{
                "id": self.run_id, "databaseId": self.run_id,
                "check_suite_id": self.run_id, "head_sha": self.ci_sha,
                "head_branch": self.branch, "status": "completed",
                "conclusion": "success", "event": "push"}]}
            return subprocess.CompletedProcess(args, 0, json.dumps(body), "")
        return subprocess.CompletedProcess(args, 1, "", "запрос не ожидался")

    # -------------------------------------------------------- приёмка

    def accept(self, fresh: bool = False):
        """Итог приёмки (узел `approve` и автогейта) и новые записи журнала:
        (итог или None, отказ дерева прогона, новые записи)."""
        conn = store.db()
        before = len(store.task_steps(conn, self.task))
        self.local.reset_mock()
        run = None
        with appendix_tree.suite_tree(conn, self.task, self.wt,
                                      branch=self.branch) as tree:
            refusal = tree.refusal
            if tree.root is not None:
                run = acceptance.acceptance_suite(
                    conn, tree.root, self.task, self.branch,
                    workspace.task_repo(self.task), actor="operator",
                    fresh=fresh)
        added = list(store.task_steps(store.db(), self.task))[before:]
        return run, refusal, added

    def journal(self, added) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}" for r in added)


@pytest.fixture
def stand(real_git):
    """Стенд режима `local`: песочница настоящего git с `origin` и
    подменённой границей CI; задачу заводит тест (`make_task`)."""
    return Stand(real_git)


def outcome(st: Stand, fresh: bool = False):
    run, refusal, added = st.accept(fresh=fresh)
    context = st.note(f"отказ дерева: {refusal!r}; итог: "
                      f"{run and (run.outcome, run.detail)!r}\n"
                      + st.journal(added))
    return run, refusal, added, context


def accepted_records(added) -> list:
    return [r["detail"] or "" for r in added
            if (r["detail"] or "").startswith(ACCEPTED_PREFIX)]


def assert_accepted(st: Stand, basis: str, fresh: bool = False) -> None:
    """Итог CI принят без локального прогона; запись о принятии начинается
    прежним текстом и называет основание `basis` после него."""
    run, refusal, added, context = outcome(st, fresh)
    assert refusal == "", context
    assert run is not None and run.green, context
    assert acceptance.is_ci_result(run), context
    assert not st.local.called, f"локальный прогон вызван; {context}"
    records = [d for d in accepted_records(added)
               if basis in d[len(ACCEPTED_PREFIX):]]
    assert records, f"нет записи «{ACCEPTED_PREFIX} …{basis}»; {context}"


def assert_refused(st: Stand, reason: str = "", fresh: bool = False) -> str:
    """Итог CI не принят: локальный прогон вызван один раз, записи о
    принятии нет, причина локального прогона — одной строкой (с `reason`,
    если задан). Возвращает причину."""
    run, refusal, added, context = outcome(st, fresh)
    assert refusal == "", context
    assert st.local.call_count == 1, f"локальный прогон не вызван; {context}"
    assert not accepted_records(added), context
    assert run is not None and not acceptance.is_ci_result(run), context
    reasons = [r["detail"] or "" for r in added if r["action"] == LOCAL_ACTION]
    assert len(reasons) == 1 and reasons[0].strip(), context
    assert "\n" not in reasons[0], context
    if reason:
        assert reason in reasons[0], f"причина не «{reason}»; {context}"
    return reasons[0]


# ------------------------------------------------------------ стенд ci


class FakeForge:
    """Поддельный хостинг: задания и отчёт ровно для sha головы стенда."""

    CI_BY_PIPELINE = False

    def __init__(self, st):
        self.st = st
        self.calls = []

    def pipeline_status(self, target, sha):
        self.calls.append(("pipeline_status", sha))
        if sha != self.st.sha:
            return forge.PipelineStatus(forge.NONE, f"конвейера {sha[:8]} нет")
        return forge.PipelineStatus(forge.GREEN, "", list(self.st.jobs))

    def job_result(self, target, sha, job_name):
        self.calls.append(("job_result", sha))
        if sha != self.st.sha:
            return forge.JobResult(None, f"задания «{job_name}» нет")
        return forge.JobResult("success")

    def job_test_report(self, target, sha, job_name):
        self.calls.append(("job_test_report", sha))
        if sha != self.st.sha:
            return forge.TestReport(None, f"задания «{job_name}» нет")
        return forge.TestReport(dict(self.st.outcomes))


PROJECT = "uchcifresh"


def write_ci_entry(st, gate: str) -> None:
    fields = {
        "command": "[python3, -m, pytest]",
        "report": "junit-xml",
        "long_lived_dir": "tests",
        "long_lived_name": "test_<id>_<name>.py",
        "weakening_scope": "[tests/**]",
        "mutation_claim_scope": "[tests/test_*.py]",
        "full_suite": "ci",
        "ci_job": st.job,
    }
    text = (f"  {PROJECT}:\n"
            "    forge: github\n"
            f"    url: https://localhost/artel-tests/{PROJECT}\n"
            f"    base: {st.base}\n"
            f"    token_slot: {PROJECT}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            f"    merge_gate: {gate}\n"
            "    components:\n"
            "      app:\n"
            + "".join(f"        {k}: {v}\n" for k, v in fields.items()))
    config.TARGETS.write_text(st.artel_text.rstrip("\n") + "\n" + text,
                              encoding="utf-8")


@pytest.fixture
def ci_stand(light_transition):
    """Задача внешнего проекта с `full_suite: ci` в `acceptance`: хостинг
    подменён, деревья гейта и головы равны, голова содержит множество
    веток `contains` (по умолчанию базу записи и `main`); `merge_gate`
    записи — `operator`, тест переписывает запись сам."""
    st = light_transition
    st.seed = random.randrange(1 << 30)
    print(f"зерно: {st.seed}")
    st.rng = random.Random(st.seed)
    st.base = st.rng.choice(OTHER_BASES)
    st.sha = f"{st.rng.getrandbits(160):040x}"
    st.job = f"full-suite-{st.rng.randrange(1, 99)}"
    st.job_id = st.rng.randrange(1000, 100000)
    st.jobs = [forge.Job(st.job, "success", "test", st.job_id)]
    st.n = st.rng.randrange(3, 40)
    st.outcomes = {f"pkg.test_mod.Case::test_{i}": "success"
                   for i in range(st.n)}
    st.tree = f"{st.rng.getrandbits(160):040x}"
    st.contains = {st.base, config.MAIN_BRANCH}
    st.artel_text = config.TARGETS.read_text(encoding="utf-8")
    st.forge = FakeForge(st)
    st.local = mock.Mock(return_value=LOCAL_GREEN)
    real_is_ancestor = acceptance.gitcmd.is_ancestor

    def is_ancestor(ancestor, descendant, repo=None):
        if "origin/" in ancestor:
            name = ancestor.split("origin/", 1)[1]
            return descendant == st.sha and name in st.contains
        return real_is_ancestor(ancestor, descendant, repo=repo)

    st.wt_path.mkdir(parents=True, exist_ok=True)
    for target, name, kwargs in (
            (workspace, "on_task_branch", {"return_value": True}),
            (workspace, "path", {"return_value": st.wt_path}),
            (ci, "head_sha", {"return_value": (st.sha, "")}),
            (acceptance.gitcmd, "is_ancestor", {"side_effect": is_ancestor}),
            (acceptance, "full_suite", {"side_effect": st.local}),
            (acceptance, "suite_tree_hash", {"return_value": st.tree}),
    ):
        patcher = mock.patch.object(target, name, **kwargs)
        patcher.start()
        st.addCleanup(patcher.stop)
    patcher = mock.patch.dict(forge.IMPLEMENTATIONS, {"github": st.forge})
    patcher.start()
    st.addCleanup(patcher.stop)
    write_ci_entry(st, "operator")
    make_project_repo(PROJECT, origin=False)
    store.update_task(store.db(), st.TASK, target=PROJECT)
    st.set_state("acceptance")
    return st


def ci_suite(st, fresh: bool = False):
    conn = store.db()
    before = len(store.task_steps(conn, st.TASK))
    st.local.reset_mock()
    run = acceptance.acceptance_suite(
        conn, st.wt_path, st.TASK, st.branch, workspace.task_repo(st.TASK),
        actor="operator", fresh=fresh)
    added = list(store.task_steps(store.db(), st.TASK))[before:]
    context = (f"{run.outcome} {run.detail!r}\n"
               + "\n".join(f"{r['action']} | {r['detail'] or ''}"
                           for r in added) + f"\nзерно: {st.seed}")
    return run, added, context


def ci_records(added) -> list:
    return [r["detail"] or "" for r in added
            if (r["detail"] or "").startswith(acceptance.CI_JOB_RECORD)]


# ------------------------------------------------------------- AC-1


def test_ac1_local_operator_gate_accepts_ci_without_freshness(stand):
    """Режим `local`, `merge_gate: operator`, `main` в `origin` ушёл коммитом после отхода ветки, дерево приёмки равно дереву головы, CI зелёный — итог CI принят без локального прогона.

    Задача артели без приложений PLAN; запись о принятии начинается
    «полный набор: принят итог CI» и дальше несёт «без проверки свежести:
    её держит merge_gate».

    Ловит мутацию: условие свежести осталось для `merge_gate: operator` —
    локальный прогон с причиной «ветка не свежа»; основание дописано
    перед прежним началом записи — записи, начинающейся прежним текстом
    и несущей основание после него, нет.
    """
    st = stand
    st.case = "AC-1 local"
    st.make_task(0)
    st.move_base()
    assert_accepted(st, BASIS_FRESHNESS)


def test_ac1_ci_operator_gate_accepts_ci_without_freshness(ci_stand):
    """Режим `ci`, `merge_gate: operator`, голова не содержит `origin/<база записи>`, CI зелёный — итог задания CI принят без локального прогона, запись начинается `CI_JOB_RECORD` и дальше несёт основание.

    Ловит мутацию: условие свежести осталось для `merge_gate: operator` —
    итог «неизвестно» с причиной «ветка не свежа»; основание дописано
    перед `CI_JOB_RECORD` — запись не начинается прежним текстом,
    `is_ci_result` итог не узнаёт.
    """
    st = ci_stand
    st.contains = {config.MAIN_BRANCH}
    run, added, context = ci_suite(st)
    assert run.green, context
    assert acceptance.is_ci_result(run), context
    st.local.assert_not_called()
    records = [d for d in ci_records(added)
               if BASIS_FRESHNESS in d[len(acceptance.CI_JOB_RECORD):]]
    assert records, context


# ------------------------------------------------------------- AC-2


@pytest.mark.parametrize("case,gate,accepted", [
    ("1", "operator", True),
    ("4", "target-human", False),
])
def test_ac2_local_base_other_than_main_by_merge_gate(stand, case, gate,
                                                      accepted):
    """Режим `local`, запись артели с базой не `main`, голова не содержит ни `origin/<base>`, ни `origin/main`: (1) `operator` — итог CI принят без проверки свежести; (4) `target-human` — локальный прогон с причиной «ветка не свежа относительно origin/main».

    Ловит мутацию: свежесть снята и для `target-human` — случай (4)
    принимает итог CI; в режиме `local` сверка переведена на
    `origin/<base>` записи — причина случая (4) называет не
    `origin/main`; свежесть осталась для `operator` — случай (1) уходит
    в локальный прогон.
    """
    st = stand
    st.case = f"AC-2 ({case})"
    st.make_task(0)
    st.write_targets(gate, base=st.rng.choice(OTHER_BASES))
    st.move_base()
    if accepted:
        assert_accepted(st, BASIS_FRESHNESS)
    else:
        assert_refused(st, f"ветка не свежа относительно "
                           f"origin/{config.MAIN_BRANCH}")


@pytest.mark.parametrize("case,gate,contains,accepted", [
    ("1", "operator", ["main"], True),
    ("2", "target-human", ["main"], False),
    ("3", "target-human", ["base"], True),
])
def test_ac2_ci_base_other_than_main_by_merge_gate(ci_stand, case, gate,
                                                   contains, accepted):
    """Режим `ci`, запись с базой не `main`: (1) `operator`, голова не содержит `origin/<base>` — итог принят; (2) `target-human`, то же — «неизвестно» с причиной «ветка не свежа относительно origin/<base>»; (3) `target-human`, голова содержит `origin/<base>`, но не `origin/main` — итог принят.

    Ловит мутацию: свежесть снята и для `target-human` — случай (2)
    зелёный; свежесть сверяется с `main` — случай (3) «неизвестно»;
    свежесть осталась для `operator` — случай (1) «неизвестно».
    """
    st = ci_stand
    write_ci_entry(st, gate)
    st.contains = {st.base if name == "base" else config.MAIN_BRANCH
                   for name in contains}
    run, added, context = ci_suite(st)
    st.local.assert_not_called()
    if accepted:
        assert run.green, f"({case}) {context}"
        assert ci_records(added), f"({case}) {context}"
        return
    assert acceptance.is_unknown(run), f"({case}) {context}"
    assert f"ветка не свежа относительно origin/{st.base}" in \
        run.detail.splitlines()[0], f"({case}) {context}"


# ------------------------------------------------------------- AC-3


@pytest.mark.parametrize("breakage", ["no_merge_gate", "unparsable"])
def test_ac3_unread_merge_gate_keeps_freshness(stand, breakage):
    """Значение `merge_gate` записи не прочитано — свежесть проверяется: при свежей голове итог CI принят, при ушедшей базе не принят, причина одной строкой.

    Запись артели теряет поле `merge_gate` либо файл деклараций не
    разбирается. Сначала голова свежа — итог CI принимается прежним
    условием (стенд годен); затем база уходит коммитом — локальный
    прогон, причина одной строкой.

    Ловит мутацию: непрочитанное значение `merge_gate` трактуется как
    `operator` (сравнение «не target-human») — при ушедшей базе итог CI
    принят без локального прогона.
    """
    st = stand
    st.case = f"AC-3 {breakage}"
    st.make_task(0)
    if breakage == "no_merge_gate":
        config.TARGETS.write_text(
            config.TARGETS.read_text(encoding="utf-8").replace(
                "    merge_gate: operator\n", ""), encoding="utf-8")
    else:
        config.TARGETS.write_text("targets: [\n  - не разбирается\n",
                                  encoding="utf-8")
    run, refusal, added, context = outcome(st)
    assert run is not None and run.green and not st.local.called, \
        f"при свежей голове итог CI не принят; {context}"
    st.move_base()
    assert_refused(st)


# ------------------------------------------------------------- AC-4


@pytest.mark.parametrize("y_kind", ["same", "passport"])
def test_ac4_appendix_tree_accepts_published_ci(stand, y_kind):
    """Непустые приложения PLAN, чистая рабочая копия, CI опубликовал «приложения наложены из X», голова ссылки в `origin` — X либо X плюс строка паспорта — итог CI принят, запись называет основание «для дерева с приложениями PLAN».

    Число приложений — от зерна (1–3). Локальная ссылка документов равна
    `origin`, PLAN.md в X и Y побайтно равны, список sha256 публикации —
    по правилу требования 2 SPEC; у `FULL_SUITE_JOB` рядом лежит
    посторонняя аннотация другого заголовка.

    Ловит мутацию: итог CI с приложениями не принимается (прежнее условие
    равенства деревьев) — локальный прогон; ссылка сравнивается с X на
    равенство вместо «X — предок Y» — случай со строкой паспорта
    отказывает; основание не записано или записано перед прежним
    началом — записи «полный набор: принят итог CI … для дерева с
    приложениями PLAN» нет.
    """
    st = stand
    st.case = f"AC-4 {y_kind}"
    st.make_task(st.rng.randint(1, 3))
    if y_kind == "passport":
        st.passport()
    assert_accepted(st, BASIS_APPENDICES)


# ------------------------------------------------------------- AC-5


@pytest.mark.parametrize("published", ["head_list", "x_list"])
def test_ac5_plan_changed_after_ci_is_refused(stand, published):
    """PLAN.md в голове ссылки Y отличается от PLAN.md в X новым приложением — итог CI не принят, локальный прогон, причина одной строкой.

    X — коммит ссылки, опубликованный CI; поверх него в ссылку (и в
    `origin`) пришёл PLAN с ещё одним приложением. Публикация несёт
    список диффов либо разбора головы (`head_list` — расходится только
    PLAN.md, список совпадает с разбором приёмки), либо разбора PLAN в X
    (`x_list`).

    Ловит мутацию: PLAN.md в X не сверяется с PLAN.md головы ссылки — при
    `head_list` итог CI принят без локального прогона.
    """
    st = stand
    st.case = f"AC-5 {published}"
    st.make_task(st.rng.randint(1, 2))
    old = st.plan
    new = plan_text(st.task, [*guard_diffs(old), st.diff_of(
        st.rng.choice(PROTECTED_FILES))], "Фикстура с новым приложением.")
    st.docs_commit({"PLAN.md": new})
    st.plan = new
    st.publish(publication(st.x, "applied",
                           digests(new if published == "head_list" else old)))
    assert_refused(st)


def guard_diffs(plan: str) -> list:
    """Тексты диффов приложений PLAN по порядку — разбор `guard`."""
    appendices, _errors = guard.plan_appendices(
        plan, tuple(config.PROTECTED_PATHS))
    return [a.diff for a in appendices]


# ------------------------------------------------------------- AC-6


def test_ac6_published_ref_not_ancestor_is_refused(stand):
    """X не предок головы ссылки Y (ссылка переписана), PLAN.md и список равны — итог CI не принят, причина одной строкой.

    X — коммит с тем же деревом, что голова ссылки, но без родителя.

    Ловит мутацию: X не проверяется как предок головы ссылки в `origin` —
    итог CI принят без локального прогона.
    """
    st = stand
    st.case = "AC-6"
    st.make_task(st.rng.randint(1, 3))
    st.passport()
    st.publish(publication(st.orphan_like_ref(), "applied", digests(st.plan)))
    assert_refused(st)


# ------------------------------------------------------------- AC-7


def test_ac7_local_ref_ahead_of_origin_is_refused(stand):
    """Локальная ссылка документов опережает её голову в `origin` на коммит — итог CI не принят, причина одной строкой; `origin` после приёмки по-прежнему отстаёт.

    Ловит мутацию: локальная ссылка не сверяется с `origin` — итог CI
    принят; сверка идёт через досылку ссылки (`origin_sync_refusal`) —
    `origin` после приёмки равен локальной ссылке.
    """
    st = stand
    st.case = "AC-7"
    st.make_task(st.rng.randint(1, 3))
    remote_before = st.ref_head()
    local = st.passport(push=False)
    assert_refused(st)
    remote = st.git("ls-remote", "origin", st.ref).split("\t")[0].strip()
    assert remote == remote_before != local, st.note(
        f"origin {remote}, было {remote_before}, локально {local}")


# ------------------------------------------------------------- AC-8


@pytest.mark.parametrize("published", ["no-plan", "no-appendices", "no-ref"])
def test_ac8_outcome_other_than_applied_is_refused(stand, published):
    """Все прочие условия AC-4 выполнены, PLAN.md в X равен PLAN.md в Y, а CI опубликовал иной исход — итог CI не принят, причина одной строкой.

    Обязательный вариант — «PLAN нет» (`no-plan`) с sha X и списком
    диффов, равным разбору приёмки; дополнительно — «приложений нет» и
    «ссылки нет» (без sha).

    Ловит мутацию: исход публикации не проверяется (читаются только sha и
    список) — при `no-plan` итог CI принят без локального прогона.
    """
    st = stand
    st.case = f"AC-8 {published}"
    st.make_task(st.rng.randint(1, 3))
    ref = "" if published == "no-ref" else st.x
    st.publish(publication(ref, published, digests(st.plan)))
    assert_refused(st)


# ------------------------------------------------------------- AC-9


@pytest.mark.parametrize("absence", ["no_annotation", "annotations_fail",
                                     "two_publications"])
def test_ac9_no_publication_falls_back_to_local(stand, absence):
    """Непустые приложения PLAN, у `FULL_SUITE_JOB` нет однозначной публикации sha и исхода — локальный прогон, причина одной строкой.

    Варианты: аннотации проверки — только посторонняя (прогон до мержа
    задачи); запрос аннотаций не ответил (сбой чтения); две публикации с
    заголовком `plan-appendix-docs` (ANSWER-4, п. 1: больше одной —
    прежний путь).

    Ловит мутацию: сбой чтения аннотаций или их отсутствие читается как
    годная публикация, либо из двух публикаций берётся первая — итог CI
    принят без локального прогона.
    """
    st = stand
    st.case = f"AC-9 {absence}"
    st.make_task(st.rng.randint(1, 3))
    if absence == "no_annotation":
        st.publish()
    elif absence == "annotations_fail":
        st.annotations_fail = True
    else:
        st.publish(st.good(), st.good())
    assert_refused(st)


# ------------------------------------------------------------- AC-10


def test_ac10_foreign_plan_source_is_refused(stand):
    """Источник PLAN приёмки (`artifact_source.resolve`) — чужая ветка с тем же содержимым, а не ссылка документов задачи — локальный прогон, причина одной строкой.

    Чужая ветка указывает на тот же коммит, что ссылка документов:
    приложения те же и ложатся, публикация годна; отличается только
    источник.

    Ловит мутацию: источник PLAN не сверяется со ссылкой документов
    задачи — итог CI принят без локального прогона.
    """
    st = stand
    st.case = "AC-10"
    st.make_task(st.rng.randint(1, 3))
    foreign = f"docs-copy-{st.rng.randrange(10**6)}"
    st.git("branch", foreign, st.ref_head())
    with mock.patch.object(artifact_source, "resolve",
                           return_value=(foreign, True)):
        assert_refused(st)


# ------------------------------------------------------------- AC-11


@pytest.mark.parametrize("appendices,dirt,reason", [
    (0, "edit", "дерево гейта отличается от дерева головного коммита"),
    (0, "untracked", "дерево гейта или головного коммита не прочитано"),
    (1, "edit", "дерево гейта отличается от дерева головного коммита"),
    (1, "untracked", "дерево гейта отличается от дерева головного коммита"),
])
def test_ac11_dirty_worktree_reason_by_kind(stand, appendices, dirt, reason):
    """Грязная рабочая копия — итог CI не принят, причина по виду грязи.

    Без приложений PLAN: незакоммиченная правка — «дерево гейта
    отличается от дерева головного коммита»; неотслеживаемый
    неигнорируемый файл вне каталога задач — «дерево гейта или
    головного коммита не прочитано». С приложением PLAN (публикация CI
    годна): правка или неотслеживаемый файл — «дерево гейта отличается
    от дерева головного коммита» от проверки чистоты.

    Ловит мутацию: проверка чистоты рабочей копии при приложениях снята
    (дерево приёмки строится от головы ветки и грязи не видит) — с
    приложением итог CI принят; неотслеживаемый файл не считается грязью —
    тот же исход.
    """
    st = stand
    st.case = f"AC-11 приложений {appendices}, {dirt}"
    st.make_task(appendices)
    if dirt == "edit":
        (st.wt / "feature.txt").write_text("незакоммиченная правка\n",
                                           encoding="utf-8")
    else:
        (st.wt / f"scratch-{st.rng.randrange(10**6)}.txt").write_text(
            "черновик\n", encoding="utf-8")
    assert_refused(st, reason)


# ------------------------------------------------------------- AC-12


def test_ac12_local_fresh_suite_runs_locally(stand):
    """`approve --fresh-suite` (`fresh=True` узла приёмки) в режиме `local` при `merge_gate: operator` и ушедшей базе — локальный прогон, итог CI не принят.

    Ловит мутацию: новое принятие без свежести обходит запрос свежего
    прогона — итог CI принят без локального прогона.
    """
    st = stand
    st.case = "AC-12 local"
    st.make_task(0)
    st.move_base()
    assert_refused(st, fresh=True)


def test_ac12_ci_fresh_suite_rereads_ci(ci_stand):
    """`approve --fresh-suite` (`fresh=True` узла приёмки) в режиме `ci` при `merge_gate: operator` и ушедшей базе — итог задания CI перечитан у хостинга и принят, без локального прогона.

    Ловит мутацию: `fresh` в режиме `ci` переведён на локальный прогон —
    шпион вызван, хостинг не спрошен.
    """
    st = ci_stand
    st.contains = {config.MAIN_BRANCH}
    st.forge.calls.clear()
    run, _added, context = ci_suite(st, fresh=True)
    st.local.assert_not_called()
    assert run.green, context
    read = {name for name, sha in st.forge.calls if sha == st.sha}
    assert read & {"job_result", "job_test_report"}, context


# ------------------------------------------------------------- AC-16


@pytest.mark.parametrize("case", ["1", "2"])
def test_ac16_publication_read_only_from_full_suite_job(stand, case):
    """Годная публикация лежит только у другой проверки CI того же коммита — итог CI не принят, причина одной строкой.

    (1) у `FULL_SUITE_JOB` публикации нет (только посторонняя
    аннотация), у другой проверки — подходящая; (2) у `FULL_SUITE_JOB` —
    «приложения наложены из X1», PLAN.md в X1 отличен от PLAN.md в Y
    (список диффов тот же), у другой проверки — подходящая из X.

    Ловит мутацию: публикация читается у любой проверки CI, а не только у
    `FULL_SUITE_JOB`, — в случае (1) итог CI принят; из нескольких
    проверок берётся любая подходящая — в случае (2) итог CI принят.
    """
    st = stand
    st.case = f"AC-16 ({case})"
    st.make_task(st.rng.randint(1, 3))
    x1 = st.x
    final = st.plan.replace("## Подход\n\n", "## Подход\n\nУточнено.\n", 1)
    st.x = st.docs_commit({"PLAN.md": final})
    st.plan = final
    st.publish(st.good(), check=st.other_check())
    if case == "1":
        st.publish()
    else:
        st.publish(publication(x1, "applied", digests(final)))
    assert_refused(st)


# ------------------------------------------------------------- AC-17


def test_ac17_changed_publisher_script_is_refused(stand):
    """`scripts/plan_appendix_ci.py` в головном коммите отличается от него же в `origin/main` — итог CI не принят, локальный прогон, причина одной строкой.

    Ловит мутацию: сценарий-публикатор не сверяется с базой — итог CI
    принят без локального прогона.
    """
    st = stand
    st.case = "AC-17"
    st.make_task(st.rng.randint(1, 3))
    st.change_script_on_branch()
    assert_refused(st)


# ------------------------------------------------------------- AC-18


@pytest.mark.parametrize("change", ["shorter", "one_changed", "reordered"])
def test_ac18_published_digests_differ_from_parse(stand, change):
    """Упорядоченный список sha256 диффов публикации отличается от разбора приёмки — итог CI не принят, локальный прогон, причина одной строкой.

    (1) на одно приложение меньше; (2) то же число, sha256 одного
    приложения другой; дополнительно — те же sha256 в другом порядке.
    PLAN несёт 2–3 приложения с разными диффами.

    Ловит мутацию: список диффов не сверяется с разбором приёмки — все
    случаи принимают итог CI; сверяется только по числу — (2) и порядок
    принимают; сверяется как множество — порядок принимает.
    """
    st = stand
    st.case = f"AC-18 {change}"
    st.make_task(st.rng.randint(2, 3))
    hashes = digests(st.plan)
    if change == "shorter":
        del hashes[st.rng.randrange(len(hashes))]
    elif change == "one_changed":
        hashes[st.rng.randrange(len(hashes))] = \
            f"{st.rng.getrandbits(256):064x}"
    else:
        hashes = hashes[1:] + hashes[:1]
    st.publish(publication(st.x, "applied", hashes))
    assert_refused(st)


# ------------------------------------------------------------- AC-15


def ci_publication(st: Stand) -> tuple:
    """Строки аннотации `plan-appendix-docs` в выводе настоящего сценария
    CI, запущенного в «раннере» — клоне `origin` на ветке задачи — по
    пушу ветки."""
    runner = st.tmp / f"runner-{st.rng.randrange(10**9)}"
    st.git("clone", "-q", "--depth", "1", "--branch", st.branch,
           f"file://{st.origin}", str(runner))
    env = dict(os.environ)
    env.update({"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": f"refs/heads/{st.branch}",
                "GITHUB_REF_NAME": st.branch, "GITHUB_REF_TYPE": "branch",
                "GITHUB_WORKSPACE": str(runner),
                "PYTHONDONTWRITEBYTECODE": "1"})
    res = run_group([sys.executable, str(CODE_ROOT / SCRIPT_REL)], runner, env)
    prefix = f"::notice title={TITLE}::"
    return [ln.rstrip()[len(prefix):]
            for ln in (res.stdout + "\n" + res.stderr).splitlines()
            if ln.startswith(prefix)], f"код {res.returncode}\n{res.stdout}\n{res.stderr}"


MUTATIONS = ["freshness", "plan_in_x", "ancestor", "outcome", "other_check",
             "digests", "script_publication"]


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_ac15_each_named_mutation_flips_one_condition(stand, mutation):
    """Парная проверка на одном стенде: годное состояние принимает итог CI, смена ровно одного условия, которое снимает названная в AC-15 мутация, — отказ.

    Пары: `merge_gate: operator` и `target-human` при ушедшей базе
    (свежесть); новое приложение в PLAN головы ссылки (PLAN.md в X);
    X без родства с головой (предок); исход «PLAN нет» (исход); годная
    публикация только у другой проверки (`FULL_SUITE_JOB`); тот же
    список с одним другим sha256 (сверка списка). Для «список не
    публикуется» и «иная форма хеша» — сквозной путь: строка настоящего
    сценария CI на голом `origin` стенда, отданная аннотацией
    `FULL_SUITE_JOB`, принимается приёмкой.

    Ловит мутацию: каждая из названных в AC-15 — отказ в паре не
    наступает (итог CI принят на сменённом условии); сценарий не
    публикует список или хеширует не байты UTF-8 `PlanAppendix.diff` —
    сквозная публикация не принимается, локальный прогон.
    """
    st = stand
    st.case = f"AC-15 {mutation}"
    st.make_task(0 if mutation == "freshness" else st.rng.randint(1, 3))
    if mutation == "freshness":
        st.move_base()
        assert_accepted(st, BASIS_FRESHNESS)
        st.write_targets("target-human")
        assert_refused(st)
        return
    if mutation == "script_publication":
        lines, out = ci_publication(st)
        assert len(lines) == 1, st.note(out)
        st.publish(annotation(lines[0]))
        assert_accepted(st, BASIS_APPENDICES)
        return
    assert_accepted(st, BASIS_APPENDICES)
    if mutation == "plan_in_x":
        new = plan_text(st.task, [*guard_diffs(st.plan), st.diff_of(
            st.rng.choice(PROTECTED_FILES))], "Фикстура с новым приложением.")
        st.docs_commit({"PLAN.md": new})
        st.plan = new
        st.publish(st.good())
    elif mutation == "ancestor":
        st.publish(publication(st.orphan_like_ref(), "applied",
                               digests(st.plan)))
    elif mutation == "outcome":
        st.publish(publication(st.x, "no-plan", digests(st.plan)))
    elif mutation == "other_check":
        st.publish(st.good(), check=st.other_check())
        st.publish()
    else:
        hashes = digests(st.plan)
        hashes[st.rng.randrange(len(hashes))] = \
            f"{st.rng.getrandbits(256):064x}"
        st.publish(publication(st.x, "applied", hashes))
    assert_refused(st)
