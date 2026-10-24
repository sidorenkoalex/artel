"""Прогон приёмочной планки после подтяжки main (`pull.evaluate`) — на дереве с приложениями PLAN, как на рубеже `in_dev -> verifying`.

Группа: долгоживущий
Красен до реализации: после подтяжки `pull.evaluate` гоняет планку и долгоживущие файлы в рабочей копии задачи без приложений PLAN — test_ac1, test_ac6, test_ac7 видят планку без правки приложения (Conflict/escalated, правки в дереве прогона нет), test_ac3 не находит записи отказа по приложению (планка исполнена, итог Pulled), test_ac4 не находит записи пропуска `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION`, test_ac5 видит прогон с cwd рабочей копии, а не во временном дереве. Зелёный с рождения: test_ac2 (без приложений PLAN и у задачи не артели прогон и сегодня идёт с cwd рабочей копии).

Песочница — `tests.sandbox.GitignoreCommittedRealGitSandbox`: пульт и клон
артели — один настоящий git-репозиторий `self.root` с голым origin и
записью артели с профилем тестов (образец —
`tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`). База (`main`)
несёт защищённые markdown-файлы из `config.PROTECTED_PATHS` — тексты из
строк «строка базы NN». Задача заводится строкой БД в `in_dev`, рабочей
копией `workspace.ensure` и коммитом своего кода; SPEC, PLAN (с
приложениями — диффами настоящего `git diff` к защищённым файлам), планка
и перечень долгоживущих файлов — в ссылке документов автокоммитом пульта
(`checkpoint.commit_step_artifacts`). Затем `main` продвигается
недокументным коммитом, и вызывается публичный `pull.evaluate` с вершиной
`main` — настоящий `git merge`, настоящий pytest.

Планка и долгоживущий файл задачи сами пишут каждое своё исполнение
строкой JSON в журнал вне репозитория: свой путь, корень дерева от своего
расположения, cwd, pid процесса pytest и видна ли нужная правка
приложения в защищённом файле — от своего расположения и от cwd. Правки,
их строки, файлы, число приложений и место нужного — от зерна; зерно
печатается и входит в текст каждого провала.

Сбой git при построении дерева — обёртка `git` первой в PATH: отказывает
на `git worktree add`, пока лежит файл-флаг (тот же приём, что
`tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`).

Валидировано временным стабом реализации (в `pull.py` прогон под
`appendix_tree.suite_tree`, отказ по `tree.fixable`, выкладка планки
`acceptance.plank_in_code_copy` во временное дерево): все тесты файла
зелёные на трёх зёрнах, стаб удалён.
"""
import contextlib
import hashlib
import io
import json
import os
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, config, idgen,
                          projects, pull, store, workspace)
from orchestrator.advance_gates import plan_appendix
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox, make_project_repo

DOCS_REF_PREFIX = "refs/artifacts/"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
RED_TEXT = ("приёмочные тесты красные после подтяжки {branch} "
            "(слияние сохранено, откат не выполняется)")

# Защищённые файлы — от `config.PROTECTED_PATHS`, не литералом: перечень
# меняет Оператор. Markdown вне `tests/` и `.github/`: текст фикстуры в
# защищённом конфиге читался бы пультом как конфиг.
PROTECTED_MD = [p for p in config.PROTECTED_PATHS
                if p.endswith(".md") and "*" not in p
                and not p.startswith(("tests/", ".github"))]

BASE_LINES = [f"строка базы {n:02d} из 40" for n in range(1, 41)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
# Строки правок — через восемь: контекст хунка соседней правки их не
# задевает, диффы от базы ложатся друг на друга в любом порядке.
EDIT_LINES = BASE_LINES[::8]

ARTEL_TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: src/, tests/
budget_usd: 30
---

# SPEC: фикстура подтяжки с приложениями

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
{sections}"""

# Исполнение фикстуры (планки либо долгоживущего файла) — строка JSON в
# журнале `__RUNS__`; `__DEPTH__` — сколько уровней от файла до корня
# дерева прогона; `__FAIL__` — текст намеренного провала после записи.
PROBE_TEXT = '''"""Фикстура песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import json
import os
import unittest
from pathlib import Path

RUNS = Path(__RUNS__)
NEEDS = __NEEDS__
FAIL = __FAIL__


def seen(root):
    for rel, marker in NEEDS:
        path = root / rel
        if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
            return False
    return True


class __CLS__(unittest.TestCase):

    def __METHOD__(self):
        """Фикстурный метод: правки приложений в дереве прогона."""
        here = Path(__file__).resolve()
        root = here.parents[__DEPTH__]
        cwd = Path.cwd().resolve()
        record = {"kind": __KIND__, "file": str(here), "root": str(root),
                  "cwd": str(cwd), "pid": os.getpid(),
                  "seen_root": seen(root), "seen_cwd": seen(cwd)}
        with RUNS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\\n")
        self.assertTrue(record["seen_root"] and record["seen_cwd"], record)
        if FAIL:
            self.fail(FAIL)
'''

PLANK_KIND = "планка"
LONG_LIVED_KIND = "долгоживущий"

# Обёртка git: `git worktree add` отказывает, пока лежит файл-флаг.
GIT_WRAPPER = '''#!{python}
import os, sys
args = sys.argv[1:]
rest = list(args)
while rest and rest[0] in ("-C", "-c", "--git-dir", "--work-tree"):
    rest = rest[2:]
if os.path.exists({flag!r}) and rest[:2] == ["worktree", "add"]:
    sys.stderr.write("fatal: " + {token!r} + "\\n")
    sys.exit(128)
os.execv({git!r}, [{git!r}, *args])
'''


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(length))


class PullPlankSandbox(GitignoreCommittedRealGitSandbox):
    """База с защищёнными markdown-файлами; задачи артели (и внешнего
    проекта) в `in_dev` с планкой в ссылке документов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.case = ""
        self.assertTrue(PROTECTED_MD, self.note(
            "в config.PROTECTED_PATHS нет защищённого markdown-файла"))
        for rel in PROTECTED_MD:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = self.add_synced_origin()
        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.probe = Path(tempfile.mkdtemp(prefix="artel-pull-plank-")).resolve()
        self.addCleanup(shutil.rmtree, self.probe, ignore_errors=True)
        self.runs = self.probe / f"runs-{word(self.rng)}.jsonl"
        self.task = ""
        self.wt = None
        self.repo = self.root

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {self.case or 'сценарий'}; {text}"

    def run_cmd(self, fn, *args, **kwargs) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def marker(self) -> str:
        return f"правка {word(self.rng)} {self.rng.randrange(10**6)}"

    def edit(self, rel: str, replacements: dict) -> None:
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            self.assertIn(old, text)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    def diff_of(self, edits: dict) -> str:
        """Unified-дифф правок `edits` ({путь: {старое: новое}}) к дереву
        `main` — настоящим `git diff`, правка затем откатывается."""
        self.checkout(config.MAIN_BRANCH)
        for rel, replacements in edits.items():
            self.edit(rel, replacements)
        diff = self.git("diff", "--", *edits)
        self.git("checkout", "-q", "--", *edits)
        self.assertIn("diff --git a/", diff)
        return diff

    def appendices(self, count: int) -> tuple:
        """`count` применимых к базе приложений к защищённым файлам: (диффы,
        нужные правки [(путь, строка правки)]); правленые строки базы — в
        `self.edited` в том же порядке."""
        diffs, needs = [], []
        self.edited = self.rng.sample(EDIT_LINES, count)
        for line in self.edited:
            rel, marker = self.rng.choice(PROTECTED_MD), self.marker()
            diffs.append(self.diff_of({rel: {line: marker}}))
            needs.append((rel, marker))
        return diffs, needs

    def probe_text(self, kind: str, depth: int, needs: list,
                   fail: str = "") -> str:
        cls = f"Fx{word(self.rng).capitalize()}Test"
        return (PROBE_TEXT.replace("__RUNS__", repr(str(self.runs)))
                .replace("__NEEDS__", repr([list(n) for n in needs]))
                .replace("__FAIL__", repr(fail))
                .replace("__CLS__", cls)
                .replace("__METHOD__", f"test_fx_{word(self.rng)}")
                .replace("__DEPTH__", str(depth))
                .replace("__KIND__", repr(kind)))

    def plan(self, diffs: list) -> str:
        sections = "".join(
            f"\n## Приложение {i}: {word(self.rng)}\n\n```diff\n{diff}```\n"
            for i, diff in enumerate(diffs, 1))
        return PLAN_TEXT.format(task=self.task, sections=sections)

    def make_task(self, diffs: list, needs: list, *, target: str = None,
                  long_lived: bool = False, fail: str = "") -> None:
        """Задача `target` (по умолчанию артели) в `in_dev`: рабочая копия
        на ветке с кодом задачи (ветка в origin), PLAN с приложениями
        `diffs`, планка, которой нужны правки `needs`; `long_lived` —
        долгоживущий файл задачи в ветке, его сумма в перечне и лок."""
        target = target or config.DEFAULT_TARGET
        self.task = idgen.new_task_id()
        branch = f"task/{self.task.lower()}-{word(self.rng)}"
        store.insert_task(store.db(), self.task, f"Задача {self.task}",
                          "in_dev", branch, target, config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(self.task, branch, target)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.wt = Path(wt).resolve()
        self.repo = Path(workspace.task_repo(self.task)).resolve()
        (self.wt / "src").mkdir(parents=True, exist_ok=True)
        (self.wt / "src" / f"feature_{word(self.rng)}.txt").write_text(
            f"код задачи {self.task}\n", encoding="utf-8")
        docs_files = {"SPEC.md": SPEC_TEXT.format(task=self.task),
                      "PLAN.md": self.plan(diffs),
                      "acceptance_tests/test_plank.py":
                          self.probe_text(PLANK_KIND, 3, needs, fail)}
        self.long_lived_rel = ""
        if long_lived:
            self.long_lived_rel = (f"tests/test_{self.task.lower()}_"
                                   f"{word(self.rng)}.py")
            path = self.wt / self.long_lived_rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.probe_text(LONG_LIVED_KIND, 1, needs),
                            encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            docs_files[f"acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}"] = (
                f"{digest}  {self.long_lived_rel}\n")
        self.git("-C", str(self.wt), "add", "-A")
        self.git("-C", str(self.wt), "commit", "-q", "-m",
                 f"{self.task}: код задачи")
        self.git("-C", str(self.wt), "push", "-q", "origin", branch)
        docs = config.PROJECTS / target / "tasks" / self.task
        for rel, text in docs_files.items():
            path = docs / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.run_cmd(checkpoint.commit_step_artifacts, store.db(), self.task,
                     "developer")
        head = self.git("-C", str(self.repo), "rev-parse",
                        DOCS_REF_PREFIX + self.task).strip()
        self.assertTrue(head, self.note("ссылки документов нет"))
        if long_lived:
            store.update_task(store.db(), self.task, tests_locked_sha=head)
        self.runs.unlink(missing_ok=True)

    def advance_main(self, edits: dict = None) -> str:
        """Недокументный коммит в `main` клона задачи (и правки `edits`
        защищённых файлов тем же коммитом) — в origin; вершина `main`."""
        repo = self.repo
        if repo == self.root.resolve():
            self.checkout(config.MAIN_BRANCH)
        for rel, replacements in (edits or {}).items():
            self.edit(rel, replacements)
        rel = f"src/main_{word(self.rng)}.py"
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("# код main\n", encoding="utf-8")
        self.git("-C", str(repo), "add", "-A", "--", "src", *(edits or {}))
        self.git("-C", str(repo), "commit", "-q", "-m", "main: код")
        self.git("-C", str(repo), "push", "-q", "origin", config.MAIN_BRANCH)
        return self.git("-C", str(repo), "rev-parse", config.MAIN_BRANCH).strip()

    def evaluate(self, base: str):
        conn = store.db()
        t = store.get_task(conn, self.task)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            return pull.evaluate(
                conn, self.task, t, t["state"],
                origin_main_source=lambda target: ("origin", config.MAIN_BRANCH),
                origin_main_sha=lambda target: base,
                read_branch_text_or_refuse=lambda *args: None)

    def state(self) -> str:
        return store.get_task(store.db(), self.task)["state"]

    def steps(self) -> list:
        return list(store.task_steps(store.db(), self.task))

    def journal(self) -> list:
        return [f"{s['action']} | {s['detail'] or ''}" for s in self.steps()]

    def executions(self) -> list:
        if not self.runs.exists():
            return []
        return [json.loads(line) for line in
                self.runs.read_text(encoding="utf-8").splitlines() if line]

    def of_kind(self, kind: str) -> list:
        return [e for e in self.executions() if e["kind"] == kind]

    def context(self, outcome) -> str:
        return self.note(f"итог: {outcome!r}\nисполнения: {self.executions()}"
                         f"\nжурнал:\n" + "\n".join(self.journal()))

    def spy_run(self):
        """Шпион на `acceptance.run`: настоящий прогон, вызовы записаны."""
        return mock.patch.object(acceptance, "run", wraps=acceptance.run)

    @staticmethod
    def cwd_of(call) -> Path:
        return Path(call.kwargs.get("cwd")).resolve()

    def registered_worktrees(self) -> list:
        out = self.git("-C", str(self.repo), "worktree", "list", "--porcelain")
        return [Path(line.split(" ", 1)[1]).resolve() for line in out.splitlines()
                if line.startswith("worktree ")]


class AppendixTreeAfterPullTest(PullPlankSandbox):

    def test_ac1_plank_green_on_tree_with_appendices_after_pull(self):
        """Планке нужна правка приложения к защищённому файлу — после подтяжки итог `Pulled`, планка исполнена в дереве с приложениями.

        Сценарий: PLAN несёт одно-три приложения к защищённым markdown-файлам
        (строки и файлы — от зерна), планка красна, пока правок всех
        приложений нет в дереве — и от своего расположения, и от cwd.
        `main` продвинут недокументным коммитом, `pull.evaluate`: итог
        `Pulled` с вершиной `main`, задача в `in_dev`; планка исполнялась,
        видела правки от расположения и от cwd, её корень — не рабочая
        копия задачи (где правок приложений нет).

        Ловит мутацию: после подтяжки планка по-прежнему материализуется и
        гоняется в рабочей копии без приложений — планка не видит правки,
        итог `Conflict`, задача `escalated`; дерево с приложениями собрано,
        но `acceptance.run` зовётся с `cwd=wt_path` — правки нет от cwd;
        планка выложена в рабочую копию, а cwd — временное дерево — правки
        нет от расположения планки.
        """
        diffs, needs = self.appendices(self.rng.randint(1, 3))
        self.case = f"приложений {len(diffs)}"
        self.make_task(diffs, needs)
        base = self.advance_main()

        outcome = self.evaluate(base)

        context = self.context(outcome)
        self.assertEqual(outcome, pull.Pulled(base), context)
        self.assertEqual(self.state(), "in_dev", context)
        runs = self.of_kind(PLANK_KIND)
        self.assertTrue(runs, context)
        for run in runs:
            self.assertTrue(run["seen_root"] and run["seen_cwd"], context)
            self.assertNotEqual(Path(run["root"]), self.wt, context)


class WorkingCopyRunTest(PullPlankSandbox):

    def test_ac2_no_appendices_or_foreign_project_runs_with_wt_cwd(self):
        """Без приложений PLAN и у задачи не артели планка и долгоживущие файлы гоняются с cwd рабочей копии.

        Сценарий: (1) задача артели, PLAN без приложений, долгоживущий файл
        в ветке и в перечне лока; (2) задача внешнего проекта (свой клон и
        origin), PLAN с одним-двумя приложениями. После подтяжки — шпион на
        `acceptance.run`: каждый вызов прогона — с `cwd`, равным рабочей
        копии задачи; итог `Pulled`; исполнения планки (и долгоживущего
        файла в (1)) — с cwd и корнем рабочей копии.

        Ловит мутацию: временное дерево заводится всегда, без сверки
        «задача артели и приложения есть» — `cwd` прогона не рабочая копия;
        проверка `tree.root == wt_path` перепутана — у задачи без приложений
        планка гоняется из временного каталога; долгоживущие файлы выпали из
        прогона без приложений — исполнения долгоживущего файла нет.
        """
        cases = [("артель без приложений", None),
                 ("внешний проект", f"p{word(self.rng)}")]
        self.rng.shuffle(cases)
        for name, target in cases:
            with self.subTest(case=name):
                self.case = name
                if target is None:
                    self.make_task([], [], long_lived=True)
                else:
                    make_project_repo(target)
                    diffs, _needs = self.appendices(self.rng.randint(1, 2))
                    self.make_task(diffs, [], target=target)
                base = self.advance_main()
                with self.spy_run() as run:
                    outcome = self.evaluate(base)
                context = self.context(outcome)
                self.assertEqual(outcome, pull.Pulled(base), context)
                self.assertTrue(run.call_args_list, context)
                self.assertEqual({self.cwd_of(c) for c in run.call_args_list},
                                 {self.wt}, context)
                kinds = [PLANK_KIND] + ([LONG_LIVED_KIND] if target is None
                                        else [])
                for kind in kinds:
                    runs = self.of_kind(kind)
                    self.assertTrue(runs, self.note(f"{kind}: {context}"))
                    for e in runs:
                        self.assertEqual(Path(e["cwd"]), self.wt, context)
                        self.assertEqual(Path(e["root"]), self.wt, context)


class AppendixRefusalAfterPullTest(PullPlankSandbox):

    def test_ac3_appendix_refusal_journals_class_and_does_not_run_plank(self):
        """Неразобранное или неналожимое приложение и сбой git дерева — запись отказа своего класса, планка не запускается, задача не `escalated`.

        Сценарий (по одной задаче на случай): (а) приложение к незащищённому
        пути — не разбирается; (б) приложение к защищённому файлу по строкам,
        которых нет в дереве, — не накладывается; (в) приложения применимы,
        но `git worktree add` отказывает (обёртка git). Место плохого
        приложения среди применимых — от зерна. Вне пути `pull-main`
        (`operator_pull` не задан): итог не `Pulled`, состояние — прежнее
        `in_dev`, планка не исполнялась; в журнале — запись с действием
        `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION` в (а) и (б) — с путём
        плохого приложения в подробностях — и
        `PLAN_APPENDIX_GATE_FAILURE_ACTION` в (в) — с ответом git.

        Ловит мутацию: отказ дерева (`tree.root is None`) не проверяется —
        планка гоняется в рабочей копии и итог `Pulled`; запись пишется
        одним действием для обоих классов (`tree.fixable` не читается) —
        в (в) действие сбоя гейта не найдено; отказ эскалирует задачу
        (`store.set_state` в `escalated`) вместо записи отказа; в
        подробностях записи нет причины (`tree.refusal` не передан).
        """
        cases = ["не разбирается", "не накладывается", "сбой git"]
        self.rng.shuffle(cases)
        for name in cases:
            with self.subTest(case=name):
                self.case = name
                good, _needs = self.appendices(self.rng.randint(0, 2))
                bad_path, action, why = "", "", ""
                if name == "не разбирается":
                    bad_path = f"src/free_{word(self.rng)}.txt"
                    bad = (f"diff --git a/{bad_path} b/{bad_path}\n"
                           f"--- a/{bad_path}\n+++ b/{bad_path}\n"
                           f"@@ -1 +1 @@\n-старое\n+{self.marker()}\n")
                    action = plan_appendix.PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION
                    why = bad_path
                elif name == "не накладывается":
                    bad_path = self.rng.choice(PROTECTED_MD)
                    bad = (f"diff --git a/{bad_path} b/{bad_path}\n"
                           f"--- a/{bad_path}\n+++ b/{bad_path}\n"
                           f"@@ -1,3 +1,3 @@\n строки, которой нет\n"
                           f"-и этой нет\n+{self.marker()}\n и этой нет\n")
                    action = plan_appendix.PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION
                    why = bad_path
                else:
                    bad = None
                    action = plan_appendix.PLAN_APPENDIX_GATE_FAILURE_ACTION
                    why = f"сбой git песочницы {word(self.rng)}"
                diffs = list(good)
                if bad is not None:
                    diffs.insert(self.rng.randrange(len(diffs) + 1), bad)
                elif not diffs:
                    diffs, _needs = self.appendices(1)
                self.make_task(diffs, [])
                base = self.advance_main()
                with contextlib.ExitStack() as stack:
                    if bad is None:
                        stack.enter_context(self.failing_worktree_add(why))
                    outcome = self.evaluate(base)
                context = self.context(outcome)
                self.assertNotIsInstance(outcome, pull.Pulled, context)
                self.assertEqual(self.state(), "in_dev", context)
                self.assertEqual(self.executions(), [], context)
                records = [s for s in self.steps() if s["action"] == action
                           and why in (s["detail"] or "")]
                self.assertTrue(records, self.note(
                    f"нет записи «{action}» с «{why}»; {context}"))

    @contextlib.contextmanager
    def failing_worktree_add(self, token: str):
        """Обёртка `git` первой в PATH: `git worktree add` отказывает с
        текстом `token`, прочие команды — настоящий git."""
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "git не найден в PATH")
        bin_dir = self.probe / f"bin-{word(self.rng)}"
        bin_dir.mkdir()
        flag = self.probe / f"flag-{word(self.rng)}"
        wrapper = bin_dir / "git"
        wrapper.write_text(GIT_WRAPPER.format(
            python=sys.executable, flag=str(flag), token=token, git=real_git),
            encoding="utf-8")
        wrapper.chmod(0o755)
        flag.write_text("1", encoding="utf-8")
        path = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        try:
            with mock.patch.dict(os.environ, {"PATH": path}):
                yield
        finally:
            flag.unlink(missing_ok=True)


class AlreadyInPulledMainTest(PullPlankSandbox):

    def test_ac4_appendix_already_in_pulled_main_is_skipped(self):
        """Приложение, уже наложенное в подтянутом main, пропускается записью узла признания — планка зелёная, итог `Pulled`.

        Сценарий: PLAN несёт одно-три приложения; правку одного из них
        (место — от зерна) Оператор внёс в `main` уже ПОСЛЕ отхода ветки
        задачи — она приходит подтяжкой. Планке нужны правки всех
        приложений. `pull.evaluate`: итог `Pulled`, планка исполнялась и
        видела все правки; в журнале задачи — запись с действием
        `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION: <путь>` и подробностями
        «приложение N (<путь>)» с номером этого приложения.

        Ловит мутацию: дерево после подтяжки строится без узла признания
        `plan_appendix.skip_in_base` (прямой `git apply` и отказ) — итог не
        `Pulled`, запись отказа наложения; прогон по-прежнему в рабочей
        копии без дерева — записи пропуска нет; номер приложения считается
        с нуля — «приложение N» не совпадает с местом в PLAN.
        """
        diffs, needs = self.appendices(self.rng.randint(1, 3))
        number = self.rng.randrange(len(diffs)) + 1
        rel, marker = needs[number - 1]
        line = self.edited[number - 1]
        self.case = f"приложений {len(diffs)}, уже в main — {number} ({rel})"
        self.make_task(diffs, needs)
        base = self.advance_main({rel: {line: marker}})

        outcome = self.evaluate(base)

        context = self.context(outcome)
        self.assertEqual(outcome, pull.Pulled(base), context)
        runs = self.of_kind(PLANK_KIND)
        self.assertTrue(runs, context)
        self.assertTrue(all(r["seen_root"] and r["seen_cwd"] for r in runs),
                        context)
        action = f"{plan_appendix.PLAN_APPENDIX_ALREADY_IN_BASE_ACTION}: {rel}"
        detail = f"приложение {number} ({rel})"
        records = [s for s in self.steps() if s["action"] == action
                   and detail in (s["detail"] or "")]
        self.assertTrue(records, self.note(
            f"нет записи «{action}» с «{detail}»; {context}"))


class TempTreeRemovedTest(PullPlankSandbox):

    def test_ac5_temp_tree_removed_after_green_run_and_after_exception(self):
        """Временное дерево прогона удалено с диска после зелёного прогона и после исключения внутри прогона.

        Сценарий (порядок — от зерна): (1) PLAN с одним-двумя приложениями,
        планка зелёная — после `Pulled` каталога, с которым позван прогон
        (шпион на `acceptance.run`), и корня исполнения планки нет на диске
        и среди рабочих копий клона; (2) то же, но `acceptance.run` поднимает
        исключение — после него каталога, с которым прогон был позван, тоже
        нет. В обоих случаях этот каталог — не рабочая копия задачи.

        Ловит мутацию: временное дерево заводится не менеджером контекста
        `suite_tree` (или выход из `with` пропущен на исключении) — каталог
        дерева остаётся на диске после исключения; дерево не строится вовсе
        и прогон идёт в рабочей копии — каталог прогона равен рабочей копии.
        """
        cases = ["зелёный прогон", "исключение"]
        self.rng.shuffle(cases)
        for name in cases:
            with self.subTest(case=name):
                self.case = name
                diffs, needs = self.appendices(self.rng.randint(1, 2))
                self.make_task(diffs, needs)
                base = self.advance_main()
                token = f"сбой прогона {word(self.rng)}"
                if name == "зелёный прогон":
                    with self.spy_run() as run:
                        outcome = self.evaluate(base)
                    calls = run.call_args_list
                    roots = [Path(e["root"]) for e in self.of_kind(PLANK_KIND)]
                    self.assertEqual(outcome, pull.Pulled(base),
                                     self.context(outcome))
                    self.assertTrue(roots, self.context(outcome))
                else:
                    calls = []

                    def boom(*args, **kwargs):
                        calls.append(mock.call(*args, **kwargs))
                        raise RuntimeError(token)

                    outcome = None
                    with mock.patch.object(acceptance, "run", side_effect=boom):
                        with contextlib.suppress(RuntimeError):
                            outcome = self.evaluate(base)
                    roots = []
                context = self.context(outcome)
                self.assertTrue(calls, context)
                dirs = {self.cwd_of(c) for c in calls} | set(roots)
                self.assertNotIn(self.wt, dirs, context)
                for path in dirs:
                    self.assertFalse(path.exists(), self.note(
                        f"каталог прогона {path} остался; {context}"))
                    self.assertNotIn(path, self.registered_worktrees(), context)


class RedPlankOnTreeTest(PullPlankSandbox):

    def test_ac6_red_plank_on_tree_escalates_with_former_text(self):
        """Красная планка на дереве с приложениями — `escalated` прежним текстом с хвостом прогона, итог `Conflict`.

        Сценарий: PLAN с одним-тремя приложениями; планка видит их правки и
        затем падает с текстом-меткой от зерна. `pull.evaluate`: итог
        `Conflict`, его текст начинается с «приёмочные тесты красные после
        подтяжки <главная ветка> (слияние сохранено, откат не
        выполняется)» и несёт метку из хвоста прогона; задача `escalated`;
        планка исполнялась на дереве с правками приложений.

        Ловит мутацию: красный итог на дереве с приложениями отдаётся
        отказом `Refused` без эскалации; текст эскалации изменён (другая
        формулировка, ветка не названа); хвост прогона не попал в текст;
        прогон по-прежнему в рабочей копии — планка не видит правок.
        """
        diffs, needs = self.appendices(self.rng.randint(1, 3))
        token = f"метка провала {word(self.rng)} {self.rng.randrange(10**6)}"
        self.make_task(diffs, needs, fail=token)
        base = self.advance_main()

        outcome = self.evaluate(base)

        context = self.context(outcome)
        self.assertIsInstance(outcome, pull.Conflict, context)
        self.assertTrue(outcome.note.startswith(
            RED_TEXT.format(branch=config.MAIN_BRANCH)), context)
        self.assertIn(token, outcome.note, context)
        self.assertEqual(self.state(), "escalated", context)
        runs = self.of_kind(PLANK_KIND)
        self.assertTrue(runs, context)
        self.assertTrue(all(r["seen_root"] and r["seen_cwd"] for r in runs),
                        context)


class LongLivedSameTreeTest(PullPlankSandbox):

    def test_ac7_long_lived_files_run_in_same_run_and_tree_as_plank(self):
        """Долгоживущий файл зафиксированной планки исполняется в том же прогоне и на том же дереве, что планка.

        Сценарий: PLAN с одним-тремя приложениями; планка и долгоживущий
        файл задачи (в ветке, его сумма в перечне дерева лока) красны без
        правок приложений. `pull.evaluate`: итог `Pulled`; оба исполнялись,
        видели правки, одним процессом pytest (тот же pid), корень дерева
        — один и тот же и не рабочая копия задачи.

        Ловит мутацию: `extra=long_lived` не передан в прогон на дереве —
        исполнения долгоживущего файла нет; долгоживущие файлы гоняются
        отдельным прогоном в рабочей копии — pid и корень расходятся, правок
        приложений там нет.
        """
        diffs, needs = self.appendices(self.rng.randint(1, 3))
        self.make_task(diffs, needs, long_lived=True)
        base = self.advance_main()

        outcome = self.evaluate(base)

        context = self.context(outcome)
        self.assertEqual(outcome, pull.Pulled(base), context)
        plank = self.of_kind(PLANK_KIND)
        lived = self.of_kind(LONG_LIVED_KIND)
        self.assertTrue(plank, context)
        self.assertTrue(lived, context)
        runs = plank + lived
        self.assertTrue(all(r["seen_root"] and r["seen_cwd"] for r in runs),
                        context)
        self.assertEqual(len({r["pid"] for r in runs}), 1, context)
        self.assertEqual(len({r["root"] for r in runs}), 1, context)
        self.assertNotEqual(Path(runs[0]["root"]), self.wt, context)


if __name__ == "__main__":
    unittest.main()
