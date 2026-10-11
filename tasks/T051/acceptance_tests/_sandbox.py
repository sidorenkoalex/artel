"""Общая песочница приёмочных тестов T051 (не test_*.py — не подхватывается
unittest discover напрямую, только импортом из test_ac*.py).

Сверка свежести ветки — операции над РЕАЛЬНЫМ git (merge, конфликт,
`git merge --abort`, счёт коммитов между ветками): подменять их заглушками
нечем проверить требования 1-8 SPEC. Тот же приём временного git-репозитория
и per-task worktree, что и `tasks/T048/acceptance_tests/_sandbox.py` /
`tasks/T045/acceptance_tests/_sandbox.py`.

Тесты не переоткрывают конкретную функцию проверки свежести (её ещё нет —
эту задачу впервые пишет developer после test_author) — только наблюдаемое
поведение публичных точек входа `fsm.cmd_advance`/`fsm.cmd_approve`/
`doctor.all_checks`, которые уже существуют и не должны менять сигнатуру.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (catalog, config, fsm, gitcmd, store,  # noqa: E402
                          workspace)

REPO_ROOT = Path(__file__).resolve().parents[3]

TASK = "T001"

# Минимальный PLAN.md, готовый к переходу in_dev -> review (все обязательные
# секции присутствуют, содержимое пустое — guard проверяет только форму).
PLAN_READY_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: проверка свежести

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

# Приёмочный тест, который всегда проходит — маркер того, что прогон
# приёмочных тестов задачи в свежей ветке состоялся и был зелёным.
PASSING_ACCEPTANCE_TEST = '''"""Маркер: заведомо зелёный приёмочный тест песочницы T051."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''

# Приёмочный тест, который всегда падает — маркер AC-3 (тесты красные
# после успешной подтяжки main).
FAILING_ACCEPTANCE_TEST = '''"""Маркер: заведомо красный приёмочный тест песочницы T051."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_zz_marker_ac3_deliberately_red(self):
        self.fail("MARKER-AC3-RED")
'''


def fake_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git` без обращения к реальному репозиторию (AC-6):
    тот же приём вырожденного случая, что `tests/sandbox.py::fake_git`
    (git-идентичность для коммита шага, отказ на любой `rev-parse --verify`
    — веток в песочнице нет ни одной)."""
    if (len(args) >= 3 and args[0] == "rev-parse" and args[1] == "--verify"
            and args[-1].startswith("refs/heads/")):
        return subprocess.CompletedProcess(list(args), 1, "", "")
    identity = {"user.name": "Роль Артели", "user.email": "role@artel.invalid"}
    value = identity.get(args[-1], "") if args[:2] == ("config", "--get") else ""
    return subprocess.CompletedProcess(list(args), 0, f"{value}\n", "")


class RealGitFreshnessTest(unittest.TestCase):
    """Задача T001 в свежем временном git-репозитории с веткой main;
    ветка задачи заводится тестом там, где сценарию нужна (не всякий тест
    нуждается в worktree)."""

    TASK = TASK

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "shared.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
            ("PROJECTS", self.root / ".artel" / "projects"),
            ("TARGETS", self.root / "targets.yaml"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("BACKUP_MARKER", self.root / ".artel" / "backup-marker"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.branch = f"task/{self.TASK.lower()}-svezhest"
        store.insert_task(store.db(), self.TASK, "Проверка свежести",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    @staticmethod
    def capture(fn, *args):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def task_row(self, task_id=None):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?",
            (task_id or self.TASK,)).fetchone()

    def set_state(self, state: str, task_id=None) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     (state, task_id or self.TASK))
        conn.commit()

    def journal_details(self, task_id=None) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (task_id or self.TASK,))]

    def make_worktree(self, task_id=None, branch=None) -> Path:
        wt_path, error = workspace.ensure(task_id or self.TASK,
                                          branch or self.branch)
        self.assertIsNone(error, error)
        return wt_path

    def commit_all(self, path: Path, message: str) -> str:
        self.git("add", "-A", cwd=path)
        self.git("commit", "-q", "-m", message, cwd=path)
        return self.head(path)

    def head(self, path=None) -> str:
        return self.git("rev-parse", "HEAD", cwd=path).stdout.strip()

    def main_head(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).stdout.strip()

    def branch_head(self, branch=None) -> str:
        return self.git("rev-parse",
                        f"refs/heads/{branch or self.branch}").stdout.strip()

    def parent_count(self, path=None) -> int:
        """Число родителей HEAD: 1 — обычный коммит, 2 — merge-коммит."""
        return len(self.git("log", "-1", "--pretty=%P",
                            cwd=path).stdout.split())

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str,
                    cwd=None) -> bool:
        res = self.git("merge-base", "--is-ancestor", ancestor_sha,
                       descendant_sha, cwd=cwd, check=False)
        return res.returncode == 0

    def add_main_commit(self, name: str = "main-progress.txt",
                        content: str = "прогресс main\n") -> str:
        (self.root / name).write_text(content, encoding="utf-8")
        return self.commit_all(self.root, "прогресс main")

    def write_plan_ready(self, wt_path: Path, task_id=None) -> None:
        tdir = wt_path / "tasks" / (task_id or self.TASK)
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text(
            PLAN_READY_MD.format(task=task_id or self.TASK), encoding="utf-8")

    def write_acceptance_test(self, wt_path: Path, content: str,
                              task_id=None) -> None:
        acc_dir = wt_path / "tasks" / (task_id or self.TASK) / "acceptance_tests"
        acc_dir.mkdir(parents=True, exist_ok=True)
        (acc_dir / "test_marker.py").write_text(content, encoding="utf-8")
