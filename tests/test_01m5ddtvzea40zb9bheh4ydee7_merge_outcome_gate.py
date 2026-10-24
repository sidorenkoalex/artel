"""Гейт неослабления по исходам на гейте мержа, доказательство для головы, пакет ревьювера и двусторонний прогон по имени ошибки.

Группа: долгоживущий
Красен до реализации: запись пройденного гейта исходов не несёт строки «голова …; база …; ключ …; мандат …», ключ компонента не считается и его сбой не отказывает; на гейте мержа гейт исходов не исполняется — находка не эскалирует, сбой подготовки не останавливает мерж, записи «гейт исходов: доказан …» нет; раздел «Изменённые утверждения тестов» пакета ревьювера без строк гейта исходов и без строки «не исполнялся»; двусторонний прогон по отчёту считает проверкой любой `failed` и `passed` с повтором — зелёной стороной; ключа «merge отклонён: гейт неослабления по исходам» в `REFUSAL_CLASSES` нет. Зелены и на базе ветки методы, держащие прежнее поведение: AC-13 (правило G3а-1а уже действует на выходе из `in_dev`) и AC-14 (вне границы гейта).

Стенд — песочница гейта исходов G3а-1а
(`tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.OutcomeGateSandbox`):
настоящий git, учебный внешний проект с единственным компонентом
`junit-xml` на поддельном `pytest` (либо `pult-vitest` без Node), раннер
подменён шпионом `subprocess.Popen`; СТОРОНА прогона — по метке выписки
(`app.py`: `'base'` у базы, `'head-…'` у головы кодовой ветки), исход
теста — последовательность сценария по стороне. Гейт мержа — сквозной
`fsm.cmd_approve` задачи на `merge_gate`: подменены только внешние
проверки, которых в песочнице нет, — цвет CI ветки и main
(`ci.branch_status` — шпион, считающий вызовы; `ci.main_line_status`),
Draft MR форджа и публикация головы (`github_adapter`). Тело гейта мержа
за один `approve` входит дважды (первый вход уходит ждать CI), поэтому
«прогон был» — хоть один вызов полного набора, «прогона не было» — ни
одного.

Сбои подготовки — шпион `subprocess.run`: отказ git только в кадрах модулей
гейта (`orchestrator.advance_gates.outcome_integrity`,
`orchestrator.fsm_merge_gate`) — выписка с sha головы, `ls-tree` файлов
блокировки (ключ компонента не снят); фетч `refs/heads/main` — в любом
кадре (sha main не получен).

Ключ компонента сверяется публичным `acceptance.suite_result_key` по дереву
головы (`<голова>^{tree}`) с профилем решения `project_profile.decide` и
рабочей копией головы (`root`): это тот же ключ `_report_suite_result_key`
с `base=False`, что требует SPEC.

Имена проектов, файлов, тестов и числа — из `random`; зерно печатается и
входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен): строка
доказательства в записи пройденного гейта, гейт исходов в окне мержа после
«fresh» с базой merge-base головы и зафетченного sha main, доказательство
по четвёрке, эскалация находки и отказ подготовки без push, строки пакета
ревьювера, классификатор `_check_failure_kind` в двустороннем прогоне —
все методы файла зелёные.
"""
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


# ---------------------------------------------------------------- AC-1

class Ac1ProofLineTest(MergeOutcomeSandbox):

    def test_ac1_passed_record_carries_head_base_key_and_mandate(self):
        """Запись пройденного гейта на выходе из `in_dev`: сразу после строки чисел — строка головы, базы, ключа компонента и отпечатка мандата.

        Сценарий (подслучай — свежая задача): (а) все тесты зелёные — у
        записи строка `голова <sha40>; база <sha40>; ключ <ключ>; мандат
        нет`; (б) ветка удаляет два файла тестов, на оба — мандат
        Оператора, плюс элемент мандата на третий путь без находок —
        отпечаток равен sha256 строки двух покрывших путей, отсортированных
        и соединённых переводом строки. В обоих: строка идёт сразу после
        строки чисел, голова — голова кодовой ветки, база — merge-base с
        `origin/main` (`diff_base`), ключ — `suite_result_key` по дереву
        головы с её рабочей копией.

        Ловит мутацию: строка доказательства не пишется или стоит не после
        строки чисел; голова и база перепутаны; ключ по коммиту, а не по
        дереву, либо с `base=True`; отпечаток без сортировки, по всем
        элементам мандата (включая непокрывший) или через запятую; при
        отсутствии покрывших элементов — пустой отпечаток вместо «нет».
        """
        for label in ("без мандата", "мандат"):
            with self.subTest(case=label, seed=self.seed):
                keep_rel = self.py_rel()
                tests = {keep_rel: [self.py_name() for _ in range(2)]}
                covered = []
                if label == "мандат":
                    covered = [self.py_rel() for _ in range(2)]
                    for rel in covered:
                        tests[rel] = [self.py_name()]
                project = self.junit_project(tests)
                extra = self.py_rel()
                elements = covered + [extra] if covered else None
                t = self.verifying_task(project, {rel: None for rel in covered},
                                        mandate=elements)
                detail = t.passed[-1]
                index, fields = self.proof(detail)
                self.assertIsNotNone(fields, self.note(f"нет строки доказательства:\n{detail}"))
                lines = detail.splitlines()
                counts = [i for i, line in enumerate(lines) if COUNTS_MARK in line]
                self.assertTrue(counts, self.note(detail))
                self.assertEqual(index, counts[0] + 1, self.note(detail))
                head, base, key, fingerprint = fields
                self.assertEqual(head, self.head(t), self.note(detail))
                self.assertEqual(base, self.merge_base(
                    t, f"refs/remotes/origin/{config.MAIN_BRANCH}"), self.note(detail))
                self.assertEqual(key, self.expected_key(t), self.note(detail))
                if covered:
                    wanted = hashlib.sha256(
                        "\n".join(sorted(covered)).encode("utf-8")).hexdigest()
                else:
                    wanted = MANDATE_NONE
                self.assertEqual(fingerprint, wanted, self.note(detail))

    def test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record(self):
        """Ключ компонента не снят на выходе из `in_dev` — отказ подготовки гейта исходов, записи пройденного гейта нет.

        Сценарий: проект `junit-xml`, все тесты зелёные; git отказывает
        `ls-tree` файлов блокировки в кадрах гейта (суммы блокировки не
        сняты — ключ `None`). `advance` из `in_dev`: отказ «переход
        отклонён: гейт неослабления по исходам — подготовка», записи «гейт
        неослабления по исходам пройден» нет, задача в `in_dev`.

        Ловит мутацию: ключ `None` пишется в строку записи («ключ None») и
        гейт пройден; сбой ключа проглочен — запись без строки
        доказательства, переход в `verifying`.
        """
        project = self.junit_project({self.py_rel(): [self.py_name()]})
        t = self.task(project)
        locks = set(acceptance.LOCK_FILE_NAMES)
        self.git_fail = lambda args: "ls-tree" in args and any(
            a.rsplit("/", 1)[-1] in locks for a in args)
        rows, output = self.developer_advance(t)
        self.git_fail = None
        self.assertTrue(self.details(rows, PREPARE_ACTION), self.explain(rows, output))
        self.assertEqual(self.details(rows, PASSED_ACTION), [], self.explain(rows, output))
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))


# ---------------------------------------------------------------- AC-2

class Ac2MergeFindingTest(MergeOutcomeSandbox):

    def test_ac2_finding_without_mandate_escalates_merge(self):
        """Находка без мандата на гейте мержа — `escalated`, действие журнала «merge отклонён: гейт неослабления по исходам» с находкой, push нет.

        Сценарий (подслучай — свежая задача сразу на `merge_gate`, записи
        пройденного гейта нет): (а) тест базы на ветке красен все три
        прогона («сломан правкой»); (б) тест базы исчез из отчёта ветки
        (текст файла не менялся — гейт по тексту его не видит). После
        `approve`: задача в `escalated`, среди новых записей — действие
        «merge отклонён: гейт неослабления по исходам», идентификатор
        теста — в тексте записей, `origin/main` проекта не сдвинулся.

        Ловит мутацию: гейт исходов не включён в окно мержа — задача в
        `done`; «сломан правкой» пишется своим действием («… — сломан
        правкой») либо возвращает задачу в `in_dev`; находка исчезновения
        не эскалирует.
        """
        for label in ("сломан", "исчез"):
            with self.subTest(case=label, seed=self.seed):
                rel, name = self.py_rel(), self.py_name()
                project = self.junit_project({rel: [name, self.py_name()]})
                head = ["failed"] if label == "сломан" else ["missing"]
                self.cases[(rel, name)] = {"base": ["passed"], "head": head}
                t = self.direct_task(project, "merge_gate")
                main = self.origin_main(t)
                rows, output = self.approve(t)
                cid = self.case_id(project, rel, name)
                self.assertEqual(self.state(t), "escalated", self.explain(rows, output))
                self.assertTrue(self.details(rows, MERGE_OUTCOME_ACTION),
                                self.explain(rows, output))
                self.assertTrue(any(cid in x for x in self.texts(rows)),
                                self.explain(rows, output))
                self.assertEqual(self.origin_main(t), main, self.explain(rows, output))

    def test_ac2_merge_refusal_action_is_operator_class_key(self):
        """Действие «merge отклонён: гейт неослабления по исходам» — ключ словаря `REFUSAL_CLASSES` со значением «чинит Оператор».

        Ловит мутацию: ключ не добавлен в словарь — `refusal_class`
        отдаёт «чинит Оператор» по умолчанию, но ключа в словаре нет;
        действие отнесено к «чинит роль».
        """
        self.assertIn(MERGE_OUTCOME_ACTION, refusal_classes.REFUSAL_CLASSES)
        self.assertEqual(refusal_classes.REFUSAL_CLASSES[MERGE_OUTCOME_ACTION],
                         OPERATOR_FIXES)
        self.assertEqual(refusal_classes.refusal_class(MERGE_OUTCOME_ACTION),
                         OPERATOR_FIXES)


# ---------------------------------------------------------------- AC-3

class Ac3MergePrepareTest(MergeOutcomeSandbox):

    def test_ac3_prepare_failures_keep_merge_gate_without_push(self):
        """Сбой подготовки гейта исходов на мерже — задача на `merge_gate`, push нет, подсказка «повтори artel.py approve», мерж дальше не идёт.

        Сценарий (подслучай — свежая задача сразу на `merge_gate`, тест базы
        на ветке красен): (а) выписка головы отказана git в кадрах гейта;
        (б) полный набор головы не пишет отчёт («не начат»/«неизвестно»);
        (в) полный набор базы превышает предел; (г) полный набор бросает
        исключение; (д) фетч `refs/heads/main` отказан — «fresh» без sha
        main; (е) `ls-tree` файлов блокировки отказан в кадрах гейта — ключ
        компонента `None`. В каждом: задача на `merge_gate`, `origin/main`
        не сдвинулся, подсказка «повтори artel.py approve» — в выводе или
        журнале, CI ветки не опрашивался (окно до CI не дошло); в (д) и (е)
        полный набор не звался вовсе, записи «гейт исходов: доказан» нет.

        Ловит мутацию: сбой подготовки пропускает гейт — мерж идёт к CI и
        в `done`; сбой проглочен как отсутствие находок — `done`; «fresh»
        без sha main берёт базой `diff_base` — полный набор прогнан и мерж
        дошёл до CI; ключ `None` сравнивается как значение — прогон и
        проход.
        """
        locks = set(acceptance.LOCK_FILE_NAMES)

        def checkout_head(t):
            head = self.head(t)
            return lambda args: (("worktree" in args and "add" in args)
                                 or "clone" in args or "archive" in args) and any(
                head in a or t.branch in a for a in args)

        def full(side):
            return lambda run: run["full"] and not run["plank"] and run["side"] == side

        cases = ("выписка", "не начат", "таймаут", "исключение", "без sha main",
                 "ключ None")
        for label in cases:
            with self.subTest(case=label, seed=self.seed):
                project, _rel, _name = self.broken_case()
                t = self.direct_task(project, "merge_gate")
                main = self.origin_main(t)
                if label == "выписка":
                    self.git_fail = checkout_head(t)
                elif label == "ключ None":
                    self.git_fail = lambda args: "ls-tree" in args and any(
                        a.rsplit("/", 1)[-1] in locks for a in args)
                self.no_report_when = full("head") if label == "не начат" else None
                self.timeout_when = full("base") if label == "таймаут" else None
                self.suite_error = label == "исключение"
                self.fetch_fail = label == "без sha main"
                rows, output = self.approve(t)
                self.git_fail = self.no_report_when = self.timeout_when = None
                self.suite_error = self.fetch_fail = False
                context = self.explain(rows, output) + f"\nCI: {self.ci_calls}"
                self.assertEqual(self.state(t), "merge_gate", context)
                self.assertEqual(self.origin_main(t), main, context)
                self.assertTrue(APPROVE_HINT in output or any(
                    APPROVE_HINT in x for x in self.texts(rows)), context)
                self.assertEqual(self.ci_calls, [], context)
                if label in ("без sha main", "ключ None"):
                    self.assertEqual(self.suite_calls, [], context)
                    self.assertFalse(any("доказан" in x for x in self.texts(rows)),
                                     context)


# ---------------------------------------------------------------- AC-4

class Ac4ProofTest(MergeOutcomeSandbox):

    def test_ac4_same_quadruple_proves_without_run(self):
        """Запись пройденного гейта с той же головой, базой, ключом и отпечатком — на мерже прогона нет, запись «гейт исходов: доказан для головы <sha7> и базы <sha7>».

        Сценарий (подслучай — свежая задача): задача проходит настоящий
        выход из `in_dev` (гейт исходов пройден) — (а) без находок; (б) с
        находками исчезнувших тестов удалённого файла под мандатом
        Оператора. Задача на `merge_gate`, `approve`: полный набор не
        звался ни разу, раннер полного набора не запускался, среди новых
        записей — «гейт исходов: доказан для головы <sha7 головы> и базы
        <sha7 merge-base>», задача в `done`.

        Ловит мутацию: доказательство не ищется — полный набор прогнан на
        мерже; доказательство при находках под мандатом не сверяет
        отпечаток текущего мандата верно — прогон; текст записи с полным
        sha или без базы — записи нет.
        """
        for label in ("без находок", "мандат"):
            with self.subTest(case=label, seed=self.seed):
                gone = self.py_rel()
                tests = {self.py_rel(): [self.py_name()]}
                if label == "мандат":
                    tests[gone] = [self.py_name()]
                project = self.junit_project(tests)
                t = self.verifying_task(
                    project, {gone: None} if label == "мандат" else None,
                    mandate=[gone] if label == "мандат" else None)
                head = self.head(t)
                base = self.merge_base(t, self.origin_main(t))
                self.to_merge_gate(t)
                rows, output = self.approve(t)
                context = self.explain(rows, output)
                self.assertEqual(self.suite_calls, [], context)
                self.assertEqual(self.full_runs(), [], context)
                wanted = PROVEN.format(head=head[:7], base=base[:7])
                self.assertTrue(any(wanted in x for x in self.texts(rows)),
                                context + f"\nожидалось: {wanted}")
                self.assertEqual(self.state(t), "done", context)


# ---------------------------------------------------------------- AC-5

class Ac5ProofMismatchTest(MergeOutcomeSandbox):

    def test_ac5_other_base_key_or_mandate_runs_gate(self):
        """Запись, отличающаяся от текущей четвёрки базой, ключом компонента или отпечатком мандата, доказательством не служит — на мерже прогон.

        Сценарий (подслучай — свежая задача): настоящий выход из `in_dev`
        (для подслучая мандата — с удалённым файлом тестов под мандатом
        Оператора); в записи пройденного гейта в журнале заменено одно
        поле строки доказательства: (а) база — случайный sha; (б) ключ —
        случайный; (в) отпечаток мандата — sha256 набора, где к покрывшему
        элементу добавлен отозванный (текущий мандат его не несёт).
        `approve`: полный набор прогнан на мерже на обеих сторонах.

        Ловит мутацию: доказательство сверяет только голову — прогона нет
        во всех подслучаях; не сверяет ключ — (б) без прогона; отпечаток
        записи не сравнивается с отпечатком текущего мандата — (в) без
        прогона.
        """
        for field in ("база", "ключ", "мандат"):
            with self.subTest(field=field, seed=self.seed):
                keep, gone = self.py_rel(), self.py_rel()
                project = self.junit_project({keep: [self.py_name()],
                                              gone: [self.py_name()]})
                t = self.verifying_task(project, {gone: None}, mandate=[gone])
                revoked = self.py_rel()

                def edit(detail, field=field, gone=gone, revoked=revoked):
                    out = []
                    for line in detail.splitlines():
                        m = PROOF_LINE.match(line.strip())
                        if m:
                            head, base, key, mark = m.groups()
                            if field == "база":
                                base = self.hexword(40)
                            elif field == "ключ":
                                key = self.hexword(64)
                            else:
                                mark = hashlib.sha256("\n".join(sorted(
                                    [gone, revoked])).encode("utf-8")).hexdigest()
                            line = f"голова {head}; база {base}; ключ {key}; мандат {mark}"
                        out.append(line)
                    return "\n".join(out)
                self.rewrite_passed(t, edit)
                self.to_merge_gate(t)
                rows, output = self.approve(t)
                self.assertEqual(self.sides(), ["base", "head"],
                                 self.explain(rows, output))


# ---------------------------------------------------------------- AC-6

class Ac6LegacyRecordTest(MergeOutcomeSandbox):

    def test_ac6_record_without_proof_line_runs_gate(self):
        """Прежняя запись пройденного гейта без строки «голова …; база …» доказательством не служит — на мерже прогон.

        Сценарий: настоящий выход из `in_dev`; из записи пройденного гейта
        в журнале убрана строка доказательства (остаётся прежняя форма —
        строка чисел). `approve`: полный набор прогнан на мерже на обеих
        сторонах, записи «гейт исходов: доказан» с этой головой до прогона
        нет.

        Ловит мутацию: запись без строки доказательства принимается как
        доказательство (любая запись пройденного гейта) — прогона нет.
        """
        project = self.junit_project({self.py_rel(): [self.py_name()]})
        t = self.verifying_task(project)
        self.rewrite_passed(t, lambda detail: "\n".join(
            line for line in detail.splitlines()
            if not PROOF_LINE.match(line.strip())))
        self.to_merge_gate(t)
        rows, output = self.approve(t)
        self.assertEqual(self.sides(), ["base", "head"], self.explain(rows, output))


# ---------------------------------------------------------------- AC-7

class Ac7MergeBaseTest(MergeOutcomeSandbox):

    def test_ac7_base_is_merge_base_with_fetched_main_not_diff_base(self):
        """База гейта на мерже — merge-base головы с зафетченным sha main, не `diff_base`: голова, влившая main, даёт базой этот main.

        Сценарий: задача сразу на `merge_gate`; в main проекта (и его
        `origin`) — новый коммит с новым файлом тестов, кодовая ветка его
        влила. Ссылка отслеживания `refs/remotes/origin/main` клона
        возвращена на прежний main, а `remote.origin.fetch` снят — фетч
        её не обновляет, и `diff_base` ветки — прежний main (предусловие).
        `approve`: полный набор базы прогнан на дереве, где новый файл
        тестов есть; задача в `done`.

        Ловит мутацию: база на мерже — повторный `diff_base` — выписка
        базы на прежнем main, нового файла в её дереве нет.
        """
        project = self.junit_project({self.py_rel(): [self.py_name()]})
        t = self.direct_task(project, "merge_gate")
        clone = str(project.clone)
        old_main = self.rev(t, config.MAIN_BRANCH)
        new_rel = self.py_rel()
        self.commit_project(project.clone, {new_rel: py_source([self.py_name()])})
        new_main = self.rev(t, config.MAIN_BRANCH)
        self.git("-C", str(t.wt), "merge", "-q", "--no-edit", config.MAIN_BRANCH)
        self.git("-C", clone, "update-ref",
                 f"refs/remotes/origin/{config.MAIN_BRANCH}", old_main)
        self.git("-C", clone, "config", "--unset-all", "remote.origin.fetch")
        self.assertEqual(self.merge_base(
            t, f"refs/remotes/origin/{config.MAIN_BRANCH}"), old_main, self.note(
                "предусловие: diff_base ветки — прежний main"))
        self.assertEqual(self.merge_base(t, new_main), new_main, self.note(
            "предусловие: голова влила новый main"))
        self.watch = (new_rel,)
        rows, output = self.approve(t)
        context = self.explain(rows, output) + f"\nвызовы: {self.suite_calls}"
        base_calls = [c for c in self.suite_calls if c["side"] == "base"]
        self.assertTrue(base_calls, context)
        self.assertTrue(all(c["seen"][new_rel] for c in base_calls), context)
        self.assertEqual(self.state(t), "done", context)

    def test_ac7_doc_only_lag_runs_gate_with_merge_base(self):
        """Отставание ветки только на документные коммиты main — штатный путь: гейт исполняется, база — merge-base головы, документного коммита в её дереве нет.

        Сценарий: задача сразу на `merge_gate`; после ветвления в main
        проекта — коммит одного документного файла `docs/<слово>.md`.
        `approve`: сверка свежести записала «свежесть: … документных
        коммитов main без подтяжки» (предусловие пути); полный набор
        прогнан на обеих сторонах, в дереве базы документного файла нет;
        отказа подготовки нет, задача в `done`.

        Ловит мутацию: базой служит сам зафетченный sha main — в дереве
        базы есть документный файл; документное отставание считается
        сбоем подготовки — задача остаётся на `merge_gate`.
        """
        project = self.junit_project({self.py_rel(): [self.py_name()]})
        t = self.direct_task(project, "merge_gate")
        doc = f"docs/{self.word()}.md"
        self.commit_project(project.clone, {doc: f"заметка {self.seed}\n"})
        self.watch = (doc,)
        rows, output = self.approve(t)
        context = self.explain(rows, output) + f"\nвызовы: {self.suite_calls}"
        self.assertTrue(any(r["action"].startswith(FRESHNESS_DOCS) for r in rows),
                        context)
        self.assertEqual(self.sides(), ["base", "head"], context)
        base_calls = [c for c in self.suite_calls if c["side"] == "base"]
        self.assertFalse(any(c["seen"][doc] for c in base_calls), context)
        self.assertEqual(self.state(t), "done", context)

    def test_ac7_gate_after_fresh_and_before_acceptance_locks(self):
        """Гейт исходов идёт после «fresh» и до сверки лока приёмочных тестов.

        Сценарий (подслучай — свежая задача после настоящего выхода из
        `in_dev`): (а) лок планки нарушен — файл планки в ссылке документов
        правлен после лока; `approve`: запись «гейт исходов: доказан …» для
        головы есть, мерж остановлен (задача не в `done`). (б) В main
        проекта — коммит кода (не документ): сверка свежести подтягивает
        main в ветку, пушит и уходит ждать CI; на следующем входе — «fresh».
        Записи «доказан» для прежней головы нет; каждый прогон полного
        набора на голове — на дереве с файлом из main; задача в `done`.

        Ловит мутацию: гейт после `_acceptance_locks_refuse` — в (а)
        записи «доказан» нет; гейт до `_sync_main_or_wait` — в (б)
        доказательство для прежней головы записано до подтяжки.
        """
        with self.subTest(case="лок", seed=self.seed):
            project = self.junit_project({self.py_rel(): [self.py_name()]})
            t = self.verifying_task(project)
            head = self.head(t)
            base = self.merge_base(t, self.origin_main(t))
            name, body = self.last_plank
            t.plank.mkdir(parents=True, exist_ok=True)
            (t.plank / name).write_text(
                body + f"\n# правка после лока {self.seed}\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
            self.to_merge_gate(t)
            rows, output = self.approve(t)
            # Предусловие: мерж остановлен сверкой лока.
            self.assertNotEqual(self.state(t), "done", self.explain(rows, output))
            wanted = PROVEN.format(head=head[:7], base=base[:7])
            self.assertTrue(any(wanted in x for x in self.texts(rows)),
                            self.explain(rows, output))
        with self.subTest(case="подтяжка", seed=self.seed):
            project = self.junit_project({self.py_rel(): [self.py_name()]})
            t = self.verifying_task(project)
            old_head = self.head(t)
            lib = f"lib_{self.word()}.py"
            self.commit_project(project.clone, {lib: f"LIB = {self.seed}\n"})
            self.to_merge_gate(t)
            self.watch = (lib,)
            rows, output = self.approve(t)
            context = self.explain(rows, output) + f"\nвызовы: {self.suite_calls}"
            # Предусловие: сверка свежести подтянула main в ветку.
            self.assertIn(PULLED, output, context)
            self.assertFalse(any(f"доказан для головы {old_head[:7]}" in x
                                 for x in self.texts(rows)), context)
            head_calls = [c for c in self.suite_calls if c["side"] == "head"]
            self.assertTrue(head_calls, context)
            self.assertTrue(all(c["seen"][lib] for c in head_calls), context)
            self.assertEqual(self.state(t), "done", context)

    def test_ac7_canary_from_db_and_in_dev_base_is_diff_base(self):
        """Признак канарейки на мерже — из строки задачи: у канареечной задачи гейт исходов на мерже не исполняется; на выходе из `in_dev` база записи — `diff_base`.

        Сценарий (подслучай): (а) канареечная задача проекта в границе
        сразу на `merge_gate`, тест базы на ветке красен — `approve`:
        полный набор не звался, записей гейта исходов нет, задача в
        `done`; (б) задача после настоящего выхода из `in_dev` — база
        строки доказательства равна merge-base ветки с
        `refs/remotes/origin/main` и не равна голове.

        Ловит мутацию: признак канарейки не читается на мерже — у
        канарейки полный набор прогнан и мерж эскалирован; база выхода из
        `in_dev` — голова или sha зафетченного main вместо `diff_base`.
        """
        with self.subTest(case="канарейка", seed=self.seed):
            project, _rel, _name = self.broken_case()
            t = self.direct_task(project, "merge_gate", canary=True)
            rows, output = self.approve(t)
            self.assertEqual(self.suite_calls, [], self.explain(rows, output))
            self.assertEqual(self.gate_rows(rows), [], self.explain(rows, output))
            self.assertEqual(self.state(t), "done", self.explain(rows, output))
        with self.subTest(case="in_dev", seed=self.seed):
            project = self.junit_project({self.py_rel(): [self.py_name()]})
            t = self.verifying_task(project)
            _index, fields = self.proof(t.passed[-1])
            self.assertIsNotNone(fields, self.note(t.passed[-1]))
            self.assertEqual(fields[1], self.merge_base(
                t, f"refs/remotes/origin/{config.MAIN_BRANCH}"), self.note(t.passed[-1]))
            self.assertNotEqual(fields[1], self.head(t), self.note(t.passed[-1]))


# ---------------------------------------------------------------- AC-8

class Ac8ReviewLinesTest(MergeOutcomeSandbox):

    def test_ac8_review_section_carries_outcome_gate_lines_for_head(self):
        """Пакет ревьювера при записи пройденного гейта с текущей головой — в разделе «Изменённые утверждения тестов» числа базы и ветки, покрытые находки с ANSWER, «нестабилен и на базе», перепрогоны.

        Сценарий: проект `junit-xml`; на базе `nb` тестов (из `random`), из
        них `m` в файле, который ветка удаляет под мандатом Оператора;
        ветка добавляет `k` новых зелёных; один тест трижды красен на ветке
        и красен на одном перепрогоне базы. Настоящий выход из `in_dev`,
        затем `review.review_package`. Раздел есть; в нём числа `nb` и
        число тестов ветки, идентификатор каждой покрытой находки и имя
        ANSWER из записи, строка «нестабилен и на базе» с идентификатором
        нестабильного теста, слово «перепрогон».

        Ловит мутацию: раздел строится только по гейту по тексту — строк
        гейта исходов нет; запись ищется не по текущей голове — строки
        «не исполнялся» вместо чисел; покрытые находки без имени ANSWER.
        """
        nb = self.rng.randint(11, 19)
        m = self.rng.randint(2, 3)
        k = self.rng.randint(21, 29)
        covered = self.py_rel()
        gone = [self.py_name() for _ in range(m)]
        flaky_rel, flaky = self.py_rel(), self.py_name()
        rest = [self.py_name() for _ in range(nb - m - 1)]
        project = self.junit_project({covered: gone, flaky_rel: [flaky],
                                      self.py_rel(): rest})
        self.cases[(flaky_rel, flaky)] = {"base": ["passed", "failed", "passed"],
                                          "head": ["failed"]}
        added = [self.py_name() for _ in range(k)]
        t = self.verifying_task(project, {covered: None,
                                          self.py_rel(): py_source(added)},
                                mandate=[covered])
        detail = t.passed[-1]
        sources = sorted({line.rsplit(COVERED_BY, 1)[1].strip()
                          for line in detail.splitlines() if COVERED_BY in line})
        self.assertTrue(sources, self.note(detail))
        text = self.package(t)
        part = self.section(text)
        self.assertIsNotNone(part, self.note(text[-3000:]))
        context = self.note(f"раздел:\n{part}\nзапись:\n{detail}")
        nh = nb - m + k
        self.assertTrue({nb, nh} <= self.numbers(part), context)
        for name in gone:
            self.assertIn(self.case_id(project, covered, name), part, context)
        for source in sources:
            self.assertIn(source, part, context)
        flaky_id = self.case_id(project, flaky_rel, flaky)
        self.assertTrue(any(FLAKY_ON_BASE in line and flaky_id in line
                            for line in part.splitlines()), context)
        self.assertIn("перепрогон", part.lower(), context)


# ---------------------------------------------------------------- AC-9

class Ac9ReviewNotRunTest(MergeOutcomeSandbox):

    def test_ac9_no_record_for_current_head_says_not_run(self):
        """Пакет ревьювера без записи пройденного гейта с текущей головой — строка «гейт исходов для головы <sha7> не исполнялся».

        Сценарий (подслучай): (а) задача проекта в границе заведена сразу
        в `review`, гейт исходов не исполнялся ни разу; (б) задача прошла
        выход из `in_dev`, затем в кодовую ветку закоммичена ещё правка —
        запись есть, но для прежней головы. В обоих раздел «Изменённые
        утверждения тестов» несёт строку для sha7 текущей головы.

        Ловит мутацию: запись берётся последняя по журналу без сверки
        головы — в (б) строки прежней записи вместо «не исполнялся»; при
        отсутствии записи раздела нет либо нет строки.
        """
        with self.subTest(case="без записи", seed=self.seed):
            project = self.junit_project({self.py_rel(): [self.py_name()]})
            t = self.direct_task(project, "review")
            text = self.package(t)
            self.assertIn(NOT_RUN.format(head=self.head(t)[:7]),
                          self.section(text) or "", self.note(text[-3000:]))
        with self.subTest(case="другая голова", seed=self.seed):
            project = self.junit_project({self.py_rel(): [self.py_name()]})
            t = self.verifying_task(project)
            self.commit_code(t, {})
            text = self.package(t)
            self.assertIn(NOT_RUN.format(head=self.head(t)[:7]),
                          self.section(text) or "", self.note(text[-3000:]))


# --------------------------------------------------------------- AC-10

class Ac10NoPythonSectionTest(MergeOutcomeSandbox):

    def test_ac10_component_without_python_has_section_except_canary(self):
        """У компонента без Python (строк гейта по тексту нет) раздел «Изменённые утверждения тестов» есть у обычной задачи и, по прежнему условию, отсутствует у канареечной.

        Сценарий (подслучай): проект `pult-vitest`, задача заведена в
        `review` — (а) не канареечная: в пакете ревьювера есть заголовок
        раздела; (б) канареечная: заголовка раздела нет.

        Ловит мутацию: раздел по-прежнему появляется только при строках
        гейта по тексту — в (а) раздела нет; канареечная задача получает
        раздел — в (б) заголовок есть.
        """
        for canary in (False, True):
            with self.subTest(canary=canary, seed=self.seed):
                project = self.vitest_project({self.js_rel(): [self.js_name()]})
                t = self.direct_task(project, "review", canary=canary)
                text = self.package(t)
                if canary:
                    self.assertIsNone(self.section(text), self.note(text[-3000:]))
                else:
                    self.assertIsNotNone(self.section(text), self.note(text[-3000:]))


# ---------------------------------------------------------- AC-11, AC-12

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


class Ac11TwoSidedErrorNameTest(TwoSidedSandbox):

    def test_ac11_only_check_failure_is_failure_on_check(self):
        """Двусторонний прогон профиля в границе: `failed` с именем ошибки вне списка компонента, `error` и таймаут — «упал не на проверке» с видом; провал проверки — доказательство.

        Сценарий (подслучай — свежая задача, проект `junit-xml` со списком
        «провал проверки» `AssertionError`, сторона — из `random`): одна
        сторона падает проверкой (`assert`), другая — (а) `failed` с
        `ValueError`; (б) `error` `TypeError`; (в) таймаут прогона; (г)
        контроль — тоже проверкой. В (а)–(в): отказ прогона есть, исход
        этой стороны — не «утверждение»; в (а) и (б) он называет имя
        ошибки. В (г): отказов нет, обе стороны — «утверждение».

        Ловит мутацию: признак проверки — любой `outcome == failed` (как
        до задачи) — в (а) сторона «утверждение», отказа нет; классификатор
        не зовётся вовсе — в (г) отказ.
        """
        labels = {"base": two_sided.NEW_ON_BASE, "head": two_sided.OLD_ON_BRANCH}
        for case in ("failed_other", "error", "таймаут", "контроль"):
            with self.subTest(case=case, seed=self.seed):
                rel, name = self.py_rel(), self.py_name()
                project = self.junit_project({rel: [name]})
                side = self.rng.choice(("base", "head"))
                other = "head" if side == "base" else "base"
                kind = {"failed_other": "failed_other", "error": "error"}.get(case, "failed")
                result, address = self.two_sided(
                    project, rel, name, {side: kind, other: "failed"},
                    timeout_side=side if case == "таймаут" else None)
                text = self.side_text(result, address, labels[side])
                context = self.note(f"{case} на «{side}»: {result}")
                if case == "контроль":
                    self.assertEqual(result.refusals, [], context)
                    for label in labels.values():
                        self.assertEqual(self.side_text(result, address, label),
                                         two_sided.SIDE_ASSERTION, context)
                    continue
                self.assertTrue(result.refusals, context)
                self.assertNotEqual(text, two_sided.SIDE_ASSERTION, context)
                if case == "failed_other":
                    self.assertIn("ValueError", text, context)
                if case == "error":
                    self.assertIn("TypeError", text, context)


class Ac12TwoSidedRetryTest(TwoSidedSandbox):

    def test_ac12_passed_with_retry_is_side_failure_retry(self):
        """Двусторонний прогон профиля в границе: `passed` с повтором на любой стороне — сбой стороны с видом «повтор», не доказательство и не «зелёная».

        Сценарий (подслучай — сторона): проект `pult-vitest`; на одной
        стороне запись `pass` с `retry_count: 1`, на другой — провал
        проверки. Отказ прогона есть; исход стороны с повтором называет
        «повтор» и не равен «зелёная».

        Ловит мутацию: `passed` с повтором считается зелёным — исход
        стороны «зелёная», вида «повтор» нет.
        """
        labels = {"base": two_sided.NEW_ON_BASE, "head": two_sided.OLD_ON_BRANCH}
        for side in ("base", "head"):
            with self.subTest(side=side, seed=self.seed):
                rel, name = self.js_rel(), self.js_name()
                project = self.vitest_project({rel: [name]})
                other = "head" if side == "base" else "base"
                result, address = self.two_sided(project, rel, name,
                                                 {side: "retried", other: "failed"})
                text = self.side_text(result, address, labels[side])
                context = self.note(f"повтор на «{side}»: {result}")
                self.assertTrue(result.refusals, context)
                self.assertIn("повтор", text, context)
                self.assertNotEqual(text, two_sided.SIDE_GREEN, context)


# --------------------------------------------------------------- AC-13

class Ac13RetriedBaseRerunTest(MergeOutcomeSandbox):

    def test_ac13_retried_on_base_rerun_is_red_base(self):
        """Запись `passed` с повтором на перепрогоне базы — красная база: «нестабилен и на базе», находки нет.

        Сценарий: проект `pult-vitest`; тест базы зелёный в полном
        прогоне, на ветке красен все три прогона, на первом перепрогоне
        базы — `pass` с `retry_count: 1`, на втором — `pass`. Выход из
        `in_dev`: отказа гейта исходов нет, запись пройденного гейта несёт
        «нестабилен и на базе: <идентификатор>», задача в `verifying`.

        Ловит мутацию: на перепрогоне базы зелёным считается любой
        `passed` без сверки повторов — база зелёна трижды, отказ «… —
        сломан правкой».
        """
        rel, name = self.js_rel(), self.js_name()
        project = self.vitest_project({rel: [name, self.js_name()]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed", "retried", "passed"],
                                   "head": ["failed"]}
        rows, output = self.developer_advance(t)
        self.no_gate_refusal(rows, output)
        cid = self.case_id(project, rel, name)
        self.assertTrue(any(f"{FLAKY_ON_BASE}: {cid}" in d
                            for d in self.details(rows, PASSED_ACTION)),
                        self.explain(rows, output))
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))


# --------------------------------------------------------------- AC-14

class Ac14OutOfBoundsTest(TwoSidedSandbox):

    def test_ac14_test_profile_and_multi_component_keep_prior_results(self):
        """Вне границы (запись `test_profile`, запись из нескольких компонентов) — гейт мержа, пакет ревьювера и двусторонний прогон прежние.

        Сценарий (подслучай): (а) проект `test_profile` с `report:
        junit-xml`, задача сразу на `merge_gate`, тест базы на ветке красен
        — `approve`: полный набор не звался, записей гейта исходов нет,
        задача в `done`; (б) тот же вид проекта, задача в `review` без
        строк гейта по тексту — раздела «Изменённые утверждения тестов»
        нет, слов «гейт исходов» в пакете нет; (в) тот же вид проекта,
        двусторонний прогон: одна сторона `failed` с `ValueError`, другая —
        провал проверки — прежнее правило: отказов нет; (г) запись из двух
        компонентов `junit-xml`: `approve` и пакет ревьювера не несут
        записей и строк гейта исходов, полный набор на мерже не звался.

        Ловит мутацию: граница по `reported(profile)` без
        `from_components` — у `test_profile` гейт исходов на мерже прогнан и
        эскалирует, раздел пакета появился со строкой «не исполнялся»,
        двусторонний прогон отказывает по имени ошибки.
        """
        with self.subTest(case="мерж test_profile", seed=self.seed):
            project, _rel, _name = self.broken_case("test_profile")
            t = self.direct_task(project, "merge_gate")
            rows, output = self.approve(t)
            self.assertEqual(self.suite_calls, [], self.explain(rows, output))
            self.assertEqual(self.gate_rows(rows), [], self.explain(rows, output))
            self.assertEqual(self.state(t), "done", self.explain(rows, output))
        with self.subTest(case="пакет test_profile", seed=self.seed):
            project = self.junit_project({self.py_rel(): [self.py_name()]},
                                         test_profile=True)
            t = self.direct_task(project, "review")
            text = self.package(t)
            self.assertIsNone(self.section(text), self.note(text[-3000:]))
            self.assertNotIn("гейт исходов", text, self.note(text[-3000:]))
        with self.subTest(case="двусторонний test_profile", seed=self.seed):
            rel, name = self.py_rel(), self.py_name()
            project = self.junit_project({rel: [name]}, test_profile=True)
            side = self.rng.choice(("base", "head"))
            other = "head" if side == "base" else "base"
            result, _address = self.two_sided(project, rel, name,
                                              {side: "failed_other", other: "failed"})
            self.assertEqual(result.refusals, [], self.note(str(result)))
        with self.subTest(case="несколько компонентов", seed=self.seed):
            project = self.multi_project()
            t = self.direct_task(project, "merge_gate")
            rows, output = self.approve(t)
            self.assertEqual(self.suite_calls, [], self.explain(rows, output))
            self.assertEqual(self.gate_rows(rows), [], self.explain(rows, output))
            store.set_state(self.conn, t.id, "review", "operator",
                            expected_state=self.state(t), detail="сценарий")
            text = self.package(t)
            self.assertNotIn("гейт исходов", text, self.note(text[-3000:]))


if __name__ == "__main__":
    unittest.main()
