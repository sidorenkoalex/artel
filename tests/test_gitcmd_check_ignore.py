"""Юнит-тесты `gitcmd.check_ignore`/`gitcmd.diff_names` (SPEC
01M1KVG3KSCY47HWXWF5HM0E76, требования 1 и 3): критерий «игнорируется»
обязан быть настоящим разбором `.gitignore` пульта (`git check-ignore`),
не самодельным списком расширений — единственный способ поймать
директорное правило (`dropme/`), которое списком суффиксов не выразить.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

GITIGNORE_TEXT = "__pycache__/\n*.pyc\n*.log\ndropme/\n.artel/\n"


class CheckIgnoreTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        (self.root / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "gitignore")

    def test_empty_paths_is_empty_without_a_git_call(self):
        self.assertEqual(gitcmd.check_ignore([]), set())

    def test_extension_rule_matches(self):
        ignored = gitcmd.check_ignore(["tasks/X/acceptance_tests/"
                                       "__pycache__/test_ac.cpython-311.pyc"])
        self.assertEqual(
            ignored,
            {"tasks/X/acceptance_tests/__pycache__/test_ac.cpython-311.pyc"})

    def test_directory_rule_not_expressible_as_an_extension_list_matches(self):
        # `dropme/` — директорное правило; список суффиксов в коде такой
        # путь никогда не поймает (единственный способ — настоящий парсинг
        # .gitignore, ровно то, что здесь проверяется).
        ignored = gitcmd.check_ignore(["tasks/X/dropme/notes.txt"])
        self.assertEqual(ignored, {"tasks/X/dropme/notes.txt"})

    def test_path_need_not_exist_on_disk(self):
        # `checkpoint`/`fsm_advance` зовут `check_ignore` над путями
        # внешнего target, которых на диске `config.ROOT` нет вовсе —
        # директорное правило обязано матчиться по строке пути, не по
        # факту существования каталога/файла.
        self.assertFalse((self.root / "tasks").exists())
        ignored = gitcmd.check_ignore(["tasks/X/dropme/nested/deep.txt"])
        self.assertEqual(ignored, {"tasks/X/dropme/nested/deep.txt"})

    def test_non_ignored_path_is_not_in_the_result(self):
        ignored = gitcmd.check_ignore(["tasks/X/PLAN.md"])
        self.assertEqual(ignored, set())

    def test_mixed_batch_returns_only_the_ignored_subset(self):
        paths = ["tasks/X/PLAN.md",
                 "tasks/X/acceptance_tests/__pycache__/x.pyc",
                 "tasks/X/dropme/notes.txt",
                 "tasks/X/SPEC.md"]
        ignored = gitcmd.check_ignore(paths)
        self.assertEqual(
            ignored,
            {"tasks/X/acceptance_tests/__pycache__/x.pyc",
             "tasks/X/dropme/notes.txt"})

    def test_unresponsive_git_is_none(self):
        with mock.patch.object(gitcmd.subprocess, "run",
                               side_effect=OSError("git не найден")):
            self.assertIsNone(gitcmd.check_ignore(["tasks/X/PLAN.md"]))


class DiffNamesTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        (self.root / "a.txt").write_text("1\n", encoding="utf-8")
        (self.root / "b.txt").write_text("1\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "before")
        self.before = gitcmd.head_sha()
        (self.root / "a.txt").write_text("2\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "after")
        self.after = gitcmd.head_sha()

    def test_lists_changed_paths(self):
        self.assertEqual(gitcmd.diff_names(self.before, self.after),
                         ["a.txt"])

    def test_no_changes_is_an_empty_list(self):
        self.assertEqual(gitcmd.diff_names(self.before, self.before), [])

    def test_unreachable_sha_is_none(self):
        self.assertIsNone(gitcmd.diff_names("d" * 40, self.after))

    def test_pathspec_narrows_the_comparison(self):
        self.assertEqual(gitcmd.diff_names(self.before, self.after, "b.txt"), [])


if __name__ == "__main__":
    unittest.main()
