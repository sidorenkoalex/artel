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
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox, TmpRootTest  # noqa: E402


class _GitcmdRealGitSandbox(RealGitSandbox):
    """Надстройка над общей `sandbox.RealGitSandbox`, нужная только этому
    файлу: чтение головы ветки и добавление коммита без переключения на
    ветку задачи (тесты `on_foreign_branch`/`show`/`ls_tree_files` читают
    ветки, не переключая на них рабочее дерево)."""

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def write_and_commit(self, name: str, content: str,
                         message: str = "правка") -> None:
        (self.root / name).write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


class ShowTest(_GitcmdRealGitSandbox):

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


class LsTreeFilesTest(_GitcmdRealGitSandbox):

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


class BranchHeadShaTest(_GitcmdRealGitSandbox):

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


class OnForeignBranchTest(_GitcmdRealGitSandbox):

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


class CommitsBehindTest(_GitcmdRealGitSandbox):
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


class IsAncestorTest(_GitcmdRealGitSandbox):
    """`gitcmd.is_ancestor` (tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md,
    ANSWER-1 п.3) — критерий, которым guard AC-1/AC-3/AC-4 отбрасывает
    зелёные прогоны канарейки с чужой, несвязанной историей."""

    def test_ancestor_commit_is_true(self):
        base = self.head()
        self.write_and_commit("a.txt", "1\n")

        self.assertTrue(gitcmd.is_ancestor(base, self.head()))

    def test_same_commit_is_true(self):
        self.assertTrue(gitcmd.is_ancestor(self.head(), self.head()))

    def test_descendant_as_ancestor_is_false(self):
        base = self.head()
        self.write_and_commit("a.txt", "1\n")

        self.assertFalse(gitcmd.is_ancestor(self.head(), base))

    def test_commit_on_an_unrelated_branch_is_false(self):
        self.checkout("abandoned", create=True)
        self.write_and_commit("x.txt", "x\n")
        abandoned = self.head()
        self.checkout(config.MAIN_BRANCH)

        self.assertFalse(gitcmd.is_ancestor(abandoned, self.head()))

    def test_nonexistent_sha_is_false(self):
        self.assertFalse(gitcmd.is_ancestor("0" * 40, self.head()))


class MergesBetweenTest(_GitcmdRealGitSandbox):
    """`gitcmd.merges_between` — «возраст» зелёного прогона канарейки в
    мержах main (ANSWER-1 01M1NGFK3N6MRMYGCC09H975V3 п.3): считает
    только merge-коммиты диапазона, не любые."""

    def test_counts_only_merge_commits_on_the_range(self):
        base = self.head()
        self.checkout("feature", create=True)
        self.write_and_commit("f.txt", "1\n")
        self.checkout(config.MAIN_BRANCH)
        self.git("merge", "--no-ff", "-q", "-m", "merge feature", "feature")
        self.write_and_commit("plain.txt", "2\n")  # обычный коммит — не merge

        self.assertEqual(gitcmd.merges_between(base, self.head()), 1)

    def test_zero_when_no_merges_on_the_range(self):
        base = self.head()
        self.write_and_commit("a.txt", "1\n")

        self.assertEqual(gitcmd.merges_between(base, self.head()), 0)

    def test_unresponsive_git_is_none(self):
        with mock.patch.object(gitcmd, "git", lambda *a: None):
            self.assertIsNone(gitcmd.merges_between("a", "b"))


class RemoteBranchShaTest(_GitcmdRealGitSandbox):
    """`gitcmd.remote_branch_sha` (SPEC 01M1GS5HZ1JXFGKVR95HEW0AEZ, AC-2):
    sha ветки в origin по точному `refs/heads/<branch>`, не по факту
    присутствия имени ветки в origin — настоящий bare-remote, заглушкой
    `gitcmd.git` расхождение конкретных sha не изобразить (тот же довод,
    что у `_sandbox.HeadInOriginSandbox` в приёмочных тестах этой задачи).
    """

    def setUp(self):
        super().setUp()
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", bare)
        self.git("remote", "add", "origin", bare)

    def test_branch_never_pushed_is_empty(self):
        self.checkout("feature", create=True)

        self.assertEqual(gitcmd.remote_branch_sha("feature"), "")

    def test_matches_the_pushed_head(self):
        self.checkout("feature", create=True)
        self.write_and_commit("f.txt", "правка\n")
        feature_head = self.head()
        self.git("push", "-q", "-u", "origin", "feature")

        self.assertEqual(gitcmd.remote_branch_sha("feature"), feature_head)

    def test_stale_origin_does_not_match_the_new_local_head(self):
        """Origin знает ветку, но на старом коммите — сверка обязана
        отличить это от «уже актуально», не только от «ветки там нет»."""
        self.checkout("feature", create=True)
        self.write_and_commit("f.txt", "1\n")
        self.git("push", "-q", "-u", "origin", "feature")
        stale = gitcmd.remote_branch_sha("feature")
        self.write_and_commit("f.txt", "2\n")

        self.assertEqual(gitcmd.remote_branch_sha("feature"), stale)
        self.assertNotEqual(gitcmd.remote_branch_sha("feature"), self.head())

    def test_no_origin_remote_configured_is_empty(self):
        self.git("remote", "remove", "origin")
        self.checkout("feature", create=True)

        self.assertEqual(gitcmd.remote_branch_sha("feature"), "")

    def test_unresponsive_git_is_empty(self):
        with mock.patch.object(gitcmd, "git", lambda *a: None):
            self.assertEqual(gitcmd.remote_branch_sha("feature"), "")


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
