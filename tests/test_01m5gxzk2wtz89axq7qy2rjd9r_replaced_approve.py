"""Раздел SPEC «## Заменяемые тесты» на переходе `spec_writing -> spec_gate`, утверждение на `approve` гейта SPEC, `approved_replacements` и сверка на выходе из `tests_writing` (AC-1 — половина перехода, AC-4..AC-9, AC-11, AC-20, AC-24, AC-25).

Группа: долгоживущий
Красен до реализации: переход `spec_writing -> spec_gate` форму раздела не проверяет; `approve` раздел не сверяет — задача с непустым разделом уходит в `tests_writing` у артели, `test_profile`, компонента без `report`, проекта без профиля и артели без `test_profile`, при чужом компоненте, пути вне масок, отсутствующем файле, молчании git и матрице без идентификатора; записи «утверждены заменяемые тесты» и функции `mandate.approved_replacements` нет; выход из `tests_writing` не сверяет критерии утверждённой замены с покрытыми тестом, действия «переход отклонён: заменяемые тесты» и его класса нет. Зелены с рождения: канареечная задача уходит в `tests_writing` без записи (AC-9), `approve` артели и `test_profile` без раздела — как прежде (AC-20).

Стенд — настоящий git (`tests.sandbox.GitignoreCommittedRealGitSandbox`),
связка «запись проекта — профиль — ссылка документов — `approve`/`advance`
— журнал»: клон артели — корень песочницы с bare `origin`; учебные внешние
проекты — `tests.sandbox.make_project_repo` со своим `origin` и записью в
`targets.yaml` песочницы: компонент `pult-vitest` с `report` (граница гейта
исходов), `test_profile`, компонент без `report`, проект без профиля; отказ
решения профиля — запись артели без `test_profile`. В голове `main` проекта лежат файлы
тестов под масками `tests` компонента и файл вне масок. Задача заводится
строкой БД (`store.insert_task`), рабочая копия — `workspace.ensure`, SPEC —
в ссылку документов чекпоинтом шага; `approve` — `fsm.cmd_approve`, переход
— `fsm.cmd_advance`. Раннер Vitest (сухой сбор и прогон базы на выходе из
`tests_writing`) подменён шпионом `subprocess.Popen` без Node и сети: отчёт
пульта несёт по записи на тест переданных файлов с провалом проверки
(`AssertionError`); прочие вызовы — настоящий `subprocess`.

Имена проектов, компонентов, файлов, тестов, номера критериев — из
`random`; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (checkpoint, config, fsm, github_adapter,
                          project_profile, store, workspace)
from orchestrator.advance_gates import mandate, refusal_classes
from orchestrator.advance_gates.acceptance import in_outcome_bounds
from tests.sandbox import (ARTEL_TEST_PROFILE, GitignoreCommittedRealGitSandbox,
                           artel_target_entry, make_project_repo)

REAL_POPEN = subprocess.Popen
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
VITEST_BIN = project_profile.VITEST_BASE_ARGV[0]
VITEST_REPORT_ARGS = ["--reporter=default", "--reporter={pult_reporter}",
                      "--outputFile={path}"]
TESTS_MASK = "frontend/src/**/*.test.jsx"

REPLACED_ACTION = "утверждены заменяемые тесты"
DECLARED_ACTION = "объявлена смена поведения тестов"
REPLACEMENT_REFUSAL = "переход отклонён: заменяемые тесты"
APPROVE_REFUSED = "approve отклонён"
GUARD_REFUSED = "переход отклонён guard'ом"
SECTION = "Заменяемые тесты"
OUT_OF_BOUNDS = ("раздел «Заменяемые тесты» действует только у компонента с "
                 "отчётом; у проекта {name} — раздел «Меняемое поведение» или "
                 "мандат Оператора")
MATRIX_HEADERS = ("Что меняется", "Какое свойство сейчас держит",
                  "Остаётся ли свойство после изменения", "Чем покрыто после",
                  "Решение")

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def arg_value(args: list, flag: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


def matrix(cells) -> str:
    """Раздел матрицы неослабления: строка на ячейку «Что меняется»,
    свойство не остаётся — покрытие не требуется."""
    rows = "".join(f"| {cell} | свойство фикстуры | нет | не покрыто | ок |\n"
                   for cell in cells)
    return ("## Матрица неослабления\n\n| " + " | ".join(MATRIX_HEADERS)
            + " |\n|" + "---|" * len(MATRIX_HEADERS) + "\n" + rows + "\n")


class ReplacedSandbox(GitignoreCommittedRealGitSandbox):
    """Клон артели с `origin`; учебные проекты и задачи заводит сценарий;
    раннер Vitest — шпион `subprocess.Popen`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        fake = Path(tempfile.mkdtemp(prefix="artel-fake-")).resolve()
        self.addCleanup(shutil.rmtree, fake, True)
        self.installer = fake / f"install{self.word()}"
        self.installer.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.installer.chmod(0o755)
        self.vitest_version = next(
            f"{major}.0.0" for major, flags in
            project_profile.VITEST_VERSION_FLAGS.items()
            if flags.require_assertions)
        for patcher in (
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda *args, **kwargs: (True, "")),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda *args, **kwargs: None),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: []),
                mock.patch.object(subprocess, "Popen", self.spy_popen)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        config.TARGETS.write_text("targets:\n" + artel_target_entry(),
                                  encoding="utf-8")
        self.clones = {config.DEFAULT_TARGET: self.root}
        self.conn = store.db()

    # --- входы ----------------------------------------------------------

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def vitest_name(self) -> str:
        return f"{self.word()} > {self.word(4)} {self.word(5)}"

    # --- шпион Vitest ---------------------------------------------------

    def answer(self, code: int, out: str, args, kwargs):
        script = f"import sys; sys.stdout.write({out!r}); sys.exit({code})"
        return REAL_POPEN([sys.executable, "-c", script], *args, **kwargs)

    def spy_popen(self, argv, *args, **kwargs):
        if not isinstance(argv, (list, tuple)) or not argv:
            return REAL_POPEN(argv, *args, **kwargs)
        parts = [str(a) for a in argv]
        cwd = Path(str(kwargs.get("cwd") or os.getcwd()))
        if parts[0] == str(self.installer):
            (cwd / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
            return self.answer(0, "", args, kwargs)
        if parts[0] != VITEST_BIN:
            return REAL_POPEN(argv, *args, **kwargs)
        if parts[1:2] == ["--version"]:
            return self.answer(0, f"vitest/{self.vitest_version}\n", args, kwargs)
        items = []
        for part in parts[1:]:
            path = Path(part) if os.path.isabs(part) else cwd / part
            found = ([p for p in sorted(path.rglob("*.test.jsx"))]
                     if path.is_dir() else
                     [path] if path.is_file() and path.name.endswith(".test.jsx")
                     else [])
            for file in found:
                for name in guard_names(file.read_text(encoding="utf-8")):
                    items.append({"file": os.path.relpath(file, cwd),
                                  "name": name, "state": "fail", "mode": "run",
                                  "fails": False, "retry_count": 0,
                                  "error_name": "AssertionError",
                                  "timeout": False, "hook": None,
                                  "duration_ms": 3})
        out = arg_value(parts, "--outputFile")
        if out:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(json.dumps({"tests": items}), encoding="utf-8")
        return self.answer(1 if items else 0, f"{len(items)} tests\n", args, kwargs)

    # --- проекты --------------------------------------------------------

    def append_entry(self, text: str) -> None:
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + text,
                                  encoding="utf-8")

    def vitest_fields(self) -> dict:
        return {"command": flow(project_profile.VITEST_BASE_ARGV),
                "report": "pult-vitest",
                "report_args": flow(VITEST_REPORT_ARGS),
                "select": flow([f"--sel{self.word()}", "{tests}"]),
                "install": flow([str(self.installer)]),
                "tests": flow([TESTS_MASK]),
                "plank_layout": f"frontend/src/.pv{self.word(5)}/<id>",
                "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
                "weakening_scope": flow(["frontend/src/**"]),
                "mutation_claim_scope": flow(["frontend/src/**"]),
                "failure_errors": flow(["AssertionError"])}

    def component_lines(self, comp: str, fields: dict) -> list:
        lines = [f"      {comp}:\n"]
        lines += [f"        {key}: {value}\n" for key, value in fields.items()]
        if fields.get("report") == "pult-vitest":
            lines += ["        tools:\n",
                      f'          vitest: "{self.vitest_version}"\n']
        return lines

    def project(self, kind: str) -> SimpleNamespace:
        """Учебный проект: `vitest` — компонент `pult-vitest` с `report`
        (в границе); `tp` — запись `test_profile`; `noreport` — компонент
        без `report`; `bare` — без профиля; `artel` — артель (запись
        песочницы). Голова `main` учебного проекта: файлы тестов под
        масками и файл вне масок."""
        if kind == "artel":
            return SimpleNamespace(name=config.DEFAULT_TARGET, comp="default",
                                   kind=kind, tests=[], outside="")
        name, comp = f"p{self.word()}", f"c{self.word()}"
        body = ""
        if kind == "vitest":
            body = "".join(["    components:\n"]
                           + self.component_lines(comp, self.vitest_fields()))
        elif kind == "noreport":
            body = "".join(["    components:\n"] + self.component_lines(comp, {
                "command": flow(["python3", "-m", "pytest"]),
                "long_lived_dir": "tests",
                "long_lived_name": "test_<id>_<name>.py",
                "weakening_scope": flow(["frontend/src/**"]),
                "mutation_claim_scope": flow(["tests/**"]),
                "tests": flow([TESTS_MASK]),
                "plank_layout": f".pn{self.word(5)}/<id>"}))
        elif kind == "tp":
            body = ARTEL_TEST_PROFILE
        self.append_entry(ENTRY_HEAD.format(name=name) + body)
        clone = make_project_repo(name)
        tests = [f"frontend/src/{self.word(5)}/{self.word()}.test.jsx"
                 for _ in range(self.rng.randint(1, 3))]
        outside = f"lib{self.word(4)}/{self.word()}.test.jsx"
        files = {"package.json": '{"name": "web"}\n',
                 "vitest.config.js": "export default {}\n",
                 "package-lock.json": json.dumps({"lockfileVersion": 3}) + "\n",
                 "frontend/src/app.jsx": "export const app = 1;\n",
                 outside: "it('вне масок', () => {});\n"}
        files.update({rel: f"it('тест {self.word()}', () => {{}});\n"
                      for rel in tests})
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.clones[name] = clone
        decision = project_profile.decide(name)
        if kind == "bare":
            self.assertTrue(decision.skip and decision.profile is None,
                            self.note(f"фикстура: {decision}"))
        else:
            self.assertIsNotNone(decision.profile,
                                 self.note(f"фикстура {kind}: {decision}"))
            self.assertEqual(kind == "vitest", in_outcome_bounds(decision.profile),
                             self.note(f"фикстура {kind}: граница {decision}"))
        return SimpleNamespace(name=name, comp=comp, kind=kind, tests=tests,
                               outside=outside, clone=clone)

    def replaced_id(self, project, rel: str | None = None,
                    comp: str | None = None) -> str:
        path = rel or self.rng.choice(project.tests or
                                      [f"frontend/src/{self.word()}.test.jsx"])
        return project_profile.test_id(comp or project.comp, path,
                                       self.vitest_name())

    # --- SPEC ------------------------------------------------------------

    def spec(self, task_id: str, criteria: int, lines=None, matrix_ids=None,
             behavior=None) -> str:
        """SPEC фикстуры: критерии `1..criteria`; `lines` — строки раздела
        «Заменяемые тесты» (`None` — раздела нет); `matrix_ids` — ячейки
        «Что меняется» матрицы (по умолчанию — каждый идентификатор строк в
        одинарных обратных кавычках); `behavior` — строки «Меняемое
        поведение»."""
        items = "\n\n".join(f"AC-{n}. Критерий фикстуры номер {n}."
                            for n in range(1, criteria + 1))
        text = ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
                "status: ready\nschema_version: 5\nzones: frontend/src/app.jsx\n"
                "budget_usd: 30\n---\n\n# SPEC: фикстура заменяемых тестов\n\n"
                "## Контекст\n\nФикстура песочницы.\n\n## Требования\n\n"
                f"1. Требование фикстуры.\n\n## Критерии приёмки\n\n{items}\n\n")
        if behavior is not None:
            text += ("## Меняемое поведение\n\nСмена ожидания фикстуры.\n\n"
                     + "\n".join(behavior) + "\n\n")
        if lines is not None:
            text += f"## {SECTION}\n\n" + "\n".join(lines) + "\n\n"
            cells = matrix_ids
            if cells is None:
                cells = [f"`{line.split('`')[1]}`" for line in lines
                         if line.count("`") >= 2]
            if cells:
                text += matrix(cells)
        return text + "## Не входит\n\nНичего.\n"

    def line(self, test_id: str, n: int) -> str:
        return f"- `{test_id}` → AC-{n}: замена по требованию {self.word()}"

    # --- задачи ---------------------------------------------------------

    def task(self, project, spec_of, state: str = "spec_gate",
             canary: bool = False) -> SimpleNamespace:
        """Задача проекта в `state`: SPEC (`spec_of(id)`) в ссылке
        документов чекпоинтом шага."""
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, f"Фикстура замен {self.word()}",
                          state, branch, project.name, 25.0, is_canary=canary)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=project.name, wt=Path(wt), project=project)
        t.docs = config.PROJECTS / project.name / TASKS_DIR / tid
        self.put_spec(t, spec_of(tid))
        return t

    def put_spec(self, t, text: str, role: str = "analyst") -> None:
        """SPEC.md — в ссылку документов чекпоинтом шага; копия — в
        каталоге документов и в `config.TASKS` (дисковый путь чтения)."""
        t.spec = text
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(text, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, t.id, role)
        store.record_fixation(self.conn, t.id)
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(text, encoding="utf-8")
        disk = config.TASKS / t.id
        disk.mkdir(parents=True, exist_ok=True)
        (disk / "SPEC.md").write_text(text, encoding="utf-8")

    def call(self, fn, *args) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\nSystemExit: {exc.code}")
        return buf.getvalue()

    def approve(self, t) -> str:
        store.record_fixation(self.conn, t.id)
        return self.call(fsm.cmd_approve, t.id)

    def state(self, t) -> str:
        return store.get_task(self.conn, t.id)["state"]

    def rows(self, t) -> list:
        return [(r["action"], r["detail"] or "")
                for r in store.task_steps(self.conn, t.id)]

    def details(self, t, action: str) -> list:
        return [detail for act, detail in self.rows(t) if act == action]

    def journal(self, t) -> str:
        return "\n".join(f"{act} | {detail}" for act, detail in self.rows(t))

    def assert_soft_refusal(self, t, out: str, named: str = "") -> str:
        """Задача на `spec_gate`, непустая запись «approve отклонён»
        (несёт `named`), записи `REPLACED_ACTION` нет."""
        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal(t)}")
        self.assertEqual(self.state(t), "spec_gate", context)
        refused = [d for d in self.details(t, APPROVE_REFUSED) if d.strip()]
        self.assertTrue(refused, context)
        if named:
            self.assertIn(named, refused[-1], context)
        self.assertEqual(self.details(t, REPLACED_ACTION), [], context)
        return refused[-1]

    def approved(self, t) -> dict:
        """`approved_replacements` задачи с номером критерия числом."""
        found = mandate.approved_replacements(self.conn, t.id)
        return {key: int(str(value)) for key, value in found.items()}


def guard_names(text: str) -> list:
    """Имена тестов `it('…')` файла фикстуры (без разбора guard)."""
    names, start = [], 0
    while True:
        at = text.find("it('", start)
        if at < 0:
            return names
        end = text.find("'", at + 4)
        names.append(text[at + 4:end])
        start = end + 1


# ---------------------------------------------------------------- AC-1

class Ac1TransitionFormTest(ReplacedSandbox):

    def test_ac1_spec_writing_advance_names_each_violation(self):
        """Каждое нарушение формы раздела отказывает переходу `spec_writing -> spec_gate` записью guard, называющей свою строку.

        Сценарий: проект `pult-vitest`, задача в `spec_writing`, SPEC в
        ссылке документов со строкой нарушения (идентификатор не в обратных
        кавычках; не той формы; нет `→ AC-<n>:`; нет критерия; пустая
        причина; повтор; строка не с «- ») рядом с годной строкой.
        `advance` оставляет задачу в `spec_writing`, запись «переход
        отклонён guard'ом» называет идентификатор строки нарушения.
        Контроль: SPEC только с годными строками уходит на `spec_gate`.

        Ловит мутацию: проверка формы раздела подключена к CLI, но не к
        `check_content`, которым зовёт guard переход, — задача уходит на
        `spec_gate`.
        """
        project = self.project("vitest")
        good_id = self.replaced_id(project)
        control = self.task(project, lambda tid: self.spec(
            tid, 2, [self.line(good_id, 1)]), state="spec_writing")
        out = self.call(fsm.cmd_advance, control.id)
        self.assertEqual(self.state(control), "spec_gate",
                         self.note(f"контроль:\n{out}\n{self.journal(control)}"))
        for case in ("без кавычек", "не та форма", "нет стрелки",
                     "нет критерия", "пустая причина", "повтор", "не с «- »"):
            with self.subTest(case=case, seed=self.seed):
                good, bad = self.replaced_id(project), self.replaced_id(project)
                named = bad
                lines = [self.line(good, 1)]
                if case == "без кавычек":
                    lines.append(f"- {bad} → AC-1: причина {self.word()}")
                elif case == "не та форма":
                    named = bad.split("::", 1)[0]
                    lines.append(f"- `{named}` → AC-1: причина {self.word()}")
                elif case == "нет стрелки":
                    lines.append(f"- `{bad}` причина {self.word()}")
                elif case == "нет критерия":
                    lines.append(self.line(bad, 2 + self.rng.randint(1, 30)))
                elif case == "пустая причина":
                    lines.append(f"- `{bad}` → AC-1:")
                elif case == "повтор":
                    lines += [self.line(bad, 1), self.line(bad, 2)]
                else:
                    lines.append(f"* `{bad}` → AC-1: причина {self.word()}")
                t = self.task(project, lambda tid, lines=lines: self.spec(
                    tid, 2, lines, matrix_ids=[f"`{good}`"]),
                    state="spec_writing")
                out = self.call(fsm.cmd_advance, t.id)
                context = self.note(f"{case}:\n{out}\n{self.journal(t)}")
                self.assertEqual(self.state(t), "spec_writing", context)
                refused = self.details(t, GUARD_REFUSED)
                self.assertTrue(refused and named in refused[-1], context)


# ---------------------------------------------------------------- AC-4

class Ac4ProfileBoundsTest(ReplacedSandbox):

    def test_ac4_out_of_bounds_profiles_refused_with_text(self):
        """Профиль вне границы гейта исходов — мягкий отказ `approve` с текстом «раздел «Заменяемые тесты» действует только у компонента с отчётом; у проекта <проект> — …».

        Сценарий: по задаче на `spec_gate` у артели, у проекта с записью
        `test_profile`, у компонента без `report` и у проекта без профиля
        тестов (решение `skip`); SPEC с непустым годным разделом и матрицей.
        Задача остаётся на `spec_gate`, запись «approve отклонён» несёт
        текст отказа с именем проекта, записи «утверждены заменяемые
        тесты» нет.

        Ловит мутацию: граница проверяется только отказом решения профиля
        (`decision.refusal`), а не `in_outcome_bounds`, — `test_profile` и
        компонент без `report` проходят; решение `skip` (профиля нет)
        принимается за «сверять нечего» — проект без профиля проходит.
        """
        for kind in ("artel", "tp", "noreport", "bare"):
            with self.subTest(kind=kind, seed=self.seed):
                project = self.project(kind)
                cid = project_profile.test_id(
                    f"c{self.word()}", f"frontend/src/{self.word()}.test.jsx",
                    self.vitest_name())
                t = self.task(project, lambda tid, cid=cid: self.spec(
                    tid, 1, [self.line(cid, 1)]))
                out = self.approve(t)
                self.assert_soft_refusal(t, out, OUT_OF_BOUNDS.format(
                    name=project.name))

    def test_ac4_profile_decision_refusal_carries_reason(self):
        """Решение профиля с отказом (у записи артели нет `test_profile`) — мягкий отказ `approve` с причиной решения.

        Сценарий: запись артели в `targets.yaml` песочницы без поля
        `test_profile` — контекст разрешён, `project_profile.decide`
        отказывает; задача артели на `spec_gate`, SPEC с непустым разделом.
        Задача остаётся на `spec_gate`, запись «approve отклонён» несёт
        `decide(<артель>).refusal`, записи «утверждены заменяемые тесты» нет.

        Ловит мутацию: отказ решения профиля читается как «вне границы» —
        текст отказа о границе без причины решения; отказ решения
        пропускается — задача уходит в `tests_writing`.
        """
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry().replace(ARTEL_TEST_PROFILE, ""),
            encoding="utf-8")
        project = self.project("artel")
        reason = project_profile.decide(project.name).refusal
        self.assertTrue(reason, self.note("фикстура: решение без отказа"))
        cid = project_profile.test_id(f"c{self.word()}",
                                      f"frontend/src/{self.word()}.test.jsx",
                                      self.vitest_name())
        t = self.task(project, lambda tid: self.spec(tid, 1, [self.line(cid, 1)]))
        self.assert_soft_refusal(t, self.approve(t), reason)


# ---------------------------------------------------------------- AC-5

class Ac5InBoundsRefusalsTest(ReplacedSandbox):

    def test_ac5_each_check_refuses_softly(self):
        """В границе: чужой компонент, путь вне масок `tests`, файла нет в `main`, git молчит, матрица без идентификатора — мягкий отказ, записи нет.

        Сценарий: проект `pult-vitest`, по задаче на случай; раздел несёт
        годную строку о существующем файле под масками и строку случая:
        (а) компонент идентификатора — другое имя; (б) путь — файл вне
        масок, лежащий в `main`; (в) путь под масками, которого в `main`
        нет; (г) годный раздел, но `main` нет ни в клоне, ни в его
        `origin` (git не отвечает); (д) годный раздел, матрица называет
        только другой идентификатор. Задача остаётся на `spec_gate`,
        непустая запись «approve отклонён», записи «утверждены заменяемые
        тесты» нет.

        Ловит мутацию: компонент идентификатора не сверяется с компонентом
        профиля — (а) проходит; маски `tests` не проверяются, только
        наличие файла — (б) проходит; наличие файла в `main` не
        проверяется — (в) проходит; молчание git читается как «файл есть» —
        (г) проходит; `matrix_refusals` зовётся без `test_ids` — (д)
        проходит.
        """
        project = self.project("vitest")
        for case in ("чужой компонент", "вне масок", "нет в main",
                     "git молчит", "матрица"):
            with self.subTest(case=case, seed=self.seed):
                good = self.replaced_id(project, rel=project.tests[0])
                cells = None
                if case == "чужой компонент":
                    bad = self.replaced_id(project, comp=f"z{self.word()}")
                elif case == "вне масок":
                    bad = self.replaced_id(project, rel=project.outside)
                elif case == "нет в main":
                    bad = self.replaced_id(
                        project, rel=f"frontend/src/{self.word()}/{self.word()}"
                                     f".test.jsx")
                else:
                    bad = self.replaced_id(project, rel=project.tests[-1])
                if case == "матрица":
                    cells = [f"`{good}`", f"`{self.replaced_id(project)}`"]
                lines = [self.line(good, 1), self.line(bad, 2)]
                t = self.task(project, lambda tid, lines=lines, cells=cells:
                              self.spec(tid, 2, lines, matrix_ids=cells))
                if case == "git молчит":
                    moved = f"moved-{self.word()}"
                    origin = config.PROJECTS / project.name / "origin.git"
                    self.git("-C", str(project.clone), "branch", "-m",
                             config.MAIN_BRANCH, moved)
                    self.git("-C", str(project.clone), "update-ref", "-d",
                             f"refs/remotes/origin/{config.MAIN_BRANCH}")
                    self.git("-C", str(origin), "branch", "-m",
                             config.MAIN_BRANCH, moved)
                try:
                    out = self.approve(t)
                    self.assert_soft_refusal(t, out)
                finally:
                    if case == "git молчит":
                        self.git("-C", str(project.clone), "branch", "-m",
                                 moved, config.MAIN_BRANCH)
                        self.git("-C", str(origin), "branch", "-m", moved,
                                 config.MAIN_BRANCH)


# ---------------------------------------------------------------- AC-6, AC-7

class Ac6ApprovedRecordTest(ReplacedSandbox):

    def approved_task(self, criteria: int = 3) -> tuple:
        project = self.project("vitest")
        pairs = {}
        for rel in project.tests:
            pairs[self.replaced_id(project, rel=rel)] = \
                self.rng.randint(1, criteria)
        lines = [self.line(cid, n) for cid, n in pairs.items()]
        t = self.task(project, lambda tid: self.spec(tid, criteria, lines))
        return t, pairs, lines

    def test_ac6_approve_journals_parsed_lines_and_prints_them(self):
        """Годный раздел: `approve` уходит в `tests_writing`, пишет одну запись «утверждены заменяемые тесты» — строка на пункт — и печатает её; `approved_replacements` даёт {идентификатор: номер критерия}.

        Сценарий: проект `pult-vitest`, один–три файла тестов в `main` под
        масками, по пункту на файл с номером критерия из зерна, матрица
        называет каждый идентификатор. Запись ровно одна; её деталь — по
        непустой строке на пункт, каждая несёт идентификатор и `AC-<n>`
        своего пункта; вывод несёт «[<id>] утверждены заменяемые тесты:» и
        каждую строку детали после него; `mandate.REPLACED_TESTS_ACTION` —
        это действие.

        Ловит мутацию: запись пишется на каждый пункт — записей несколько;
        деталь — сырой текст раздела со свободным текстом — строк больше,
        чем пунктов; печать без строк пунктов — строки детали нет в
        выводе после заголовка; `approved_replacements` отдаёт номер из
        другого пункта — словарь иной.
        """
        t, pairs, _lines = self.approved_task()
        out = self.approve(t)
        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal(t)}")
        self.assertEqual(mandate.REPLACED_TESTS_ACTION, REPLACED_ACTION, context)
        self.assertEqual(self.state(t), "tests_writing", context)
        records = self.details(t, REPLACED_ACTION)
        self.assertEqual(len(records), 1, context)
        detail = [line for line in records[0].splitlines() if line.strip()]
        self.assertEqual(len(detail), len(pairs), context)
        for cid, n in pairs.items():
            own = [line for line in detail if cid in line]
            self.assertEqual(len(own), 1, context)
            self.assertIn(f"AC-{n}", own[0], context)
        header = f"[{t.id}] {REPLACED_ACTION}:"
        self.assertIn(header, out, context)
        tail = out[out.index(header):]
        for line in detail:
            self.assertIn(line.strip(), tail, context)
        self.assertEqual(self.approved(t), pairs, context)

    def test_ac7_section_edit_after_approve_does_not_change_result(self):
        """Правка раздела в SPEC.md после `approve` не меняет `approved_replacements`; у задачи без записи результат пуст.

        Сценарий: годный раздел, `approve`; затем SPEC в ссылке документов
        и на диске получает другой раздел (другой идентификатор, другой
        номер) — `approved_replacements` прежний. Задача того же проекта
        без раздела после `approve` и задача без `approve` — пустой словарь.

        Ловит мутацию: `approved_replacements` разбирает текущий SPEC, а не
        деталь записи, — после правки словарь иной; задача без записи
        получает разбор SPEC — словарь непуст.
        """
        t, pairs, _lines = self.approved_task()
        out = self.approve(t)
        self.assertEqual(self.state(t), "tests_writing", self.note(out))
        other = self.replaced_id(t.project, rel=t.project.tests[0])
        self.put_spec(t, self.spec(t.id, 3, [self.line(other, 3)]))
        self.assertEqual(self.approved(t), pairs, self.note(self.journal(t)))
        bare = self.task(t.project, lambda tid: self.spec(tid, 1))
        self.assertEqual(self.approved(bare), {}, self.note("без approve"))
        out = self.approve(bare)
        self.assertEqual(self.state(bare), "tests_writing", self.note(out))
        self.assertEqual(self.approved(bare), {}, self.note(self.journal(bare)))


# ---------------------------------------------------------------- AC-8

class Ac8RevokeTest(ReplacedSandbox):

    def test_ac8_repeated_approve_without_section_revokes(self):
        """Повторный `approve` без раздела или с пустым разделом после `approve` с разделом пишет запись с пустой деталью; `approved_replacements` пуст.

        Сценарий: годный раздел, `approve` (запись с деталью); задача
        возвращена на `spec_gate`, SPEC в ссылке документов — без раздела
        либо с заголовком раздела без пунктов; `approve`. Вторая запись
        «утверждены заменяемые тесты» есть, её деталь пуста,
        `approved_replacements` — пустой словарь.

        Ловит мутацию: отзыв не пишется, когда раздела нет, —
        `approved_replacements` отдаёт прежние пары; `approved_replacements`
        берёт последнюю НЕпустую запись — прежние пары.
        """
        for case in ("без раздела", "пустой раздел"):
            with self.subTest(case=case, seed=self.seed):
                project = self.project("vitest")
                cid = self.replaced_id(project, rel=project.tests[0])
                t = self.task(project, lambda tid: self.spec(
                    tid, 2, [self.line(cid, 2)]))
                out = self.approve(t)
                self.assertEqual(self.approved(t), {cid: 2},
                                 self.note(f"{out}\n{self.journal(t)}"))
                store.update_task(self.conn, t.id, state="spec_gate")
                text = self.spec(t.id, 2)
                if case == "пустой раздел":
                    text = text.replace("## Не входит",
                                        f"## {SECTION}\n\n## Не входит")
                self.put_spec(t, text)
                out = self.approve(t)
                context = self.note(f"{case}:\n{out}\n{self.journal(t)}")
                records = self.details(t, REPLACED_ACTION)
                self.assertEqual(len(records), 2, context)
                self.assertEqual(records[-1].strip(), "", context)
                self.assertEqual(self.approved(t), {}, context)


# ---------------------------------------------------------------- AC-9

class Ac9CanaryTest(ReplacedSandbox):

    def test_ac9_canary_task_no_check_no_record(self):
        """Канареечная задача: `approve` раздел не сверяет и записи не пишет.

        Сценарий: канареечная задача проекта `pult-vitest` на `spec_gate`,
        раздел называет идентификатор чужого компонента, матрица его не
        называет (у обычной задачи — отказ). `approve` переводит задачу в
        `tests_writing`, записи «утверждены заменяемые тесты» нет.

        Ловит мутацию: признак канарейки не проверяется — отказ по
        компоненту и матрице, задача остаётся на `spec_gate`; запись пишется
        и канарейке — запись есть.
        """
        project = self.project("vitest")
        cid = self.replaced_id(project, comp=f"z{self.word()}")
        t = self.task(project, lambda tid: self.spec(
            tid, 1, [self.line(cid, 1)], matrix_ids=["`другое`"]), canary=True)
        out = self.approve(t)
        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal(t)}")
        self.assertEqual(self.state(t), "tests_writing", context)
        self.assertEqual(self.details(t, REPLACED_ACTION), [], context)


# ---------------------------------------------------------------- AC-11

class Ac11PlankGateTest(ReplacedSandbox):

    def plank_jsx(self, tested, manual=()) -> str:
        body = "".join(f"it('AC-{n}: кнопка {self.word()}', () => "
                       f"{{ expect(1).toBe(2); }});\n" for n in tested)
        marks = "".join(f"// AC-{n}: manual — проверит Оператор {self.word()}\n"
                        for n in manual)
        return ("// Группа: разовый\n"
                f"// Красен до реализации: фикстура {self.word()}.\n"
                "import { expect, it } from 'vitest';\n\n" + marks + body)

    def advance(self, t) -> tuple:
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        store.journal(self.conn, t.id, "test_author", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, t.id, "test_author")
        before = len(store.task_steps(self.conn, t.id))
        out = self.call(fsm.cmd_advance, t.id)
        rows = [(r["action"], r["detail"] or "")
                for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, out

    def test_ac11_replaced_criterion_without_plank_test_refused(self):
        """Критерий утверждённой замены без теста планки — отказ выхода из `tests_writing` действием «переход отклонён: заменяемые тесты» с деталью по строке на нарушение; класс — «чинит роль».

        Сценарий: проект `pult-vitest`, SPEC с тремя критериями и разделом,
        где два идентификатора сопоставлены критериям `AC-2` и `AC-3`,
        `approve` (запись замен). Планка: тест `AC-1`, у `AC-2` и `AC-3` —
        пометки `// AC-n: manual`. `advance` оставляет задачу в
        `tests_writing`; запись отказа — строка «заменяемый тест <ид>
        сопоставлен AC-<n>, а у AC-<n> нет теста планки» на каждый из двух;
        `refusal_classes.REPLACEMENT_REFUSAL_ACTION` — это действие,
        `refusal_class` относит его к «чинит роль». Контроль: та же задача
        с тестами `AC-1..AC-3` уходит в `in_dev` без такой записи.

        Ловит мутацию: сверка берёт критерии из пометок, а не покрытых
        тестом, — `manual` засчитан, отказа нет; сверка стоит после
        прогона базы и отказывает по первому нарушению — строка одна;
        действие не внесено в перечень классов — класс «чинит Оператор».
        """
        project = self.project("vitest")
        ids = {self.replaced_id(project, rel=project.tests[0]): 2,
               self.replaced_id(project, rel=project.tests[-1]): 3}
        lines = [self.line(cid, n) for cid, n in ids.items()]
        t = self.task(project, lambda tid: self.spec(tid, 3, lines))
        out = self.approve(t)
        self.assertEqual(self.state(t), "tests_writing",
                         self.note(f"approve:\n{out}\n{self.journal(t)}"))
        t.docs.mkdir(parents=True, exist_ok=True)
        plank = t.docs / PLANK_DIR
        plank.mkdir(parents=True, exist_ok=True)
        (plank / f"a{self.word()}.test.jsx").write_text(
            self.plank_jsx((1,), manual=(2, 3)), encoding="utf-8")
        rows, out = self.advance(t)
        context = self.note(f"вывод:\n{out[-3000:]}\nзаписи: {rows}")
        self.assertEqual(refusal_classes.REPLACEMENT_REFUSAL_ACTION,
                         REPLACEMENT_REFUSAL, context)
        self.assertEqual(refusal_classes.refusal_class(REPLACEMENT_REFUSAL),
                         refusal_classes.ROLE_FIXES, context)
        self.assertEqual(self.state(t), "tests_writing", context)
        found = [d for a, d in rows if a == REPLACEMENT_REFUSAL]
        self.assertTrue(found, context)
        for cid, n in ids.items():
            self.assertIn(f"заменяемый тест {cid} сопоставлен AC-{n}, а у "
                          f"AC-{n} нет теста планки", found[-1].splitlines(),
                          context)

        good = self.task(project, lambda tid: self.spec(tid, 3, lines))
        out = self.approve(good)
        self.assertEqual(self.state(good), "tests_writing", self.note(out))
        plank = good.docs / PLANK_DIR
        plank.mkdir(parents=True, exist_ok=True)
        (plank / f"a{self.word()}.test.jsx").write_text(
            self.plank_jsx((1, 2, 3)), encoding="utf-8")
        rows, out = self.advance(good)
        context = self.note(f"контроль:\n{out[-3000:]}\nзаписи: {rows}")
        self.assertEqual([d for a, d in rows if a == REPLACEMENT_REFUSAL], [],
                         context)
        self.assertEqual(self.state(good), "in_dev", context)


# ---------------------------------------------------------------- AC-20

class Ac20UnchangedTest(ReplacedSandbox):

    def test_ac20_without_section_approve_as_before(self):
        """У артели и у записи `test_profile` SPEC без раздела: `approve` уходит в `tests_writing`, вывод и журнал без следа раздела «Заменяемые тесты».

        Сценарий: задача артели и задача проекта с `test_profile` на
        `spec_gate`, SPEC без раздела. `approve` переводит каждую в
        `tests_writing`; записи «утверждены заменяемые тесты» нет (и отзыва
        тоже), ни вывод, ни журнал не называют раздел.

        Ловит мутацию: отзыв пишется при отсутствии раздела всегда, а не
        только после прежней записи, — запись с пустой деталью есть;
        сверка раздела зовётся и без раздела и печатает строку о нём.
        """
        for kind in ("artel", "tp"):
            with self.subTest(kind=kind, seed=self.seed):
                project = self.project(kind)
                t = self.task(project, lambda tid: self.spec(tid, 2))
                out = self.approve(t)
                context = self.note(f"{kind}:\n{out}\n{self.journal(t)}")
                self.assertEqual(self.state(t), "tests_writing", context)
                self.assertEqual(self.details(t, REPLACED_ACTION), [], context)
                self.assertNotIn("аменяемые тесты", out + self.journal(t),
                                 context)


# ---------------------------------------------------------------- AC-24

class Ac24NoPartialRecordsTest(ReplacedSandbox):

    def artel_base(self) -> tuple:
        """База артели на `main`: файл тестов с методом, чьё утверждение
        несёт литерал `1`; строка «Меняемое поведение» о нём."""
        cls = f"Fx{self.word().capitalize()}Test"
        rel = f"tests/test_fx_{self.word()}.py"
        method = f"test_{self.word()}"
        (self.root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "import unittest\n\nimport app\n\n\n"
            f"class {cls}(unittest.TestCase):\n\n"
            f"    def {method}(self):\n"
            f'        """Фикстура.\n\n        Ловит мутацию: фикстура.\n        """\n'
            "        self.assertEqual(app.VALUE, 1)\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база артели")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        return [f"- `{rel}::{cls}::{method}`: `1` → `2` (требование 1)"]

    def test_ac24_refused_approve_writes_neither_record(self):
        """Отказ `approve` из-за раздела «Заменяемые тесты» не оставляет ни записи объявления смены поведения, ни записи замен.

        Сценарий: (а) задача артели, SPEC с годным разделом «Меняемое
        поведение» (метод и литерал есть в `main`) и непустым разделом
        «Заменяемые тесты»; (б) проект `pult-vitest`, годная форма и
        граница, матрица не называет идентификатор. В обоих — задача на
        `spec_gate`, непустая запись «approve отклонён», записей «объявлена
        смена поведения тестов» и «утверждены заменяемые тесты» нет.
        Контроль: задача артели с тем же «Меняемое поведение» без раздела
        замен уходит в `tests_writing` с записью объявления.

        Ловит мутацию: запись «объявлена смена поведения тестов» пишется
        сразу после её сверки, до сверки раздела замен, — (а) несёт запись
        объявления.
        """
        behavior = self.artel_base()
        artel = self.project("artel")
        control = self.task(artel, lambda tid: self.spec(tid, 1,
                                                          behavior=behavior))
        out = self.approve(control)
        context = self.note(f"контроль:\n{out}\n{self.journal(control)}")
        self.assertEqual(self.state(control), "tests_writing", context)
        self.assertEqual(len(self.details(control, DECLARED_ACTION)), 1, context)

        cid = project_profile.test_id(f"c{self.word()}",
                                      f"frontend/src/{self.word()}.test.jsx",
                                      self.vitest_name())
        t = self.task(artel, lambda tid: self.spec(
            tid, 1, [self.line(cid, 1)], behavior=behavior))
        out = self.assert_soft_refusal(t, self.approve(t))
        self.assertEqual(self.details(t, DECLARED_ACTION), [],
                         self.note(f"артель:\n{out}\n{self.journal(t)}"))

        project = self.project("vitest")
        cid = self.replaced_id(project, rel=project.tests[0])
        t = self.task(project, lambda tid: self.spec(
            tid, 1, [self.line(cid, 1)], matrix_ids=[f"`{self.word()}`"]))
        out = self.assert_soft_refusal(t, self.approve(t))
        self.assertEqual(self.details(t, DECLARED_ACTION), [],
                         self.note(f"проект:\n{out}\n{self.journal(t)}"))


# ---------------------------------------------------------------- AC-25

class Ac25DocsRefPathTest(ReplacedSandbox):

    def test_ac25_gate_edit_with_violation_refused_and_round_trip(self):
        """Ссылка документов: SPEC, прошедший переход на `spec_gate` и исправленный на гейте строкой с нарушением формы, — мягкий отказ с текстом guard; годный раздел даёт тот же словарь туда и обратно.

        Сценарий: проект `pult-vitest`, задача в `spec_writing` с годным
        SPEC — `advance` уводит её на `spec_gate`. Правка на гейте в ссылке
        документов: строка без `→ AC-<n>:` либо повтор идентификатора.
        `approve` оставляет задачу на `spec_gate`, запись «approve
        отклонён» называет идентификатор строки, записи замен нет. Затем
        годный раздел — `approve` уходит в `tests_writing`,
        `approved_replacements` равен словарю {идентификатор: номер} строк
        раздела.

        Ловит мутацию: `approve` берёт SPEC с диска, а не из ссылки
        документов, — правка на гейте не видна, `approve` проходит;
        сверка формы на `approve` пропущена (форма считается проверенной
        переходом) — `approve` проходит с нарушением.
        """
        project = self.project("vitest")
        for case in ("нет стрелки", "повтор"):
            with self.subTest(case=case, seed=self.seed):
                good = self.replaced_id(project, rel=project.tests[0])
                t = self.task(project, lambda tid: self.spec(
                    tid, 2, [self.line(good, 1)]), state="spec_writing")
                out = self.call(fsm.cmd_advance, t.id)
                self.assertEqual(self.state(t), "spec_gate", self.note(
                    f"переход:\n{out}\n{self.journal(t)}"))
                bad = self.replaced_id(project, rel=project.tests[-1])
                lines = [self.line(good, 1)]
                if case == "нет стрелки":
                    lines.append(f"- `{bad}` причина {self.word()}")
                else:
                    lines += [self.line(bad, 1), self.line(bad, 2)]
                self.put_spec(t, self.spec(t.id, 2, lines,
                                           matrix_ids=[f"`{good}`", f"`{bad}`"]))
                self.assert_soft_refusal(t, self.approve(t), bad)
        pairs = {self.replaced_id(project, rel=rel): self.rng.randint(1, 2)
                 for rel in project.tests}
        t = self.task(project, lambda tid: self.spec(
            tid, 2, [self.line(cid, n) for cid, n in pairs.items()]),
            state="spec_writing")
        out = self.call(fsm.cmd_advance, t.id)
        self.assertEqual(self.state(t), "spec_gate", self.note(out))
        out = self.approve(t)
        context = self.note(f"approve:\n{out}\n{self.journal(t)}")
        self.assertEqual(self.state(t), "tests_writing", context)
        self.assertEqual(self.approved(t), pairs, context)


if __name__ == "__main__":
    unittest.main()
