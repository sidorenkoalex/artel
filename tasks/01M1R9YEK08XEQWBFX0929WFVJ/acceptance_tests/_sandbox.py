"""Общая песочница приёмочных тестов задачи 01M1R9YEK08XEQWBFX0929WFVJ (не
test_*.py — не подхватывается `unittest discover` напрямую, только импортом
из test_ac*.py).

НАСТОЯЩИЙ git на всём протяжении (тот же принцип, что и `tasks/
01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/_sandbox.py::
OriginDivergedSandbox`, `tasks/T053/.../_sandbox.py`,
`tests/test_merge_gate_ci_wait.py`'s собственный докстринг: «приёмочные
тесты кроют AC сквозным путём через fsm.cmd_approve в НАСТОЯЩЕМ git; узлы
в изоляции — дело tests/, не этой планки»). Ни `gitcmd.show`/
`gitcmd.ls_tree_files`, ни `gitcmd.git` здесь не подменяются — обе
ветки задачи (кодовая и артефактная) реальные ветки одного и того же
`self.root`, материализация из артефактной ветки (`acceptance.
materialize_from_branch`) читает их по-настоящему.

`AcceptancePullSandbox` — предмет проверки AC-1..AC-5, AC-10: источник
приёмочной планки на входе `approve` из `acceptance` (сверка свежести
ветки в состоянии «подтяжка», `_pull_main_or_escalate`, — единственная
точка, где эта планка сегодня вообще прогоняется на этом гейте, SPEC
«Требования» п.1). Кодовая ветка задачи всегда СПЕЦИАЛЬНО заводится
ПОЗАДИ main (main получает лишний коммит уже после ответвления кодовой
ветки) — иначе `_pull_main_or_escalate` возвращает `"fresh"` и планка не
прогоняется вовсе (см. `tests/test_branch_freshness_gate.py::
test_approve_skips_pull_when_branch_not_behind`, тот же вырожденный
случай).

`MergeGateSnapshotSandbox` — предмет проверки AC-6..AC-8, AC-11: итоговое
содержимое `tasks/<id>/`, которое `merge_gate -> done` кладёт в main,
— тело гейта `fsm_merge_gate._cmd_approve_merge_gate` зовётся НАПРЯМУЮ
(тот же приём, что `tests/test_fsm_merge_gate_done_snapshot.py`),
`confirmed_ci_note` передаётся явно вместо прогона цикла ожидания CI.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (acceptance, artifact_branch, catalog, ci, config,  # noqa: E402
                          fsm, fsm_merge_gate, gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

SPEC_REQUIRES_TESTS = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: фикстура приёмочной планки (не собственный SPEC этой задачи)

## Контекст
Фикстура для песочницы 01M1R9YEK08XEQWBFX0929WFVJ.

## Требования
1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.
"""

SPEC_SKIP_TESTS = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
skip_tests: фикстура — тесты этой синтетической задачи не нужны
---

# SPEC: фикстура приёмочной планки (skip_tests)

## Контекст
Фикстура для песочницы 01M1R9YEK08XEQWBFX0929WFVJ.

## Требования
1. Фикстура.

## Критерии приёмки

AC-1. Фикстура — тесты пропущены.
"""

GREEN_TEST = '''"""Зелёный с рождения: фикстура артефактной ветки песочницы
01M1R9YEK08XEQWBFX0929WFVJ — не собственный критерий этой задачи, просто
заведомо зелёный unittest, используемый как содержимое чужой планки."""
import unittest


class FixtureGreenTest(unittest.TestCase):

    def test_fixture_green(self):
        self.assertEqual(1 + 1, 2)
'''

RED_TEST = '''"""Зелёный с рождения: фикстура — намеренно красный unittest, используемый
как содержимое ЧУЖОЙ (worktree/устаревшей) планки, чтобы отличить её от
настоящего источника."""
import unittest


class FixtureRedTest(unittest.TestCase):

    def test_fixture_red(self):
        self.assertEqual(1 + 1, 3, "фикстура: намеренно красный тест")
'''


class AcceptancePullSandbox(RealGitSandbox):
    """Задача в состоянии `acceptance`; кодовая ветка на один коммит
    ПОЗАДИ main на origin (`_pull_main_or_escalate` обязана подтянуть и
    прогнать планку)."""

    TASK = "01ACCPULLSANDBOXTASK001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

        self.origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

        self.branch = f"task/{self.TASK.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        # Кодовая ветка НИКОГДА не несёт tasks/<id>/ (conventions-core) —
        # только код фичи.
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: код фичи")
        self.git("checkout", "-q", config.MAIN_BRANCH)

        # main уходит вперёд ПОСЛЕ ответвления кодовой ветки — ветка
        # задачи отстаёт, `_pull_main_or_escalate` обязана подтянуть.
        (self.root / "main-advance.txt").write_text(
            "main ушёл вперёд после ответвления\n", encoding="utf-8")
        self.git("add", "main-advance.txt")
        self.git("commit", "-q", "-m", "main ушёл вперёд")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

        store.insert_task(store.db(), self.TASK, "Песочница приёмки",
                          "acceptance", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    # ------------------------------------------------------------ утилиты

    def commit_artifact(self, files: dict) -> None:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: фикстура планки")
        self.assertTrue(sha, "artifact_branch.commit_files не сработал")

    def spec_requires_tests(self) -> dict:
        return {f"tasks/{self.TASK}/SPEC.md":
                SPEC_REQUIRES_TESTS.format(task=self.TASK)}

    def spec_skip_tests(self) -> dict:
        return {f"tasks/{self.TASK}/SPEC.md":
                SPEC_SKIP_TESTS.format(task=self.TASK)}

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def journal_details(self) -> list[str]:
        """`action` + `detail` конкатенированы — см. тот же приём в
        `MergeGateSnapshotSandbox.journal_details` ниже."""
        return [f"{r['action']} {r['detail']}" for r in store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def approve(self) -> str:
        return capture(fsm.cmd_approve, self.TASK)

    def worktree_dir(self) -> Path:
        wt_path, error = workspace.ensure(self.TASK, self.branch)
        self.assertIsNone(error, f"worktree не заведён: {error}")
        return wt_path


class MergeGateSnapshotSandbox(RealGitSandbox):
    """Задача в состоянии `merge_gate`, готовая пройти в `done`: кодовая
    ветка не отстаёт от main (путь `"fresh"` — merge случается в этом же
    вызове тела гейта), CI ветки замокан зелёным."""

    TASK = "01MERGESNAPSHOTSANDBOX01"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

        self.pult_origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.pult_origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(self.pult_origin))
        self.git("remote", "add", "origin", str(self.pult_origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

        self.branch = f"task/{self.TASK.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: код фичи")
        self.git("checkout", "-q", config.MAIN_BRANCH)

        store.insert_task(store.db(), self.TASK, "Песочница merge_gate",
                          "merge_gate", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        ci_patcher.start()
        self.addCleanup(ci_patcher.stop)

    def commit_artifact(self, files: dict) -> None:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: снимок артефактов")
        self.assertTrue(sha, "artifact_branch.commit_files не сработал")

    def commit_legacy_on_code_branch(self, files: dict) -> None:
        """Коммитит `files` НА КОДОВУЮ ветку задачи — легаси-копия
        `tasks/<id>/`, которую ordinary `git merge` иначе перенёс бы в
        main как есть (AC-6/AC-7/AC-11)."""
        self.git("checkout", "-q", self.branch)
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", f"{self.TASK}: легаси-копия артефактов")
        self.git("checkout", "-q", config.MAIN_BRANCH)

    def approve_merge_gate(self) -> tuple:
        t = store.get_task(store.db(), self.TASK)
        return fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), self.TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def journal_details(self) -> list[str]:
        """`action` + `detail` конкатенированы (не только `detail`):
        implementация вправе назвать предупреждение расхождения в любом
        из двух полей журнала — тест не обязан гадать, в каком именно."""
        return [f"{r['action']} {r['detail']}" for r in store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def origin_main_file_text(self, rel: str) -> str | None:
        res = subprocess.run(
            ["git", "-C", str(self.pult_origin), "show",
             f"{config.MAIN_BRANCH}:{rel}"],
            capture_output=True, text=True)
        return res.stdout if res.returncode == 0 else None


if __name__ == "__main__":
    unittest.main()
