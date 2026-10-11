"""Общая песочница приёмочных тестов T053 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py) для критериев,
которым нужен НАСТОЯЩИЙ git (AC-3, AC-4): сверка свежести ВНУТРИ окна
`merge_gate` (T051-механика, требование 5 SPEC T053) и сам merge — те же
операции над git (`git merge`, счёт коммитов между ветками, настоящий push
в bare-remote), что и `tasks/T051/acceptance_tests/_sandbox.py` и
`tasks/T052/acceptance_tests/_sandbox.py` (предыдущие шаги той же цепочки
§4 п.2а, откуда и позаимствован приём песочницы) — заглушкой `gitcmd.git`
их не проверить.

Тесты не переоткрывают конкретную функцию сверки свежести внутри окна (её
ещё нет — эту задачу впервые пишет developer после test_author) — только
наблюдаемое поведение публичной точки входа `fsm.cmd_approve`, которая уже
существует и не должна менять сигнатуру.
"""
import io
import re
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

# Минимальный SPEC.md на ветке задачи — только для того, чтобы
# `tasks/<id>` на ветке существовал и был закоммичен (чистота, которую
# сверяет `fixation._fix_dogfood`); содержимое гейтом фиксации не читается.
SPEC_STUB = "# SPEC: заглушка песочницы T053\n"

# Приёмочный тест, который всегда проходит — маркер того, что прогон
# приёмочных тестов задачи внутри окна merge_gate состоялся и был зелёным
# (SPEC T053 требование 5 — тот же прогон, что T051 уже вводила для входа
# на гейт).
PASSING_ACCEPTANCE_TEST = '''"""Маркер: заведомо зелёный приёмочный тест песочницы T053."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class MergeQueueRealGitTest(unittest.TestCase):
    """Задача T001 в состоянии `acceptance` в свежем временном
    git-репозитории: настоящая ветка main с upstream (локальный
    bare-remote — `git pull --ff-only`/`git push` внутри последовательности
    merge иначе отказали бы за отсутствием remote) и настоящий worktree
    ветки задачи, готовый пройти `acceptance -> merge_gate -> done`.
    """

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

        # Upstream — bare-remote без сети (тот же приём, что
        # tasks/T045/acceptance_tests/_sandbox.py::MergeGateReadyTest /
        # tasks/T052/acceptance_tests/_sandbox.py::MergeGateRealGitTest).
        bare = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.origin = bare

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.branch = f"task/{self.TASK.lower()}-merge-queue"
        store.insert_task(store.db(), self.TASK, "Merge queue строго по одному",
                          "acceptance", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        # CI ветки — зелёный (подменён): предмет AC-3/AC-4 — разбор
        # свежести и исхода merge, не сам гейт CI (тот уже проверен
        # MergeNeedsGreenCiTest в tests/test_invariants.py).
        ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        ci_patcher.start()
        self.addCleanup(ci_patcher.stop)

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

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def make_worktree(self) -> Path:
        path = self.root / ".artel" / "worktrees" / self.TASK
        path.parent.mkdir(parents=True, exist_ok=True)
        self.git("worktree", "add", "-q", "-b", self.branch, str(path))
        tdir = path / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(SPEC_STUB, encoding="utf-8")
        return path

    def write_acceptance_test(self, wt_path: Path, content: str) -> None:
        acc_dir = wt_path / "tasks" / self.TASK / "acceptance_tests"
        acc_dir.mkdir(parents=True, exist_ok=True)
        (acc_dir / "test_marker.py").write_text(content, encoding="utf-8")

    def commit_all(self, path: Path, message: str) -> str:
        self.git("add", "-A", cwd=path)
        self.git("commit", "-q", "-m", message, cwd=path)
        return self.head(path)

    def head(self, path=None) -> str:
        return self.git("rev-parse", "HEAD", cwd=path).stdout.strip()

    def main_head(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).stdout.strip()

    def branch_head(self) -> str:
        return self.git("rev-parse", f"refs/heads/{self.branch}").stdout.strip()

    def origin_main_sha(self) -> str:
        return self.git("rev-parse", f"refs/heads/{config.MAIN_BRANCH}",
                        cwd=self.origin).stdout.strip()

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str,
                    cwd=None) -> bool:
        res = self.git("merge-base", "--is-ancestor", ancestor_sha,
                       descendant_sha, cwd=cwd, check=False)
        return res.returncode == 0

    def add_main_commit(self, name: str = "main-progress.txt",
                        content: str = "прогресс main\n") -> str:
        (self.root / name).write_text(content, encoding="utf-8")
        return self.commit_all(self.root, "прогресс main")

    def approve(self) -> str:
        """Двухшаговое подтверждение sha (`orchestrator/fsm.py`
        `confirm_fixation`/`APPROVE_NEEDS_SHA`), тем же приёмом, что
        `tasks/T045/acceptance_tests/_sandbox.py::MergeGateReadyTest.approve` /
        `tasks/T052/acceptance_tests/_sandbox.py::MergeGateRealGitTest.approve`.
        Каждый вызов независим (заново раскрывает актуальный sha) —
        корректно работает и когда предыдущий approve сдвинул head ветки
        подтяжкой main (AC-3), не только когда head не менялся (AC-4)."""
        first = self.capture(fsm.cmd_approve, self.TASK)
        match = re.search(r"зафиксирован (\S+)", first)
        if match is None:
            return first
        second = self.capture(fsm.cmd_approve, self.TASK, match.group(1))
        return first + second
