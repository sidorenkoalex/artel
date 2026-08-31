"""Юнит-тесты orchestrator/workspace.py: git worktree задачи в
стандартном месте (SPEC T045).

Git тут настоящий (по образцу tests/test_git_fixation.py RealPultGitTest):
сама суть модуля — операции `git worktree`, подменять их заглушками
нечем проверять. Приёмочные тесты (tasks/T045/acceptance_tests/) уже
покрывают AC-1..AC-9 сквозным путём через `artel.py`/`cmd_run`/`cmd_kill`/
`cmd_approve`; здесь — модуль в изоляции, без агентных шагов и FSM.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, gitcmd, store, workspace  # noqa: E402
from tests.sandbox import capture, resilient_tmp_cleanup  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class RealGitWorkspaceTest(unittest.TestCase):
    """Задача T001 в свежем временном git-репозитории с веткой main;
    ветка задачи ещё НЕ заведена в git (как и в реальности до T045 —
    её заводит сама worktree-норма, не роль и не `cmd_new`)."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
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
        # НЕ через `catalog.cmd_new`: с SPEC T048 он сам заводит ветку и
        # worktree (`workspace.ensure`) — это сломало бы предпосылку
        # класса «ветка ещё не заведена в git», которую тестируют модули
        # ниже. Прямая вставка строки задачи — тот же путь до `cmd_new`
        # (T025), тут он ещё пригождается для изолированного теста модуля.
        title = "Worktree-модуль"
        self.branch = f"task/{self.TASK.lower()}-{catalog.slugify(title)}"
        store.insert_task(store.db(), self.TASK, title, "spec_writing",
                          self.branch, config.DEFAULT_TARGET,
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

    capture = staticmethod(capture)

    def task_row(self, task_id=None):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?",
            (task_id or self.TASK,)).fetchone()

    def wt_path(self, task_id=None) -> Path:
        return config.WORKTREES / (task_id or self.TASK)

    def worktree_list(self) -> str:
        return self.git("worktree", "list", "--porcelain").stdout


class PathTest(RealGitWorkspaceTest):

    def test_path_is_the_standard_location(self):
        self.assertEqual(workspace.path(self.TASK),
                         config.WORKTREES / self.TASK)


class RegisteredPathsTest(RealGitWorkspaceTest):

    def test_lists_the_main_checkout(self):
        paths = workspace.registered_paths()

        self.assertEqual(paths, [str(self.root)])

    def test_includes_a_worktree_added_directly_by_git(self):
        path = self.wt_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.git("worktree", "add", "-b", self.branch, str(path))

        self.assertIn(str(path), workspace.registered_paths())

    def test_empty_when_git_does_not_answer(self):
        with mock.patch.object(gitcmd, "git", lambda *a: None):
            self.assertEqual(workspace.registered_paths(), [])


class EnsureTest(RealGitWorkspaceTest):

    def test_creates_worktree_on_a_fresh_branch_from_main(self):
        path, error = workspace.ensure(self.TASK, self.branch)

        self.assertIsNone(error)
        self.assertEqual(path, self.wt_path())
        self.assertTrue(path.is_dir())
        self.assertIn(str(path), self.worktree_list())
        branch_res = self.git("-C", str(path), "rev-parse",
                              "--abbrev-ref", "HEAD")
        self.assertEqual(branch_res.stdout.strip(), self.branch)

    def test_fresh_branch_forks_from_main_not_from_head_of_something_else(self):
        path, _error = workspace.ensure(self.TASK, self.branch)

        merge_base = self.git("merge-base", config.MAIN_BRANCH,
                              self.branch).stdout.strip()
        main_head = self.git("rev-parse", config.MAIN_BRANCH).stdout.strip()
        self.assertEqual(merge_base, main_head)
        self.assertTrue(path.is_dir())

    def test_repeated_call_is_idempotent(self):
        first, error1 = workspace.ensure(self.TASK, self.branch)

        second, error2 = workspace.ensure(self.TASK, self.branch)

        self.assertIsNone(error1)
        self.assertIsNone(error2)
        self.assertEqual(first, second)
        self.assertEqual(self.worktree_list().count(str(first)), 1,
                         "повторный ensure не должен плодить дублирующую "
                         "запись worktree")

    def test_reuses_an_already_existing_branch_without_reseeding(self):
        """Ветка уже существует (например, разработчик закоммитил
        предыдущим шагом) — worktree заводится НА неё, а не поверх main;
        перенос незакоммиченного `tasks/<id>` не нужен и не происходит,
        потому что нужное содержимое уже в самой ветке."""
        self.git("branch", self.branch, config.MAIN_BRANCH)
        (config.TASKS / self.TASK).mkdir(parents=True, exist_ok=True)
        (config.TASKS / self.TASK / "PLAN.md").write_text(
            "план в главной копии, не в ветке\n", encoding="utf-8")

        path, error = workspace.ensure(self.TASK, self.branch)

        self.assertIsNone(error)
        branch_res = self.git("-C", str(path), "rev-parse",
                              "--abbrev-ref", "HEAD")
        self.assertEqual(branch_res.stdout.strip(), self.branch)
        self.assertFalse((path / "tasks" / self.TASK / "PLAN.md").exists(),
                         "существующая ветка не переносит untracked главной "
                         "копии — там либо уже есть коммит, либо нечего")

    def test_failure_is_reported_without_raising(self):
        real_git = gitcmd.git

        def failing_git(*args: str) -> subprocess.CompletedProcess:
            if args[:2] == ("worktree", "add"):
                return subprocess.CompletedProcess(
                    list(args), 128, "", "fatal: не удалось")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", failing_git):
            path, error = workspace.ensure(self.TASK, self.branch)

        self.assertEqual(path, self.wt_path())
        self.assertIn("не удалось", error)

    def test_failure_without_a_git_response_is_reported(self):
        with mock.patch.object(gitcmd, "git", lambda *a: None):
            path, error = workspace.ensure(self.TASK, self.branch)

        self.assertEqual(path, self.wt_path())
        self.assertIn("вернул", error)


class OnTaskBranchTest(RealGitWorkspaceTest):

    def test_none_when_worktree_is_not_registered(self):
        self.assertIsNone(workspace.on_task_branch(self.TASK, self.branch))

    def test_true_when_worktree_stands_on_the_task_branch(self):
        path, _error = workspace.ensure(self.TASK, self.branch)
        self.assertTrue(path.is_dir())

        self.assertTrue(workspace.on_task_branch(self.TASK, self.branch))

    def test_false_when_worktree_was_switched_to_a_foreign_branch(self):
        path, _error = workspace.ensure(self.TASK, self.branch)
        self.git("checkout", "-b", "intruder", cwd=path)

        self.assertFalse(workspace.on_task_branch(self.TASK, self.branch))


class RemoveTest(RealGitWorkspaceTest):

    def test_removes_a_registered_worktree(self):
        path, _error = workspace.ensure(self.TASK, self.branch)
        self.assertTrue(path.is_dir())

        note = workspace.remove(self.TASK)

        self.assertFalse(path.exists())
        self.assertNotIn(str(path), self.worktree_list())
        self.assertIn(str(path), note)

    def test_reports_nothing_to_remove_when_not_registered(self):
        note = workspace.remove(self.TASK)

        self.assertIn("не найден", note)
        self.assertIn(str(self.wt_path()), note)

    def test_repeated_remove_is_not_an_error(self):
        workspace.ensure(self.TASK, self.branch)
        workspace.remove(self.TASK)

        note = workspace.remove(self.TASK)

        self.assertIn("не найден", note)

    def test_failure_with_empty_stderr_still_reports_a_reason(self):
        """Review T045 итерация 1 замечание 2: `git worktree remove`
        отказал (returncode != 0), но ничего не написал в stderr — как
        `ensure()` на тот же вырожденный случай, отчёт не пустая строка."""
        workspace.ensure(self.TASK, self.branch)
        real_git = gitcmd.git

        def failing_git(*args: str) -> subprocess.CompletedProcess:
            if args[:2] == ("worktree", "remove"):
                return subprocess.CompletedProcess(list(args), 1, "", "")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", failing_git):
            note = workspace.remove(self.TASK)

        self.assertIn("не убран", note)
        self.assertIn("вернул", note)


class CmdWorkspaceTest(RealGitWorkspaceTest):

    def test_prints_the_worktree_path(self):
        out = self.capture(workspace.cmd_workspace, self.TASK)

        expected = self.wt_path()
        self.assertIn(str(expected), out)
        self.assertTrue(expected.is_dir())

    def test_repeated_call_returns_the_same_path(self):
        first = self.capture(workspace.cmd_workspace, self.TASK)

        second = self.capture(workspace.cmd_workspace, self.TASK)

        expected = self.wt_path()
        self.assertIn(str(expected), first)
        self.assertIn(str(expected), second)
        self.assertEqual(self.worktree_list().count(str(expected)), 1)

    def test_exits_with_a_reason_when_worktree_add_fails(self):
        real_git = gitcmd.git

        def failing_git(*args: str) -> subprocess.CompletedProcess:
            if args[:2] == ("worktree", "add"):
                return subprocess.CompletedProcess(
                    list(args), 128, "", "fatal: не удалось")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", failing_git):
            with self.assertRaises(SystemExit) as ctx:
                self.capture(workspace.cmd_workspace, self.TASK)

        self.assertIn("не удалось", str(ctx.exception))


class CmdWorkspaceLeaseTest(RealGitWorkspaceTest):
    """SPEC T044 требование 2, review T045 итерация 1 замечание 1:
    `workspace <id>` — мутирующая команда задачи как и остальные, берёт
    lease перед `git worktree add` (по образцу
    `tests.test_auto_cycle.AutoLeaseTest`)."""

    def test_foreign_fresh_lease_refuses_without_creating_a_worktree(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, "holder-host", store.now()))
        conn.commit()

        with self.assertRaises(SystemExit) as ctx:
            self.capture(workspace.cmd_workspace, self.TASK, "sess-caller")

        self.assertIn("sess-holder", str(ctx.exception))
        self.assertIn("holder-host", str(ctx.exception))
        self.assertNotIn(str(self.wt_path()), self.worktree_list())

    def test_own_fresh_lease_is_released_after_the_call(self):
        self.capture(workspace.cmd_workspace, self.TASK, "sess-a")

        self.assertIsNone(store.lease_row(store.db(), self.TASK),
                          "cmd_workspace не отпустила взятый ею с нуля lease")


if __name__ == "__main__":
    unittest.main()
