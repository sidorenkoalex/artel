"""Независимость копий песочниц и ветка bare origin.

Группа: долгоживущий
Красен до реализации: один из последовательных экземпляров ещё получает общий каталог или bare origin наследует master из git-конфига.
"""

import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

from orchestrator import config
from tests.sandbox import OriginRealGitSandbox, RealGitSandbox, TmpRootTest


class _RealProbe(RealGitSandbox):
    __test__ = False

    def runTest(self):
        pass


class _TmpProbe(TmpRootTest):
    __test__ = False

    def runTest(self):
        pass


class _OriginProbe(OriginRealGitSandbox):
    __test__ = False

    def runTest(self):
        pass


class SandboxCopiesTest(unittest.TestCase):
    def test_ac1_real_git_repositories_are_independent(self):
        """Два последовательных экземпляра получают разные истории и каталоги.

        Ловит мутацию: общий каталог вместо копии сохраняет коммит первого
        экземпляра в истории и рабочем дереве второго.
        """
        seed = random.SystemRandom().randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for number in range(2):
            filename = f"copy_{rng.getrandbits(48):012x}_{number}.txt"
            first = _RealProbe()
            try:
                first.setUp()
                first_root = first.root
                self.assertEqual(first.git("branch", "--show-current").strip(),
                                 config.MAIN_BRANCH, f"зерно: {seed}")
                self.assertEqual(first.git("rev-list", "--count", "HEAD").strip(),
                                 "1", f"зерно: {seed}")
                (first_root / filename).write_text("written by first\n", encoding="utf-8")
                first.git("add", filename)
                first.git("commit", "-m", "first test")
            finally:
                first.doCleanups()

            second = _RealProbe()
            try:
                second.setUp()
                self.assertNotEqual(second.root, first_root, f"зерно: {seed}")
                self.assertEqual(second.git("branch", "--show-current").strip(),
                                 config.MAIN_BRANCH, f"зерно: {seed}")
                self.assertEqual(second.git("rev-list", "--count", "HEAD").strip(),
                                 "1", f"зерно: {seed}")
                self.assertFalse((second.root / filename).exists(), f"зерно: {seed}")
                self.assertNotIn(filename, second.git("ls-tree", "-r", "--name-only", "HEAD"),
                                 f"зерно: {seed}")
                self.assertNotIn("first test", second.git("log", "--format=%s"),
                                 f"зерно: {seed}")
            finally:
                second.doCleanups()

    def test_ac2_clone_stubs_are_independent(self):
        """Запись в клоне первого экземпляра не появляется во втором.

        Ловит мутацию: общий каталог заглушки сохраняет файл и коммит
        первого экземпляра для следующего.
        """
        seed = random.SystemRandom().randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for number in range(2):
            filename = f"stub_{rng.getrandbits(48):012x}_{number}.txt"
            first = _TmpProbe()
            try:
                first.setUp()
                clone = config.PROJECTS / config.DEFAULT_TARGET / "repo"
                first_clone = clone.resolve()
                (clone / filename).write_text("written by first\n", encoding="utf-8")
            finally:
                first.doCleanups()

            second = _TmpProbe()
            try:
                second.setUp()
                clone = config.PROJECTS / config.DEFAULT_TARGET / "repo"
                self.assertNotEqual(clone.resolve(), first_clone, f"зерно: {seed}")
                self.assertFalse((clone / filename).exists(), f"зерно: {seed}")
            finally:
                second.doCleanups()

    def test_ac3_template_is_not_exposed_or_changed_by_a_test(self):
        """Экземпляр хранит только свои пути, а удаление копии не портит следующую.

        Ловит мутацию: путь к шаблону сохраняется в атрибуте экземпляра
        либо следующий тест использует удалённый каталог предыдущего.
        """
        for probe in (_RealProbe, _TmpProbe):
            first = probe()
            try:
                first.setUp()
                root = first.root.resolve()
                for name, value in vars(first).items():
                    if isinstance(value, Path) and value.is_absolute():
                        self.assertTrue(value.resolve().is_relative_to(root),
                                        f"{probe.__name__}.{name} points outside {root}: {value}")
                marker = root / "copy_destroyed.txt"
                marker.write_text("changed\n", encoding="utf-8")
            finally:
                first.doCleanups()
            second = probe()
            try:
                second.setUp()
                self.assertNotEqual(second.root.resolve(), root)
                self.assertFalse((second.root / marker.name).exists())
                self.assertTrue(second.root.exists())
            finally:
                second.doCleanups()

    def test_ac5_bare_origins_head_tracks_main_branch(self):
        """Оба публичных пути создания origin обходят чужой defaultBranch.

        Ловит мутацию: `git init --bare` без `-b` оставляет HEAD на master
        при глобальном git-конфиге сценария.
        """
        with tempfile.TemporaryDirectory() as directory:
            global_config = Path(directory) / "gitconfig"
            global_config.write_text("[init]\n\tdefaultBranch = master\n", encoding="utf-8")
            env = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(global_config)}
            with mock.patch.dict(os.environ, env):
                for probe, method in ((_RealProbe, "add_synced_origin"),
                                      (_OriginProbe, "add_origin")):
                    instance = probe()
                    try:
                        instance.setUp()
                        origin = Path(getattr(instance, method)())
                        self.assertEqual((origin / "HEAD").read_text(encoding="utf-8").strip(),
                                         f"ref: refs/heads/{config.MAIN_BRANCH}")
                    finally:
                        instance.doCleanups()
