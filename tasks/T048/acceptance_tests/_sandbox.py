"""Общая песочница приёмочных тестов T048 (не test_*.py — не подхватывается
unittest discover напрямую, только импортом из test_ac*.py).

`cmd_new` по SPEC T048 обязан заводить ветку и worktree задачи реальным
git (`git branch`/`git worktree add`/`git commit`), а не писать файлы
untracked в рабочую копию main — подменять эти операции заглушками
нечем проверять требования 1-4 SPEC. Тот же приём реального временного
git-репозитория, что и `tasks/T045/acceptance_tests/_sandbox.py`.

`roles.yaml` НЕ копируется — `config.ROLES` вычисляется при импорте
модуля от исходного `config.ROOT` и патчем `config.ROOT` не задевается,
так что читается настоящий файл пульта (см. тот же комментарий в T045).
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

from orchestrator import artel, catalog, config, runner, store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки."""

    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.lines)

    def close(self):
        pass


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines=("готово\n",), returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class TmpGitTaskTest(unittest.TestCase):
    """Свежий временный git-репозиторий с веткой main; `cmd_init` уже
    прогнан, задачи в тестах заводит сам `cmd_new` новым флоу (SPEC T048).
    """

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

        # Файл ТЗ — вне репозитория: `--tz <файл>` принимает произвольный
        # путь на диске, не обязан жить в рабочей копии.
        tz_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tz_dir, ignore_errors=True)
        self.tz_dir = Path(tz_dir)

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

    def cli_new(self, title: str, tz_path=None) -> str:
        argv = ["artel.py", "new", title]
        if tz_path is not None:
            argv = argv + ["--tz", str(tz_path)]
        with mock.patch.object(sys, "argv", argv):
            return self.capture(artel.main)

    def write_tz_file(self, text: str, name: str = "tz.txt") -> Path:
        path = self.tz_dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def task_row(self, task_id: str):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

    def last_task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT 1").fetchone()

    def main_head_sha(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).stdout.strip()

    def branch_exists(self, branch: str) -> bool:
        return self.git("rev-parse", "--verify", "--quiet",
                        f"refs/heads/{branch}", check=False).returncode == 0

    def commit_message(self, branch: str, n: int = 1) -> str:
        return self.git("log", f"-{n}", "--format=%s", branch).stdout.strip()

    def commits_ahead_of_main(self, branch: str) -> int:
        out = self.git("rev-list", "--count",
                       f"{config.MAIN_BRANCH}..{branch}").stdout.strip()
        return int(out)

    def tree_files(self, branch: str, rel_dir: str) -> list:
        res = self.git("ls-tree", "-r", "--name-only", branch, "--", rel_dir)
        return [p for p in res.stdout.splitlines() if p]

    def worktree_path(self, task_id: str) -> Path:
        return self.root / ".artel" / "worktrees" / task_id


class AnalystRunTaskTest(TmpGitTaskTest):
    """Расширяет базовую песочницу тем, что нужно для реального прогона
    роли (по образцу `tasks/T045/acceptance_tests/_sandbox.py`
    `WorktreeRepoTest`): skills/, docs/codebase-map.md — читаются с
    (патченного) `config.ROOT` реальным кодом промпта/брифа; keychain и
    pre-flight подменены, чтобы прогон не требовал настоящего окружения.
    """

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / "docs" / "codebase-map.md",
                   self.root / "docs" / "codebase-map.md")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "skills+map")

        for attr, value in (
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def run_agent(self, task_id: str):
        """Прогон `run <id>` с подменённым процессом агента; возвращает
        мок `Popen` (для разбора `call_args`) и захваченный stdout."""
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc()
            out = self.capture(runner.cmd_run, task_id)
        return popen, out
