"""Полный набор `tests/` на автогейте приёмки и на `approve` в `acceptance`
идёт на временном дереве «голова ветки задачи плюс приложения PLAN»;
гейт мержа накладывает приложения прежним порядком и при прежних условиях.

Группа: долгоживущий
Красен до реализации: автогейт и approve гоняют полный набор в рабочей копии задачи без приложений PLAN — тест-проба ветки красен, автогейт «не пройден», approve отклонён; неприменимое приложение и сбой git прогону не мешают, а признака «с приложениями PLAN» в журнале нет. Зелёные с рождения: test_ac9 (без приложений и вне артели прогон и сегодня идёт в рабочей копии) и test_ac12 (гейт мержа держит прежнее поведение). Валидировано временным стабом общего узла (все тесты файла зелены, стаб удалён).

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`, клон
артели — сам репозиторий песочницы) с bare `origin`, задача артели с
рабочей копией (`workspace.ensure`), PLAN/SPEC/REVIEW и планка — в ссылке
документов задачи автокоммитом пульта (`checkpoint.commit_step_artifacts`).
Входы — публичные: `fsm.cmd_advance` из `review` (автогейт на входе в
`acceptance`, политика `gates.yaml` песочницы — `auto`) и `fsm.cmd_approve`
из `acceptance` и `merge_gate`.

Полный набор гоняется НАСТОЯЩИМ `acceptance.run_full_suite` (pytest с
параллелью 1): подмена только записывает корень прогона и пропускает
вызов дальше. Ветка задачи несёт тест-пробу `tests/test_probe_*.py`: он
красен, пока в защищённых файлах дерева прогона нет правок приложений
PLAN, и пишет в журнал наблюдения корень, cwd и исход. Подменены внешние
проверки, которых в песочнице нет: цвет CI ветки и main, Draft MR форжа.

Сбой git — обёртка `git` первой в `PATH`: в режиме сбоя она отвечает
ненулевым кодом на `git apply` либо `git worktree add`, остальное
исполняет настоящий git. Временный каталог процесса (`tempfile.tempdir`)
уведён в каталог наблюдения: после прогона в нём не остаётся ничего, а
`git worktree list` клона — прежний.
"""
import contextlib
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          github_adapter, idgen, store, workspace)
from tests.sandbox import RealGitSandbox, capture, make_project_repo

# Защищённые файлы — от `config.PROTECTED_PATHS`, не литералом: перечень
# меняет Оператор. Только markdown вне `tests/` и `.github/`: текст фикстуры
# в защищённом конфиге читался бы пультом как конфиг, а правка `tests/`
# меняет условие полного прогона на гейте мержа.
PROTECTED_FILES = [p for p in config.PROTECTED_PATHS
                   if p.endswith(".md") and "*" not in p
                   and not p.startswith(("tests/", ".github"))]

TARGETS_YAML = """targets:
  {name}:
    forge: github
    url: http://localhost/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

GATES_YAML = "gates:\n  acceptance: auto\n"

BASE_LINES = [f"строка базы {n:02d} из 40" for n in range(1, 41)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
# Строки правок — через восемь: контекст хунка соседней правки их не задевает.
EDIT_LINES = BASE_LINES[::8]

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
---

# SPEC: фикстура

## Контекст

## Требования

## Критерии приёмки

AC-1. Фикстура.

## Не входит
"""

REVIEW_TEXT = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: фикстура

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания

Нет.

## Вердикт

approved

## Проверено исполнением

Прогон планки фикстуры — зелёный.
"""

PLANK_TEXT = '''"""Фикстура планки.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_fixture(self):
        """Фикстура."""
        self.assertTrue(True)
'''

PROBE = '''import json
import os
from pathlib import Path


def test_{name}():
    root = Path(__file__).resolve().parent.parent
    present = all(marker in (root / rel).read_text(encoding="utf-8")
                  for rel, marker in {needs!r})
    with open({journal!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"root": os.path.realpath(str(root)),
                             "cwd": os.path.realpath(os.getcwd()),
                             "present": present}}) + "\\n")
    assert present, "правок приложений PLAN в дереве прогона нет"
'''

GIT_WRAPPER = '''#!{python}
import os, sys
args = sys.argv[1:]
rest = list(args)
while rest and rest[0] in ("-C", "-c", "--git-dir", "--work-tree"):
    rest = rest[2:]
mode = ""
if os.path.exists({mode_file!r}):
    with open({mode_file!r}, encoding="utf-8") as fh:
        mode = fh.read().strip()
words = " ".join(rest[:2])
if mode and (words == mode or (mode == "apply" and rest[:1] == ["apply"])):
    with open({log_file!r}, "a", encoding="utf-8") as fh:
        fh.write(" ".join(args) + "\\n")
    sys.stderr.write("fatal: сбой git песочницы\\n")
    sys.exit(128)
os.execv({git!r}, [{git!r}, *args])
'''

WITH_APPENDICES = "с приложениями plan"
AUTOGATE_REFUSED = "автогейт acceptance не пройден"
APPROVE_REFUSED = "approve отклонён"
INAPPLICABLE_PREFIX = "приложение PLAN неприменимо после подтяжки:"
WORDS = ("правка", "шаг", "сторож", "настройка", "перечень")


def names_number(text: str, number: int) -> bool:
    """Текст называет номер приложения рядом со словом «приложение»."""
    return re.search(rf"приложени\w*\s*(№\s*)?{number}\b", text,
                     re.IGNORECASE) is not None


class AppendixRunSandbox(RealGitSandbox):
    """Задача артели с рабочей копией, тестом-пробой на ветке и PLAN с
    приложениями в ссылке документов; `origin` синхронный с `main`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.case = ""
        self.assertGreaterEqual(len(PROTECTED_FILES), 2, self.note(
            "в config.PROTECTED_PATHS нет двух защищённых markdown-файлов"))
        self.files = self.rng.sample(PROTECTED_FILES, 2)

        self.probe = Path(tempfile.mkdtemp(prefix="artel-appendix-probe-")).resolve()
        self.addCleanup(shutil.rmtree, self.probe, ignore_errors=True)
        self.journal_file = self.probe / "probe.jsonl"
        self.mode_file = self.probe / "git-mode"
        self.git_log = self.probe / "git-failures.log"
        bin_dir = self.probe / "bin"
        bin_dir.mkdir()
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "git не найден в PATH")
        wrapper = bin_dir / "git"
        wrapper.write_text(GIT_WRAPPER.format(
            python=sys.executable, mode_file=str(self.mode_file),
            log_file=str(self.git_log), git=real_git), encoding="utf-8")
        wrapper.chmod(0o755)
        self.tmp_dir = self.probe / "tmp"
        self.tmp_dir.mkdir()

        config.TARGETS.write_text(TARGETS_YAML.format(
            name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH),
            encoding="utf-8")
        (self.root / "gates.yaml").write_text(GATES_YAML, encoding="utf-8")
        for rel in self.files:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
            self.git("add", rel)
        self.git("add", "gates.yaml")
        self.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)

        self.runs = []
        real_run = acceptance.run_full_suite
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.dict(os.environ, {
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}),
                mock.patch.object(tempfile, "tempdir", str(self.tmp_dir)),
                mock.patch.object(config, "FULL_SUITE_WORKERS", "1"),
                mock.patch.object(acceptance, "run_full_suite",
                                  lambda root: self.observed_run(real_run, root)),
                mock.patch.object(ci, "branch_status",
                                  lambda branch, repo=None:
                                  (True, "зелёный (тест)")),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main),
                mock.patch.object(ci, "verifying_status",
                                  lambda branch, repo=None:
                                  (ci.VERIFYING_GREEN, "зелёный (тест)")),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.raise_in_run = False
        self.case = ""

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed}; {self.case or 'сценарий'})"

    def word(self) -> str:
        return "".join(self.rng.choice("abcdefghijkmnpqrstuvwxyz")
                       for _ in range(8))

    def observed_run(self, real_run, root):
        root = Path(root).resolve()
        self.runs.append(root)
        if self.raise_in_run:
            raise RuntimeError("сбой прогона песочницы")
        return real_run(root)

    def make_task(self, needs: list, state: str, target: str = None) -> None:
        """Задача проекта `target` (по умолчанию — артели) в `state`:
        рабочая копия на ветке с тестом-пробой, которому нужны правки
        `needs` ([(путь, маркер)]) в дереве прогона."""
        self.target = target or config.DEFAULT_TARGET
        self.task = idgen.new_task_id()
        self.branch = f"task/{self.task.lower()}-x"
        store.insert_task(store.db(), self.task, f"Задача {self.task}", state,
                          self.branch, self.target,
                          config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(self.task, self.branch, self.target)
        self.assertIsNone(error, f"рабочая копия не заведена: {error}")
        self.wt = Path(wt).resolve()
        self.probe_name = f"probe_{self.word()}"
        probe = self.wt / "tests" / f"test_{self.probe_name}.py"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(PROBE.format(name=self.probe_name, needs=needs,
                                      journal=str(self.journal_file)),
                         encoding="utf-8")
        self.wt_git("add", "tests")
        self.wt_git("commit", "-q", "-m", f"{self.task}: код задачи")
        self.wt_git("push", "-q", "origin", self.branch)

    def wt_git(self, *args: str) -> str:
        return self.git("-C", str(self.wt), *args)

    def edit(self, rel: str, replacements: dict) -> None:
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            self.assertIn(old, text)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    def diff_chain(self, edits: list) -> list:
        """Дифф каждой правки из `edits` ([{путь: {старое: новое}}]) к дереву
        `main` с наложенными ПРЕДЫДУЩИМИ правками — настоящим `git diff`;
        главная копия затем возвращается к `main`."""
        diffs = []
        for edit in edits:
            self.git("add", "-A", "--", *self.files)
            for rel, replacements in edit.items():
                self.edit(rel, replacements)
            diff = self.git("diff", "--", *edit)
            self.assertIn("diff --git a/", diff)
            diffs.append(diff)
        self.git("reset", "-q", "--", *self.files)
        self.git("checkout", "-q", "--", *self.files)
        return diffs

    def heading(self, number: int) -> str:
        return (f"Приложение {number}: {self.rng.choice(WORDS)} "
                f"{self.rng.randrange(10**6)}")

    def write_docs(self, diffs: list) -> None:
        """SPEC, PLAN с приложениями `diffs` (в этом порядке), REVIEW
        approved и планка — в ссылку документов автокоммитом пульта."""
        sections = "".join(f"\n## {self.heading(i)}\n\n```diff\n{diff}```\n"
                           for i, diff in enumerate(diffs, 1))
        plan = (f"---\ntask: {self.task}\ntype: plan\n"
                f"author_role: developer\nstatus: ready\n"
                f"schema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
                f"Фикстура.\n{sections}")
        docs = config.PROJECTS / self.target / "tasks" / self.task
        (docs / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=self.task),
                                      encoding="utf-8")
        (docs / "PLAN.md").write_text(plan, encoding="utf-8")
        (docs / "REVIEW.md").write_text(REVIEW_TEXT.format(task=self.task),
                                        encoding="utf-8")
        (docs / "acceptance_tests" / "test_ac1_fixture.py").write_text(
            PLANK_TEXT, encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, store.db(), self.task,
                "developer")

    def chained_edits(self, count: int) -> tuple:
        """`count` правок одной строки защищённого файла, каждая следующая —
        поверх предыдущей (контекст хунка несёт её маркер). (диффы,
        [(путь, маркер последней правки)])."""
        rel = self.files[0]
        line = self.rng.choice(EDIT_LINES)
        current, edits = line, []
        for i in range(count):
            marker = f"правка {i + 1} ({self.rng.randrange(10**6)})"
            edits.append({rel: {current: marker}})
            current = marker
        return self.diff_chain(edits), [(rel, current)]

    def independent_edits(self, count: int) -> tuple:
        """`count` независимых правок разных строк (файл — от зерна)."""
        lines = self.rng.sample(EDIT_LINES, count)
        edits, needs = [], []
        for line in lines:
            rel = self.rng.choice(self.files)
            marker = f"правка ({self.rng.randrange(10**6)})"
            edits.append({rel: {line: marker}})
            needs.append((rel, marker))
        diffs = []
        for edit in edits:
            diffs.extend(self.diff_chain([edit]))
        return diffs, needs

    def advance_from_review(self) -> str:
        self.set_row(state="review", reviewed_iter=0)
        return self.call(fsm.cmd_advance, self.task)

    def approve(self) -> str:
        self.set_row(state="acceptance")
        return self.call(fsm.cmd_approve, self.task)

    def call(self, fn, *args) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
            except RuntimeError as exc:
                buf.write(f"\nисключение: {exc}")
        return buf.getvalue()

    def set_row(self, **fields) -> None:
        store.update_task(store.db(), self.task, **fields)

    def state(self) -> str:
        return store.get_task(store.db(), self.task)["state"]

    def journal(self) -> list:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(store.db(), self.task)]

    def probe_records(self) -> list:
        if not self.journal_file.exists():
            return []
        return [json.loads(line) for line in
                self.journal_file.read_text(encoding="utf-8").splitlines()
                if line.strip()]

    def context(self, out: str) -> str:
        return self.note("журнал:\n" + "\n".join(self.journal())
                         + f"\n--- вывод:\n{out}\n--- прогоны: {self.runs}"
                         f"\n--- проба: {self.probe_records()}")

    def worktree_list(self) -> str:
        return self.git("worktree", "list", "--porcelain")

    def wt_snapshot(self) -> dict:
        return {"status": self.wt_git("status", "--porcelain",
                                      "--untracked-files=all"),
                "index": self.wt_git("ls-files", "--stage"),
                "head": self.wt_git("rev-parse", "HEAD"),
                "branch": self.wt_git("rev-parse", "--abbrev-ref", "HEAD"),
                "refs": self.git("for-each-ref", "--format=%(refname) %(objectname)",
                                 "refs/heads", "refs/remotes", "refs/tags"),
                "worktrees": self.worktree_list()}

    def leftovers(self) -> list:
        return sorted(p.name for p in self.tmp_dir.iterdir())

    def set_git_failure(self, mode: str) -> None:
        self.mode_file.write_text(mode, encoding="utf-8")

    def failed_git_calls(self) -> list:
        if not self.git_log.exists():
            return []
        return self.git_log.read_text(encoding="utf-8").splitlines()

    def assert_run_with_appendices(self, out: str) -> None:
        """Полный набор прошёл ровно на временном дереве с правками: проба
        видела правки, корень прогона — не рабочая копия задачи."""
        ctx = self.context(out)
        self.assertTrue(self.runs, f"полный набор не запускался; {ctx}")
        self.assertNotIn(self.wt, self.runs,
                         f"прогон шёл в рабочей копии задачи; {ctx}")
        records = self.probe_records()
        self.assertTrue(records, f"тест-проба ветки не исполнялся; {ctx}")
        self.assertTrue(all(r["present"] for r in records),
                        f"дерево прогона без правок приложений; {ctx}")


    def inapplicable_scenario(self) -> tuple:
        """Одно-два применимых приложения ко второму файлу и одно
        неприменимое к первому (место — от зерна): его контекст несёт строку,
        которой в `main` нет. (диффы, нужды пробы, номер неприменимого,
        его путь)."""
        good = []
        for line in self.rng.sample(EDIT_LINES, self.rng.randint(1, 2)):
            marker = f"правка ({self.rng.randrange(10**6)})"
            good.extend(self.diff_chain([{self.files[1]: {line: marker}}]))
        bad = self.chained_edits(2)[0][1]
        index = self.rng.randrange(len(good) + 1)
        diffs = good[:index] + [bad] + good[index:]
        return diffs, [], index + 1, self.files[0]

    def assert_no_run(self, out: str) -> None:
        ctx = self.context(out)
        self.assertEqual(self.runs, [], f"полный набор запускался; {ctx}")
        self.assertEqual(self.probe_records(), [],
                         f"тест-проба исполнялся; {ctx}")

    def assert_names_appendix(self, text: str, number: int, rel: str,
                              out: str) -> None:
        ctx = self.context(out)
        self.assertTrue(names_number(text, number),
                        f"причина не называет приложение {number}: {text!r}; {ctx}")
        self.assertIn(rel, text, f"причина не называет путь {rel}; {ctx}")

    def entries(self, action: str) -> list:
        return [e for e in self.journal() if e.startswith(action)]

    def assert_no_temp_tree(self, before: dict, tmp_before: list,
                            out: str) -> None:
        """Временного дерева на диске нет: корни прогонов вне рабочей копии
        удалены, временный каталог процесса — как до прогона, `git worktree
        list` клона прежний."""
        ctx = self.context(out)
        for root in self.runs:
            if root != self.wt:
                self.assertFalse(root.exists(),
                                 f"дерево прогона {root} осталось; {ctx}")
        self.assertEqual(self.leftovers(), tmp_before,
                         f"во временном каталоге остались файлы; {ctx}")
        self.assertEqual(self.worktree_list(), before["worktrees"],
                         f"git worktree list изменился; {ctx}")


class AutogateAppendixTest(AppendixRunSandbox):

    def test_ac1_autogate_green_with_plan_appendix(self):
        """Автогейт: тест ветки красен на голове и зелёный с приложением.

        Сценарий: PLAN несёт одно-три независимых приложения к защищённым
        markdown-файлам (число и файлы — от зерна); тест-проба ветки требует
        правок всех. `advance` из `review` с вердиктом approved: автогейт
        приёмки проходит — задача в `merge_gate`; полный набор шёл не в
        рабочей копии задачи, а на дереве, где проба увидела все правки.

        Ловит мутацию: автогейт гоняет набор по-прежнему в
        `workspace.path` — проба красна, запись «автогейт acceptance не
        пройден», задача в `acceptance`; накладывается только первое
        приложение (`break` после первого `git apply`) — проба не видит
        правки второго и красна.
        """
        diffs, needs = self.independent_edits(self.rng.randint(1, 3))
        self.make_task(needs, "review")
        self.write_docs(diffs)

        out = self.advance_from_review()

        ctx = self.context(out)
        self.assertEqual(self.state(), "merge_gate", ctx)
        self.assert_run_with_appendices(out)


class ApproveAppendixTest(AppendixRunSandbox):

    def test_ac2_approve_passes_without_accept_red(self):
        """approve в `acceptance`: тест красен без приложения — приёмка проходит.

        Сценарий: тот же, что у автогейта (одно-три приложения от зерна);
        `approve` без `--accept-red`. Задача в `merge_gate`, записи
        осознанного принятия красноты нет, записи «approve отклонён» нет;
        набор шёл на дереве с правками приложений.

        Ловит мутацию: approve по-прежнему гоняет набор в рабочей копии —
        проба красна, «approve отклонён», задача остаётся в `acceptance`;
        приложения наложены, но прогон запущен на корне рабочей копии, а не
        временного дерева — корень прогона равен `workspace.path`.
        """
        diffs, needs = self.independent_edits(self.rng.randint(1, 3))
        self.make_task(needs, "acceptance")
        self.write_docs(diffs)

        out = self.approve()

        ctx = self.context(out)
        self.assertEqual(self.state(), "merge_gate", ctx)
        journal = "\n".join(self.journal())
        self.assertNotIn(fsm.ACCEPTANCE_RED_ACCEPTED_ACTION, journal, ctx)
        self.assertNotIn(APPROVE_REFUSED, journal, ctx)
        self.assert_run_with_appendices(out)


class AppendixOrderTest(AppendixRunSandbox):

    def test_ac4_chained_appendices_green_on_autogate_and_approve(self):
        """Два приложения, второе применимо только поверх первого, — зелено.

        Сценарий: две задачи; у каждой PLAN несёт два приложения к одной
        строке защищённого файла: первое меняет строку базы, второе — уже
        изменённую первым (контекст второго хунка несёт маркер первого).
        Проба требует маркера второго. Автогейт первой задачи проходит
        (`merge_gate`), `approve` второй в `acceptance` проходит.

        Ловит мутацию: приложения накладываются в обратном порядке либо
        каждое проверяется `git apply --check` против чистой головы —
        второе «неприменимо», прогона нет, автогейт не пройден и approve
        отклонён; наложено только первое — проба не видит маркера второго.
        """
        diffs, needs = self.chained_edits(2)
        self.make_task(needs, "review")
        self.write_docs(diffs)
        out = self.advance_from_review()
        self.assertEqual(self.state(), "merge_gate", self.context(out))
        self.assert_run_with_appendices(out)

        self.runs.clear()
        self.journal_file.unlink(missing_ok=True)
        diffs, needs = self.chained_edits(2)
        self.make_task(needs, "acceptance")
        self.write_docs(diffs)
        out = self.approve()
        self.assertEqual(self.state(), "merge_gate", self.context(out))
        self.assert_run_with_appendices(out)


class WorkingCopyIntactTest(AppendixRunSandbox):

    def check_intact(self, enter) -> None:
        diffs, needs = self.independent_edits(self.rng.randint(1, 2))
        self.make_task(needs, "review")
        self.write_docs(diffs)
        untracked = self.wt / f"заметка-{self.word()}.txt"
        untracked.write_text("неотслеживаемый файл\n", encoding="utf-8")
        before = self.wt_snapshot()
        tmp_before = self.leftovers()

        out = enter()

        self.assertEqual(self.state(), "merge_gate", self.context(out))
        self.assert_run_with_appendices(out)
        after = self.wt_snapshot()
        for key, value in before.items():
            self.assertEqual(after[key], value,
                             f"{key} рабочей копии изменился; {self.context(out)}")
        self.assertTrue(untracked.exists(), self.context(out))
        self.assert_no_temp_tree(before, tmp_before, out)

    def test_ac5_autogate_leaves_working_copy_untouched(self):
        """Автогейт с приложениями не трогает рабочую копию задачи.

        Сценарий: в рабочей копии — неотслеживаемый файл; автогейт с одним-
        двумя приложениями проходит. После него `git status --porcelain`,
        индекс (`ls-files --stage`), голова, имя ветки, ссылки `refs/heads`,
        `refs/remotes`, `refs/tags` и `git worktree list` — как до прогона;
        корня прогона на диске нет, временный каталог процесса пуст как был.

        Ловит мутацию: приложения накладываются прямо в рабочую копию и
        откатываются `git checkout -- .` — правки сняты, но неотслеживаемый
        файл и статус целы только при честном откате, а `git stash -u`
        вместо отката уносит неотслеживаемый файл; временное дерево заведено
        `git worktree add -b` и ветка не удалена — `refs/heads` изменился;
        `git worktree remove` забыт — `git worktree list` и каталог остаются.
        """
        self.check_intact(self.advance_from_review)

    def test_ac5_approve_leaves_working_copy_untouched(self):
        """approve с приложениями не трогает рабочую копию задачи.

        Сценарий и проверки — те же, что у автогейта, вход — `approve` в
        `acceptance`.

        Ловит мутацию: approve накладывает приложения в рабочую копию и не
        откатывает их — статус показывает изменённые защищённые файлы;
        уборка временного дерева пропущена на зелёном исходе — его каталог
        и запись `git worktree list` остаются.
        """
        self.check_intact(self.approve)


class InapplicableAppendixTest(AppendixRunSandbox):

    def test_ac6_autogate_refuses_inapplicable_without_run(self):
        """Неприменимое приложение — автогейт не пройден, набор не запущен.

        Сценарий: среди двух-трёх приложений одно (место от зерна) не ложится
        на голову ветки. `advance` из `review`: задача осталась в
        `acceptance`, запись «автогейт acceptance не пройден» называет номер
        неприменимого приложения и его путь; полный набор не запускался.

        Ловит мутацию: неприменимое приложение пропускается, прогон идёт с
        остальными — набор запущен; отказ без номера (только «приложение
        неприменимо») или без пути — причина не называет приложение.
        """
        diffs, needs, number, rel = self.inapplicable_scenario()
        self.make_task(needs, "review")
        self.write_docs(diffs)

        out = self.advance_from_review()

        self.assertEqual(self.state(), "acceptance", self.context(out))
        refused = self.entries(AUTOGATE_REFUSED)
        self.assertTrue(refused, self.context(out))
        self.assert_names_appendix(refused[-1], number, rel, out)
        self.assert_no_run(out)

    def test_ac6_approve_refuses_inapplicable_without_run(self):
        """Неприменимое приложение — approve отклонён, набор не запущен.

        Сценарий тот же, вход — `approve` в `acceptance`: задача осталась в
        `acceptance`, запись «approve отклонён» называет номер приложения и
        его путь; полный набор не запускался.

        Ловит мутацию: approve при неприменимом приложении откатывается на
        прогон в рабочей копии — набор запущен в `workspace.path`; отказ
        называет только путь без номера приложения.
        """
        diffs, needs, number, rel = self.inapplicable_scenario()
        self.make_task(needs, "acceptance")
        self.write_docs(diffs)

        out = self.approve()

        self.assertEqual(self.state(), "acceptance", self.context(out))
        refused = self.entries(APPROVE_REFUSED)
        self.assertTrue(refused, self.context(out))
        self.assert_names_appendix(refused[-1], number, rel, out)
        self.assert_no_run(out)


class GitFailureTest(AppendixRunSandbox):

    def check_git_failure(self, mode: str, state: str, enter,
                          refusal: str) -> None:
        diffs, needs = self.independent_edits(self.rng.randint(1, 2))
        self.make_task(needs, state)
        self.write_docs(diffs)
        self.set_git_failure(mode)
        try:
            out = enter()
        finally:
            self.mode_file.unlink(missing_ok=True)
        ctx = self.context(out) + f"\n--- режим сбоя: {mode}; отказы git: " \
                                  f"{self.failed_git_calls()}"
        self.assertNotIn(self.wt, self.runs,
                         f"прогон без приложений в рабочей копии; {ctx}")
        if mode == "worktree add" and not self.failed_git_calls():
            # Временное дерево готовится не `git worktree add` — сбоя
            # подготовки этим способом не вызвать; держится только запрет
            # прогона в рабочей копии без приложений.
            return
        self.assertTrue(self.failed_git_calls(),
                        f"git apply не вызывался вовсе; {ctx}")
        self.assertEqual(self.state(), "acceptance", ctx)
        self.assertTrue(self.entries(refusal), ctx)
        self.assertEqual(self.runs, [], f"полный набор запускался; {ctx}")
        self.assertEqual(self.probe_records(), [], ctx)

    def test_ac7_git_failure_refuses_autogate_and_approve(self):
        """Сбой git при подготовке дерева или наложении — отказ без прогона.

        Сценарий: для каждого режима сбоя (`git apply` ненулевым кодом,
        `git worktree add` ненулевым кодом) — задача с применимыми
        приложениями на автогейте и задача на `approve`. Исход: задача в
        `acceptance`, запись «автогейт acceptance не пройден» / «approve
        отклонён»; полный набор не запускался ни на временном дереве, ни в
        рабочей копии. Если реализация вовсе не зовёт `git worktree add`,
        для этого режима держится только запрет прогона в рабочей копии.

        Ловит мутацию: сбой наложения принят за «приложений нет» — прогон
        идёт в `workspace.path` (fail-open); ответ `git worktree add` не
        проверен — прогон запущен на пустом каталоге либо в рабочей копии;
        сбой `git apply` записан как неприменимость, но прогон всё равно
        запущен.
        """
        for mode in ("apply", "worktree add"):
            for state, enter, refusal in (
                    ("review", self.advance_from_review, AUTOGATE_REFUSED),
                    ("acceptance", self.approve, APPROVE_REFUSED)):
                self.case = f"режим сбоя {mode}, вход из {state}"
                self.runs.clear()
                self.journal_file.unlink(missing_ok=True)
                self.git_log.unlink(missing_ok=True)
                self.check_git_failure(mode, state, enter, refusal)


class TempTreeRemovedTest(AppendixRunSandbox):

    OUTCOMES = ("зелёный", "красный", "неприменимое приложение",
                "сбой git", "исключение")

    def prepare(self, outcome: str, state: str) -> None:
        if outcome == "неприменимое приложение":
            diffs, needs, _number, _rel = self.inapplicable_scenario()
        else:
            diffs, needs = self.independent_edits(self.rng.randint(1, 2))
        if outcome == "красный":
            needs = needs + [(self.files[0], f"нет такой правки {self.word()}")]
        self.make_task(needs, state)
        self.write_docs(diffs)

    def test_ac8_temp_tree_absent_after_each_outcome(self):
        """Временного дерева нет после прогона на каждом исходе.

        Сценарий: для автогейта и для approve — по задаче на исход: зелёный
        прогон, красный (проба ждёт правки, которой нет ни в одном
        приложении), неприменимое приложение, сбой `git apply`, исключение
        в ходе прогона (`run_full_suite` бросает). После каждого: корень
        прогона (если был) удалён, временный каталог процесса — как до
        прогона, `git worktree list` клона прежний.

        Ловит мутацию: уборка дерева стоит после разбора исхода, а не в
        `finally` — на исключении каталог и запись worktree остаются;
        на красном исходе выход раньше уборки — каталог остаётся; на отказе
        наложения дерево не убирается — `git worktree list` растёт.
        """
        for state, enter in (("review", self.advance_from_review),
                             ("acceptance", self.approve)):
            for outcome in self.OUTCOMES:
                self.case = f"исход «{outcome}», вход из {state}"
                self.runs.clear()
                self.journal_file.unlink(missing_ok=True)
                self.prepare(outcome, state)
                before = self.wt_snapshot()
                tmp_before = self.leftovers()
                self.raise_in_run = outcome == "исключение"
                if outcome == "сбой git":
                    self.set_git_failure("apply")
                try:
                    out = enter()
                finally:
                    self.raise_in_run = False
                    self.mode_file.unlink(missing_ok=True)
                if outcome in ("зелёный", "красный", "исключение"):
                    self.assertTrue(self.runs, self.context(out))
                    self.assertNotIn(self.wt, self.runs, self.context(out))
                self.assert_no_temp_tree(before, tmp_before, out)


class NoAppendixTest(AppendixRunSandbox):

    def test_ac9_plan_without_appendices_runs_in_working_copy(self):
        """PLAN без приложений — набор идёт в рабочей копии задачи.

        Сценарий: PLAN без разделов «## Приложение», проба ничего не
        требует. Автогейт одной задачи и approve другой проходят; корень
        прогона и cwd пробы равны `workspace.path` задачи.

        Ловит мутацию: временное дерево заводится всегда, даже без
        приложений, — корень прогона не рабочая копия; без приложений
        прогон пропускается вовсе — набор не запущен.
        """
        for state, enter in (("review", self.advance_from_review),
                             ("acceptance", self.approve)):
            self.case = f"вход из {state}"
            self.runs.clear()
            self.journal_file.unlink(missing_ok=True)
            self.make_task([], state)
            self.write_docs([])
            out = enter()
            ctx = self.context(out)
            self.assertEqual(self.state(), "merge_gate", ctx)
            self.assertEqual(self.runs, [self.wt], ctx)
            records = self.probe_records()
            self.assertTrue(records, ctx)
            self.assertEqual({r["cwd"] for r in records}, {str(self.wt)}, ctx)


    def test_ac9_non_artel_task_runs_in_working_copy(self):
        """Задача не артели — набор идёт в рабочей копии, приложения не накладываются.

        Сценарий: внешний проект (`tests/sandbox.py::make_project_repo`),
        задача с рабочей копией и тестом-пробой без требований; PLAN несёт
        одно-два приложения к защищённым путям. Автогейт одной задачи и
        approve другой проходят; корень прогона и cwd пробы — рабочая копия
        задачи, временного дерева не заводилось.

        Ловит мутацию: проверка `repo_context.is_artel` пропущена —
        приложения накладываются и во внешнем проекте: файлов пульта там
        нет, `git apply` отказывает, автогейт не пройден и approve отклонён
        (или прогон идёт на временном дереве — корень не рабочая копия).
        """
        target = f"p{self.word()}"
        make_project_repo(target)
        for state, enter in (("review", self.advance_from_review),
                             ("acceptance", self.approve)):
            self.case = f"внешний проект {target}, вход из {state}"
            diffs, _needs = self.independent_edits(self.rng.randint(1, 2))
            self.runs.clear()
            self.journal_file.unlink(missing_ok=True)
            self.make_task([], state, target)
            self.write_docs(diffs)
            out = enter()
            ctx = self.context(out)
            self.assertEqual(self.state(), "merge_gate", ctx)
            self.assertEqual(self.runs, [self.wt], ctx)
            records = self.probe_records()
            self.assertTrue(records, ctx)
            self.assertEqual({r["cwd"] for r in records}, {str(self.wt)}, ctx)


class JournalMarkTest(AppendixRunSandbox):

    def check_mark(self, state: str, enter) -> None:
        diffs, needs = self.independent_edits(self.rng.randint(1, 3))
        self.make_task(needs, state)
        self.write_docs(diffs)
        out = enter()
        ctx = self.context(out)
        self.assertEqual(self.state(), "merge_gate", ctx)
        paths = sorted({rel for rel, _marker in needs})
        marked = [e for e in self.journal()
                  if WITH_APPENDICES in e.lower()
                  and all(p in e for p in paths)]
        self.assertTrue(marked, f"нет записи «с приложениями PLAN» с путями "
                                f"{paths}; {ctx}")

    def test_ac10_autogate_journal_names_appendix_run(self):
        """Запись автогейта называет прогон с приложениями PLAN и их пути.

        Сценарий: одно-три приложения к одному-двум защищённым файлам;
        автогейт проходит. Среди записей журнала задачи есть запись с
        признаком «с приложениями PLAN» и всеми путями наложенных
        приложений.

        Ловит мутацию: условие «полный набор зелёный» пишется прежней
        строкой без признака — по журналу не отличить прогон с приложениями
        от прогона рабочей копии; в записи только путь первого приложения.
        """
        self.check_mark("review", self.advance_from_review)

    def test_ac10_approve_journal_names_appendix_run(self):
        """Запись approve называет прогон с приложениями PLAN и их пути.

        Сценарий тот же, вход — `approve` в `acceptance`.

        Ловит мутацию: approve журналирует зелёный прогон прежним `detail`
        узла `full_suite` без признака приложений; пути приложений есть в
        выводе команды, но не в журнале.
        """
        self.check_mark("acceptance", self.approve)


class MergeGateUnchangedTest(AppendixRunSandbox):

    def conftest_diff(self) -> str:
        line = f"# приложение песочницы {self.rng.randrange(10**6)}"
        return ("diff --git a/tests/conftest.py b/tests/conftest.py\n"
                "new file mode 100644\n"
                "--- /dev/null\n"
                "+++ b/tests/conftest.py\n"
                "@@ -0,0 +1 @@\n"
                f"+{line}\n")

    def merge(self) -> str:
        self.set_row(state="merge_gate")
        return self.call(fsm.cmd_approve, self.task)

    def origin_file(self, rel: str) -> str:
        return self.git("--git-dir", str(self.origin), "show",
                        f"refs/heads/{config.MAIN_BRANCH}:{rel}")

    def origin_main_sha(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse",
                        f"refs/heads/{config.MAIN_BRANCH}").strip()

    def test_ac12_merge_gate_applies_in_order_and_refuses_as_before(self):
        """Гейт мержа: прежний порядок, условие прогона и прежний отказ.

        Сценарий 1: PLAN несёт два цепных приложения (второе — поверх
        первого) и, от зерна, приложение `tests/conftest.py`. `approve` на
        `merge_gate`: задача в `done`, в `origin/main` — маркер второго
        приложения; полный набор на мерже запускался тогда и только тогда,
        когда среди приложений есть путь `tests/` (условие
        `_FULL_SUITE_APPENDIX_PREFIXES`), и шёл не в рабочей копии задачи.
        Сценарий 2: одно приложение неприменимо — задача возвращена в
        `in_dev` записью «приложение PLAN неприменимо после подтяжки: …» с
        его путём, `origin/main` не сдвинут.

        Ловит мутацию: вынесенный узел накладывает приложения в обратном
        порядке — второе неприменимо, задача уходит в `in_dev`; узел гоняет
        полный набор всегда (или никогда) — число прогонов на мерже не
        совпадает с условием путей; отказ гейта мержа переписан текстом
        нового узла — прежнего префикса записи нет.
        """
        diffs, needs = self.chained_edits(2)
        with_conftest = self.rng.random() < 0.5
        if with_conftest:
            diffs.insert(self.rng.randrange(len(diffs) + 1), self.conftest_diff())
        self.make_task(needs, "merge_gate")
        self.write_docs(diffs)
        out = self.merge()
        ctx = self.context(out) + f"\n--- приложение conftest: {with_conftest}"
        self.assertEqual(self.state(), "done", ctx)
        (rel, marker), = needs
        self.assertIn(marker, self.origin_file(rel), ctx)
        if with_conftest:
            self.assertTrue(self.runs, f"прогон на мерже не запускался; {ctx}")
            self.assertNotIn(self.wt, self.runs, ctx)
        else:
            self.assertEqual(self.runs, [], f"прогон на мерже без tests/; {ctx}")

        self.runs.clear()
        diffs, needs, _number, bad_rel = self.inapplicable_scenario()
        self.make_task(needs, "merge_gate")
        self.write_docs(diffs)
        before = self.origin_main_sha()
        out = self.merge()
        ctx = self.context(out)
        self.assertEqual(self.state(), "in_dev", ctx)
        returned = [e for e in self.journal()
                    if INAPPLICABLE_PREFIX in e and bad_rel in e]
        self.assertTrue(returned, ctx)
        self.assertEqual(self.origin_main_sha(), before, ctx)


if __name__ == "__main__":
    unittest.main()
