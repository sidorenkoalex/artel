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

Волна 2а-1б (SPEC 01M5QAEPC6RF097YQ43T3Y56D9) свела сюда 42 теста
долгоживущего `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`
(сквозные сценарии перехода `in_dev -> verifying` по SPEC
01M5CJVB5B5V55PQQVR2QRHWZN: граница, место гейта, прогоны, подготовка,
перепрогоны, вердикт по записи, сравнение, порядок, мандат, запись
пройденного гейта); файл удалён решением Оператора (ADR-0020 п. 8). Стенд
`box` — `OutcomeGateSandbox` из `tests/outcome_gate_sandbox.py`; методы
подготовки с утверждениями тесты зовут через стенд. Помощники, утверждающие
исход, — функции модуля `refusal`, `no_gate_refusal`, `assert_no_gate`,
`assert_prepare` (первый параметр — стенд, последний — `case`: ярлык
подслучая и зерно спереди к тексту каждого сообщения); `prepared` и
`broken_task` — функции модуля по тому же правилу. Бывшие `subTest` —
прямым кодом или прежним циклом в одной функции: ярлык подслучая и зерно —
в локальном `case`, он стоит в сообщении каждого утверждения подслучая.
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
from tests.outcome_gate_sandbox import (py_source, re, BROKEN_ACTION,
    FLAKY_ON_BASE, GATE_ACTIONS, OutcomeGateSandbox, PASSED_NOTE,
    PREPARE_ACTION, REVIEW_CHANGES, REWORK_ACTION, SEP, TASKS_DIR,
    TEXT_GATE_ACTION, TEXT_GATE_SKIP, VITEST_KIND)
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



@pytest.fixture
def box():
    """Стенд OutcomeGateSandbox после setUp."""
    yield from _sandbox(OutcomeGateSandbox)


# ---------------------------------------------------------------- помощники гейта исходов


def refusal(box, rows: list, output: str, action: str, case: str = "") -> str:
    """Деталь последней записи `action`; провал — записи нет, есть
    запись другого действия гейта исходов, либо задача ушла из
    `in_dev`."""
    found = box.details(rows, action)
    box.assertTrue(found, case + f"advance не записал «{action}»:\n"
                    + box.explain(rows, output))
    others = [a for a in GATE_ACTIONS if a != action and box.details(rows, a)]
    box.assertEqual(others, [], case + box.explain(rows, output))
    box.assertEqual(box.state_of(rows), "in_dev", case + box.explain(rows, output))
    return found[-1]


def no_gate_refusal(box, rows: list, output: str, case: str = "") -> None:
    for action in GATE_ACTIONS:
        box.assertEqual(box.details(rows, action), [],
                         case + box.explain(rows, output))


def assert_no_gate(box, rows, output, case: str = "") -> None:
    box.assertEqual(box.suite_calls, [], case + box.explain(rows, output))
    box.assertEqual(box.gate_rows(rows), [], case + box.explain(rows, output))
    box.assertEqual(box.full_runs(), [], case + box.explain(rows, output))


def prepared(box, git_fail=None, timeout_when=None, no_report_when=None):
    rel, name = box.py_rel(), box.py_name()
    project = box.junit_project({rel: [name]})
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
    clone = t.project.clone
    base = box.git("-C", str(clone), "merge-base",
                    f"origin/{config.MAIN_BRANCH}", t.branch).strip()
    box.git_fail = git_fail(t, base) if git_fail else None
    box.timeout_when = timeout_when
    box.no_report_when = no_report_when
    return t


def assert_prepare(box, t, rows, output, side_words=(), case: str = "") -> str:
    detail = refusal(box, rows, output, PREPARE_ACTION, case=case)
    box.assertTrue(detail.strip(), case + box.explain(rows, output))
    box.assertEqual(box.subset_runs(), [], case + box.explain(rows, output))
    box.assertNotEqual(box.state(t), "verifying", case + box.explain(rows, output))
    if side_words:
        low = detail.lower()
        box.assertTrue(any(w in low for w in side_words),
                        case + box.explain(rows, output))
    return detail


def broken_task(box, names):
    """Проект `junit-xml` с классами тестов в одном файле; тесты
    `names` — трижды красные на ветке."""
    rel = box.py_rel()
    project = box.junit_project({rel: names + [box.py_name()]})
    t = box.task(project)
    for name in names:
        box.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
    return project, t, rel


# ---------------------------------------------------------------- Ac1OutOfBoundsTest


def test_ac1_artel_and_test_profile_no_gate(box):
    """Артель и запись `test_profile` с `report: junit-xml`: полного набора нет, записей гейта исходов нет, переход как прежде.

    Сценарий (подслучай — свежая задача): (а) задача артели с зелёной
    планкой; (б) учебный проект с `test_profile` (`runner: pytest-own`,
    `report: junit-xml`) и тестом, который на ветке падает. Шаг
    developer, `advance` из `in_dev`: `acceptance.full_suite` не
    звался, раннер полного набора на выписке не запускался, ни одной
    записи с «по исходам», в (б) — «приёмочные тесты пройдены» и
    `verifying`.

    Ловит мутацию: граница по `reported(profile)` без
    `from_components` — у `test_profile` с `report` гейт создан: полный
    набор прогнан, сломанный тест даёт отказ «… — сломан правкой»;
    гейт создаётся у любого профиля — у артели звался `full_suite`.
    """
    case = f"артель, зерно {box.seed}"
    t = box.artel_in_dev_task()
    box.current = t.id
    rows, output = box.developer_advance(t)
    assert_no_gate(box, rows, output, case=case)
    assert box.state(t) == "verifying", case + box.explain(rows, output)
    case = f"test_profile, зерно {box.seed}"
    rel, name = box.py_rel(), box.py_name()
    project = box.junit_project({rel: [name]}, test_profile=True)
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
    rows, output = box.developer_advance(t)
    assert_no_gate(box, rows, output, case=case)
    assert box.details(rows, PASSED_NOTE), case + box.explain(rows, output)
    assert box.state(t) == "verifying", case + box.explain(rows, output)


def test_ac1_decide_skip_refusal_and_canary_no_gate(box):
    """Пропуск и отказ решения `decide` и канареечная задача: гейт исходов не создаётся.

    Сценарий (подслучай): (а) канареечная задача проекта с компонентом
    `junit-xml`, тест базы на ветке падает; (б) проект задачи без
    `test_profile` и `components:` (пропуск решения; переход доходит
    до записи пропуска гейта по тексту); (в) `decide`, позванный из
    модуля гейта, отдаёт отказ (подмена публичного
    `project_profile.decide` только для кадров гейта), тест базы на
    ветке падает. Во всех — `acceptance.full_suite` не звался, раннер
    полного набора на выписке не запускался, записей с «по исходам»
    нет; в (а) и (в) задача ушла в `verifying`.

    Ловит мутацию: условие `t["is_canary"]` пропущено — у канарейки
    полный набор прогнан и отказ «… — сломан правкой»; отказ решения
    `decide` у гейта исходов — отказ перехода (запись с «по исходам»)
    или прогон по профилю записи в обход решения — `full_suite` звался.
    """
    case = f"канарейка, зерно {box.seed}"
    rel, name = box.py_rel(), box.py_name()
    project = box.junit_project({rel: [name]})
    t = box.task(project, canary=True)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
    rows, output = box.developer_advance(t)
    assert_no_gate(box, rows, output, case=case)
    assert box.state(t) == "verifying", case + box.explain(rows, output)
    case = f"пропуск decide, зерно {box.seed}"
    project = box.bare_project()
    assert project_profile.decide(project.name).skip, case + box.note("решение не пропуск")
    tid = ulid(box.rng)
    branch = f"task/{tid.lower()}-{box.word()}"
    store.insert_task(box.conn, tid, "Фикстура", "in_dev", branch,
                      project.name, 25.0)
    wt, error = workspace.ensure(tid, branch)
    assert error is None, case + box.note(str(error))
    t = SimpleNamespace(id=tid, branch=branch, target=project.name,
                        wt=Path(wt), project=project,
                        docs=config.PROJECTS / project.name / TASKS_DIR / tid)
    box.current = tid
    rows, output = box.developer_advance(t)
    assert_no_gate(box, rows, output, case=case)
    # Переход дошёл до соседа гейта: пропуск гейта по тексту записан.
    assert box.details(rows, TEXT_GATE_SKIP), case + box.explain(rows, output)
    case = f"отказ decide, зерно {box.seed}"
    rel, name = box.py_rel(), box.py_name()
    project = box.junit_project({rel: [name]})
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
    real = project_profile.decide
    decide_refusal = f"профиль сценария {box.word()} не прочитан"

    def decide(target, *args, **kwargs):
        if box.in_gate():
            return project_profile.Decision(target, refusal=decide_refusal)
        return real(target, *args, **kwargs)
    with mock.patch.object(project_profile, "decide", decide):
        rows, output = box.developer_advance(t)
    assert_no_gate(box, rows, output, case=case)
    assert box.state(t) == "verifying", case + box.explain(rows, output)


# ---------------------------------------------------------------- Ac2PlaceTest


def test_ac2_text_gate_refusal_first_no_outcome_runs(box):
    """Отказ гейта неослабления по тексту — прогона исходов нет.

    Сценарий: проект `junit-xml` с двумя тестами в файле `tests/`;
    правка ветки удаляет один тест из файла без мандата. `advance`
    записывает «переход отклонён: гейт неослабления тестов»;
    `acceptance.full_suite` не звался, записей гейта исходов нет.

    Ловит мутацию: гейт исходов поставлен до гейта по тексту — полный
    набор прогнан, и отказ — «гейт неослабления по исходам» (исчезнувший
    тест), а не отказ по тексту.
    """
    rel, keep, gone = box.py_rel(), box.py_name(), box.py_name()
    project = box.junit_project({rel: [keep, gone]})
    t = box.task(project)
    rows, output = box.developer_advance(t, {rel: py_source([keep])})
    assert box.details(rows, TEXT_GATE_ACTION), box.explain(rows, output)
    assert box.suite_calls == [], box.explain(rows, output)
    assert box.gate_rows(rows) == [], box.explain(rows, output)


def test_ac2_outcome_refusal_stops_before_review_rework_gate(box):
    """Отказ гейта исходов — гейт переделки ревью не исполняется; при пройденном гейте исходов тот же REVIEW.md даёт отказ переделки.

    Сценарий (подслучай — свежая задача): после коммита кода задача
    проходит `in_dev -> review -> in_dev`, в ссылку документов ложится
    REVIEW.md `changes_requested` автокоммитом шага reviewer, шага
    developer после него нет. (а) Тест базы на ветке
    красен все три раза — отказ «… — сломан правкой», записи «переход
    отклонён: замечания ревью не отработаны» нет. (б) Все тесты зелены
    — гейт исходов пройден, отказ переделки ревью есть.

    Ловит мутацию: гейт исходов поставлен после гейта переделки ревью —
    в (а) отказ переделки ревью вместо отказа гейта исходов.
    """
    for label in ("сломан", "зелёный"):
        case = f"{label}, зерно {box.seed}"
        rel, name = box.py_rel(), box.py_name()
        project = box.junit_project({rel: [name]})
        t = box.task(project)
        if label == "сломан":
            box.cases[(rel, name)] = {"base": ["passed"],
                                       "head": ["failed"]}

        def review():
            store.set_state(box.conn, t.id, "review", "fsm",
                            expected_state="in_dev",
                            detail="сценарий: на ревью")
            t.docs.mkdir(parents=True, exist_ok=True)
            (t.docs / "REVIEW.md").write_text(
                REVIEW_CHANGES.format(task=t.id, word=box.word()),
                encoding="utf-8")
            store.journal(box.conn, t.id, "reviewer",
                          "agent run started", "шаг сценария")
            checkpoint.commit_step_artifacts(box.conn, t.id, "reviewer")
            store.set_state(box.conn, t.id, "in_dev", "fsm",
                            expected_state="review",
                            detail="сценарий: замечания ревью")
        rows, output = box.developer_advance(t, before=review)
        if label == "сломан":
            refusal(box, rows, output, BROKEN_ACTION, case=case)
            assert box.details(rows, REWORK_ACTION) == [], case + box.explain(rows, output)
        else:
            no_gate_refusal(box, rows, output, case=case)
            assert box.details(rows, REWORK_ACTION), case + box.explain(rows, output)


# ---------------------------------------------------------------- Ac3RunsTest


def test_ac3_full_suite_on_base_and_head_checkouts_fresh(box):
    """Полный набор компонента — дважды, `fresh=True`, на отдельных выписках базы и головы; сторона — по метке дерева.

    Сценарий: проект `junit-xml` с двумя-тремя файлами тестов, все
    зелёные на обеих сторонах. `acceptance.full_suite` позван ровно
    дважды, оба раза с `fresh=True` и профилем компонента; корни — два
    разных каталога, ни один не рабочая копия задачи; метка одного
    корня — база, другого — голова; раннер компонента запущен полным
    набором по разу на каждой стороне; гейт пройден, отказа нет.

    Ловит мутацию: голова гоняется в рабочей копии задачи — корень
    совпадает с рабочей копией; база гоняется на дереве головы (одна
    выписка дважды) — обе метки «head»; `fresh` не передан — `False`
    в вызове.
    """
    tests = {box.py_rel(): [box.py_name() for _ in range(2)]
             for _ in range(box.rng.randint(2, 3))}
    project = box.junit_project(tests)
    t = box.task(project)
    rows, output = box.developer_advance(t)
    no_gate_refusal(box, rows, output)
    calls = box.suite_calls
    assert len(calls) == 2, box.explain(rows, output)
    assert all(c["fresh"] is True for c in calls), box.explain(rows, output)
    assert sorted(c["side"] for c in calls) == ["base", "head"], box.explain(rows, output)
    roots = {os.path.realpath(c["root"]) for c in calls}
    assert len(roots) == 2, box.explain(rows, output)
    assert os.path.realpath(t.wt) not in roots, box.explain(rows, output)
    for c in calls:
        assert getattr(c["command"], "component", None) == project.comp, box.explain(rows, output)
    sides = sorted(r["side"] for r in box.full_runs())
    assert sides == ["base", "head"], box.explain(rows, output)


# ---------------------------------------------------------------- Ac4PrepareTest


def test_ac4_git_preparation_failures_refuse(box):
    """Сбой подготовки git — отказ «… — подготовка» с причиной, без сравнения и без перепрогонов.

    Сценарий (подслучай — свежая задача, тест базы на ветке красен):
    git отказывает только вызовам из модуля гейта — (а) `merge-base`
    (база `diff_base` не определена); (б) любое чтение кодовой ветки,
    кроме `merge-base` (голова не прочитана); (в) выписка с sha базы;
    (г) выписка с sha головы (или по имени ветки). В каждом —
    отказ «переход отклонён: гейт неослабления по исходам —
    подготовка» с непустой деталью, ни «… — сломан правкой», ни общего
    отказа, перепрогонов нет, задача не в `verifying`.

    Ловит мутацию: `None` от `diff_base` или пустая голова — гейт
    пропущен (задача уходит дальше без отказа); сбой выписки
    проглочен — сравнение по одной стороне даёт «сломан правкой» или
    проход.

    Метод исполняет подслучай (а) «база не определена» (`cases[0]`):
    ветки и помощники всех подслучаев — в теле, исполняется одна
    ветка; (б)–(г) — методы `test_ac4_git_head_not_read_refuses`,
    `test_ac4_git_base_checkout_failure_refuses`,
    `test_ac4_git_head_checkout_failure_refuses`.
    """
    def merge_base(t, base):
        return lambda args: "merge-base" in args

    def head_read(t, base):
        return lambda args: "merge-base" not in args and any(
            t.branch in a for a in args)

    def checkout(side):
        def rule(t, base):
            head = box.git("-C", str(t.project.clone), "rev-parse",
                            t.branch).strip()
            wanted = base if side == "base" else head

            def fail(args):
                making = ("worktree" in args and "add" in args) or \
                    "clone" in args or "archive" in args
                return making and any(
                    wanted in a or (side == "head" and t.branch in a)
                    for a in args)
            return fail
        return rule

    cases = (("база не определена", merge_base),
             ("голова не прочитана", head_read),
             ("выписка базы", checkout("base")),
             ("выписка головы", checkout("head")))
    label, rule = cases[0]  # «база не определена»
    case = f"{label}, зерно {box.seed}"
    t = prepared(box, git_fail=rule)
    rows, output = box.developer_advance(t)
    box.git_fail = None
    assert_prepare(box, t, rows, output, case=case)


def test_ac4_git_head_not_read_refuses(box):
    """Сбой чтения кодовой ветки (кроме `merge-base`) — отказ «… — подготовка» с причиной, без сравнения и перепрогонов.

    Сценарий (подслучай (б) `test_ac4_git_preparation_failures_refuse`
    — свежая задача, тест базы на ветке красен): git отказывает только
    вызовам из модуля гейта, читающим кодовую ветку, кроме
    `merge-base` (голова не прочитана). Отказ «переход отклонён: гейт
    неослабления по исходам — подготовка» с непустой деталью, ни «… —
    сломан правкой», ни общего отказа, перепрогонов нет, задача не в
    `verifying`.

    Ловит мутацию: пустая голова — гейт пропущен (задача уходит
    дальше без отказа).
    """
    def merge_base(t, base):
        return lambda args: "merge-base" in args

    def head_read(t, base):
        return lambda args: "merge-base" not in args and any(
            t.branch in a for a in args)

    def checkout(side):
        def rule(t, base):
            head = box.git("-C", str(t.project.clone), "rev-parse",
                            t.branch).strip()
            wanted = base if side == "base" else head

            def fail(args):
                making = ("worktree" in args and "add" in args) or \
                    "clone" in args or "archive" in args
                return making and any(
                    wanted in a or (side == "head" and t.branch in a)
                    for a in args)
            return fail
        return rule

    cases = (("база не определена", merge_base),
             ("голова не прочитана", head_read),
             ("выписка базы", checkout("base")),
             ("выписка головы", checkout("head")))
    label, rule = cases[1]  # «голова не прочитана»
    case = f"{label}, зерно {box.seed}"
    t = prepared(box, git_fail=rule)
    rows, output = box.developer_advance(t)
    box.git_fail = None
    assert_prepare(box, t, rows, output, case=case)


def test_ac4_git_base_checkout_failure_refuses(box):
    """Сбой выписки дерева с sha базы — отказ «… — подготовка» с причиной, без сравнения и перепрогонов.

    Сценарий (подслучай (в) `test_ac4_git_preparation_failures_refuse`
    — свежая задача, тест базы на ветке красен): git отказывает только
    выписке (`worktree add`, `clone`, `archive`) модуля гейта с sha
    базы. Отказ «переход отклонён: гейт неослабления по исходам —
    подготовка» с непустой деталью, ни «… — сломан правкой», ни
    общего отказа, перепрогонов нет, задача не в `verifying`.

    Ловит мутацию: сбой выписки проглочен — сравнение по одной
    стороне даёт «сломан правкой» или проход.
    """
    def merge_base(t, base):
        return lambda args: "merge-base" in args

    def head_read(t, base):
        return lambda args: "merge-base" not in args and any(
            t.branch in a for a in args)

    def checkout(side):
        def rule(t, base):
            head = box.git("-C", str(t.project.clone), "rev-parse",
                            t.branch).strip()
            wanted = base if side == "base" else head

            def fail(args):
                making = ("worktree" in args and "add" in args) or \
                    "clone" in args or "archive" in args
                return making and any(
                    wanted in a or (side == "head" and t.branch in a)
                    for a in args)
            return fail
        return rule

    cases = (("база не определена", merge_base),
             ("голова не прочитана", head_read),
             ("выписка базы", checkout("base")),
             ("выписка головы", checkout("head")))
    label, rule = cases[2]  # «выписка базы»
    case = f"{label}, зерно {box.seed}"
    t = prepared(box, git_fail=rule)
    rows, output = box.developer_advance(t)
    box.git_fail = None
    assert_prepare(box, t, rows, output, case=case)


def test_ac4_git_head_checkout_failure_refuses(box):
    """Сбой выписки дерева головы — отказ «… — подготовка» с причиной, без сравнения и перепрогонов.

    Сценарий (подслучай (г) `test_ac4_git_preparation_failures_refuse`
    — свежая задача, тест базы на ветке красен): git отказывает только
    выписке модуля гейта с sha головы или по имени ветки. Отказ
    «переход отклонён: гейт неослабления по исходам — подготовка» с
    непустой деталью, ни «… — сломан правкой», ни общего отказа,
    перепрогонов нет, задача не в `verifying`.

    Ловит мутацию: сбой выписки проглочен — сравнение по одной
    стороне даёт «сломан правкой» или проход.
    """
    def merge_base(t, base):
        return lambda args: "merge-base" in args

    def head_read(t, base):
        return lambda args: "merge-base" not in args and any(
            t.branch in a for a in args)

    def checkout(side):
        def rule(t, base):
            head = box.git("-C", str(t.project.clone), "rev-parse",
                            t.branch).strip()
            wanted = base if side == "base" else head

            def fail(args):
                making = ("worktree" in args and "add" in args) or \
                    "clone" in args or "archive" in args
                return making and any(
                    wanted in a or (side == "head" and t.branch in a)
                    for a in args)
            return fail
        return rule

    cases = (("база не определена", merge_base),
             ("голова не прочитана", head_read),
             ("выписка базы", checkout("base")),
             ("выписка головы", checkout("head")))
    label, rule = cases[3]  # «выписка головы»
    case = f"{label}, зерно {box.seed}"
    t = prepared(box, git_fail=rule)
    rows, output = box.developer_advance(t)
    box.git_fail = None
    assert_prepare(box, t, rows, output, case=case)


def test_ac4_side_not_started_or_timeout_refuses_naming_side(box):
    """Исход стороны «неизвестно/не начат» или таймаут на базе либо на ветке — отказ подготовки, названа сторона.

    Сценарий (подслучай — свежая задача, тест базы на ветке красен):
    (а) раннер полного набора на базе не пишет отчёт (исход
    «неизвестно»); (б) то же на голове; (в) полный прогон базы
    превышает предел; (г) то же на голове. Отказ «… — подготовка»,
    деталь называет сторону («баз…» либо «ветк…»/«голов…»),
    перепрогонов нет, отказа «… — сломан правкой» нет.

    Ловит мутацию: «неизвестно» на базе принят за пустой отчёт — набор
    `PASS_TO_PASS` пуст, гейт пройден; таймаут головы принят за
    красный прогон — находки «сломан правкой» вместо отказа подготовки;
    сторона в отказе не названа.

    Метод исполняет подслучай (а) «неизвестно база» (`cases[0]`);
    (б)–(г) — методы `test_ac4_side_head_unknown_refuses_naming_head`,
    `test_ac4_side_base_timeout_refuses_naming_base`,
    `test_ac4_side_head_timeout_refuses_naming_head`.
    """
    base_words, head_words = ("баз",), ("ветк", "голов")
    cases = (("неизвестно база", "base", "report", base_words),
             ("неизвестно голова", "head", "report", head_words),
             ("таймаут база", "base", "timeout", base_words),
             ("таймаут голова", "head", "timeout", head_words))
    label, side, kind, words = cases[0]  # «неизвестно база»
    case = f"{label}, зерно {box.seed}"
    def pick(run, side=side):
        return run["full"] and not run["plank"] and run["side"] == side
    t = prepared(box, timeout_when=pick if kind == "timeout" else None,
                      no_report_when=pick if kind == "report" else None)
    rows, output = box.developer_advance(t)
    box.timeout_when = box.no_report_when = None
    assert_prepare(box, t, rows, output, words, case=case)


def test_ac4_side_head_unknown_refuses_naming_head(box):
    """Исход «неизвестно» полного прогона на голове — отказ подготовки, названа ветка.

    Сценарий (подслучай (б)
    `test_ac4_side_not_started_or_timeout_refuses_naming_side` —
    свежая задача, тест базы на ветке красен): раннер полного набора
    на голове не пишет отчёт. Отказ «… — подготовка», деталь называет
    сторону («ветк…»/«голов…»), перепрогонов нет, отказа «… — сломан
    правкой» нет.

    Ловит мутацию: «неизвестно» на голове принят за красный прогон
    или пустой отчёт — находки «сломан правкой» или проход вместо
    отказа подготовки; сторона в отказе не названа.
    """
    base_words, head_words = ("баз",), ("ветк", "голов")
    cases = (("неизвестно база", "base", "report", base_words),
             ("неизвестно голова", "head", "report", head_words),
             ("таймаут база", "base", "timeout", base_words),
             ("таймаут голова", "head", "timeout", head_words))
    label, side, kind, words = cases[1]  # «неизвестно голова»
    case = f"{label}, зерно {box.seed}"
    def pick(run, side=side):
        return run["full"] and not run["plank"] and run["side"] == side
    t = prepared(box, timeout_when=pick if kind == "timeout" else None,
                      no_report_when=pick if kind == "report" else None)
    rows, output = box.developer_advance(t)
    box.timeout_when = box.no_report_when = None
    assert_prepare(box, t, rows, output, words, case=case)


def test_ac4_side_base_timeout_refuses_naming_base(box):
    """Таймаут полного прогона базы — отказ подготовки, названа база.

    Сценарий (подслучай (в)
    `test_ac4_side_not_started_or_timeout_refuses_naming_side` —
    свежая задача, тест базы на ветке красен): полный прогон базы
    превышает предел. Отказ «… — подготовка», деталь называет сторону
    («баз…»), перепрогонов нет, отказа «… — сломан правкой» нет.

    Ловит мутацию: таймаут базы принят за пустой отчёт — набор
    `PASS_TO_PASS` пуст, гейт пройден; сторона в отказе не названа.
    """
    base_words, head_words = ("баз",), ("ветк", "голов")
    cases = (("неизвестно база", "base", "report", base_words),
             ("неизвестно голова", "head", "report", head_words),
             ("таймаут база", "base", "timeout", base_words),
             ("таймаут голова", "head", "timeout", head_words))
    label, side, kind, words = cases[2]  # «таймаут база»
    case = f"{label}, зерно {box.seed}"
    def pick(run, side=side):
        return run["full"] and not run["plank"] and run["side"] == side
    t = prepared(box, timeout_when=pick if kind == "timeout" else None,
                      no_report_when=pick if kind == "report" else None)
    rows, output = box.developer_advance(t)
    box.timeout_when = box.no_report_when = None
    assert_prepare(box, t, rows, output, words, case=case)


def test_ac4_side_head_timeout_refuses_naming_head(box):
    """Таймаут полного прогона головы — отказ подготовки, названа ветка.

    Сценарий (подслучай (г)
    `test_ac4_side_not_started_or_timeout_refuses_naming_side` —
    свежая задача, тест базы на ветке красен): полный прогон головы
    превышает предел. Отказ «… — подготовка», деталь называет сторону
    («ветк…»/«голов…»), перепрогонов нет, отказа «… — сломан правкой»
    нет.

    Ловит мутацию: таймаут головы принят за красный прогон — находки
    «сломан правкой» вместо отказа подготовки; сторона в отказе не
    названа.
    """
    base_words, head_words = ("баз",), ("ветк", "голов")
    cases = (("неизвестно база", "base", "report", base_words),
             ("неизвестно голова", "head", "report", head_words),
             ("таймаут база", "base", "timeout", base_words),
             ("таймаут голова", "head", "timeout", head_words))
    label, side, kind, words = cases[3]  # «таймаут голова»
    case = f"{label}, зерно {box.seed}"
    def pick(run, side=side):
        return run["full"] and not run["plank"] and run["side"] == side
    t = prepared(box, timeout_when=pick if kind == "timeout" else None,
                      no_report_when=pick if kind == "report" else None)
    rows, output = box.developer_advance(t)
    box.timeout_when = box.no_report_when = None
    assert_prepare(box, t, rows, output, words, case=case)


# ---------------------------------------------------------------- Ac5PassToPassTest


def test_ac5_retried_on_base_not_in_pass_to_pass(box):
    """Тест, прошедший на базе с повтором, — вне `PASS_TO_PASS`: красный на ветке не находка и не перепрогоняется (`pult-vitest` и `junit-xml`).

    Сценарий (подслучай): (а) `pult-vitest`: на базе тест `pass` с
    `retry_count: 1`, на ветке — `fail`; соседний тест зелён везде.
    Отказов гейта исходов нет, перепрогонов нет. (б) Контроль — тот же
    тест без повтора на базе: отказ «… — сломан правкой».

    Ловит мутацию: в набор берётся любой `passed` базы без сверки
    `retries == 0` — в (а) тест перепрогоняется и даёт «сломан
    правкой».
    """
    for retried in (True, False):
        case = f"{retried}, зерно {box.seed}"
        rel, name, other = box.js_rel(), box.js_name(), box.js_name()
        project = box.vitest_project({rel: [name, other]})
        t = box.task(project)
        box.cases[(rel, name)] = {
            "base": ["retried" if retried else "passed", "passed"],
            "head": ["failed"]}
        rows, output = box.developer_advance(t)
        if retried:
            no_gate_refusal(box, rows, output, case=case)
            assert box.subset_runs() == [], case + box.explain(rows, output)
        else:
            detail = refusal(box, rows, output, BROKEN_ACTION, case=case)
            assert box.case_id(project, rel, name) in detail, case + box.explain(rows, output)


def test_ac5_no_tests_on_base_empty_pass_to_pass(box):
    """«Нет тестов» на базе — `PASS_TO_PASS` пуст: новый красный тест ветки не находка.

    Сценарий: проект `junit-xml` без каталога `tests/` на базе; ветка
    добавляет файл `tests/` с тестом, который на ветке падает. Полный
    набор прогнан на обеих сторонах, отказа гейта исходов нет,
    перепрогонов нет.

    Ловит мутацию: «нет тестов» базы принят за отказ подготовки или за
    «все тесты исчезли» — отказ гейта исходов на ветке без единой
    находки по `PASS_TO_PASS`.
    """
    project = box.junit_project({})
    t = box.task(project)
    rel, name = box.py_rel(), box.py_name()
    box.cases[(rel, name)] = {"head": ["failed"]}
    rows, output = box.developer_advance(t, {rel: py_source([name])})
    no_gate_refusal(box, rows, output)
    assert len(box.suite_calls) == 2, box.explain(rows, output)
    assert box.subset_runs() == [], box.explain(rows, output)


# ---------------------------------------------------------------- Ac6RerunTest


def test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit(box):
    """Красный на ветке (`failed`, `error`, `passed` с повтором) — по два перепрогона на ветке и на базе только по своему файлу, с пределом компонента.

    Сценарий (подслучай — свежая задача): у компонента
    `full_suite_timeout_sec` из `random`; два-три файла тестов, тест
    первого файла на ветке — (а) `failed` (`junit-xml`); (б) `error`
    (`junit-xml`); (в) `passed` с `retry_count: 1` (`pult-vitest`);
    перепрогоны зелёные на обеих сторонах. Перепрогонов ветки — два,
    базы — два; каждый передаёт раннеру только файл красного теста;
    предел каждого — `full_suite_timeout_sec` компонента.

    Ловит мутацию: перепрогон по всем файлам набора — в запуске файлы
    других тестов; перепрогон базы пропущен — перепрогонов базы ноль;
    предел — `config.FULL_SUITE_TIMEOUT_SEC` либо предел приёмки — не
    тот предел в запуске; `passed` с повтором не считается красным —
    перепрогонов нет.
    """
    for kind in ("failed", "error", "retried"):
        case = f"{kind}, зерно {box.seed}"
        limit = box.rng.randint(300, 900)
        is_vitest = kind == "retried"
        rel_of = box.js_rel if is_vitest else box.py_rel
        name_of = box.js_name if is_vitest else box.py_name
        tests = {rel_of(): [name_of()] for _ in range(box.rng.randint(2, 3))}
        (rel, (name,)), = list(tests.items())[:1]
        project = (box.vitest_project(tests, limit=limit) if is_vitest
                   else box.junit_project(tests, limit=limit))
        t = box.task(project)
        box.cases[(rel, name)] = {"base": ["passed"],
                                   "head": [kind, "passed"]}
        rows, output = box.developer_advance(t)
        for side in ("head", "base"):
            runs = box.subset_runs(side)
            assert len(runs) == 2, case + box.explain(rows, output)
            for run in runs:
                assert run["files"] == [rel], case + box.explain(rows, output)
                assert run["timeout"] == limit, case + box.explain(rows, output)


def test_ac6_skipped_on_branch_not_rerun(box):
    """Тест `PASS_TO_PASS`, ставший на ветке `skipped`, не перепрогоняется.

    Сценарий: проект `junit-xml`; тест базы зелён, на ветке — пропуск.
    Перепрогонов нет ни на одной стороне (находка «стал пропуском» —
    предмет AC-9).

    Ловит мутацию: `skipped` на ветке считается красным — тест
    перепрогоняется дважды на каждой стороне.
    """
    rel, name, other = box.py_rel(), box.py_name(), box.py_name()
    project = box.junit_project({rel: [name, other]})
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["skipped"]}
    rows, output = box.developer_advance(t)
    assert box.subset_runs() == [], box.explain(rows, output)


# ---------------------------------------------------------------- Ac7RerunPrepareTest


def test_ac7_rerun_preparation_refusals(box):
    """Отказ подготовки перепрогона: `pult-vitest` без `select`, исход перепрогона не «зелёный» и не «красный», пропуск или нет записи на перепрогоне базы.

    Сценарий (подслучай — свежая задача, тест базы на ветке красен):
    (а) компонент `pult-vitest`, с записи которого после выхода из
    `tests_writing` снят `select`; (б) перепрогон ветки без
    отчёта (исход «неизвестно»); (в) перепрогон ветки превышает предел;
    (г) на перепрогоне базы запись теста `skipped`; (д) на перепрогоне
    базы записи теста нет. В каждом — отказ «переход отклонён: гейт
    неослабления по исходам — подготовка», находки «сломан правкой»
    нет.

    Ловит мутацию: без `select` перепрогон идёт полным набором — отказа
    подготовки нет; «неизвестно»/предел перепрогона принят за красный —
    отказ «сломан правкой»; пропуск или отсутствие записи на базе
    принят за красный базы — «нестабилен и на базе», гейт пройден.

    Метод исполняет подслучай (а) «без select» (`cases[0]`); (б)–(д) —
    методы `test_ac7_rerun_unknown_outcome_refuses`,
    `test_ac7_rerun_timeout_refuses`,
    `test_ac7_rerun_base_skipped_refuses`,
    `test_ac7_rerun_base_record_missing_refuses`.
    """
    def rerun_head(run):
        return not run["full"] and not run["plank"] and run["side"] == "head"

    cases = ("без select", "неизвестно", "таймаут", "база пропуск",
             "база нет записи")
    label = cases[0]  # «без select»
    case = f"{label}, зерно {box.seed}"
    is_vitest = label == "без select"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    if is_vitest:
        # Выход из `tests_writing` гоняет планку подмножеством —
        # `select` снимается с записи после него.
        box.drop_select()
    base = {"база пропуск": ["passed", "skipped"],
            "база нет записи": ["passed", "missing"]}.get(
                label, ["passed"])
    box.cases[(rel, name)] = {"base": base, "head": ["failed"]}
    box.no_report_when = rerun_head if label == "неизвестно" else None
    box.timeout_when = rerun_head if label == "таймаут" else None
    rows, output = box.developer_advance(t)
    box.no_report_when = box.timeout_when = None
    refusal(box, rows, output, PREPARE_ACTION, case=case)


def test_ac7_rerun_unknown_outcome_refuses(box):
    """Перепрогон ветки без отчёта (исход «неизвестно») — отказ подготовки перепрогона.

    Сценарий (подслучай (б) `test_ac7_rerun_preparation_refusals` —
    свежая задача, тест базы на ветке красен): компонент `junit-xml`,
    перепрогон ветки не пишет отчёт. Отказ «переход отклонён: гейт
    неослабления по исходам — подготовка», находки «сломан правкой»
    нет.

    Ловит мутацию: «неизвестно» перепрогона принят за красный — отказ
    «сломан правкой».
    """
    def rerun_head(run):
        return not run["full"] and not run["plank"] and run["side"] == "head"

    cases = ("без select", "неизвестно", "таймаут", "база пропуск",
             "база нет записи")
    label = cases[1]  # «неизвестно»
    case = f"{label}, зерно {box.seed}"
    is_vitest = label == "без select"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    if is_vitest:
        # Выход из `tests_writing` гоняет планку подмножеством —
        # `select` снимается с записи после него.
        box.drop_select()
    base = {"база пропуск": ["passed", "skipped"],
            "база нет записи": ["passed", "missing"]}.get(
                label, ["passed"])
    box.cases[(rel, name)] = {"base": base, "head": ["failed"]}
    box.no_report_when = rerun_head if label == "неизвестно" else None
    box.timeout_when = rerun_head if label == "таймаут" else None
    rows, output = box.developer_advance(t)
    box.no_report_when = box.timeout_when = None
    refusal(box, rows, output, PREPARE_ACTION, case=case)


def test_ac7_rerun_timeout_refuses(box):
    """Перепрогон ветки превышает предел — отказ подготовки перепрогона.

    Сценарий (подслучай (в) `test_ac7_rerun_preparation_refusals` —
    свежая задача, тест базы на ветке красен): компонент `junit-xml`,
    перепрогон ветки превышает предел. Отказ «переход отклонён: гейт
    неослабления по исходам — подготовка», находки «сломан правкой»
    нет.

    Ловит мутацию: предел перепрогона принят за красный — отказ
    «сломан правкой».
    """
    def rerun_head(run):
        return not run["full"] and not run["plank"] and run["side"] == "head"

    cases = ("без select", "неизвестно", "таймаут", "база пропуск",
             "база нет записи")
    label = cases[2]  # «таймаут»
    case = f"{label}, зерно {box.seed}"
    is_vitest = label == "без select"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    if is_vitest:
        # Выход из `tests_writing` гоняет планку подмножеством —
        # `select` снимается с записи после него.
        box.drop_select()
    base = {"база пропуск": ["passed", "skipped"],
            "база нет записи": ["passed", "missing"]}.get(
                label, ["passed"])
    box.cases[(rel, name)] = {"base": base, "head": ["failed"]}
    box.no_report_when = rerun_head if label == "неизвестно" else None
    box.timeout_when = rerun_head if label == "таймаут" else None
    rows, output = box.developer_advance(t)
    box.no_report_when = box.timeout_when = None
    refusal(box, rows, output, PREPARE_ACTION, case=case)


def test_ac7_rerun_base_skipped_refuses(box):
    """Запись теста `skipped` на перепрогоне базы — отказ подготовки перепрогона.

    Сценарий (подслучай (г) `test_ac7_rerun_preparation_refusals` —
    свежая задача, тест базы на ветке красен): компонент `junit-xml`,
    на перепрогоне базы запись теста `skipped`. Отказ «переход
    отклонён: гейт неослабления по исходам — подготовка», находки
    «сломан правкой» нет.

    Ловит мутацию: пропуск на базе принят за красный базы —
    «нестабилен и на базе», гейт пройден.
    """
    def rerun_head(run):
        return not run["full"] and not run["plank"] and run["side"] == "head"

    cases = ("без select", "неизвестно", "таймаут", "база пропуск",
             "база нет записи")
    label = cases[3]  # «база пропуск»
    case = f"{label}, зерно {box.seed}"
    is_vitest = label == "без select"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    if is_vitest:
        # Выход из `tests_writing` гоняет планку подмножеством —
        # `select` снимается с записи после него.
        box.drop_select()
    base = {"база пропуск": ["passed", "skipped"],
            "база нет записи": ["passed", "missing"]}.get(
                label, ["passed"])
    box.cases[(rel, name)] = {"base": base, "head": ["failed"]}
    box.no_report_when = rerun_head if label == "неизвестно" else None
    box.timeout_when = rerun_head if label == "таймаут" else None
    rows, output = box.developer_advance(t)
    box.no_report_when = box.timeout_when = None
    refusal(box, rows, output, PREPARE_ACTION, case=case)


def test_ac7_rerun_base_record_missing_refuses(box):
    """Нет записи теста на перепрогоне базы — отказ подготовки перепрогона.

    Сценарий (подслучай (д) `test_ac7_rerun_preparation_refusals` —
    свежая задача, тест базы на ветке красен): компонент `junit-xml`,
    на перепрогоне базы записи теста нет. Отказ «переход отклонён:
    гейт неослабления по исходам — подготовка», находки «сломан
    правкой» нет.

    Ловит мутацию: отсутствие записи на базе принято за красный базы
    — «нестабилен и на базе», гейт пройден.
    """
    def rerun_head(run):
        return not run["full"] and not run["plank"] and run["side"] == "head"

    cases = ("без select", "неизвестно", "таймаут", "база пропуск",
             "база нет записи")
    label = cases[4]  # «база нет записи»
    case = f"{label}, зерно {box.seed}"
    is_vitest = label == "без select"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    if is_vitest:
        # Выход из `tests_writing` гоняет планку подмножеством —
        # `select` снимается с записи после него.
        box.drop_select()
    base = {"база пропуск": ["passed", "skipped"],
            "база нет записи": ["passed", "missing"]}.get(
                label, ["passed"])
    box.cases[(rel, name)] = {"base": base, "head": ["failed"]}
    box.no_report_when = rerun_head if label == "неизвестно" else None
    box.timeout_when = rerun_head if label == "таймаут" else None
    rows, output = box.developer_advance(t)
    box.no_report_when = box.timeout_when = None
    refusal(box, rows, output, PREPARE_ACTION, case=case)


def test_ac7_branch_rerun_red_kinds(box):
    """На перепрогоне ветки `failed`, `error`, `passed` с повтором, `skipped` или нет записи — красный этого прогона: трижды красный — «сломан правкой».

    Сценарий (подслучай — свежая задача): тест базы зелён на базе
    трижды, на ветке полный прогон — `failed`, оба перепрогона ветки —
    (а) `failed`, (б) `error`, (в) `skipped`, (г) нет записи (`junit-
    xml`), (д) `passed` с `retry_count: 1` (`pult-vitest`). Отказ «… —
    сломан правкой» с идентификатором теста.

    Ловит мутацию: `skipped` или отсутствие записи на перепрогоне ветки
    — зелёный либо отказ подготовки; `passed` с повтором — зелёный;
    итог — «нестабилен после правки» (общий отказ) вместо «сломан
    правкой».

    Метод исполняет подслучай (а) `failed`; (б)–(д) — методы
    `test_ac7_branch_rerun_error_is_red`,
    `test_ac7_branch_rerun_skipped_is_red`,
    `test_ac7_branch_rerun_missing_is_red`,
    `test_ac7_branch_rerun_retried_is_red`.
    """
    kind = "failed"
    case = f"{kind}, зерно {box.seed}"
    is_vitest = kind == "retried"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"],
                               "head": ["failed", kind]}
    rows, output = box.developer_advance(t)
    detail = refusal(box, rows, output, BROKEN_ACTION, case=case)
    assert box.case_id(project, rel, name) in detail, case + box.explain(rows, output)


def test_ac7_branch_rerun_error_is_red(box):
    """`error` на обоих перепрогонах ветки — красный прогона: трижды красный — «сломан правкой».

    Сценарий (подслучай (б) `test_ac7_branch_rerun_red_kinds` —
    свежая задача, `junit-xml`): тест базы зелён на базе трижды, на
    ветке полный прогон — `failed`, оба перепрогона ветки — `error`.
    Отказ «… — сломан правкой» с идентификатором теста.

    Ловит мутацию: `error` перепрогона не считается красным — зелёный
    либо итог «нестабилен после правки» (общий отказ) вместо «сломан
    правкой».
    """
    kind = "error"
    case = f"{kind}, зерно {box.seed}"
    is_vitest = kind == "retried"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"],
                               "head": ["failed", kind]}
    rows, output = box.developer_advance(t)
    detail = refusal(box, rows, output, BROKEN_ACTION, case=case)
    assert box.case_id(project, rel, name) in detail, case + box.explain(rows, output)


def test_ac7_branch_rerun_skipped_is_red(box):
    """`skipped` на обоих перепрогонах ветки — красный прогона: трижды красный — «сломан правкой».

    Сценарий (подслучай (в) `test_ac7_branch_rerun_red_kinds` —
    свежая задача, `junit-xml`): тест базы зелён на базе трижды, на
    ветке полный прогон — `failed`, оба перепрогона ветки — `skipped`.
    Отказ «… — сломан правкой» с идентификатором теста.

    Ловит мутацию: `skipped` на перепрогоне ветки — зелёный либо
    отказ подготовки.
    """
    kind = "skipped"
    case = f"{kind}, зерно {box.seed}"
    is_vitest = kind == "retried"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"],
                               "head": ["failed", kind]}
    rows, output = box.developer_advance(t)
    detail = refusal(box, rows, output, BROKEN_ACTION, case=case)
    assert box.case_id(project, rel, name) in detail, case + box.explain(rows, output)


def test_ac7_branch_rerun_missing_is_red(box):
    """Нет записи теста на обоих перепрогонах ветки — красный прогона: трижды красный — «сломан правкой».

    Сценарий (подслучай (г) `test_ac7_branch_rerun_red_kinds` —
    свежая задача, `junit-xml`): тест базы зелён на базе трижды, на
    ветке полный прогон — `failed`, на обоих перепрогонах ветки записи
    теста нет. Отказ «… — сломан правкой» с идентификатором теста.

    Ловит мутацию: отсутствие записи на перепрогоне ветки — зелёный
    либо отказ подготовки.
    """
    kind = "missing"
    case = f"{kind}, зерно {box.seed}"
    is_vitest = kind == "retried"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"],
                               "head": ["failed", kind]}
    rows, output = box.developer_advance(t)
    detail = refusal(box, rows, output, BROKEN_ACTION, case=case)
    assert box.case_id(project, rel, name) in detail, case + box.explain(rows, output)


def test_ac7_branch_rerun_retried_is_red(box):
    """`passed` с повтором на обоих перепрогонах ветки — красный прогона: трижды красный — «сломан правкой».

    Сценарий (подслучай (д) `test_ac7_branch_rerun_red_kinds` —
    свежая задача, `pult-vitest`): тест базы зелён на базе трижды, на
    ветке полный прогон — `failed`, оба перепрогона ветки — `passed` с
    `retry_count: 1`. Отказ «… — сломан правкой» с идентификатором
    теста.

    Ловит мутацию: `passed` с повтором — зелёный; итог — «нестабилен
    после правки» (общий отказ) вместо «сломан правкой».
    """
    kind = "retried"
    case = f"{kind}, зерно {box.seed}"
    is_vitest = kind == "retried"
    rel = box.js_rel() if is_vitest else box.py_rel()
    name = box.js_name() if is_vitest else box.py_name()
    project = (box.vitest_project({rel: [name]}) if is_vitest
               else box.junit_project({rel: [name]}))
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"],
                               "head": ["failed", kind]}
    rows, output = box.developer_advance(t)
    detail = refusal(box, rows, output, BROKEN_ACTION, case=case)
    assert box.case_id(project, rel, name) in detail, case + box.explain(rows, output)


# ---------------------------------------------------------------- Ac8VerdictByRecordTest


def test_ac8_broken_unstable_and_flaky_on_base(box):
    """«Сломан правкой», «нестабилен после правки» и «нестабилен и на базе» по исходам трёх прогонов.

    Сценарий (подслучай — свежая задача, проект `junit-xml`): (а) на
    ветке красный трижды, база зелёна трижды — отказ «… — сломан
    правкой» с идентификатором; (б) на ветке красный, затем зелёный
    (порядок из `random`) — общий отказ «переход отклонён: гейт
    неослабления по исходам» с идентификатором; (в) на ветке трижды
    красный, база красна на одном из перепрогонов (`failed` или
    `error`) — отказа гейта исходов нет, в журнале строка «нестабилен и
    на базе: <идентификатор>».

    Ловит мутацию: «нестабилен» не отличается от «сломан» — в (б)
    действие «… — сломан правкой»; красная база перепрогона не читается
    — в (в) отказ «сломан правкой»; строка о базе не пишется — её нет
    в журнале.

    Метод исполняет подслучай (а) «сломан»: ветки и помощники всех
    подслучаев — в теле, исполняется одна ветка; (б) и (в) — методы
    `test_ac8_unstable_after_change_general_refusal`,
    `test_ac8_flaky_on_base_no_refusal`.
    """
    label = "сломан"
    case = f"{label}, зерно {box.seed}"
    rel, name = box.py_rel(), box.py_name()
    project = box.junit_project({rel: [name, box.py_name()]})
    t = box.task(project)
    tid = box.case_id(project, rel, name)
    head = ["failed", "failed", "failed"]
    base = ["passed", "passed", "passed"]
    if label == "нестабилен":
        head[box.rng.choice((1, 2))] = "passed"
    if label == "база":
        base[box.rng.choice((1, 2))] = box.rng.choice(("failed", "error"))
    box.cases[(rel, name)] = {"base": base, "head": head}
    rows, output = box.developer_advance(t)
    if label == "сломан":
        assert tid in refusal(box, rows, output, BROKEN_ACTION, case=case), case + box.explain(rows, output)
    elif label == "нестабилен":
        assert tid in refusal(box, rows, output, OUTCOME_ACTION, case=case), case + box.explain(rows, output)
    else:
        no_gate_refusal(box, rows, output, case=case)
        texts = [f"{r['action']} {r['detail'] or ''}" for r in rows]
        assert any(FLAKY_ON_BASE + tid in x for x in texts), case + box.explain(rows, output)


def test_ac8_unstable_after_change_general_refusal(box):
    """«Нестабилен после правки»: на ветке красный, затем зелёный — общий отказ гейта исходов.

    Сценарий (подслучай (б) `test_ac8_broken_unstable_and_flaky_on_base`
    — свежая задача, проект `junit-xml`): на ветке красный, затем
    зелёный (порядок из `random`), база зелёна трижды — общий отказ
    «переход отклонён: гейт неослабления по исходам» с
    идентификатором.

    Ловит мутацию: «нестабилен» не отличается от «сломан» — действие
    «… — сломан правкой».
    """
    label = "нестабилен"
    case = f"{label}, зерно {box.seed}"
    rel, name = box.py_rel(), box.py_name()
    project = box.junit_project({rel: [name, box.py_name()]})
    t = box.task(project)
    tid = box.case_id(project, rel, name)
    head = ["failed", "failed", "failed"]
    base = ["passed", "passed", "passed"]
    if label == "нестабилен":
        head[box.rng.choice((1, 2))] = "passed"
    if label == "база":
        base[box.rng.choice((1, 2))] = box.rng.choice(("failed", "error"))
    box.cases[(rel, name)] = {"base": base, "head": head}
    rows, output = box.developer_advance(t)
    if label == "сломан":
        assert tid in refusal(box, rows, output, BROKEN_ACTION, case=case), case + box.explain(rows, output)
    elif label == "нестабилен":
        assert tid in refusal(box, rows, output, OUTCOME_ACTION, case=case), case + box.explain(rows, output)
    else:
        no_gate_refusal(box, rows, output, case=case)
        texts = [f"{r['action']} {r['detail'] or ''}" for r in rows]
        assert any(FLAKY_ON_BASE + tid in x for x in texts), case + box.explain(rows, output)


def test_ac8_flaky_on_base_no_refusal(box):
    """«Нестабилен и на базе»: база красна на одном из перепрогонов — отказа нет, строка о базе в журнале.

    Сценарий (подслучай (в) `test_ac8_broken_unstable_and_flaky_on_base`
    — свежая задача, проект `junit-xml`): на ветке трижды красный,
    база красна на одном из перепрогонов (`failed` или `error`) —
    отказа гейта исходов нет, в журнале строка «нестабилен и на базе:
    <идентификатор>».

    Ловит мутацию: красная база перепрогона не читается — отказ
    «сломан правкой»; строка о базе не пишется — её нет в журнале.
    """
    label = "база"
    case = f"{label}, зерно {box.seed}"
    rel, name = box.py_rel(), box.py_name()
    project = box.junit_project({rel: [name, box.py_name()]})
    t = box.task(project)
    tid = box.case_id(project, rel, name)
    head = ["failed", "failed", "failed"]
    base = ["passed", "passed", "passed"]
    if label == "нестабилен":
        head[box.rng.choice((1, 2))] = "passed"
    if label == "база":
        base[box.rng.choice((1, 2))] = box.rng.choice(("failed", "error"))
    box.cases[(rel, name)] = {"base": base, "head": head}
    rows, output = box.developer_advance(t)
    if label == "сломан":
        assert tid in refusal(box, rows, output, BROKEN_ACTION, case=case), case + box.explain(rows, output)
    elif label == "нестабилен":
        assert tid in refusal(box, rows, output, OUTCOME_ACTION, case=case), case + box.explain(rows, output)
    else:
        no_gate_refusal(box, rows, output, case=case)
        texts = [f"{r['action']} {r['detail'] or ''}" for r in rows]
        assert any(FLAKY_ON_BASE + tid in x for x in texts), case + box.explain(rows, output)


def test_ac8_neighbour_red_in_same_file_does_not_redden_rerun(box):
    """Итог перепрогона — по записи теста: красный сосед в том же файле не делает зелёную запись красной.

    Сценарий: в одном файле тест A (`PASS_TO_PASS`) и сосед B, красный
    на базе и на ветке во всех прогонах. A на ветке: полный прогон —
    `failed`, оба перепрогона — `passed`; на базе A зелён. Итог A —
    «нестабилен после правки»: общий отказ с идентификатором A, не
    «… — сломан правкой» и не «нестабилен и на базе».

    Ловит мутацию: итог перепрогона по вердикту прогона (красный из-за
    B) — A красен трижды на ветке и база красна — отказа гейта нет или
    отказ «сломан правкой».
    """
    rel, a, b = box.py_rel(), box.py_name(), box.py_name()
    project = box.junit_project({rel: [a, b]})
    t = box.task(project)
    box.cases[(rel, a)] = {"base": ["passed"], "head": ["failed", "passed"]}
    box.cases[(rel, b)] = {"base": ["failed"], "head": ["failed"]}
    rows, output = box.developer_advance(t)
    detail = refusal(box, rows, output, OUTCOME_ACTION)
    assert box.case_id(project, rel, a) in detail, box.explain(rows, output)
    assert box.case_id(project, rel, b) not in detail, box.explain(rows, output)


# ---------------------------------------------------------------- Ac9CompareTest


def test_ac9_vitest_records_findings_and_non_findings(box):
    """Сравнение записей `pult-vitest`: исчезнувший, ставший пропуском, `todo`/`fails` появились, новый пропуск/`todo`/`fails` — находки; неизменные `todo`/`fails` — нет.

    Сценарий: один проект `pult-vitest`, один отказ. База: `gone`
    (`pass`, на ветке файла нет теста), `s_pass`/`s_fail`/`s_err`
    (`pass`/`fail AssertionError`/`fail TypeError`, на ветке `skip`),
    `to_todo` (`pass`, на ветке `todo`), `to_fails` (`pass`, на ветке
    `pass` с `fails`), `keep_todo` (`todo` на обеих сторонах),
    `keep_fails` (`pass` с `fails` на обеих), `quiet` (зелёный везде).
    Ветка добавляет `new_skip`, `new_todo`, `new_fails`, `new_pass`.
    Общий отказ «… по исходам»: идентификаторы всех находок — в детали,
    каждый ровно одной строкой; `keep_todo`, `keep_fails`, `quiet`,
    `new_pass` в детали нет. Деталь несёт итоговую строку о росте
    пропусков без идентификатора теста.

    Ловит мутацию: «стал пропуском» только у `passed` базы — у `s_fail`/
    `s_err` нет находки; `todo`/`fails` — находка без сверки с базой —
    `keep_todo`/`keep_fails` в отказе; новый идентификатор не
    проверяется — `new_*` нет в детали; у `to_todo` две находки (пропуск
    и `todo`) — две строки; рост пропусков — отдельные строки по
    тестам без итоговой.
    """
    rel, gone_rel = box.js_rel(), box.js_rel()
    n = {k: box.js_name() for k in (
        "gone", "s_pass", "s_fail", "s_err", "to_todo", "to_fails",
        "keep_todo", "keep_fails", "quiet", "new_skip", "new_todo",
        "new_fails", "new_pass")}
    base_names = [n[k] for k in ("s_pass", "s_fail", "s_err", "to_todo",
                                 "to_fails", "keep_todo", "keep_fails",
                                 "quiet")]
    project = box.vitest_project({rel: base_names, gone_rel: [n["gone"]]})
    t = box.task(project)
    plan = {"s_pass": ("passed", "skipped"), "s_fail": ("failed", "skipped"),
            "s_err": ("error", "skipped"), "to_todo": ("passed", "todo"),
            "to_fails": ("passed", "fails"), "keep_todo": ("todo", "todo"),
            "keep_fails": ("fails", "fails"),
            "new_skip": ("passed", "skipped"), "new_todo": ("passed", "todo"),
            "new_fails": ("passed", "fails")}
    for key, (base, head) in plan.items():
        box.cases[(rel, n[key])] = {"base": [base], "head": [head]}
    head_names = base_names + [n[k] for k in ("new_skip", "new_todo",
                                              "new_fails", "new_pass")]
    rows, output = box.developer_advance(t, {rel: js_source(head_names),
                                              gone_rel: js_source([])})
    detail = refusal(box, rows, output, OUTCOME_ACTION)
    found = ("s_pass", "s_fail", "s_err", "to_todo", "to_fails",
             "new_skip", "new_todo", "new_fails")
    for key in found:
        cid = box.case_id(project, rel, n[key])
        assert len(box.lines_with(detail, cid)) == 1, box.explain(rows, output) + f"\n{key}: {cid}"
    gone = box.case_id(project, gone_rel, n["gone"])
    assert len(box.lines_with(detail, gone)) == 1, box.explain(rows, output)
    for key in ("keep_todo", "keep_fails", "quiet", "new_pass"):
        assert box.case_id(project, rel, n[key]) not in detail, box.explain(rows, output) + f"\n{key}"
    ids = [box.case_id(project, rel, x) for x in n.values()] + [gone]
    summary = [line for line in detail.splitlines() if "пропуск" in line.lower()
               and not any(cid in line for cid in ids)]
    assert summary, box.explain(rows, output)


def test_ac9_junit_records_findings(box):
    """Сравнение записей `junit-xml`: исчезнувший тест и тест базы `passed`/`failed`/`error`, ставший пропуском, — находки; новый пропуск — находка.

    Сценарий: проект `junit-xml`; тест `gone` исчез из отчёта ветки
    (записи нет, текст файла не менялся), `s_pass`/`s_fail`/`s_err` на
    ветке `skipped`, новый тест ветки `new_skip` — пропуск, новый
    `new_pass` — зелёный. Общий отказ: идентификаторы `gone`, `s_*`,
    `new_skip` — каждый одной строкой; `new_pass` в детали нет.

    Ловит мутацию: исчезновение ищется только по тексту файлов
    (гейт по тексту), а не по отчёту — `gone` без находки; «стал
    пропуском» только у `passed` — `s_fail`/`s_err` без находки.
    """
    rel = box.py_rel()
    n = {k: box.py_name() for k in ("gone", "s_pass", "s_fail", "s_err",
                                     "new_skip", "new_pass")}
    base_names = [n[k] for k in ("gone", "s_pass", "s_fail", "s_err")]
    project = box.junit_project({rel: base_names})
    t = box.task(project)
    plan = {"gone": ("passed", "missing"), "s_pass": ("passed", "skipped"),
            "s_fail": ("failed", "skipped"), "s_err": ("error", "skipped")}
    for key, (base, head) in plan.items():
        box.cases[(rel, n[key])] = {"base": [base], "head": [head]}
    new_rel = box.py_rel()
    box.cases[(new_rel, n["new_skip"])] = {"head": ["skipped"]}
    rows, output = box.developer_advance(
        t, {new_rel: py_source([n["new_skip"], n["new_pass"]])})
    detail = refusal(box, rows, output, OUTCOME_ACTION)
    for key in ("gone", "s_pass", "s_fail", "s_err"):
        cid = box.case_id(project, rel, n[key])
        assert len(box.lines_with(detail, cid)) == 1, box.explain(rows, output) + f"\n{key}"
    assert (len(box.lines_with(
        detail, box.case_id(project, new_rel, n["new_skip"])))) == 1, box.explain(rows, output)
    assert box.case_id(project, new_rel, n["new_pass"]) not in detail, box.explain(rows, output)


def test_ac9_one_finding_per_id_senior_kind(box):
    """Один идентификатор — одна находка, старшая: красный трижды тест, у которого появилось `fails`, — только «сломан правкой».

    Сценарий: `pult-vitest`; тест базы `pass` без `fails`; на ветке
    все три прогона — `fail` с `fails: true`. Отказ — действие «… —
    сломан правкой» (непокрытые находки только этого вида),
    идентификатор теста — ровно в одной строке детали.

    Ловит мутацию: находка сравнения («появилось `fails`») добавляется
    к находке «сломан правкой» — две находки, действие общего отказа и
    две строки с идентификатором.
    """
    rel, name = box.js_rel(), box.js_name()
    project = box.vitest_project({rel: [name, box.js_name()]})
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
    with mock.patch.dict(VITEST_KIND, {"failed": {
            "state": "fail", "error_name": "AssertionError", "fails": True}}):
        rows, output = box.developer_advance(t)
    detail = refusal(box, rows, output, BROKEN_ACTION)
    assert len(box.lines_with(detail, box.case_id(project, rel, name))) == 1, box.explain(rows, output)


# ---------------------------------------------------------------- Ac10OrderTest


def test_ac10_findings_order_and_one_line_each(box):
    """Порядок находок одного отказа: исчезнувшие → «сломан правкой» → «нестабилен после правки» → прочие; внутри вида — по идентификатору.

    Сценарий: проект `junit-xml`; по два теста каждого вида в
    случайных файлах: исчезнувшие из отчёта ветки, трижды красные на
    ветке, красные один раз из трёх, ставшие пропуском. Общий отказ;
    строки с идентификаторами идут видами в указанном порядке, внутри
    вида — по возрастанию идентификатора; у каждой находки своя
    строка, не несущая идентификатора другой находки.

    Ловит мутацию: находки в порядке отчёта или в порядке сравнения
    (прочие раньше красных) — порядок строк другой; внутри вида без
    сортировки — пары идут в порядке файлов; все находки одной
    строкой.
    """
    kinds = ("gone", "broken", "unstable", "skip")
    names = {k: [(box.py_rel(), box.py_name()) for _ in range(2)]
             for k in kinds}
    tests: dict = {}
    for items in names.values():
        for rel, name in items:
            tests.setdefault(rel, []).append(name)
    project = box.junit_project(tests)
    t = box.task(project)
    plan = {"gone": {"base": ["passed"], "head": ["missing"]},
            "broken": {"base": ["passed"], "head": ["failed"]},
            "unstable": {"base": ["passed"], "head": ["failed", "passed"]},
            "skip": {"base": ["passed"], "head": ["skipped"]}}
    for kind, items in names.items():
        for rel, name in items:
            box.cases[(rel, name)] = plan[kind]
    rows, output = box.developer_advance(t)
    detail = refusal(box, rows, output, OUTCOME_ACTION)
    lines = detail.splitlines()
    ids = {k: sorted(box.case_id(project, r, n) for r, n in items)
           for k, items in names.items()}
    expected = [cid for k in kinds for cid in ids[k]]
    every = set(expected)
    position = []
    for cid in expected:
        found = [i for i, line in enumerate(lines) if cid in line]
        assert len(found) == 1, box.explain(rows, output) + f"\n{cid}"
        others = [o for o in every if o != cid and o in lines[found[0]]]
        assert others == [], box.explain(rows, output)
        position.append(found[0])
    assert position == sorted(position), box.explain(rows, output)


# ---------------------------------------------------------------- Ac11MandateTest


def test_ac11_file_and_prefix_mandate_cover_findings(box):
    """Мандат Оператора на путь файла и на префикс `путь::Класс`/`путь::Класс::метод` снимает находки этого файла; мандат на другой файл — нет.

    Сценарий (подслучай — свежая задача, тесты класса `K` трижды
    красные на ветке): ANSWER Оператора с маркером «Ослабление тестов
    разрешено:» (а) на путь файла; (б) на `путь::K`; (в) на
    `путь::K::test_x` при единственном красном `K::test_x[a]`/`[b]`
    (варианты); (г) на путь другого файла. В (а)–(в) отказа гейта
    исходов нет; в (г) — отказ «… — сломан правкой».

    Ловит мутацию: мандат сверяется точным равенством с
    идентификатором — префикс класса и метод с вариантами не покрывают;
    покрытие по имени файла без пути — мандат другого файла покрывает.

    Метод исполняет подслучай (а) «файл»: ветки всех подслучаев — в
    теле, исполняется одна; (б)–(г) — методы
    `test_ac11_class_prefix_mandate_covers`,
    `test_ac11_method_prefix_mandate_covers_variants`,
    `test_ac11_other_file_mandate_does_not_cover`.
    """
    label = "файл"
    case = f"{label}, зерно {box.seed}"
    klass = "K" + box.word().capitalize()
    method = box.py_name()
    if label == "метод":
        names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
    else:
        names = [f"{klass}{SEP}{box.py_name()}" for _ in range(2)]
    project, t, rel = broken_task(box, names)
    element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
               "метод": f"{rel}{SEP}{klass}{SEP}{method}",
               "другой файл": box.py_rel()}[label]
    box.operator_mandate(t, [element])
    rows, output = box.developer_advance(t, finished=True)
    if label == "другой файл":
        refusal(box, rows, output, BROKEN_ACTION, case=case)
    else:
        no_gate_refusal(box, rows, output, case=case)


def test_ac11_class_prefix_mandate_covers(box):
    """Мандат Оператора на префикс `путь::Класс` снимает находки класса.

    Сценарий (подслучай (б)
    `test_ac11_file_and_prefix_mandate_cover_findings` — свежая
    задача, тесты класса `K` трижды красные на ветке): ANSWER
    Оператора с маркером «Ослабление тестов разрешено:» на `путь::K`.
    Отказа гейта исходов нет.

    Ловит мутацию: мандат сверяется точным равенством с
    идентификатором — префикс класса не покрывает.
    """
    label = "класс"
    case = f"{label}, зерно {box.seed}"
    klass = "K" + box.word().capitalize()
    method = box.py_name()
    if label == "метод":
        names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
    else:
        names = [f"{klass}{SEP}{box.py_name()}" for _ in range(2)]
    project, t, rel = broken_task(box, names)
    element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
               "метод": f"{rel}{SEP}{klass}{SEP}{method}",
               "другой файл": box.py_rel()}[label]
    box.operator_mandate(t, [element])
    rows, output = box.developer_advance(t, finished=True)
    if label == "другой файл":
        refusal(box, rows, output, BROKEN_ACTION, case=case)
    else:
        no_gate_refusal(box, rows, output, case=case)


def test_ac11_method_prefix_mandate_covers_variants(box):
    """Мандат Оператора на `путь::Класс::метод` снимает находки его вариантов.

    Сценарий (подслучай (в)
    `test_ac11_file_and_prefix_mandate_cover_findings` — свежая
    задача): единственный красный метод `K::test_x[a]`/`[b]`
    (варианты), ANSWER Оператора с маркером «Ослабление тестов
    разрешено:» на `путь::K::test_x`. Отказа гейта исходов нет.

    Ловит мутацию: мандат сверяется точным равенством с
    идентификатором — метод с вариантами не покрывается.
    """
    label = "метод"
    case = f"{label}, зерно {box.seed}"
    klass = "K" + box.word().capitalize()
    method = box.py_name()
    if label == "метод":
        names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
    else:
        names = [f"{klass}{SEP}{box.py_name()}" for _ in range(2)]
    project, t, rel = broken_task(box, names)
    element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
               "метод": f"{rel}{SEP}{klass}{SEP}{method}",
               "другой файл": box.py_rel()}[label]
    box.operator_mandate(t, [element])
    rows, output = box.developer_advance(t, finished=True)
    if label == "другой файл":
        refusal(box, rows, output, BROKEN_ACTION, case=case)
    else:
        no_gate_refusal(box, rows, output, case=case)


def test_ac11_other_file_mandate_does_not_cover(box):
    """Мандат Оператора на путь другого файла находки не снимает.

    Сценарий (подслучай (г)
    `test_ac11_file_and_prefix_mandate_cover_findings` — свежая
    задача, тесты класса `K` трижды красные на ветке): ANSWER
    Оператора с маркером «Ослабление тестов разрешено:» на путь
    другого файла. Отказ «… — сломан правкой».

    Ловит мутацию: покрытие по имени файла без пути — мандат другого
    файла покрывает.
    """
    label = "другой файл"
    case = f"{label}, зерно {box.seed}"
    klass = "K" + box.word().capitalize()
    method = box.py_name()
    if label == "метод":
        names = [f"{klass}{SEP}{method}[a]", f"{klass}{SEP}{method}[b]"]
    else:
        names = [f"{klass}{SEP}{box.py_name()}" for _ in range(2)]
    project, t, rel = broken_task(box, names)
    element = {"файл": rel, "класс": f"{rel}{SEP}{klass}",
               "метод": f"{rel}{SEP}{klass}{SEP}{method}",
               "другой файл": box.py_rel()}[label]
    box.operator_mandate(t, [element])
    rows, output = box.developer_advance(t, finished=True)
    if label == "другой файл":
        refusal(box, rows, output, BROKEN_ACTION, case=case)
    else:
        no_gate_refusal(box, rows, output, case=case)


def test_ac11_prefix_needs_separator_after_it(box):
    """Префикс `путь::Класс` не покрывает `путь::КлассДругой::метод`: за префиксом иной символ.

    Сценарий: в файле тесты классов `K<слово>` и `K<слово>Other`, оба
    трижды красные на ветке; мандат Оператора — `путь::K<слово>`. Отказ
    «… — сломан правкой»; деталь несёт идентификатор теста класса
    `K<слово>Other` и не несёт идентификатора теста класса `K<слово>`.

    Ловит мутацию: покрытие — `startswith` без сверки следующего
    символа — `K<слово>Other` покрыт, отказа нет.
    """
    klass = "K" + box.word().capitalize()
    own, other = f"{klass}{SEP}{box.py_name()}", f"{klass}Other{SEP}{box.py_name()}"
    project, t, rel = broken_task(box, [own, other])
    box.operator_mandate(t, [f"{rel}{SEP}{klass}"])
    rows, output = box.developer_advance(t, finished=True)
    detail = refusal(box, rows, output, BROKEN_ACTION)
    assert box.case_id(project, rel, other) in detail, box.explain(rows, output)
    assert box.case_id(project, rel, own) not in detail, box.explain(rows, output)


def test_ac11_role_autocommitted_answer_does_not_cover(box):
    """ANSWER с маркером мандата, унесённый автокоммитом шага developer, находку не снимает.

    Сценарий: тест трижды красный на ветке; ANSWER-1.md с маркером
    «Ослабление тестов разрешено: <путь файла>» кладётся в каталог
    документов и уходит в ссылку автокоммитом шага developer. Отказ
    «… — сломан правкой» с идентификатором теста.

    Ловит мутацию: мандат собран без отбраковки автокоммита роли —
    находка покрыта, отказа нет.
    """
    name = box.py_name()
    project, t, rel = broken_task(box, [name])
    rows, output = box.developer_advance(t, before=box.role_mandate(t, [rel]))
    assert box.case_id(project, rel, name) in refusal(box, rows, output, BROKEN_ACTION), box.explain(rows, output)


# ---------------------------------------------------------------- Ac13PassedRecordTest


def test_ac13_passed_gate_journal_counts(box):
    """Пройденный гейт пишет запись с числом тестов базы и ветки, числом прошедших перепрогон, числом прогонов файлов и числом покрытых мандатом находок.

    Сценарий: проект `junit-xml`; на базе `nb` тестов (из `random`), из
    них `m` исчезают на ветке в файле под мандатом Оператора, ветка
    добавляет `k` новых зелёных; один тест трижды красен на ветке и
    красен на одном перепрогоне базы («нестабилен и на базе»). Гейт
    пройден; среди новых записей журнала есть запись, несущая отдельными
    числами `nb`, число тестов ветки, 1 (тестов прошедших перепрогон),
    4 (прогонов файлов) и `m` (покрытых находок).

    Ловит мутацию: запись пройденного гейта не пишется — записи с
    числами нет; число покрытых мандатом находок не указано — нет
    числа `m`; прогоны файлов не посчитаны — нет числа 4.
    """
    nb = box.rng.randint(11, 19)
    m = box.rng.randint(2, 3)
    k = box.rng.randint(21, 29)
    covered = box.py_rel()
    gone = [box.py_name() for _ in range(m)]
    flaky_rel, flaky = box.py_rel(), box.py_name()
    rest_rel = box.py_rel()
    rest = [box.py_name() for _ in range(nb - m - 1)]
    tests = {covered: gone, flaky_rel: [flaky], rest_rel: rest}
    project = box.junit_project(tests)
    t = box.task(project)
    box.cases[(flaky_rel, flaky)] = {"base": ["passed", "failed", "passed"],
                                      "head": ["failed"]}
    new_rel = box.py_rel()
    added = [box.py_name() for _ in range(k)]
    box.operator_mandate(t, [covered])
    rows, output = box.developer_advance(
        t, {covered: None, new_rel: py_source(added)}, finished=True)
    no_gate_refusal(box, rows, output)
    nh = nb - m + k
    wanted = (nb, nh, 1, 4, m)

    def numbers(row) -> set:
        text = f"{row['action']} {row['detail'] or ''}"
        return {int(x) for x in re.findall(r"(?<![\w.:-])\d+(?![\w.:-])", text)}
    assert any(set(wanted) <= numbers(r) for r in rows), box.explain(rows, output) + f"\nожидались числа {wanted}"
