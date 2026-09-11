"""Юнит-тесты orchestrator/repo_context.py (SPEC 01M1R5B33CC7E6BZK085XV3ZCX,
требование 1, AC-1).

Приёмочный тест `tasks/01M1R5B33CC7E6BZK085XV3ZCX/acceptance_tests/
test_ac1_repo_context.py` кроет `resolve()` сквозным путём (self/внешний
target/неизвестный target) на настоящем git — здесь только сами примитивы
модуля в изоляции: `path_or_none`/`git` и разбор кривого targets.yaml.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd, repo_context  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class ResolveSelfTest(TmpRootTest):

    def test_self_target_does_not_touch_targets_yaml(self):
        self.assertFalse(config.TARGETS.exists())

        ctx = repo_context.resolve(config.DEFAULT_TARGET)

        self.assertEqual(ctx.path, config.ROOT)
        self.assertEqual(ctx.remote, "origin")
        self.assertEqual(ctx.base, config.MAIN_BRANCH)


class ResolveExternalTargetTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(
            "targets:\n"
            "  sled:\n"
            "    forge: github\n"
            "    url: https://example.invalid/sled\n"
            "    base: trunk\n"
            "    token_slot: sled-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n",
            encoding="utf-8")

    def test_external_target_reads_targets_yaml(self):
        ctx = repo_context.resolve("sled")

        self.assertEqual(ctx.path, config.PROJECTS / "sled" / "workspace")
        self.assertEqual(ctx.remote, "https://example.invalid/sled")
        self.assertEqual(ctx.base, "trunk")

    def test_unknown_target_degrades_to_none(self):
        self.assertIsNone(repo_context.resolve("no-such-target"))

    def test_broken_targets_yaml_degrades_to_none(self):
        config.TARGETS.write_text("не yaml вовсе: [", encoding="utf-8")

        self.assertIsNone(repo_context.resolve("sled"))


class PathOrNoneTest(unittest.TestCase):

    def test_none_context_is_none(self):
        self.assertIsNone(repo_context.path_or_none(None))

    def test_self_context_is_none(self):
        ctx = repo_context.RepoContext(path=config.ROOT, remote="origin",
                                       base=config.MAIN_BRANCH)
        self.assertIsNone(repo_context.path_or_none(ctx))

    def test_external_context_is_its_path(self):
        path = config.PROJECTS / "sled" / "workspace"
        ctx = repo_context.RepoContext(path=path, remote="https://x", base="trunk")
        self.assertEqual(repo_context.path_or_none(ctx), path)


class GitHelperTest(unittest.TestCase):

    def test_self_context_calls_plain_git(self):
        ctx = repo_context.RepoContext(path=config.ROOT, remote="origin",
                                       base=config.MAIN_BRANCH)
        with mock.patch.object(gitcmd, "git") as git_mock, \
             mock.patch.object(gitcmd, "in_repo") as in_repo_mock:
            repo_context.git(ctx, "status")

        git_mock.assert_called_once_with("status")
        in_repo_mock.assert_not_called()

    def test_external_context_calls_in_repo(self):
        path = config.PROJECTS / "sled" / "workspace"
        ctx = repo_context.RepoContext(path=path, remote="https://x", base="trunk")
        with mock.patch.object(gitcmd, "git") as git_mock, \
             mock.patch.object(gitcmd, "in_repo") as in_repo_mock:
            repo_context.git(ctx, "status")

        in_repo_mock.assert_called_once_with(path, "status")
        git_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
