"""Тесты уборки хвостов убитой задачи (см. tasks/T008/SPEC.md).

Git тут настоящий, но не рабочий: ROOT уводится во временный репозиторий
с копией templates/ и .gitignore, задачи в нём создаёт сам оркестратор.
Так проверяются реальные ответы git (`ls-tree`, `branch --merged`), а
рабочее дерево репозитория остаётся нетронутым.
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class TmpRepoTest(unittest.TestCase):
    """Задача T001 в свежем временном репозитории с веткой main."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var, а `git
        # rev-parse` и Path сравниваются как строки.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-b", artel.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-m", "init")

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs")):
            patcher = mock.patch.object(artel, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(artel.cmd_init)
        self.capture(artel.cmd_new, "Очистка хвостов задачи")
        self.branch = self.task_row()["branch"]

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res.stdout

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def task_row(self):
        return artel.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def task_dir(self) -> Path:
        return artel.TASKS / self.TASK

    def cleanup_note(self) -> str:
        """Последняя запись журнала об уборке."""
        rows = artel.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action='уборка'"
            " ORDER BY id", (self.TASK,)).fetchall()
        self.assertTrue(rows, "уборка не попала в журнал")
        return rows[-1]["detail"]

    def commit_artifacts_in_branch(self) -> None:
        """Разработчик закоммитил артефакты в ветку задачи и ушёл на main."""
        self.git("checkout", "-b", self.branch)
        self.git("add", "-A")
        self.git("commit", "-m", f"{self.TASK}: SPEC")
        self.git("checkout", artel.MAIN_BRANCH)

    def branches(self) -> list[str]:
        return self.git("branch", "--format=%(refname:short)").split()


class KillCleanupTest(TmpRepoTest):
    """`kill <id>` убирает каталог задачи и её локальную ветку."""

    def test_task_killed_before_commit_leaves_no_trace(self):
        """Критерий приёмки 1: сценарий T002 — new, kill, чистое дерево."""
        self.assertTrue(self.task_dir().exists(), "new создал каталог задачи")

        self.capture(artel.cmd_kill, self.TASK)

        self.assertFalse(self.task_dir().exists())
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.task_row()["state"], "killed")

    def test_branch_only_artifacts_and_branch_are_removed(self):
        self.commit_artifacts_in_branch()
        # Черновик, написанный агентом после коммита: не отслеживается, и
        # каталог задачи переживает переключение на main вместе с ним.
        self.task_dir().mkdir(parents=True, exist_ok=True)
        (self.task_dir() / "PLAN.md").write_text("черновик", encoding="utf-8")

        self.capture(artel.cmd_kill, self.TASK)

        self.assertFalse(self.task_dir().exists())
        self.assertNotIn(self.branch, self.branches())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_merged_task_keeps_artifacts_and_branch(self):
        """Критерий приёмки 2: артефакты в main — не трогаем ничего."""
        self.commit_artifacts_in_branch()
        self.git("merge", "--no-ff", self.branch, "-m", "merge")

        out = self.capture(artel.cmd_kill, self.TASK)

        self.assertTrue((self.task_dir() / "SPEC.md").exists())
        self.assertIn(self.branch, self.branches())
        self.assertIn("артефакты в main", out)
        self.assertIn(f"ветка {self.branch} оставлена: смержена в main", out)

    def test_unmerged_branch_is_removed_even_when_artifacts_are_in_main(self):
        """Условия требования 1 независимы: ветка ушла вперёд после мержа."""
        self.commit_artifacts_in_branch()
        self.git("merge", "--no-ff", self.branch, "-m", "merge")
        self.git("checkout", self.branch)
        (self.task_dir() / "PLAN.md").write_text("после мержа", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-m", f"{self.TASK}: PLAN")
        self.git("checkout", artel.MAIN_BRANCH)

        self.capture(artel.cmd_kill, self.TASK)

        self.assertTrue((self.task_dir() / "SPEC.md").exists(), "история в main")
        self.assertNotIn(self.branch, self.branches())

    def test_cleanup_is_listed_in_the_journal(self):
        """Требование 2: по журналу видно, что именно убрано."""
        self.commit_artifacts_in_branch()
        self.task_dir().mkdir(parents=True, exist_ok=True)
        (self.task_dir() / "SPEC.md").write_text("хвост", encoding="utf-8")

        self.capture(artel.cmd_kill, self.TASK)

        self.assertEqual(
            self.cleanup_note(),
            f"удалён каталог tasks/{self.TASK}/; удалена ветка {self.branch}")
        self.assertIn("удалён каталог", self.capture(artel.cmd_log, self.TASK))

    def test_run_logs_survive_the_kill(self):
        """Требование 4: история наблюдаемости переживает задачу."""
        log = artel.new_agent_log(self.TASK, "developer")
        log.write_text("шаг разработчика\n", encoding="utf-8")

        self.capture(artel.cmd_kill, self.TASK)

        self.assertTrue(log.exists())
        self.assertEqual(log.read_text(encoding="utf-8"), "шаг разработчика\n")

    def test_repeated_kill_finds_nothing_and_does_not_fail(self):
        """Требование 3: повтор — это пустая уборка, а не падение."""
        self.capture(artel.cmd_kill, self.TASK)

        out = self.capture(artel.cmd_kill, self.TASK)

        self.assertEqual(self.task_row()["state"], "killed")
        self.assertIn(f"каталога tasks/{self.TASK}/ нет", out)
        self.assertIn(f"локальной ветки {self.branch} нет", out)

    def test_unknown_task_is_reported(self):
        with self.assertRaises(SystemExit) as exit_:
            self.capture(artel.cmd_kill, "T404")

        self.assertIn("не найдена", str(exit_.exception))

    def test_checked_out_branch_is_left_alone_until_the_next_kill(self):
        self.commit_artifacts_in_branch()
        self.git("checkout", self.branch)

        out = self.capture(artel.cmd_kill, self.TASK)

        self.assertTrue((self.task_dir() / "SPEC.md").exists(),
                        "снести закоммиченный каталог — оставить грязное дерево")
        self.assertIn(self.branch, self.branches())
        self.assertIn("перейди на main и повтори kill", out)
        self.assertIn("checked out", self.cleanup_note())

        self.git("checkout", artel.MAIN_BRANCH)
        self.capture(artel.cmd_kill, self.TASK)

        self.assertNotIn(self.branch, self.branches(), "повтор доводит уборку")
        self.assertFalse(self.task_dir().exists())


class CleanupWithoutGitTest(TmpRepoTest):
    """git промолчал — уборка ничего не трогает и говорит об этом."""

    def test_missing_main_stops_the_cleanup(self):
        self.git("checkout", "-b", "other")
        self.git("branch", "-D", artel.MAIN_BRANCH)

        out = self.capture(artel.cmd_kill, self.TASK)

        self.assertTrue(self.task_dir().exists(), "сверять не с чем — не трогаем")
        self.assertIn("уборка пропущена: ветки main нет", out)

    def test_unavailable_git_stops_the_cleanup(self):
        with mock.patch.object(artel.subprocess, "run",
                               side_effect=OSError("git не найден")):
            out = self.capture(artel.cmd_kill, self.TASK)

        self.assertTrue(self.task_dir().exists())
        self.assertIn("git не найден", out, "в журнале видно настоящую причину")
        self.assertEqual(self.task_row()["state"], "killed",
                         "kill switch срабатывает и без git")


if __name__ == "__main__":
    unittest.main()
