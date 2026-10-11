"""Общая песочница приёмочных тестов T052 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

Разбор содержательного конфликта при `approve` из `merge_gate` (AC-3,
AC-4, часть AC-6/AC-7) — операции над НАСТОЯЩИМ git (`git merge`,
`git merge --abort`, перечень конфликтующих файлов, чистота main): их
нечем проверить заглушкой `subprocess.run`, тем же доводом, что и
`tasks/T051/acceptance_tests/_sandbox.py` (сверка свежести до гейта,
предыдущий шаг той же цепочки §4 п.2а) и
`tasks/T045/acceptance_tests/_sandbox.py::MergeGateReadyTest` (worktree +
реальный `merge_gate`, на которых стоит эта песочница).

Тесты не переоткрывают конкретную функцию разбора конфликта (её ещё
нет — эту задачу впервые пишет developer после test_author) — только
наблюдаемое поведение публичной точки входа `fsm.cmd_approve`, которая
уже существует и не должна менять сигнатуру.
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
SPEC_STUB = "# SPEC: заглушка песочницы T052\n"

# Пять защищённых путей из conventions-core (CLAUDE.md / скил
# conventions-core) — ровно тот список, что называет SPEC T052,
# требование 2, второй абзац / AC-4.
PROTECTED_PATHS = ("gates.yaml", "roles.yaml", ".github/", "templates/",
                  "skills/")


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class MergeGateRealGitTest(unittest.TestCase):
    """Задача T001 на гейте `merge_gate` в свежем временном git-репозитории:
    настоящая ветка main с upstream (локальный bare-remote — `git pull
    --ff-only` в последовательности merge иначе отказал бы за отсутствием
    remote) и настоящий worktree ветки задачи, готовый к содержательному
    конфликту при заливке в main.
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
        (self.root / "gates.yaml").write_text("base: true\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        # Upstream — bare-remote без сети (тот же приём, что
        # tasks/T045/acceptance_tests/_sandbox.py::MergeGateReadyTest):
        # `git pull --ff-only` внутри merge-последовательности approve
        # нуждается в настоящем origin/main, иначе падает до самого
        # merge и до предмета этих тестов не доходит.
        bare = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

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
        self.branch = f"task/{self.TASK.lower()}-vozvrat"
        store.insert_task(store.db(), self.TASK, "Возврат из merge_gate",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        # CI ветки — зелёный (подменён): предмет этих тестов — разбор
        # исхода merge, не сам гейт CI (тот уже проверен
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

    def set_state(self, state: str, **fields) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        for column, value in fields.items():
            conn.execute(f"UPDATE tasks SET {column}=? WHERE id=?",
                         (value, self.TASK))
        conn.commit()

    def make_worktree(self) -> Path:
        path = self.root / ".artel" / "worktrees" / self.TASK
        path.parent.mkdir(parents=True, exist_ok=True)
        self.git("worktree", "add", "-q", "-b", self.branch, str(path))
        tdir = path / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(SPEC_STUB, encoding="utf-8")
        return path

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

    def journal_details(self) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def approve(self) -> str:
        """Двухшаговое подтверждение sha (orchestrator/fsm.py
        `confirm_fixation`/`APPROVE_NEEDS_SHA`), тем же приёмом, что
        `tasks/T045/acceptance_tests/_sandbox.py::MergeGateReadyTest.approve`."""
        first = self.capture(fsm.cmd_approve, self.TASK)
        match = re.search(r"зафиксирован (\S+)", first)
        if match is None:
            return first
        second = self.capture(fsm.cmd_approve, self.TASK, match.group(1))
        return first + second

    def make_conflicting_branch(self, path: str, branch_content: str,
                                main_content: str) -> tuple[str, str]:
        """Готовит гарантированный конфликт по файлу `path`: ветка задачи
        и main правят одну и ту же строку по-разному. Возвращает
        (sha головы ветки, sha головы main) до самого approve."""
        wt = self.make_worktree()
        (wt / path).write_text(branch_content, encoding="utf-8")
        branch_sha = self.commit_all(
            wt, f"{self.TASK}: правка {path} в ветке задачи")

        (self.root / path).write_text(main_content, encoding="utf-8")
        main_sha = self.commit_all(self.root, f"правка {path} в main")

        self.set_state("merge_gate")
        return branch_sha, main_sha
