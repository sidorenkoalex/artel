"""Песочница гейта исходов на мерже: сквозной approve гейта мержа (MergeOutcomeSandbox) и двусторонний прогон (TwoSidedSandbox)."""
import contextlib
import hashlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (acceptance, checkpoint, ci, config, fsm,
                          github_adapter, project_profile, review, store,
                          workspace)
from orchestrator.advance_gates import refusal_classes, two_sided
from tests.sandbox import make_project_repo
from tests.outcome_gate_sandbox import (
    ENTRY_HEAD, PLAN_READY, PLANK_PY, SEP, OutcomeGateSandbox, flow,
    js_source, py_source, py_tests, spec_text, ulid)

PASSED_ACTION = "гейт неослабления по исходам пройден"
PREPARE_ACTION = "переход отклонён: гейт неослабления по исходам — подготовка"
MERGE_OUTCOME_ACTION = "merge отклонён: гейт неослабления по исходам"
OPERATOR_FIXES = "чинит Оператор"
APPROVE_HINT = "повтори artel.py approve"
PROVEN = "гейт исходов: доказан для головы {head} и базы {base}"
NOT_RUN = "гейт исходов для головы {head} не исполнялся"
FLAKY_ON_BASE = "нестабилен и на базе"
SECTION = "Изменённые утверждения тестов"
COVERED_BY = "покрыто мандатом "
MANDATE_NONE = "нет"
COUNTS_MARK = "тестов базы"
FRESHNESS_DOCS = "свежесть: "
PULLED = f"ветка подтянута к {config.MAIN_BRANCH}"
GATE_MODULES = ("orchestrator.advance_gates.outcome_integrity",
                "orchestrator.fsm_merge_gate")
GATE_WORDS = ("по исходам", "гейт исходов")
PROOF_LINE = re.compile(
    r"^голова ([0-9a-f]{40}); база ([0-9a-f]{40}); ключ (\S+); мандат (\S+)$")
HEX = "0123456789abcdef"

# Тело JUnit сверх видов песочницы G3а-1а: провал не на проверке — имя
# ошибки вне `failure_errors` компонента.
JUNIT_BODY = {
    "passed": "",
    "failed": '<failure message="assert 1 == 2">AssertionError: assert 1 == 2'
              '</failure>',
    "failed_other": '<failure message="ValueError: boom">ValueError: boom'
                    '</failure>',
    "error": '<error message="TypeError">TypeError: boom</error>',
    "skipped": '<skipped message="пропуск сценария"/>',
}

MULTI_FIELDS = ("command", "report", "long_lived_dir", "long_lived_name",
                "weakening_scope", "mutation_claim_scope", "failure_errors")


class MergeOutcomeSandbox(OutcomeGateSandbox):
    """Песочница G3а-1а плюс сквозной `approve` гейта мержа: CI ветки и
    main подменены, вызовы CI ветки считаются; полный набор записывает,
    какие пути сценария (`watch`) лежали в корне прогона."""

    def setUp(self):
        # Шпионы песочницы G3а-1а ставятся в её `setUp` и сразу зовутся.
        self.ci_calls: list = []
        self.watch: tuple = ()
        self.suite_error = False
        self.fetch_fail = False
        super().setUp()
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.object(ci, "branch_status", self.spy_ci),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    # --- шпионы ---------------------------------------------------------

    def spy_ci(self, branch, repo=None):
        self.ci_calls.append(branch)
        return True, "зелёный (тест)"

    def in_gate(self) -> bool:
        frame = sys._getframe(1)
        while frame is not None:
            if frame.f_globals.get("__name__") in GATE_MODULES:
                return True
            frame = frame.f_back
        return False

    def spy_run(self, argv, *args, **kwargs):
        """Сверх правила `git_fail`: при `fetch_fail` фетч главной ветки
        отвечает отказом в любом кадре."""
        if (self.fetch_fail and isinstance(argv, (list, tuple)) and argv
                and argv[0] == "git" and "fetch" in argv
                and any(str(a).startswith(f"+refs/heads/{config.MAIN_BRANCH}:")
                        for a in argv)):
            return subprocess.CompletedProcess(list(argv), 128, "",
                                               "fatal: фетч сценария\n")
        return super().spy_run(argv, *args, **kwargs)

    def spy_full_suite(self, root, task_id, *args, **kwargs):
        if self.suite_error:
            raise RuntimeError(f"сбой полного набора сценария {self.seed}")
        seen = {rel: (Path(root) / rel).exists() for rel in self.watch}
        result = super().spy_full_suite(root, task_id, *args, **kwargs)
        self.suite_calls[-1]["seen"] = seen
        return result

    def junit_report(self, run: dict, files: list) -> tuple:
        cases, red = [], False
        for rel, text in files:
            for klass, name in py_tests(text):
                full = f"{klass}{SEP}{name}" if klass else name
                if PLANK_PY.match(name):
                    kind = "passed" if self.plank_green else "failed"
                else:
                    kind = self.outcome_of(run["side"], rel, full)
                if kind == "missing":
                    continue
                red = red or kind in ("failed", "failed_other", "error")
                cases.append(f'<testcase file="{rel}" classname="{klass}" '
                             f'name="{name}" time="0.01">{JUNIT_BODY[kind]}'
                             f'</testcase>')
        text = ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
                '<testsuite name="pytest">' + "".join(cases)
                + "</testsuite></testsuites>")
        return text, red

    # --- проекты и задачи -----------------------------------------------

    def plank_text(self, project, n: int) -> tuple:
        """Планка сценария G3а-1а; (имя, текст) последней — для правки
        после лока."""
        self.last_plank = super().plank_text(project, n)
        return self.last_plank

    def multi_project(self) -> SimpleNamespace:
        """Учебный проект, чья запись несёт два компонента `junit-xml`."""
        name = f"m{self.word()}"
        lines = [ENTRY_HEAD.format(name=name), "    components:\n"]
        for _ in range(2):
            lines.append(f"      c{self.word()}:\n")
            values = {"command": flow([str(self.pytest_cmd)]),
                      "report": "junit-xml", "long_lived_dir": "tests",
                      "long_lived_name": "test_<id>_<name>.py",
                      "weakening_scope": flow(["tests/**"]),
                      "mutation_claim_scope": flow(["tests/**"]),
                      "failure_errors": flow(["AssertionError"])}
            for key in MULTI_FIELDS:
                lines.append(f"        {key}: {values[key]}\n")
            lines.append(f"        plank_layout: .pm{self.word(5)}/<id>\n")
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        self.commit_project(clone, {"app.py": "APP = 'base'\n",
                                    self.py_rel(): py_source([self.py_name()])})
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp="", layout="", kind="multi",
                               clone=clone)

    def direct_task(self, project, state: str, changes: dict | None = None,
                    canary: bool = False):
        """Задача проекта, заведённая сразу в `state` (без прохода гейтов
        `in_dev`): правка кода закоммичена в кодовую ветку, SPEC и PLAN — в
        ссылке документов автокоммитом шага."""
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Фикстура гейта исходов", state,
                          branch, project.name, 25.0, is_canary=canary)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=project.name, wt=Path(wt), project=project)
        t.docs = config.PROJECTS / project.name / "tasks" / tid
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid, (1,)), encoding="utf-8")
        (t.docs / "PLAN.md").write_text(PLAN_READY.format(task=tid),
                                        encoding="utf-8")
        self.commit_code(t, changes or {})
        with contextlib.redirect_stdout(io.StringIO()):
            checkpoint.commit_step_artifacts(self.conn, tid, "developer")
        self.current = tid
        return t

    def verifying_task(self, project, changes: dict | None = None,
                       mandate=None):
        """Задача проекта, прошедшая настоящий выход из `in_dev` (гейт
        исходов пройден, запись в журнале); `mandate` — элементы мандата
        Оператора до шага developer."""
        t = self.task(project)
        if mandate:
            self.operator_mandate(t, mandate)
        rows, output = self.developer_advance(t, changes, finished=bool(mandate))
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        t.passed = self.details(rows, PASSED_ACTION)
        self.assertTrue(t.passed, self.explain(rows, output))
        return t

    def to_merge_gate(self, t) -> None:
        store.set_state(self.conn, t.id, "merge_gate", "operator",
                        expected_state=self.state(t),
                        detail="сценарий: на гейт мержа")

    def approve(self, t) -> tuple:
        before = len(store.task_steps(self.conn, t.id))
        self.runs.clear()
        self.suite_calls.clear()
        self.ci_calls.clear()
        self.counts.clear()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_approve(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, buf.getvalue()

    # --- наблюдения -----------------------------------------------------

    def rev(self, t, ref: str) -> str:
        return self.git("-C", str(t.project.clone), "rev-parse", ref).strip()

    def head(self, t) -> str:
        return self.rev(t, t.branch)

    def origin_main(self, t) -> str:
        out = self.git("-C", str(t.project.clone), "ls-remote", "origin",
                       f"refs/heads/{config.MAIN_BRANCH}")
        return out.split()[0] if out.split() else ""

    def merge_base(self, t, other: str) -> str:
        return self.git("-C", str(t.project.clone), "merge-base", t.branch,
                        other).strip()

    def proof(self, detail: str) -> tuple:
        """(индекс строки, поля) строки доказательства детали записи."""
        for i, line in enumerate(detail.splitlines()):
            m = PROOF_LINE.match(line.strip())
            if m:
                return i, m.groups()
        return None, None

    def expected_key(self, t) -> str:
        """Ключ компонента по дереву головы с рабочей копией головы."""
        head = self.head(t)
        tree = self.rev(t, f"{head}^{{tree}}")
        holder = Path(tempfile.mkdtemp(prefix="artel-key-")).resolve()
        checkout = holder / "head"
        self.git("-C", str(t.project.clone), "worktree", "add", "--detach",
                 str(checkout), head)
        try:
            profile = project_profile.decide(t.target).profile
            return acceptance.suite_result_key(tree, profile, base=False,
                                               root=checkout)
        finally:
            self.git("-C", str(t.project.clone), "worktree", "remove",
                     "--force", str(checkout))
            shutil.rmtree(holder, ignore_errors=True)

    def journal_rows(self, t) -> list:
        return [dict(r) for r in store.task_steps(self.conn, t.id)]

    def rewrite_passed(self, t, edit) -> None:
        """Правка детали последней записи пройденного гейта исходов
        задачи в БД пульта: `edit(деталь) -> новая деталь`."""
        rows = [r for r in self.journal_rows(t) if r["action"] == PASSED_ACTION]
        self.assertTrue(rows, self.note("записи пройденного гейта нет"))
        row = rows[-1]
        new = edit(row["detail"])
        self.assertNotEqual(new, row["detail"], self.note("правка не изменила запись"))
        self.conn.execute("UPDATE steps SET detail=? WHERE id=?", (new, row["id"]))
        self.conn.commit()

    @staticmethod
    def texts(rows: list) -> list:
        return [f"{r['action']} {r['detail'] or ''}" for r in rows]

    def gate_rows(self, rows: list) -> list:
        return [x for x in self.texts(rows) if any(w in x for w in GATE_WORDS)]

    def sides(self) -> list:
        return sorted({c["side"] for c in self.suite_calls})

    def hexword(self, size: int) -> str:
        return "".join(self.rng.choice(HEX) for _ in range(size))

    def section(self, text: str):
        mark = f"### {SECTION}"
        start = text.find(mark)
        if start < 0:
            return None
        end = text.find("\n### ", start + len(mark))
        return text[start:end if end >= 0 else len(text)]

    def package(self, t) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                return review.review_package(self.conn, t.id, "Фикстура",
                                             t.branch)["text"]
            except SystemExit as exc:
                return f"SystemExit: {exc.code}\n{buf.getvalue()}"

    @staticmethod
    def numbers(text: str) -> set:
        return {int(x) for x in re.findall(r"(?<![\w.:-])\d+(?![\w.:-])", text)}

    def broken_case(self, project_kind: str = "junit") -> tuple:
        """(проект, путь, имя): тест базы зелёный, на ветке трижды
        `failed`."""
        rel, name = self.py_rel(), self.py_name()
        project = (self.junit_project({rel: [name, self.py_name()]},
                                      test_profile=project_kind == "test_profile"))
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
        return project, rel, name


class TwoSidedSandbox(MergeOutcomeSandbox):

    def two_sided(self, project, rel: str, name: str, kinds: dict,
                  timeout_side: str | None = None):
        """Двусторонний прогон метода `rel::name` (`two_sided.run`):
        `kinds` — {«base»: исход новой версии на базе, «head»: исход старой
        версии на голове}; (итог, адрес метода)."""
        vitest = project.kind == "vitest"
        old = (js_source if vitest else py_source)([name])
        new = old + ("// новая версия\n" if vitest else "# новая версия\n")
        t = self.direct_task(project, "in_dev", {rel: new})
        base = self.merge_base(t, f"refs/remotes/origin/{config.MAIN_BRANCH}")
        self.cases[(rel, name)] = {side: [kind] for side, kind in kinds.items()}
        self.counts.clear()
        self.timeout_when = (None if timeout_side is None else
                             lambda run: not run["plank"] and run["side"] == timeout_side)
        method = two_sided.Method(rel, rel, name, old, new)
        try:
            result = two_sided.run(project.clone, t.branch, base, [method],
                                   profile=project_profile.decide(project.name).profile)
        finally:
            self.timeout_when = None
        return result, method.address

    def side_text(self, result, address: str, label: str) -> str:
        return str((result.sides or {}).get(address, {}).get(label, {}).get("outcome", ""))
