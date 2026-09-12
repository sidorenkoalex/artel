"""Общая песочница приёмочных тестов 01M2ARQMTYRNPR5HRXAPCBAXNY (не
test_*.py — не подхватывается unittest discover напрямую, только импортом
из test_ac*.py).

Классификация диффа main (документный/недокументный, пересечение с
диффом ветки) — предмет проверки над РЕАЛЬНЫМ git: merge-base, `git diff
--name-only`, `git merge` — заглушками требование 1 SPEC («ВСЕ файлы,
изменённые в main от точки расхождения») не проверить достоверно.
`pull.evaluate` вызывается НАПРЯМУЮ (не через `fsm.cmd_advance`/
`cmd_approve`) — тот же приём, что уже несёт `tests/test_pull.py`
(текущая, пост-рефакторинговая версия): предмет проверки — вычисление
исхода, не диспетчеризация FSM вокруг него.

`RealGitSandbox` (`tests/sandbox.py`) — импорт, не копия (skill
test-authoring: «лёгкая песочница — не копия, импорт»): реальный
git-репозиторий с веткой main и одним коммитом + патч `ALL_CONFIG_ATTRS`
+ схема БД, без единой заглушки `subprocess`. Артефактная планка
(SPEC.md/`acceptance_tests/`) читается С ДИСКА (`disk_backed_show`/
`disk_backed_ls_tree_files`, тот же приём, что и `tests/test_pull.py`),
не из настоящей артефактной ветки — материализация планки не предмет
этой задачи, только повод для `Pulled`-сценариев дойти до
`acceptance.run` (замокан отдельно там, где он вызывается).

Ветка задачи заводится ПОСЛЕ setUp, точкой `branch_off_main()` — не
автоматически: сценарию (в) SPEC (AC-9, общий документный файл, который
правят ОБЕ стороны) нужен файл, существующий уже В ТОЧКЕ РАСХОЖДЕНИЯ, то
есть закоммиченный в main ДО того, как ветка задачи от него ответвится.
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd, pull, store, workspace  # noqa: E402
from tests.sandbox import (RealGitSandbox, disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show)

TASK = "01PULLFRESHNESSTEST"
BRANCH = f"task/{TASK.lower()}-x"

# SPEC с AC-разметкой (schema_version 2) — минимум, нужный `guard.
# requires_ac_markup`, чтобы `_materialize_and_run_plank` не считала
# отсутствие планки легитимным вырожденным случаем в `Pulled`-сценариях
# (тот же шаблон, что `tests/test_pull.py::SPEC_WITH_AC_MARKUP`).
SPEC_WITH_AC_MARKUP = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка (фикстура приёмочных тестов 01M2ARQMTYRNPR5HRXAPCBAXNY)

## Критерии приёмки

AC-1. Фикстура.
"""


class PullFreshnessSandbox(RealGitSandbox):

    TASK = TASK
    BRANCH = BRANCH

    def setUp(self):
        super().setUp()

        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        store.insert_task(store.db(), self.TASK,
                          "Гейт свежести — документные коммиты main",
                          "in_dev", self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.wt = None

    # ------------------------------------------------------------ утилиты

    def branch_off_main(self) -> Path:
        """Заводит ветку задачи от ТЕКУЩЕЙ головы main и её worktree —
        вызывается тестом явно (не в `setUp`) в момент, нужный сценарию:
        обычно сразу, но сценарий (в) (AC-9) — уже ПОСЛЕ коммита общего
        документного файла в main, чтобы у обеих сторон было общее
        начальное содержимое для чистого 3-way merge."""
        self.git("branch", self.BRANCH)
        wt_path, error = workspace.ensure(self.TASK, self.BRANCH)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt = wt_path
        return wt_path

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def main_head(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).strip()

    def worktree_head(self) -> str:
        return gitcmd.head_sha(self.wt)

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str) -> bool:
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha],
            cwd=self.root, capture_output=True, text=True)
        return res.returncode == 0

    @staticmethod
    def write_files(base: Path, files: dict) -> None:
        for rel, content in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def add_main_commit(self, files: dict, message: str) -> str:
        """Коммит НАПРЯМУЮ на `main` (`self.root` всегда стоит на main —
        `RealGitSandbox` его не переключает) — `git add -A` в `self.root`
        обязан идти ДО `write_acceptance_plank()` (иначе `tasks/<TASK>/`
        планки, лежащей на том же диске `config.TASKS == self.root/
        "tasks"`, попала бы в дифф main и сломала бы точный список файлов,
        который проверяют AC-1/AC-2/AC-8/AC-9)."""
        self.write_files(self.root, files)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.main_head()

    def commit_on_branch(self, files: dict, message: str) -> str:
        self.write_files(self.wt, files)
        subprocess.run(["git", "add", "-A"], cwd=self.wt, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.wt,
                       check=True)
        return self.worktree_head()

    def write_acceptance_plank(self) -> None:
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(
            SPEC_WITH_AC_MARKUP.format(task=self.TASK), encoding="utf-8")
        tests_dir = tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_stub.py").write_text(
            "import unittest\n\n\nclass StubTest(unittest.TestCase):\n\n"
            "    def test_stub(self):\n        pass\n", encoding="utf-8")

    def evaluate(self, state: str = "in_dev", origin_main_sha: str | None = None):
        conn = store.db()
        t = self.task_row()
        sha = origin_main_sha if origin_main_sha is not None else self.main_head()
        return pull.evaluate(
            conn, self.TASK, t, state,
            origin_main_source=lambda name: ("origin", config.MAIN_BRANCH),
            origin_main_sha=lambda name: sha,
            read_branch_text_or_refuse=mock.Mock(return_value=None))
