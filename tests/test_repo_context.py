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
        """Ловит мутацию: `resolve()` читает targets.yaml ДО (или вместо)
        проверки `target_name == DEFAULT_TARGET` — упадёт на
        несуществующем файле (`self.assertFalse` в начале доказывает, что
        файла нет вовсе), либо вернёт не тот `path`/`remote`/`base`."""
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
            "    url: http://localhost/sled\n"
            "    base: trunk\n"
            "    token_slot: sled-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n",
            encoding="utf-8")

    def test_external_target_reads_targets_yaml(self):
        """Ловит мутацию: поля `RepoContext` перепутаны местами (`remote`
        получает `base`/наоборот) либо `path` читается из `config.ROOT`
        вместо `.artel/projects/<target>/workspace` (AC-14 — один и тот
        же адрес, что уже использует `snapshot.py`)."""
        ctx = repo_context.resolve("sled")

        self.assertEqual(ctx.path, config.PROJECTS / "sled" / "workspace")
        self.assertEqual(ctx.remote, "http://localhost/sled")
        self.assertEqual(ctx.base, "trunk")

    def test_unknown_target_degrades_to_none(self):
        """Ловит мутацию: `resolve()` бросает исключение или возвращает
        частично заполненный `RepoContext` вместо `None` на имени, которого
        нет в targets.yaml (fail-closed деградация, докстринг модуля)."""
        self.assertIsNone(repo_context.resolve("no-such-target"))

    def test_broken_targets_yaml_degrades_to_none(self):
        """Ловит мутацию: `resolve()` пробрасывает исключение парсера
        YAML наружу вместо `None` — вызывающий код (например,
        `_cmd_approve_merge_gate`) ждёт именно `None`, не exception."""
        config.TARGETS.write_text("не yaml вовсе: [", encoding="utf-8")

        self.assertIsNone(repo_context.resolve("sled"))


class PathOrNoneTest(unittest.TestCase):

    def test_none_context_is_none(self):
        """Ловит мутацию: `path_or_none(None)` бросает `AttributeError`
        вместо возврата `None` — вызывающий код (`gitcmd.is_clean`-style
        сигнатуры) ждёт именно вырожденный случай, не исключение."""
        self.assertIsNone(repo_context.path_or_none(None))

    def test_self_context_is_none(self):
        """Ловит мутацию: `path_or_none` сравнивает `ctx.path` не с
        `config.ROOT`, а с чем-то ещё (например, всегда возвращает
        `ctx.path`) — self перестал бы означать «параметр repo= можно не
        передавать» (self-байт-в-байт сломан)."""
        ctx = repo_context.RepoContext(path=config.ROOT, remote="origin",
                                       base=config.MAIN_BRANCH)
        self.assertIsNone(repo_context.path_or_none(ctx))

    def test_external_context_is_its_path(self):
        """Ловит мутацию: `path_or_none` возвращает `None` и для внешнего
        target тоже — вызывающий код получил бы `repo=None` и молча ушёл
        бы в `config.ROOT` вместо клона target'а."""
        path = config.PROJECTS / "sled" / "workspace"
        ctx = repo_context.RepoContext(path=path, remote="http://localhost/x", base="trunk")
        self.assertEqual(repo_context.path_or_none(ctx), path)


class GitHelperTest(unittest.TestCase):

    def test_self_context_calls_plain_git(self):
        """Ловит мутацию: `repo_context.git` зовёт `gitcmd.in_repo` для
        self тоже (например, всегда добавляет `-C config.ROOT`) — self
        перестал бы быть байт-в-байт прежним вызовом `gitcmd.git`."""
        ctx = repo_context.RepoContext(path=config.ROOT, remote="origin",
                                       base=config.MAIN_BRANCH)
        with mock.patch.object(gitcmd, "git") as git_mock, \
             mock.patch.object(gitcmd, "in_repo") as in_repo_mock:
            repo_context.git(ctx, "status")

        git_mock.assert_called_once_with("status")
        in_repo_mock.assert_not_called()

    def test_external_context_calls_in_repo(self):
        """Ловит мутацию: `repo_context.git` зовёт голый `gitcmd.git` для
        внешнего target (класс R1-F1 — та же ошибка, что нашлась в
        `_drop_scratch_worktree`: git-команда бьёт в `config.ROOT` вместо
        клона `ctx.path`), либо передаёт не тот путь в `in_repo`."""
        path = config.PROJECTS / "sled" / "workspace"
        ctx = repo_context.RepoContext(path=path, remote="http://localhost/x", base="trunk")
        with mock.patch.object(gitcmd, "git") as git_mock, \
             mock.patch.object(gitcmd, "in_repo") as in_repo_mock:
            repo_context.git(ctx, "status")

        in_repo_mock.assert_called_once_with(path, "status")
        git_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
