"""Общая песочница приёмочных тестов T073 (не test_*.py — не подхватывается
unittest discover напрямую, только импортом из test_ac*.py).

Два стенда:

- `DoneTaskTest` — задача, доведённая РЕАЛЬНЫМ git-мержем до `done`
  (AC-1..AC-3: уборка ветки/worktree). Тот же приём временного
  git-репозитория, что и `tasks/T045/acceptance_tests/_sandbox.py`
  `MergeGateReadyTest` / `tasks/T048/acceptance_tests/_sandbox.py`:
  worktree-механика и ceal branch-merge не проверяются моком `gitcmd.git`.
- Тесты `prune` (AC-4..AC-7) сами наследуют `tests.sandbox.TmpRootTest`
  напрямую в своих файлах — команде `prune` реальный git не нужен, ей
  нужны только файлы `.artel/logs/` и таблица `alerts`.
"""
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, ci, config, fsm, store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
TASK = "T001"


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class DoneTaskTest(unittest.TestCase):
    """Задача T001 в свежем временном git-репозитории, доведённая через
    настоящий `approve` на `merge_gate` до `done` (сценарий
    `MergeGateReadyTest` из tasks/T045, минимизированный до того, что
    нужно AC-1..AC-3 этой задачи: `run`/агент не участвуют, SPEC
    закоммичен на ветку задачи напрямую)."""

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
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Задача для проверки retention")
        self.branch = self.task_row()["branch"]
        self.worktree = self.root / ".artel" / "worktrees" / self.TASK
        self.assertTrue(self.worktree.is_dir(), "worktree не завёлся")

        (self.worktree / "tasks" / self.TASK).mkdir(parents=True, exist_ok=True)
        (self.worktree / "tasks" / self.TASK / "SPEC.md").write_text(
            "содержимое задачи, зафиксированное на ветке\n", encoding="utf-8")
        self.git("add", "-A", cwd=self.worktree)
        self.git("commit", "-q", "-m", f"{self.TASK}: SPEC", cwd=self.worktree)

        bare = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.origin = bare

        ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        ci_patcher.start()
        self.addCleanup(ci_patcher.stop)

        self.set_state_raw("merge_gate")

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    capture = staticmethod(capture)

    def task_row(self, task_id=None):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?",
            (task_id or self.TASK,)).fetchone()

    def state(self, task_id=None) -> str:
        return self.task_row(task_id)["state"]

    def set_state_raw(self, state: str, task_id=None) -> None:
        """Ставит состояние в обход переходов FSM — по образцу
        tests/test_invariants.py `set_state`."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     (state, task_id or self.TASK))
        conn.commit()

    def branch_exists(self, branch: str) -> bool:
        return self.git("rev-parse", "--verify", "--quiet",
                        f"refs/heads/{branch}", check=False).returncode == 0

    def worktree_list(self) -> str:
        return self.git("worktree", "list", "--porcelain").stdout

    def journal_rows(self, task_id=None):
        return store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (task_id or self.TASK,)).fetchall()

    def approve(self, task_id=None) -> str:
        """Двухшаговое подтверждение sha (orchestrator/fsm.py
        `confirm_fixation`/`APPROVE_NEEDS_SHA`), по образцу
        tasks/T045/acceptance_tests/_sandbox.py `MergeGateReadyTest.approve`."""
        import re
        task_id = task_id or self.TASK
        first = self.capture(fsm.cmd_approve, task_id)
        match = re.search(r"зафиксирован (\S+)", first)
        if match is None:
            return first
        second = self.capture(fsm.cmd_approve, task_id, match.group(1))
        return first + second


if __name__ == "__main__":
    unittest.main()
