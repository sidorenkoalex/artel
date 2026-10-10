"""Гейт мержа и приложение PLAN, уже наложенное в подтянутом `main`: запись журнала общей формы «приложение PLAN уже в базе».

Группа: долгоживущий
Красен до реализации: test_ac5 — гейт мержа пишет о пропуске своим действием «приложение PLAN уже в main: <пути>», записи с действием `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION: <пути>` в журнале нет. Зелёный с рождения: test_ac7 (наложенное наполовину приложение и сегодня возвращает задачу в `in_dev`).

Сценарий — сквозной `fsm.cmd_approve` задачи артели на гейте `merge_gate`
в настоящем git-репозитории песочницы (`tests/sandbox.py::RealGitSandbox`)
с настоящим bare `origin`: ветка задачи отходит от `main` раньше, чем
Оператор вносит правку защищённого файла коммитом в `main`. Подменены
только внешние проверки, которых в песочнице нет: цвет CI ветки и main,
Draft MR форжа и полный прогон набора (`acceptance.run_full_suite`).

Число приложений, место уже наложенного среди них, файлы и строки правок —
от зерна; зерно печатается и входит в текст каждого провала.

Валидировано временным стабом реализации (гейт мержа пишет пропуск
действием `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION`): все тесты файла
зелёные, стаб удалён.
"""
import contextlib
import io
import random
import unittest
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          github_adapter, idgen, store)
from orchestrator.advance_gates import plan_appendix
from tests.sandbox import ARTEL_TEST_PROFILE, RealGitSandbox, capture

# Защищённые файлы — от `config.PROTECTED_PATHS`, не литералом: перечень
# меняет Оператор. Markdown вне `tests/` и `.github/`: правка `tests/`
# приложением требует на мерже полного прогона (он здесь подменён), текст
# фикстуры в защищённом конфиге читался бы как конфиг.
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

INAPPLICABLE_PREFIX = "приложение PLAN неприменимо после подтяжки:"


class MergeGateInBaseSandbox(RealGitSandbox):
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
            name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH)
            + ARTEL_TEST_PROFILE, encoding="utf-8")
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
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.object(acceptance, "run_full_suite",
                                  lambda root: (True, "1 passed (тест)")),
                mock.patch.object(ci, "branch_status",
                                  lambda branch, repo=None:
                                  (True, "зелёный (тест)")),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

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

    def write_plan(self, diffs: list) -> None:
        """PLAN.md с разделами «## Приложение N» — в каталог документов
        задачи и автокоммитом пульта в ссылку документов."""
        sections = "".join(
            f"\n## Приложение {i}: правка {self.rng.randrange(10**6)}\n\n"
            f"```diff\n{diff}```\n" for i, diff in enumerate(diffs, 1))
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

    def steps(self) -> list:
        return list(store.task_steps(store.db(), self.task))

    def journal(self) -> list:
        return [f"{r['action']} | {r['detail'] or ''}" for r in self.steps()]

    def origin_main_sha(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse",
                        "refs/heads/" + config.MAIN_BRANCH).strip()

    def origin_file(self, rel: str) -> str:
        return self.git("--git-dir", str(self.origin), "show",
                        f"refs/heads/{config.MAIN_BRANCH}:{rel}")


class MergeGateAlreadyInBaseTest(MergeGateInBaseSandbox):

    def test_ac5_merge_gate_skips_appendix_in_base_with_common_record(self):
        """Приложение, уже наложенное Оператором в `main`, гейт мержа пропускает записью общей формы.

        Сценарий: PLAN несёт одно-три приложения (число и место уже
        наложенного — от зерна); уже наложенное правит первый защищённый
        файл, прочие — второй, ещё не наложены. Оператор вносит правку
        этого приложения в `main` после отхода ветки. `approve` на
        `merge_gate`: задача в `done`; в журнале задачи есть запись с
        действием ровно `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION + ": " +
        <путь>` и подробностями, содержащими «приложение N (<путь>)» с
        номером этого приложения; правка уже наложенного в `origin/main`
        ровно один раз.

        Ловит мутацию: гейт мержа пишет пропуск прежним действием
        «приложение PLAN уже в main: <пути>» — записи с действием
        `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION: <путь>` нет; номер в
        подробностях считается с нуля — «приложение N» не совпадает с
        местом в PLAN; общее правило признания вызвано без записи журнала
        (запись осталась только у гейта применимости) — записи нет.
        """
        total = self.rng.randint(1, 3)
        number = self.rng.randrange(total) + 1
        lines = self.rng.sample(EDIT_LINES, total)
        diffs, applied = [], None
        for i in range(1, total + 1):
            rel = self.files[0] if i == number else self.files[1]
            edit = {rel: {lines[i - 1]:
                          f"правка {i} ({self.rng.randrange(10**6)})"}}
            if i == number:
                applied = edit
            diffs.append(self.diff_of(edit))
        self.write_plan(diffs)
        self.operator_commits_to_main(applied)
        rel = self.files[0]
        (marker,) = applied[rel].values()

        out = self.approve()

        context = self.note(f"приложений {total}, уже в main — {number}\n"
                            + "\n".join(self.journal())
                            + "\n--- вывод approve:\n" + out)
        self.assertEqual(self.state(), "done", context)
        action = f"{plan_appendix.PLAN_APPENDIX_ALREADY_IN_BASE_ACTION}: {rel}"
        detail = f"приложение {number} ({rel})"
        records = [s for s in self.steps() if s["action"] == action
                   and detail in (s["detail"] or "")]
        self.assertTrue(records, f"нет записи «{action}» с «{detail}»; {context}")
        self.assertEqual(self.origin_file(rel).count(marker), 1, context)


class MergeGateNeitherWayTest(MergeGateInBaseSandbox):

    def test_ac7_half_applied_appendix_refused_at_merge_gate(self):
        """Приложение, наложенное в `main` наполовину, гейт мержа отказывает прежним возвратом.

        Сценарий: одно приложение из двух правок (форма от зерна: два хунка
        одного защищённого файла либо два файла одним блоком); Оператор
        внёс в `main` только одну из правок. `approve` на `merge_gate`:
        задача возвращена в `in_dev` записью «приложение PLAN неприменимо
        после подтяжки: …» с путём приложения, записи «приложение PLAN уже в
        базе» нет, `origin/main` не сдвинут.

        Ловит мутацию: общее правило признания считает «уже в базе» любое
        приложение, не легшее прямо (обратная проверка не зовётся или её
        ответ не читается), — задача уходит в `done`, `origin/main`
        сдвигается без второй половины правки.
        """
        first, second = self.rng.sample(EDIT_LINES, 2)
        if self.rng.random() < 0.5:
            whole = {self.files[0]: {first: "правка A", second: "правка B"}}
        else:
            whole = {self.files[0]: {first: "правка A"},
                     self.files[1]: {second: "правка B"}}
        half = {self.files[0]: {first: "правка A"}}
        self.write_plan([self.diff_of(whole)])
        self.operator_commits_to_main(half)
        before = self.origin_main_sha()

        out = self.approve()

        context = self.note("\n".join(self.journal())
                            + "\n--- вывод approve:\n" + out)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertTrue([e for e in self.journal()
                         if INAPPLICABLE_PREFIX in e and self.files[0] in e],
                        context)
        self.assertFalse([s for s in self.steps() if s["action"].startswith(
            plan_appendix.PLAN_APPENDIX_ALREADY_IN_BASE_ACTION)], context)
        self.assertEqual(self.origin_main_sha(), before, context)


if __name__ == "__main__":
    unittest.main()
