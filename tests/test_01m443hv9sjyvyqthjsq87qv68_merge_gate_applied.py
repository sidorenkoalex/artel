"""Ворота мержа и приложение PLAN, уже наложенное в подтянутом `main`.

Группа: долгоживущий
Красен до реализации: test_ac5 — ворота мержа сегодня накладывают приложение только прямым `git apply`, на уже наложенной в main правке он отказывает, и задача уходит в `in_dev`; test_ac6 зелёный с рождения — частично наложенное приложение и сегодня возвращает задачу тем же исходом.

Сценарий — сквозной `fsm.cmd_approve` задачи артели на гейте `merge_gate`
в настоящем git-репозитории песочницы (`tests/sandbox.py::RealGitSandbox`)
с настоящим bare `origin`: ветка задачи отходит от `main` раньше, чем
Оператор вносит правку защищённого файла коммитом в `main` (прецедент
04.10 — ручной коммит Оператора и `reject`). Подменены только внешние
проверки, которых в песочнице нет: цвет CI ветки (`ci.branch_status`),
цвет CI main (`ci.main_line_status`), Draft MR форжа
(`github_adapter.ensure_draft_mr`/`undraft_mr`) и полный прогон набора
(`acceptance.run_full_suite`).

«Имя» приложения в журнале — любая из его опознавательных черт: путь из
заголовка `diff --git`, текст заголовка раздела «## Приложение…» или его
порядковый номер рядом со словом «приложение» (SPEC, требование 3:
«заголовок/номер»). Сам разбор приложений (`guard.plan_appendices`) путей
не меняет, поэтому путь — общая для всех способов назвать приложение черта.
"""
import contextlib
import io
import random
import re
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          github_adapter, idgen, store)
from tests.sandbox import RealGitSandbox, capture

# Защищённые файлы — от `config.PROTECTED_PATHS`, не литералом: перечень
# меняет Оператор. Вне `tests/` и `.github/` — их правка приложением
# требует полного прогона набора, а он здесь подменён и предметом не служит;
# только markdown — текст фикстуры в защищённом конфиге (YAML пульта,
# `pyproject.toml`) читался бы как конфиг.
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

BASE_LINES = [f"строка базы {n:02d} из 40" for n in range(1, 41)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
# Строки правок — через восемь: контекст хунка (три строки) соседней
# правки их не задевает, и диффы, посчитанные от базы, ложатся друг на
# друга в любом порядке.
EDIT_LINES = BASE_LINES[::8]

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
zones: feature.txt
---

# SPEC: фикстура

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

HEADING_WORDS =("правка", "шаг", "сторож", "настройка", "перечень")

INAPPLICABLE_PREFIX = "приложение PLAN неприменимо после подтяжки:"


def names_appendix(text: str, path: str, heading: str, number: int) -> bool:
    """Текст называет приложение: его путём, заголовком раздела либо
    номером рядом со словом «приложение»."""
    if path in text or heading in text:
        return True
    return re.search(rf"приложени\w*\s*(№\s*)?{number}\b", text,
                     re.IGNORECASE) is not None


class AppliedAppendixMergeSandbox(RealGitSandbox):
    """Задача артели на `merge_gate`: ветка с кодом задачи, PLAN.md с
    приложениями в ссылке документов, `origin` синхронный с `main`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.assertGreaterEqual(len(PROTECTED_FILES), 2, self.note(
            "в config.PROTECTED_PATHS нет двух защищённых файлов вне tests/"))
        self.files = self.rng.sample(PROTECTED_FILES, 2)

        config.TARGETS.write_text(TARGETS_YAML.format(
            name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH),
            encoding="utf-8")
        for rel in self.files:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)

        self.task = idgen.new_task_id()
        self.branch = f"task/{self.task.lower()}-x"
        self.checkout(self.branch, create=True)
        (self.root / "feature.txt").write_text("код задачи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.task}: код задачи")
        self.checkout(config.MAIN_BRANCH)

        store.insert_task(store.db(), self.task, f"Задача {self.task}",
                          "merge_gate", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.full_suite_calls = []
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.object(acceptance, "run_full_suite",
                                  self.fake_full_suite),
                mock.patch.object(ci, "branch_status",
                                  lambda branch, repo=None:
                                  (True, "зелёный (тест)")),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main),
                # Draft MR — обращение к форжу, которого у песочницы нет.
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def fake_full_suite(self, root):
        self.full_suite_calls.append(Path(root))
        return (True, "1 passed (тест)")

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

    def operator_commits_to_main(self, edits: dict) -> None:
        """Ручной коммит Оператора в `main` (и в `origin`) после того, как
        ветка задачи от него отошла."""
        self.checkout(config.MAIN_BRANCH)
        for rel, replacements in edits.items():
            self.edit(rel, replacements)
        self.git("add", "--", *edits)
        self.git("commit", "-q", "-m", "оператор: правка защищённого файла")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def write_plan(self, appendices: list[tuple[str, str]]) -> None:
        """PLAN.md с разделами «## Приложение…» (заголовок, дифф) — в
        каталог документов задачи и автокоммитом пульта в ссылку
        документов."""
        sections = "".join(f"\n## {heading}\n\n```diff\n{diff}```\n"
                           for heading, diff in appendices)
        text = (f"---\ntask: {self.task}\ntype: plan\n"
                f"author_role: developer\nstatus: ready\n"
                f"schema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
                f"Фикстура.\n{sections}")
        docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=self.task),
                                      encoding="utf-8")
        (docs / "PLAN.md").write_text(text, encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, store.db(), self.task,
                "developer")

    def heading(self, number: int) -> str:
        word = self.rng.choice(HEADING_WORDS)
        return f"Приложение {number}: {word} {self.rng.randrange(10**6)}"

    def approve(self) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_approve(self.task)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def state(self) -> str:
        return store.get_task(store.db(), self.task)["state"]

    def journal(self) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(store.db(), self.task)]

    def origin_main_sha(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse",
                        "refs/heads/" + config.MAIN_BRANCH).strip()

    def origin_file(self, rel: str) -> str:
        return self.git("--git-dir", str(self.origin), "show",
                        f"refs/heads/{config.MAIN_BRANCH}:{rel}")


class AlreadyAppliedAppendixTest(AppliedAppendixMergeSandbox):

    def test_ac5_appendix_already_in_main_is_accepted_and_journaled(self):
        """Приложение, уже наложенное Оператором в `main`, ворота мержа принимают.

        Сценарий: PLAN несёт от одного до трёх приложений (число и место
        уже наложенного среди них — от зерна); одно из них Оператор внёс в
        `main` своим коммитом после того, как ветка задачи отошла, прочие
        ещё не наложены. `approve` на `merge_gate`: задача не вернулась в
        `in_dev` и не осталась на гейте с отказом — дошла до `done`; в
        `origin/main` лежат правки ВСЕХ приложений (уже наложенное — ровно
        один раз, без повторной правки); журнал задачи несёт запись, что
        это приложение (названное по имени) уже в `main`; записи
        «неприменимо после подтяжки» нет.

        Ловит мутацию: ворота применяют приложение только прямым `git
        apply` без `git apply --reverse --check` — на уже наложенной правке
        git отказывает, задача уходит в `in_dev` с «неприменимо после
        подтяжки», и тест краснеет на состоянии; вторая мутация — уже
        наложенное приложение принято молча, без записи журнала, и тест
        краснеет на поиске записи «уже в main»; третья — приняв уже
        наложенное, ворота пропускают и остальные приложения задачи
        (`return` вместо `continue`), и их правки нет в `origin/main`.
        """
        total = self.rng.randint(1, 3)
        applied_index = self.rng.randrange(total)
        lines = self.rng.sample(EDIT_LINES, total)
        appendices, edits = [], []
        for i in range(total):
            rel = self.files[0] if i == applied_index else self.files[1]
            marker = f"правка {i + 1} ({self.rng.randrange(10**6)})"
            edit = {rel: {lines[i]: marker}}
            edits.append(edit)
            appendices.append((self.heading(i + 1), self.diff_of(edit)))
        # Не наложенные приложения — к ОДНОМУ файлу, но к разным строкам:
        # дифф каждого посчитан от базы и ложится поверх соседа.
        self.write_plan(appendices)
        self.operator_commits_to_main(edits[applied_index])
        applied_heading = appendices[applied_index][0]
        applied_rel = self.files[0]

        out = self.approve()

        journal = self.journal()
        context = self.note("\n".join(journal) + "\n--- вывод approve:\n" + out)
        self.assertNotEqual(self.state(), "in_dev", context)
        self.assertEqual(self.state(), "done", context)
        self.assertFalse([e for e in journal if INAPPLICABLE_PREFIX in e],
                         context)
        already = [e for e in journal
                   if "main" in e and "уже" in e.lower()
                   and names_appendix(e, applied_rel, applied_heading,
                                      applied_index + 1)]
        self.assertTrue(already, self.note(
            f"в журнале нет записи, что приложение «{applied_heading}» "
            f"({applied_rel}) уже в main:\n" + "\n".join(journal)))
        for i, edit in enumerate(edits):
            (rel, replacements), = edit.items()
            (_old, marker), = replacements.items()
            text = self.origin_file(rel)
            self.assertEqual(text.count(marker), 1, self.note(
                f"правка приложения {i + 1} в origin/main {rel}: "
                f"{text.count(marker)} раз(а)\n{text}"))


class PartiallyAppliedAppendixTest(AppliedAppendixMergeSandbox):

    def test_ac6_partially_applied_appendix_returns_task_as_before(self):
        """Частично наложенное в `main` приложение — прежний возврат задачи в `in_dev`.

        Сценарий: одно приложение из двух правок (форма от зерна: два
        хунка одного защищённого файла либо два файла одним блоком
        ```diff); Оператор внёс в `main` только одну из правок. Ни прямой
        `git apply --check`, ни `--reverse --check` такое приложение не
        проходят. `approve`: задача возвращена в `in_dev` с записью
        «приложение PLAN неприменимо после подтяжки: …» — тот же исход,
        что для неприменимого приложения; `origin/main` не сдвинут.

        Ловит мутацию: ворота считают применённым любое приложение, чей
        прямой `git apply --check` не прошёл (без сверки `--reverse
        --check`), — задача уходит в `done`, `origin/main` сдвигается без
        второй половины правки, и тест краснеет на состоянии и на sha
        `origin/main`.
        """
        first, second = self.rng.sample(EDIT_LINES, 2)
        if self.rng.random() < 0.5:
            whole = {self.files[0]: {first: "правка A", second: "правка B"}}
            half = {self.files[0]: {first: "правка A"}}
        else:
            whole = {self.files[0]: {first: "правка A"},
                     self.files[1]: {second: "правка B"}}
            half = {self.files[0]: {first: "правка A"}}
        heading = self.heading(1)
        self.write_plan([(heading, self.diff_of(whole))])
        self.operator_commits_to_main(half)
        before = self.origin_main_sha()

        out = self.approve()

        journal = self.journal()
        context = self.note("\n".join(journal) + "\n--- вывод approve:\n" + out)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertTrue([e for e in journal if INAPPLICABLE_PREFIX in e],
                        context)
        self.assertEqual(self.origin_main_sha(), before, context)


if __name__ == "__main__":
    unittest.main()
