"""AC-2, AC-3, AC-4: признак «git-модуль» — по употреблению, не по импорту;
`diff_base`/`diff_base_source` — признак везде; что считается классом
песочницы.

Фикстуры — текст долгоживущего файла, проверяемый публичным
`guard.long_lived_errors_from_files`; строки помечены `# @<метка>`.

Группа: разовый
Красен до реализации: нынешний `long_lived_sign_hits` ставит «git-модуль» на импорт `gitcmd`/`artifact_branch` и не различает класс песочницы — файл из одних импортов и вызовы `gitcmd` в методе наследника `RealGitSandbox` получают ошибку, а вызов вне песочницы признака на строке вызова не получает.

Почему разовый: фикстуры несут `gitcmd`/`artifact_branch` и литералы
`tasks/` — признаки, которые нынешний (до этой задачи) guard запрещает
долгоживущему файлу; долгоживущие тесты признаков пишет разработчик
(требование 15 SPEC).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (errors_of, errors_on, line_of, long_lived_text,  # noqa: E402
                      tags_of)
from scripts import guard  # noqa: E402

IMPORT_ONLY = long_lived_text('''
import unittest

import orchestrator.artifact_branch
from orchestrator import artifact_branch, gitcmd
from orchestrator.gitcmd import show


class PlainTest(unittest.TestCase):

    def test_ac2_plain(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        self.assertTrue(unittest)
''')

OUTSIDE = long_lived_text('''
import unittest

from orchestrator import artifact_branch, gitcmd

HEAD = gitcmd.branch_head_sha("main")  # @module-level


class PlainTest(unittest.TestCase):

    def test_ac2_plain(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        text, _ = gitcmd.show("main", "README.md")  # @plain-gitcmd
        name = artifact_branch.branch_name("T1")  # @plain-artifact
        self.assertTrue(text and name)
''')

INSIDE = long_lived_text('''
from orchestrator import artifact_branch, gitcmd
from tests.sandbox import LightTransitionSandbox, RealGitSandbox, TmpRootTest


class CopyTest(RealGitSandbox):

    def test_ac2_copy(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        text, _ = gitcmd.show("main", "README.md")  # @copy-gitcmd
        name = artifact_branch.branch_name("T1")  # @copy-artifact
        sha = artifact_branch.commit_files("T1", {}, "фикстура")  # @copy-commit
        self.assertTrue(text and name and sha)


class LightTest(LightTransitionSandbox):

    def test_ac2_light(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        head = gitcmd.branch_head_sha("main")  # @light-gitcmd
        self.assertTrue(head)


class Base(TmpRootTest):
    pass


class ChildTest(Base):

    def test_ac2_child(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        head = gitcmd.branch_head_sha("main")  # @child-gitcmd
        self.assertTrue(head)
''')

DIFF_BASE = long_lived_text('''
from orchestrator import gitcmd
from tests.sandbox import RealGitSandbox


class CopyTest(RealGitSandbox):

    def test_ac3_copy(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        base = gitcmd.diff_base("task/x")  # @diff-base
        source = gitcmd.diff_base_source("task/x")  # @diff-base-source
        ref = gitcmd.diff_base  # @diff-base-ref
        self.assertTrue(base and source and ref)
''')

NOT_SANDBOX = long_lived_text('''
import unittest

from orchestrator import config, gitcmd
from tests.sandbox import TmpDirTest, TmpRootTest


class TdirTest(TmpDirTest):

    def test_ac4_tdir(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        text, _ = gitcmd.show("main", "README.md")  # @tdir-gitcmd
        path = config.ROOT / "tasks/T1/SPEC.md"  # @tdir-config
        self.assertTrue(text and path)


class CaseTest(unittest.TestCase):

    def test_ac4_case(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        text, _ = gitcmd.show("main", "README.md")  # @case-gitcmd
        path = config.TASKS / "tasks/T1/SPEC.md"  # @case-config
        self.assertTrue(text and path)


class NarrowTest(TmpRootTest):

    PATCHED_ATTRS = ("DB",)

    def test_ac4_narrow(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        text, _ = gitcmd.show("main", "README.md")  # @narrow-gitcmd
        path = config.ROOT / "tasks/T1/SPEC.md"  # @narrow-config
        self.assertTrue(text and path)
''')

SANDBOX_HEIR = long_lived_text('''
from orchestrator import gitcmd
from tests.sandbox import RealGitSandbox


class CopyTest(RealGitSandbox):

    def test_ac4_copy(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        text, _ = gitcmd.show("main", "README.md")  # @heir-gitcmd
        self.assertTrue(text)
''')


class GitModuleSignTest(unittest.TestCase):

    def test_ac2_import_without_use_has_no_sign(self):
        """Файл, который только импортирует `gitcmd`/`artifact_branch`
        тремя формами и ничего из них не вызывает, — ни одной ошибки.

        Ловит мутацию: признак «git-модуль» остаётся на импорте — строка
        импорта получает ошибку.
        """
        self.assertEqual(errors_of(IMPORT_ONLY), [])

    def test_ac2_call_outside_sandbox_method_gets_sign(self):
        """Вызов функции `gitcmd`/`artifact_branch` на уровне модуля и в
        методе наследника `unittest.TestCase` — признак «git-модуль» на
        строке вызова.

        Ловит мутацию: признак снят вместе с импортом, а на употребление
        не перенесён (или засчитывает песочницей любой класс) — строка
        вызова без ошибки.
        """
        errors = errors_of(OUTSIDE)
        for tag in tags_of(OUTSIDE):
            with self.subTest(tag=tag):
                self.assertTrue(
                    errors_on(errors, line_of(OUTSIDE, tag),
                              guard.SIGN_GIT_MODULE),
                    f"нет признака «git-модуль» на строке @{tag}: {errors!r}")

    def test_ac2_call_in_sandbox_method_has_no_sign(self):
        """Вызов функции `gitcmd`/`artifact_branch` в методе наследника
        `RealGitSandbox`, `LightTransitionSandbox` и класса, унаследованного
        от `TmpRootTest` через другой класс того же файла, — ни одной
        ошибки во всём файле.

        Ловит мутацию: класс песочницы узнаётся только по прямому предку
        из фиксированного перечня (без наследников `TmpRootTest` и без
        цепочки через класс файла) — вызов в `LightTest`/`ChildTest`
        получает ошибку.
        """
        self.assertEqual(errors_of(INSIDE), [])

    def test_ac3_diff_base_is_sign_even_in_sandbox_method(self):
        """`gitcmd.diff_base(...)`, `gitcmd.diff_base_source(...)` и
        обращение к атрибуту `gitcmd.diff_base` без вызова в методе
        наследника `RealGitSandbox` — признак «git-модуль» на своей строке.

        Ловит мутацию: разрешение «метод класса песочницы» применено ко
        всем функциям `gitcmd` без исключения `diff_base*` — строка
        `@diff-base` без ошибки.
        """
        errors = errors_of(DIFF_BASE)
        for tag in tags_of(DIFF_BASE):
            with self.subTest(tag=tag):
                self.assertTrue(
                    errors_on(errors, line_of(DIFF_BASE, tag),
                              guard.SIGN_GIT_MODULE),
                    f"нет признака «git-модуль» на строке @{tag}: {errors!r}")

    def test_ac4_tmpdir_testcase_and_patched_attrs_are_not_sandbox(self):
        """Наследник `TmpDirTest`, наследник `unittest.TestCase` и
        наследник `TmpRootTest`, переопределивший `PATCHED_ATTRS`: вызов
        `gitcmd` даёт «git-модуль», литерал `tasks/` от `config.ROOT`/
        `config.TASKS` — признак `tasks/`, как вне песочницы.

        Ловит мутацию: классом песочницы засчитан любой класс из
        `tests.sandbox` (в т.ч. `TmpDirTest`) или переопределение
        `PATCHED_ATTRS` не снимает статус — строка `@tdir-gitcmd`/
        `@narrow-gitcmd` без ошибки.
        """
        errors = errors_of(NOT_SANDBOX)
        for tag in tags_of(NOT_SANDBOX):
            sign = (guard.SIGN_GIT_MODULE if tag.endswith("gitcmd")
                    else guard.SIGN_TASKS)
            with self.subTest(tag=tag):
                self.assertTrue(
                    errors_on(errors, line_of(NOT_SANDBOX, tag), sign),
                    f"нет признака «{sign}» на строке @{tag}: {errors!r}")

    def test_ac4_real_git_sandbox_heir_is_sandbox(self):
        """Наследник `RealGitSandbox`, импортированного из `tests.sandbox`,
        — класс песочницы: вызов `gitcmd.show` в его методе ошибки не даёт.

        Ловит мутацию: наследование от `RealGitSandbox` не прослежено до
        `TmpRootTest` (классом песочницы считается только сам
        `TmpRootTest`) — строка вызова получает ошибку.
        """
        self.assertEqual(errors_of(SANDBOX_HEIR), [])


if __name__ == "__main__":
    unittest.main()
