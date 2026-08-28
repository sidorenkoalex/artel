"""Юнит-тесты ветко-корректных примитивов `orchestrator/gitcmd.py`
(SPEC T031): `show`, `ls_tree_files`, `branch_head_sha`, `on_foreign_branch`
— источник истины для чтения артефактов задачи, когда рабочее дерево
пульта стоит не на её ветке (класс-дефект tasks/T030, журнал ~17:35
25.08.2026). Плюс `store.task_branch` — та же деградация, что у
`task_target`, на которую эти примитивы опираются.

Реальный git (не заглушка): сам предмет проверки — поведение относительно
текущего чекаута, заглушкой это не изобразить (тот же приём, что
`RealPultGitTest` в tests/test_git_fixation.py).

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002): `OnForeignBranchTest` кодирует инвариант
28 реестра (docs/invariants.md) — его отключение или ослабление допустимо
только Оператором отдельным ADR.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd, store  # noqa: E402
from tests.sandbox import ALL_CONFIG_ATTRS, TmpRootTest  # noqa: E402


class RealGitSandbox(TmpRootTest):
    """`self.root` — свежий git-репозиторий с веткой main и одним коммитом."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        (self.root / "marker.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        for attr in ALL_CONFIG_ATTRS:
            patcher = mock.patch.object(config, attr, self._patched_path(attr))
            patcher.start()
            self.addCleanup(patcher.stop)

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def checkout(self, branch: str, create: bool = False) -> None:
        args = ["checkout", "-q"]
        if create:
            args.append("-b")
        args.append(branch)
        self.git(*args)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def write_and_commit(self, name: str, content: str,
                         message: str = "правка") -> None:
        (self.root / name).write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


class ShowTest(RealGitSandbox):

    def test_reads_file_from_a_branch_regardless_of_checkout(self):
        self.checkout("feature", create=True)
        self.write_and_commit("only-on-feature.txt", "маркер\n")
        self.checkout(config.MAIN_BRANCH)

        text, reason = gitcmd.show("feature", "only-on-feature.txt")

        self.assertEqual(text, "маркер\n")
        self.assertEqual(reason, "")

    def test_missing_file_in_an_existing_branch_is_none_with_a_reason(self):
        self.checkout("feature", create=True)

        text, reason = gitcmd.show("feature", "does-not-exist.txt")

        self.assertIsNone(text)
        self.assertTrue(reason)

    def test_missing_branch_is_none_with_a_reason(self):
        text, reason = gitcmd.show("no-such-branch", "marker.txt")

        self.assertIsNone(text)
        self.assertTrue(reason)


class LsTreeFilesTest(RealGitSandbox):

    def test_lists_files_under_a_directory_in_the_branch(self):
        self.checkout("feature", create=True)
        (self.root / "dir").mkdir()
        (self.root / "dir" / "a.py").write_text("a", encoding="utf-8")
        (self.root / "dir" / "b.py").write_text("b", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "dir")

        paths = gitcmd.ls_tree_files("feature", "dir")

        self.assertEqual(sorted(paths), ["dir/a.py", "dir/b.py"])

    def test_missing_directory_in_an_existing_branch_is_an_empty_list(self):
        self.checkout("feature", create=True)

        paths = gitcmd.ls_tree_files("feature", "no-such-dir")

        self.assertEqual(paths, [])

    def test_missing_branch_is_none(self):
        self.assertIsNone(gitcmd.ls_tree_files("no-such-branch", "dir"))


class BranchHeadShaTest(RealGitSandbox):

    def test_returns_the_branch_tip_independent_of_checkout(self):
        self.checkout("feature", create=True)
        self.write_and_commit("f.txt", "правка\n")
        feature_head = self.head()
        self.checkout(config.MAIN_BRANCH)

        self.assertNotEqual(feature_head, self.head(),
                            "проверка бессмысленна на общем коммите")
        self.assertEqual(gitcmd.branch_head_sha("feature"), feature_head)

    def test_missing_branch_is_empty(self):
        self.assertEqual(gitcmd.branch_head_sha("no-such-branch"), "")


class OnForeignBranchTest(RealGitSandbox):

    def test_own_branch_checked_out_is_not_foreign(self):
        self.checkout("feature", create=True)

        self.assertFalse(gitcmd.on_foreign_branch("feature"))

    def test_other_existing_branch_checked_out_is_foreign(self):
        self.checkout("feature", create=True)
        self.checkout(config.MAIN_BRANCH)

        self.assertTrue(gitcmd.on_foreign_branch("feature"))

    def test_branch_not_yet_created_is_not_foreign(self):
        """Ролью ещё не сделан `git checkout -b` — легитимный ранний
        момент жизни задачи (ADR-0003 3д); прежнее поведение (рабочая
        копия) остаётся в силе, не именованный отказ."""
        self.assertFalse(gitcmd.on_foreign_branch("task/t999-ещё-не-заведена"))

    def test_empty_branch_name_is_not_foreign(self):
        self.assertFalse(gitcmd.on_foreign_branch(""))


class CommitsBehindTest(RealGitSandbox):
    """SPEC T051, требование 2: число коммитов base, которых нет в branch."""

    def test_branch_with_everything_from_main_is_zero_behind(self):
        self.checkout("feature", create=True)

        self.assertEqual(gitcmd.commits_behind("feature"), 0)

    def test_counts_commits_on_main_absent_from_the_branch(self):
        self.checkout("feature", create=True)
        self.checkout(config.MAIN_BRANCH)
        self.write_and_commit("a.txt", "1\n")
        self.write_and_commit("b.txt", "2\n")

        self.assertEqual(gitcmd.commits_behind("feature"), 2)

    def test_missing_branch_is_none(self):
        self.assertIsNone(gitcmd.commits_behind("no-such-branch"))

    def test_custom_base_overrides_main_branch(self):
        self.checkout("feature", create=True)
        self.checkout(config.MAIN_BRANCH)
        self.checkout("other", create=True)
        self.write_and_commit("x.txt", "x\n")

        self.assertEqual(gitcmd.commits_behind("feature", base="other"), 1)
        self.assertEqual(gitcmd.commits_behind("feature"), 0,
                         "без base сверка идёт с MAIN_BRANCH, не с 'other'")

    def test_unresponsive_git_is_none(self):
        with mock.patch.object(gitcmd, "git", lambda *a: None):
            self.assertIsNone(gitcmd.commits_behind("feature"))


class TaskBranchTest(TmpRootTest):
    """`store.task_branch` — та же деградация, что `store.task_target`."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.create_schema(self.conn)

    def test_existing_task_returns_its_branch(self):
        store.insert_task(self.conn, "T001", "Задача", "spec_writing",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

        self.assertEqual(store.task_branch(self.conn, "T001"),
                         "task/t001-zadacha")

    def test_missing_task_is_an_empty_string(self):
        self.assertEqual(store.task_branch(self.conn, "T999"), "")


if __name__ == "__main__":
    unittest.main()
