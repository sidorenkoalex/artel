"""Тесты гейта неослабления по исходам `orchestrator/advance_gates/outcome_integrity.py`
(волна 2а-1а сведения тестов, SPEC 01M5PWM5K5M23RS4RR5KK48FY5; ADR-0027 п. 8,
ADR-0020 п. 8).

Свод двух прежних файлов: долгоживущего
`tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py` (мандат
на ослабление теста по идентификатору: отбраковка автокоммита роли, точное
равенство с `#n`, подсказка отказа — AC-11..AC-13 SPEC
01M5D02N3B428V8BWC3PAM9QCT) и `tests/test_outcome_integrity.py` (помощники
гейта на уровне записей `CaseResult`: набор `PASS_TO_PASS`, краснота на
ветке, сравнение отчётов, рост пропусков, покрытие мандатом). Долгоживущий
файл удалён решением Оператора (ADR-0020 п. 8), его свойства перенесены
сюда. Доказательство неослабления — таблицы `mutation-run` «до» и «после»
в PLAN задачи.

Стенд `id_box` — бывший `IdOutcomeGateSandbox` на настоящем git
(`tests.sandbox.GitignoreCommittedRealGitSandbox`), связка «`answer` —
ссылка документов — `advance` — гейт исходов — журнал»: клон артели —
корень песочницы с bare `origin`; учебный внешний проект —
`tests.sandbox.make_project_repo` со своим `origin` и записью `components:`
в `targets.yaml` песочницы (один компонент `pult-vitest`). Раннер подменён
без Node и без сети шпионом `subprocess.Popen`: сторона прогона — по метке
`app.py` дерева. Имена проекта, компонента, файлов и тестов — из `random`;
зерно печатается и входит в текст каждого провала.

Песочница перенесена дословно; имена, совпадающие с
`tests/outcome_gate_sandbox.py` при другом содержимом, получили префикс:
`ID_GATE_ACTIONS`, `ID_VITEST_KIND`, `id_spec_text`. Помощники, утверждающие
исход, — функции модуля `gate_refusal` и `id_no_gate_refusal`.
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
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import (answer, checkpoint, config, fsm, github_adapter,
                          project_profile, store, workspace)
from orchestrator.advance_gates import outcome_integrity as gate
from orchestrator.reporters.outcome import CaseResult
from tests.fixtures import _sandbox
from tests.sandbox import GitignoreCommittedRealGitSandbox, make_project_repo


REAL_POPEN = subprocess.Popen
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
PLANK_DIR = "acceptance_tests"
VITEST_BIN = project_profile.VITEST_BASE_ARGV[0]
VITEST_REPORT_ARGS = ["--reporter=default", "--reporter={pult_reporter}",
                      "--outputFile={path}"]
LONG_TEMPLATE = "frontend/src/<dir>/<name>.<id>.test.jsx"

OUTCOME_ACTION = "переход отклонён: гейт неослабления по исходам"
ID_GATE_ACTIONS = (OUTCOME_ACTION, f"{OUTCOME_ACTION} — сломан правкой",
                f"{OUTCOME_ACTION} — подготовка")
APPROVED_DETAIL = "гейт SPEC пройден — приёмочные тесты до кода"
OLD = "Ослабление тестов разрешено:"
NEW = "Ослабление теста по идентификатору разрешено:"
HINT = "  дальше: "
CLAIM = "Ловит мутацию: фикстура сценария — исход теста другой."

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: фикстура

## Подход
Правка кода фикстуры.

## Шаги
1. Правка кода.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Только код фикстуры.

## Риски
Нет.
"""

MATRIX_HEADERS = (
    "Что меняется",
    "Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка)",
    "Остаётся ли свойство после изменения",
    "Чем покрыто после (тест файл:строка) или «не покрыто»",
    "Решение")

PLANK_JS_PREFIX = "AC-"
VITEST_IT = "it('"

# Поля записи отчётчика пульта для краткого исхода сценария.
ID_VITEST_KIND = {
    "passed": {"state": "pass"},
    "skipped": {"state": "skip", "mode": "skip"},
}


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def id_spec_text(task_id: str, n: int) -> str:
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура гейта исходов\n\n## Контекст\n\n"
            f"## Требования\n\n## Критерии приёмки\n\nAC-{n}. Критерий "
            f"фикстуры номер {n}.\n\n## Не входит\n")


def arg_value(args: list, flag: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


def js_source(names) -> str:
    body = "".join(f"// {CLAIM}\nit('{n}', () => {{ expect(1).toBe(1); }});\n"
                   for n in names)
    return "import { expect, it } from 'vitest';\n\n" + body


def js_names(text: str) -> list:
    """Имена `it('…')` текста `js_source` по порядку (с повторами)."""
    found = []
    for line in text.splitlines():
        if line.startswith(VITEST_IT):
            found.append(line[len(VITEST_IT):].split("'", 1)[0])
    return found


class IdOutcomeGateSandbox(GitignoreCommittedRealGitSandbox):
    """Клон артели с `origin`; учебный проект `pult-vitest` и задача в
    `in_dev` — по запросу сценария; раннер — шпион `subprocess.Popen`."""

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
        # Сценарий: (путь, имя) -> {"base": [...], "head": [...]}.
        self.cases: dict = {}
        self.plank_green = False
        for patcher in (
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda *args, **kwargs: (True, "")),
                mock.patch.object(subprocess, "Popen", self.spy_popen),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
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

    def js_rel(self) -> str:
        return f"frontend/src/{self.word()}.test.jsx"

    def js_name(self) -> str:
        """Имя теста Vitest с пробелом внутри и « > »."""
        return f"{self.word()} {self.word(4)} > случай {self.word()}"

    # --- шпион ----------------------------------------------------------

    def answer_proc(self, code: int, out: str, args, kwargs):
        script = f"import sys; sys.stdout.write({out!r}); sys.exit({code})"
        return REAL_POPEN([sys.executable, "-c", script], *args, **kwargs)

    def spy_popen(self, argv, *args, **kwargs):
        if not isinstance(argv, (list, tuple)) or not argv:
            return REAL_POPEN(argv, *args, **kwargs)
        parts = [str(a) for a in argv]
        cwd = Path(str(kwargs.get("cwd") or os.getcwd()))
        if parts[0] == str(self.installer):
            (cwd / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
            return self.answer_proc(0, "", args, kwargs)
        if parts[0] == VITEST_BIN:
            if parts[1:2] == ["--version"]:
                return self.answer_proc(0, f"vitest/{self.vitest_version}\n",
                                        args, kwargs)
            return self.vitest_run(parts, cwd, args, kwargs)
        return REAL_POPEN(argv, *args, **kwargs)

    @staticmethod
    def side_of(cwd: Path) -> str:
        """Сторона дерева прогона по метке `app.py` (поиск вверх)."""
        for folder in (cwd, *cwd.parents):
            marker = folder / "app.py"
            if marker.is_file():
                text = marker.read_text(encoding="utf-8")
                if "'base'" in text:
                    return "base"
                if "'head-" in text:
                    return "head"
                return "?"
            if (folder / ".git").exists():
                break
        return "?"

    @staticmethod
    def runner_files(parts: list, cwd: Path) -> list:
        """[(путь от `cwd`, текст)] файлов `.test.jsx`, переданных раннеру;
        путей нет — все файлы дерева `cwd` вне скрытых каталогов."""
        found, explicit = [], False
        for part in parts:
            if part.startswith("-"):
                continue
            path = Path(part) if os.path.isabs(part) else cwd / part
            if path.is_dir():
                explicit = True
                found += [p for p in sorted(path.rglob("*")) if p.is_file()]
            elif path.is_file() and path.name.endswith(".test.jsx"):
                explicit = True
                found.append(path)
        if not explicit:
            found = [p for p in sorted(cwd.rglob("*")) if p.is_file()]
        files = []
        for p in found:
            rel = os.path.relpath(p, cwd).replace(os.sep, "/")
            segments = rel.split("/")
            if "node_modules" in segments or not p.name.endswith(".test.jsx"):
                continue
            if not explicit and any(s.startswith(".") for s in segments):
                continue
            files.append((rel, p.read_text(encoding="utf-8")))
        return files

    def vitest_run(self, parts: list, cwd: Path, args, kwargs):
        side = self.side_of(cwd)
        items = []
        for rel, text in self.runner_files(parts[1:], cwd):
            seen: dict = {}
            for name in js_names(text):
                if name.startswith(PLANK_JS_PREFIX):
                    kind = "passed" if self.plank_green else "failed"
                else:
                    seq = self.cases.get((rel, name), {}).get(side, ["passed"])
                    index = seen.get(name, 0)
                    seen[name] = index + 1
                    kind = seq[min(index, len(seq) - 1)]
                item = {"file": rel, "name": name, "state": "pass",
                        "mode": "run", "fails": False, "retry_count": 0,
                        "error_name": None, "timeout": False, "hook": None,
                        "duration_ms": 3}
                if kind == "failed":
                    item.update(state="fail", error_name="AssertionError")
                else:
                    item.update(ID_VITEST_KIND[kind])
                items.append(item)
        path = arg_value(parts, "--outputFile")
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps({"tests": items}), encoding="utf-8")
        red = any(i["state"] == "fail" for i in items)
        return self.answer_proc(1 if red else 0, "vitest\n", args, kwargs)

    # --- проект и задача ------------------------------------------------

    def vitest_project(self, tests: dict) -> SimpleNamespace:
        """Учебный проект с единственным компонентом `pult-vitest`; `tests` —
        {путь: [имена]} тестов базы."""
        name, comp = f"v{self.word()}", f"c{self.word()}"
        layout = f"frontend/src/.pv{self.word(5)}/<id>"
        fields = {"command": flow(project_profile.VITEST_BASE_ARGV),
                  "report": "pult-vitest",
                  "report_args": flow(VITEST_REPORT_ARGS),
                  "install": flow([str(self.installer)]),
                  "tests": flow(["frontend/src/**/*.test.jsx"]),
                  "plank_layout": layout,
                  "long_lived": LONG_TEMPLATE,
                  "weakening_scope": flow(["frontend/src/**"]),
                  "mutation_claim_scope": flow(["frontend/claims/**"]),
                  "failure_errors": flow(["AssertionError"]),
                  "select": flow([f"--sel{self.word()}", "{tests}"])}
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        for key, value in fields.items():
            lines.append(f"        {key}: {value}\n")
        lines.append("        tools:\n")
        lines.append(f'          vitest: "{self.vitest_version}"\n')
        try:
            old = config.TARGETS.read_text(encoding="utf-8")
        except FileNotFoundError:
            old = "targets:\n"
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + "".join(lines),
                                  encoding="utf-8")
        clone = make_project_repo(name)
        files = {"package.json": '{"name": "web"}\n',
                 "vitest.config.js": "export default {}\n",
                 "package-lock.json": json.dumps({"lockfileVersion": 3}) + "\n",
                 "app.py": "APP = 'base'\n"}
        files.update({rel: js_source(names) for rel, names in tests.items()})
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        return SimpleNamespace(name=name, comp=comp, clone=clone)

    def in_dev_task(self, project) -> SimpleNamespace:
        """Задача проекта в `in_dev`: SPEC в ссылке документов, переход
        гейта SPEC, планка с тестом критерия (красным на базе), настоящий
        выход из `tests_writing`."""
        n = self.rng.randrange(1, 60)
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Фикстура гейта исходов", "spec_gate",
                          branch, project.name, 25.0)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, branch=branch, wt=Path(wt), project=project)
        t.docs = config.PROJECTS / project.name / "tasks" / tid
        plank = t.docs / PLANK_DIR
        plank.mkdir(parents=True, exist_ok=True)
        spec = id_spec_text(tid, n)
        (t.docs / "SPEC.md").write_text(spec, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, tid, "analyst")
        store.set_state(self.conn, tid, "tests_writing", "operator",
                        expected_state="spec_gate", detail=APPROVED_DETAIL)
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec, encoding="utf-8")
        plank.mkdir(parents=True, exist_ok=True)
        (plank / f"p{self.word()}.test.jsx").write_text(
            "// Группа: разовый\n"
            f"// Красен до реализации: фикстура {self.word()}.\n"
            "import { expect, it } from 'vitest';\n\n"
            f"it('AC-{n}: кнопка {self.word()}', () => "
            "{ expect(1).toBe(2); });\n", encoding="utf-8")
        self.plank_green = False
        store.journal(self.conn, tid, "test_author", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, tid, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, tid, "test_author")
        rows, output = self.run_advance(tid)
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        self.plank_green = True
        return t

    def run_advance(self, tid: str) -> tuple:
        before = len(store.task_steps(self.conn, tid))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(tid)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, tid)[before:]]
        return rows, buf.getvalue()

    def developer_advance(self, t, changes: dict, finished: bool = False,
                          before=None) -> tuple:
        """Шаг developer: коммит правки кода (`app.py` — метка головы,
        `changes`), `before` — правка сценария до чекпоинта, PLAN.md
        `ready` чекпоинтом шага (`finished` — и «agent run finished»),
        `advance` из `in_dev`: (новые записи журнала, вывод)."""
        files = {"app.py": f"APP = 'head-{self.word()}'\n", **changes}
        for rel, text in files.items():
            path = t.wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", "код разработчика")
        store.update_task(self.conn, t.id, zones=", ".join(sorted(files)))
        if before is not None:
            before()
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "PLAN.md").write_text(PLAN_READY.format(task=t.id),
                                        encoding="utf-8")
        store.journal(self.conn, t.id, "developer", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        if finished:
            store.journal(self.conn, t.id, "developer", "agent run finished",
                          "rc=0, шаг сценария")
        return self.run_advance(t.id)

    def mandate_text(self, cid: str) -> str:
        row = (f"`{cid}`", "фикстура теста — tests/sandbox.py:1", "нет",
               "не покрыто", "ок")
        return (f"{NEW} {cid}\n\n"
                "Независимая проверка: матрица подтверждена\n\n"
                f"Основание: решение Оператора ({self.seed}).\n\n"
                "## Матрица неослабления\n\n"
                "| " + " | ".join(MATRIX_HEADERS) + " |\n"
                + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
                + "| " + " | ".join(row) + " |\n")

    def operator_mandate(self, t, cid: str) -> None:
        """ANSWER Оператора (`answer.cmd_answer`) со строкой нового маркера
        на `cid`, независимой проверкой и матрицей; отказ — провал."""
        path = self.root / ".artel" / f"answer-{self.word()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.mandate_text(cid), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                answer.cmd_answer(t.id, str(path))
            except SystemExit as exc:
                self.assertIn(exc.code, (None, 0), self.note(
                    f"answer отказала: {buf.getvalue()}"))

    def role_mandate(self, t, cid: str):
        """Правка сценария: ANSWER-1.md со строкой нового маркера в каталоге
        документов — его унесёт автокоммит шага developer."""
        def put():
            t.docs.mkdir(parents=True, exist_ok=True)
            (t.docs / "ANSWER-1.md").write_text(f"{NEW} {cid}\n",
                                                encoding="utf-8")
        return put

    def skipped_copy_task(self, copy: int) -> tuple:
        """Проект с файлом, где имя теста повторено трижды; на ветке
        `copy`-я запись (1..3) — пропуск, прочие зелёные. (задача,
        идентификатор находки, идентификаторы прочих вариантов)."""
        rel, name = self.js_rel(), self.js_name()
        project = self.vitest_project({rel: [name, name, name, self.js_name()]})
        t = self.in_dev_task(project)
        self.current = t.id
        head = ["passed", "passed", "passed"]
        head[copy - 1] = "skipped"
        self.cases[(rel, name)] = {"base": ["passed"], "head": head}
        ids = [project_profile.test_id(project.comp, rel, name, k if k > 1
                                       else None) for k in (1, 2, 3)]
        return t, ids[copy - 1], [c for i, c in enumerate(ids) if i != copy - 1]

    # --- наблюдения -----------------------------------------------------

    def state(self, t) -> str:
        return store.get_task(self.conn, t.id)["state"]

    def explain(self, rows: list, output: str) -> str:
        return self.note(
            f"записи: {[(r['action'], r['detail']) for r in rows]}\n"
            f"вывод: {output[-3000:]}")

    @staticmethod
    def details(rows: list, action: str) -> list:
        return [r["detail"] or "" for r in rows if r["action"] == action]

    def gate_refusal(self, rows: list, output: str) -> str:
        """Деталь записи отказа гейта исходов (любого из трёх действий
        находок/подготовки — подготовка — провал); задача в `in_dev`."""
        found = self.details(rows, OUTCOME_ACTION)
        self.assertTrue(found, f"advance не записал «{OUTCOME_ACTION}»:\n"
                        + self.explain(rows, output))
        self.assertEqual(store.get_task(self.conn, self.current)["state"],
                         "in_dev", self.explain(rows, output))
        return found[-1]

    def no_gate_refusal(self, rows: list, output: str) -> None:
        for action in ID_GATE_ACTIONS:
            self.assertEqual(self.details(rows, action), [],
                             self.explain(rows, output))


# --- записи `CaseResult` -------------------------------------------------

PATH = "frontend/src/a.test.jsx"


def vitest(name: str, outcome: str = "passed", **fields) -> CaseResult:
    return CaseResult(project_profile.test_id("web", PATH, name), outcome,
                      mode=fields.pop("mode", "run"), **fields)


def junit(name: str, outcome: str = "passed") -> CaseResult:
    return CaseResult(project_profile.test_id("py", "tests/test_a.py", name),
                      outcome)


# --- помощники исхода -----------------------------------------------------

def gate_refusal(box, rows: list, output: str) -> str:
    """Деталь записи отказа гейта исходов (любого из трёх действий
    находок/подготовки — подготовка — провал); задача в `in_dev`."""
    found = box.details(rows, OUTCOME_ACTION)
    box.assertTrue(found, f"advance не записал «{OUTCOME_ACTION}»:\n"
                   + box.explain(rows, output))
    box.assertEqual(store.get_task(box.conn, box.current)["state"],
                    "in_dev", box.explain(rows, output))
    return found[-1]


def id_no_gate_refusal(box, rows: list, output: str) -> None:
    for action in ID_GATE_ACTIONS:
        box.assertEqual(box.details(rows, action), [],
                        box.explain(rows, output))


# ------------------------------------------------------------- фикстуры

@pytest.fixture
def id_box():
    """Экземпляр `IdOutcomeGateSandbox` после `setUp()`."""
    yield from _sandbox(IdOutcomeGateSandbox)


# --------------------------------------------------------------- AC-11

def test_ac11_role_autocommitted_id_mandate_does_not_cover(id_box):
    """ANSWER со строкой нового маркера на идентификатор находки, унесённый автокоммитом шага developer, находку не снимает.

    Сценарий: проект `pult-vitest`, имя теста повторено в файле трижды;
    на ветке вторая запись (`…#2`) — пропуск. ANSWER-1.md со строкой
    «Ослабление теста по идентификатору разрешено: <идентификатор #2>»
    кладётся в каталог документов и уходит в ссылку автокоммитом шага
    developer. `advance` из `in_dev`: отказ «… по исходам», деталь
    называет идентификатор `#2`, задача в `in_dev`.

    Ловит мутацию: сбор мандата нового маркера в гейте исходов без
    отбраковки `zones._answer_commit_is_role_step_autocommit` —
    находка покрыта ролью, отказа нет, задача уходит дальше.
    """
    t, cid, _others = id_box.skipped_copy_task(2)
    rows, output = id_box.developer_advance(
        t, {}, before=id_box.role_mandate(t, cid))
    assert cid in gate_refusal(id_box, rows, output), \
        id_box.explain(rows, output)


# --------------------------------------------------------------- AC-12

def test_ac12_exact_id_with_n_covers_other_variant_does_not(id_box):
    """Мандат нового маркера на тот же идентификатор с `#n` снимает находку; на другой `#n` или без `#n` — нет.

    Сценарий (подслучай — свежая задача на общем стенде, поэтому прежним
    циклом): имя теста повторено в файле трижды, на ветке вторая запись
    (`…#2`) — пропуск. ANSWER Оператора (`answer`) со строкой нового
    маркера на (а) `…#2` — отказа гейта исходов нет; (б) `…#3`; (в)
    идентификатор без `#n` — отказ «… по исходам», деталь называет `…#2`.

    Ловит мутацию: элементы нового маркера в гейте не собираются —
    (а) отказ; к ним применено префиксное правило прежнего мандата
    (`путь::имя`, за которым `#`) — (в) покрывает `…#2`, отказа нет;
    сверка по идентификатору без номера (`parse_test_id` без `#n`) —
    (б) покрывает.
    """
    for label, pick in (("тот же #2", lambda cid, others: cid),
                        ("другой #3", lambda cid, others: others[1]),
                        ("без #n", lambda cid, others: others[0])):
        case = f"case={label}, seed={id_box.seed}: "
        t, cid, others = id_box.skipped_copy_task(2)
        assert cid.endswith("#2") and others[1].endswith("#3") \
            and "#" not in others[0].rpartition("::")[2], \
            case + id_box.note(f"фикстура: {cid} {others}")
        id_box.operator_mandate(t, pick(cid, others))
        rows, output = id_box.developer_advance(t, {}, finished=True)
        if label == "тот же #2":
            id_no_gate_refusal(id_box, rows, output)
        else:
            assert cid in gate_refusal(id_box, rows, output), \
                case + id_box.explain(rows, output)


# --------------------------------------------------------------- AC-13

def test_ac13_refusal_hint_names_both_markers(id_box):
    """Подсказка отказа гейта исходов с непокрытой находкой называет оба маркера.

    Сценарий: проект `pult-vitest`, тест базы на ветке стал пропуском,
    мандата нет. `advance` из `in_dev`: отказ «… по исходам»; строка
    вывода «  дальше: …» несёт «Ослабление тестов разрешено:» и
    «Ослабление теста по идентификатору разрешено:».

    Ловит мутацию: гейт исходов по-прежнему зовёт подсказку гейта по
    тексту (`test_integrity._mandate_hint`) — нового маркера в ней
    нет; своя подсказка называет только новый маркер — прежнего нет.
    """
    rel, name = id_box.js_rel(), id_box.js_name()
    project = id_box.vitest_project({rel: [name, id_box.js_name()]})
    t = id_box.in_dev_task(project)
    id_box.current = t.id
    id_box.cases[(rel, name)] = {"base": ["passed"], "head": ["skipped"]}
    rows, output = id_box.developer_advance(t, {})
    gate_refusal(id_box, rows, output)
    hints = [line for line in output.splitlines() if line.startswith(HINT)]
    assert any(OLD in h and NEW in h for h in hints), \
        id_box.explain(rows, output)


# ------------------------------------------- помощники гейта на записях

def test_retried_pass_on_base_not_in_pass_to_pass():
    """`passed` с повтором на базе (`pult-vitest`) — вне `PASS_TO_PASS`; без повтора — в нём.

    Ловит мутацию: `in_pass_to_pass` без сверки `retries == 0` — тест с
    повтором на базе попадает в набор.
    """
    assert not gate.in_pass_to_pass(vitest("x", retries=1))
    assert gate.in_pass_to_pass(vitest("x"))
    assert gate.in_pass_to_pass(junit("x"))
    assert not gate.in_pass_to_pass(junit("x", "skipped"))


def test_red_on_branch_kinds():
    """Красный на ветке — `failed`, `error`, `passed` с повтором; `skipped` и чистый `passed` — нет.

    Набор записей собран вызовами, не литералами, — прежним циклом.

    Ловит мутацию: `passed` с повтором не считается красным либо
    `skipped` считается красным.
    """
    for case, red in ((vitest("x", "failed"), True),
                      (junit("x", "error"), True),
                      (vitest("x", retries=2), True),
                      (vitest("x", "skipped", mode="skip"), False),
                      (junit("x", "skipped"), False),
                      (junit("x"), False)):
        assert gate.red_on_branch(case) == red, f"case={case}"


def test_compare_vitest_findings_and_non_findings():
    """Сравнение `pult-vitest`: исчез, стал пропуском, появились `todo`/`fails`, новые пропуск/`todo`/`fails` — находки; неизменные `todo`/`fails` и новый зелёный — нет; по одной на идентификатор.

    Ловит мутацию: `todo`/`fails` — находка без сверки с базой; «стал
    пропуском» только у `passed`; новый идентификатор не проверяется;
    у `to_todo` две находки.
    """
    base = [vitest("gone"), vitest("s_fail", "failed"),
            vitest("to_todo"), vitest("to_fails"),
            vitest("keep_todo", "skipped", mode="todo"),
            vitest("keep_fails", fails=True), vitest("quiet")]
    head = [vitest("s_fail", "skipped", mode="skip"),
            vitest("to_todo", "skipped", mode="todo"),
            vitest("to_fails", fails=True),
            vitest("keep_todo", "skipped", mode="todo"),
            vitest("keep_fails", fails=True), vitest("quiet"),
            vitest("new_skip", "skipped", mode="skip"),
            vitest("new_todo", "skipped", mode="todo"),
            vitest("new_fails", fails=True), vitest("new_pass")]
    found = {f.id.rsplit("::", 1)[1]: f.kind for f in gate.compare(base, head)}
    assert found == {
        "gone": gate.GONE, "s_fail": gate.BECAME_SKIPPED,
        "to_todo": gate.TODO_APPEARED, "to_fails": gate.FAILS_APPEARED,
        "new_skip": gate.NEW_SKIPPED, "new_todo": gate.NEW_TODO,
        "new_fails": gate.NEW_FAILS}
    assert gate.compare(base, head)[0].kind == gate.GONE


def test_compare_junit_became_skipped_from_each_outcome():
    """`junit-xml`: `passed`/`failed`/`error` базы, ставшие `skipped`, — «стал пропуском»; пропуск на обеих сторонах — нет.

    Ловит мутацию: «стал пропуском» только у `passed` базы; пропуск,
    бывший пропуском и на базе, даёт находку.
    """
    base = [junit("p"), junit("f", "failed"), junit("e", "error"),
            junit("s", "skipped")]
    head = [junit(n, "skipped") for n in ("p", "f", "e", "s")]
    kinds = {f.id.rsplit("::", 1)[1]: f.kind for f in gate.compare(base, head)}
    assert kinds == {n: gate.BECAME_SKIPPED for n in ("p", "f", "e")}


def test_skip_growth_line():
    """Рост числа пропусков — строка без идентификаторов; без роста — пусто.

    Ловит мутацию: строка пишется и без роста либо несёт
    идентификатор теста.
    """
    base = [junit("a", "skipped"), junit("b")]
    assert gate.skip_growth(base, base) == ""
    line = gate.skip_growth(base, [junit("a", "skipped"),
                                   junit("b", "skipped")])
    assert "пропуск" in line
    assert "::" not in line


def test_mandate_prefix_needs_separator():
    """Мандат: путь файла и префикс `путь::имя` с `::`, `[`, `#` или концом за ним покрывают; иной символ — нет.

    Ловит мутацию: покрытие `startswith` без сверки следующего
    символа — `путь::K` покрывает `путь::KOther::m`.
    """
    rel = "tests/test_a.py"
    cid = project_profile.test_id("py", rel, "K::m[a]")
    other = project_profile.test_id("py", rel, "KOther::m")
    again = project_profile.test_id("py", rel, "K::m", 2)
    assert gate.covering(cid, {rel: "ANSWER-1"}) == "ANSWER-1"
    assert gate.covering(cid, {f"{rel}::K": "ANSWER-2"}) == "ANSWER-2"
    assert gate.covering(cid, {f"{rel}::K::m": "ANSWER-3"}) == "ANSWER-3"
    assert gate.covering(again, {f"{rel}::K::m": "ANSWER-3"}) == "ANSWER-3"
    assert gate.covering(other, {f"{rel}::K": "ANSWER-2"}) is None
    assert gate.covering(cid, {"tests/test_b.py": "ANSWER-1"}) is None


def test_covered_ids_round_trip_every_finding_kind():
    """Идентификаторы покрытых находок разбираются из строк записи пройденного гейта для каждого вида находки, в том числе вида с тире («новый тест — пропуск») и исходов перепрогона («сломан правкой» начинается с ветки).

    Ловит мутацию: разбор строки по первому « — » — у вида «новый
    тест — пропуск» идентификатор теряется; маркер исходов «база: » у
    «сломан правкой» — идентификатор не разобран, доказательство на
    мерже никогда не срабатывает; строки без пометки мандата
    (числа, «нестабилен и на базе») дают идентификаторы.
    """
    cid = project_profile.test_id("web", PATH, "suite > case — b")
    lines = ["тестов базы 3; тестов ветки 2", f"{gate.FLAKY_ON_BASE}: {cid}"]
    kinds = (gate.GONE, gate.BECAME_SKIPPED, gate.TODO_APPEARED,
             gate.FAILS_APPEARED, gate.NEW_SKIPPED, gate.NEW_TODO,
             gate.NEW_FAILS)
    findings = [gate.Finding(kind, cid, "база: прошёл; ветка: нет записи")
                for kind in kinds]
    findings += [gate.Finding(kind, cid, "ветка: failed, failed; база: passed")
                 for kind in (gate.BROKEN, gate.UNSTABLE)]
    lines += [f"{f.line}{gate.COVERED_MARK}ANSWER-1" for f in findings]
    assert gate._covered_ids("\n".join(lines)) == [cid] * len(findings)


def test_fingerprint_sorted_unique_or_none():
    """Отпечаток мандата — sha256 отсортированных уникальных элементов через перевод строки; без элементов — «нет».

    Ловит мутацию: отпечаток без сортировки или с повтором элемента —
    отпечаток зависит от порядка находок и записи на `in_dev` и мерже
    расходятся.
    """
    import hashlib
    wanted = hashlib.sha256(b"a/x.py\nb/y.py").hexdigest()
    assert gate.fingerprint(["b/y.py", "a/x.py", "b/y.py"]) == wanted
    assert gate.fingerprint([]) == gate.MANDATE_NONE
