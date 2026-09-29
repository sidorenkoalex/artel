"""AC-5: признак «git-вызов» — у git через `subprocess` без каталога
временной копии (и в методе класса песочницы); `cwd=self.root` и
`-C` от `self.tdir` признака не дают; `merge-base` и `os.system` с git —
признак всегда.

Фикстуры — текст долгоживущего файла, проверяемый публичным
`guard.long_lived_errors_from_files`; строки помечены `# @<метка>`.

Группа: разовый
Красен до реализации: нынешний `long_lived_sign_hits` ставит «git-вызов» любому git через `subprocess` — строки с `cwd=self.root` и `-C str(self.tdir)` получают ошибку.

Почему разовый: фикстуры несут git через `subprocess` — признак, который
нынешний (до этой задачи) guard запрещает долгоживущему файлу;
долгоживущие тесты признаков пишет разработчик (требование 15 SPEC).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (errors_of, errors_on, line_of, long_lived_text,  # noqa: E402
                      tags_of)
from scripts import guard  # noqa: E402

FORBIDDEN = long_lived_text('''
import os
import subprocess
import unittest

from tests.sandbox import RealGitSandbox, TmpDirTest


class CopyTest(RealGitSandbox):

    def test_ac5_copy(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        subprocess.run(["git", "status"])  # @sandbox-bare
        subprocess.run(["git", "log", "-1"], check=True)  # @sandbox-bare-kw
        subprocess.run(["git", "merge-base", "main", "HEAD"], cwd=self.root)  # @merge-base-cwd
        subprocess.run(["git", "-C", str(self.root), "merge-base", "a", "b"])  # @merge-base-c
        os.system("git status")  # @os-system
        os.system(f"git -C {self.root} status")  # @os-system-c


class TdirTest(TmpDirTest):

    def test_ac5_tdir(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        subprocess.run(["git", "status"])  # @tdir-bare


class PlainTest(unittest.TestCase):

    def test_ac5_plain(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        subprocess.check_output("git log -1", shell=True)  # @plain-string
''')

ALLOWED = long_lived_text('''
import subprocess

from tests.sandbox import RealGitSandbox, TmpDirTest


class CopyTest(RealGitSandbox):

    def test_ac5_copy(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        subprocess.run(["git", "status"], cwd=self.root)  # @cwd-root
        subprocess.run(["git", "log", "-1"], cwd=self.root, check=True)  # @cwd-root-kw


class TdirTest(TmpDirTest):

    def test_ac5_tdir(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        subprocess.run(["git", "-C", str(self.tdir), "status"])  # @dash-c-tdir
''')


class GitCallSignTest(unittest.TestCase):

    def test_ac5_git_without_temp_copy_merge_base_and_os_system_get_sign(self):
        """Git через `subprocess` без `cwd=`/`-C` временной копии — в
        методе класса песочницы, наследника `TmpDirTest` и
        `unittest.TestCase`; `merge-base` даже с `cwd=self.root`/`-C`
        `self.root`; `os.system` с git даже с `-C {self.root}` — признак
        «git-вызов» на своей строке.

        Ловит мутацию: метод класса песочницы освобождает любой git-вызов
        (правило каталога заменено правилом класса) или исключение по
        `cwd=` не проверяет `merge-base` — строка `@sandbox-bare`/
        `@merge-base-cwd` без ошибки.
        """
        errors = errors_of(FORBIDDEN)
        for tag in tags_of(FORBIDDEN):
            with self.subTest(tag=tag):
                self.assertTrue(
                    errors_on(errors, line_of(FORBIDDEN, tag),
                              guard.SIGN_GIT_CALL),
                    f"нет признака «git-вызов» на строке @{tag}: {errors!r}")

    def test_ac5_git_in_temp_copy_has_no_sign(self):
        """`subprocess.run(["git", …], cwd=self.root)` и
        `subprocess.run(["git", "-C", str(self.tdir), …])` — ни одной
        ошибки во всём файле.

        Ловит мутацию: признак «git-вызов» остаётся безусловным или пара
        `"-C", <якорь>` не распознаётся — строка `@dash-c-tdir` получает
        ошибку.
        """
        self.assertEqual(errors_of(ALLOWED), [])


if __name__ == "__main__":
    unittest.main()
