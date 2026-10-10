"""Регенерация карты кодовой базы после мержа при подложном `python3` первым в PATH.

Группа: долгоживущий
Красен до реализации: регенерация карты после мержа (`fsm_postmerge`) зовёт голый `python3`, подложный `python3` первым в PATH падает кодом 1 — журнал несёт «регенерация карты FAILED», карта в `origin/main` не обновлена.

Сценарий — сквозной `fsm.cmd_approve` задачи артели на гейте `merge_gate`
в настоящем git-репозитории песочницы (`tests/sandbox.py::RealGitSandbox`)
с настоящим bare `origin` — та же связка «команда — FSM — git», что
регенерирует карту на настоящем мерже. В `main` лежат карта и
регенератор-заглушка `scripts/codebase_map.py`, переписывающий карту
текстом со случайной меткой. Подменены только внешние проверки, которых в
песочнице нет: цвет CI ветки и main, Draft MR форжа и полный прогон набора
(`acceptance.run_full_suite`).

Метка карты и текст подложного `python3` — от зерна; зерно печатается и
входит в текст каждого провала.

Валидировано временным стабом реализации (регенерация под
`sys.executable`): тест зелёный, стаб удалён.
"""
import contextlib
import io
import os
import random
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          fsm_postmerge, github_adapter, idgen, store)
from tests.sandbox import ARTEL_TEST_PROFILE, RealGitSandbox, capture

MAP_REL = "docs/codebase-map.md"
REGEN_FAILED_ACTION = "регенерация карты FAILED"

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

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN

## Подход

Фикстура.
"""

COMMITTED_MAP = "# Карта кодовой базы\n\n## orchestrator/x.py\n\nдо мержа\n"
STUB_OK = (
    "import pathlib\n"
    "path = pathlib.Path('docs') / 'codebase-map.md'\n"
    "path.parent.mkdir(parents=True, exist_ok=True)\n"
    "path.write_text({text!r}, encoding='utf-8')\n")


class PostMergeMapSandbox(RealGitSandbox):
    """Задача артели на `merge_gate`: ветка с кодом задачи, карта и
    регенератор-заглушка в `main`, `origin` синхронный с `main`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.marker = f"после мержа {self.rng.randrange(10**9)}"
        regenerated = (f"# Карта кодовой базы\n\n## orchestrator/x.py\n\n"
                       f"{self.marker}\n")
        config.TARGETS.write_text(TARGETS_YAML.format(
            name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH)
            + ARTEL_TEST_PROFILE, encoding="utf-8")
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / MAP_REL).write_text(COMMITTED_MAP, encoding="utf-8")
        (self.root / "scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "scripts" / "codebase_map.py").write_text(
            STUB_OK.format(text=regenerated), encoding="utf-8")
        self.git("add", MAP_REL, "scripts/codebase_map.py")
        self.git("commit", "-q", "-m", "карта и регенератор-заглушка")
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
        docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=self.task),
                                      encoding="utf-8")
        (docs / "PLAN.md").write_text(PLAN_TEXT.format(task=self.task),
                                      encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, store.db(), self.task,
                "developer")

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

    def put_fake_python3_first(self) -> None:
        """Подложный `python3` первым в PATH: завершается кодом 1."""
        bindir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir, ignore_errors=True)
        fake = bindir / "python3"
        fake.write_text(
            "#!/bin/sh\n"
            f"echo 'подложный python3 {self.rng.randrange(10**6)}' >&2\n"
            "exit 1\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                   | stat.S_IXOTH)
        patcher = mock.patch.dict(
            os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def approve(self) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_approve(self.task)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def steps(self) -> list:
        return list(store.task_steps(store.db(), self.task))

    def journal(self) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in self.steps())

    def origin_map(self) -> str:
        return self.git("--git-dir", str(self.origin), "show",
                        f"refs/heads/{config.MAIN_BRANCH}:{MAP_REL}")


class PostMergeMapInterpreterTest(PostMergeMapSandbox):

    def test_ac2_postmerge_map_regen_succeeds_with_fake_python3(self):
        """Регенерация карты после мержа проходит при подложном `python3` первым в PATH.

        Сценарий: `approve` на `merge_gate` при `python3`, завершающемся
        кодом 1, первым в PATH. Задача в `done`; в журнале нет записи
        «регенерация карты FAILED», есть запись размера карты
        (`fsm_postmerge.MAP_SIZE_ACTION`), карта в `origin/main` — текст
        регенератора со случайной меткой.

        Ловит мутацию: регенерация в `fsm_postmerge` снова зовёт голый
        `python3` — подложный интерпретатор падает, журнал несёт
        «регенерация карты FAILED», записи размера карты нет, в
        `origin/main` прежняя карта без метки.
        """
        self.put_fake_python3_first()

        out = self.approve()

        context = self.note(f"{self.journal()}\n--- вывод approve:\n{out}")
        self.assertEqual(store.get_task(store.db(), self.task)["state"], "done",
                         context)
        actions = [r["action"] for r in self.steps()]
        self.assertNotIn(REGEN_FAILED_ACTION, actions, context)
        self.assertIn(fsm_postmerge.MAP_SIZE_ACTION, actions, context)
        self.assertIn(self.marker, self.origin_map(), context)


if __name__ == "__main__":
    unittest.main()
