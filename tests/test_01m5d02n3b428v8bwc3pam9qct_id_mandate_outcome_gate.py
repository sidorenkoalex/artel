"""Мандат на ослабление теста по идентификатору в гейте неослабления по исходам: отбраковка автокоммита роли, точное равенство с `#n`, подсказка отказа (AC-11..AC-13).

Группа: долгоживущий
Красен до реализации: гейт исходов собирает мандат только по прежнему маркеру «Ослабление тестов разрешено:» и подсказывает только его — мандат «Ослабление теста по идентификатору разрешено:» на идентификатор с `#n` находку не снимает (AC-12), подсказка отказа нового маркера не называет (AC-13); AC-11 (ANSWER автокоммита роли не покрывает) держит сегодняшний исход и зелён с рождения.

Стенд — настоящий git (`tests.sandbox.GitignoreCommittedRealGitSandbox`),
связка «`answer` — ссылка документов — `advance` — гейт исходов — журнал»:
клон артели — корень песочницы с bare `origin`; учебный внешний проект —
`tests.sandbox.make_project_repo` со своим `origin` и записью `components:`
в `targets.yaml` песочницы (один компонент `pult-vitest`). Задача проходит
настоящий выход из `tests_writing` (планка с тестом критерия, красным на
базе), затем шаг developer: коммит правки кода в кодовую ветку, PLAN.md
`ready` чекпоинтом шага, `fsm.cmd_advance`. Исход — состояние задачи,
записи журнала и вывод `advance` (строка подсказки «дальше: …»).

Раннер подменён без Node и без сети шпионом `subprocess.Popen`: запуск
`node_modules/.bin/vitest` (и `--version`) и установки записывает сторону и
пишет JSON отчётчика пульта по `--outputFile`. Сторона — по метке `app.py`
дерева прогона (`APP = 'base'` на базе, `APP = 'head-…'` на голове ветки).
Исход теста задаётся по стороне последовательностью: k-я запись теста с
этим именем в файле на стороне — k-й элемент (повторы имени в файле дают
идентификаторы `…#2`, `…#3`).

Мандат — `answer.cmd_answer` Оператора (ANSWER-n со строкой нового маркера,
строкой независимой проверки и матрицей неослабления) либо ANSWER-1.md,
положенный в каталог документов и унесённый автокоммитом шага developer.

Провалидировано временным стабом реализации (удалён, не закоммичен): сбор
мандата нового маркера в гейте исходов с отбраковкой автокоммита, покрытие
точным равенством, подсказка с обоими маркерами — все методы зелёные.

Имена проекта, компонента, файлов и тестов — из `random`; зерно печатается
и входит в текст каждого провала.
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

from orchestrator import (answer, checkpoint, config, fsm, github_adapter,
                          project_profile, store, workspace)
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
GATE_ACTIONS = (OUTCOME_ACTION, f"{OUTCOME_ACTION} — сломан правкой",
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
VITEST_KIND = {
    "passed": {"state": "pass"},
    "skipped": {"state": "skip", "mode": "skip"},
}


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def spec_text(task_id: str, n: int) -> str:
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
                    item.update(VITEST_KIND[kind])
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
        spec = spec_text(tid, n)
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
        for action in GATE_ACTIONS:
            self.assertEqual(self.details(rows, action), [],
                             self.explain(rows, output))


# --------------------------------------------------------------- AC-11

class RoleAutocommitTest(IdOutcomeGateSandbox):

    def test_ac11_role_autocommitted_id_mandate_does_not_cover(self):
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
        t, cid, _others = self.skipped_copy_task(2)
        rows, output = self.developer_advance(
            t, {}, before=self.role_mandate(t, cid))
        self.assertIn(cid, self.gate_refusal(rows, output),
                      self.explain(rows, output))


# --------------------------------------------------------------- AC-12

class ExactIdTest(IdOutcomeGateSandbox):

    def test_ac12_exact_id_with_n_covers_other_variant_does_not(self):
        """Мандат нового маркера на тот же идентификатор с `#n` снимает находку; на другой `#n` или без `#n` — нет.

        Сценарий (подслучай — свежая задача): имя теста повторено в файле
        трижды, на ветке вторая запись (`…#2`) — пропуск. ANSWER Оператора
        (`answer`) со строкой нового маркера на (а) `…#2` — отказа гейта
        исходов нет; (б) `…#3`; (в) идентификатор без `#n` — отказ «… по
        исходам», деталь называет `…#2`.

        Ловит мутацию: элементы нового маркера в гейте не собираются —
        (а) отказ; к ним применено префиксное правило прежнего мандата
        (`путь::имя`, за которым `#`) — (в) покрывает `…#2`, отказа нет;
        сверка по идентификатору без номера (`parse_test_id` без `#n`) —
        (б) покрывает.
        """
        for label, pick in (("тот же #2", lambda cid, others: cid),
                            ("другой #3", lambda cid, others: others[1]),
                            ("без #n", lambda cid, others: others[0])):
            with self.subTest(case=label, seed=self.seed):
                t, cid, others = self.skipped_copy_task(2)
                self.assertTrue(cid.endswith("#2") and others[1].endswith("#3")
                                and "#" not in others[0].rpartition("::")[2],
                                self.note(f"фикстура: {cid} {others}"))
                self.operator_mandate(t, pick(cid, others))
                rows, output = self.developer_advance(t, {}, finished=True)
                if label == "тот же #2":
                    self.no_gate_refusal(rows, output)
                else:
                    self.assertIn(cid, self.gate_refusal(rows, output),
                                  self.explain(rows, output))


# --------------------------------------------------------------- AC-13

class HintTest(IdOutcomeGateSandbox):

    def test_ac13_refusal_hint_names_both_markers(self):
        """Подсказка отказа гейта исходов с непокрытой находкой называет оба маркера.

        Сценарий: проект `pult-vitest`, тест базы на ветке стал пропуском,
        мандата нет. `advance` из `in_dev`: отказ «… по исходам»; строка
        вывода «  дальше: …» несёт «Ослабление тестов разрешено:» и
        «Ослабление теста по идентификатору разрешено:».

        Ловит мутацию: гейт исходов по-прежнему зовёт подсказку гейта по
        тексту (`test_integrity._mandate_hint`) — нового маркера в ней
        нет; своя подсказка называет только новый маркер — прежнего нет.
        """
        rel, name = self.js_rel(), self.js_name()
        project = self.vitest_project({rel: [name, self.js_name()]})
        t = self.in_dev_task(project)
        self.current = t.id
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["skipped"]}
        rows, output = self.developer_advance(t, {})
        self.gate_refusal(rows, output)
        hints = [line for line in output.splitlines() if line.startswith(HINT)]
        self.assertTrue(any(OLD in h and NEW in h for h in hints),
                        self.explain(rows, output))


if __name__ == "__main__":
    unittest.main()
