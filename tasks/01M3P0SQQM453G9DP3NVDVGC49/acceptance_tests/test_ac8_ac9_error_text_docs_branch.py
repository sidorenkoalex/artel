"""AC-8: текст ошибки признаков `tasks/`, «git-модуль», «git-вызов»
называет привязку к настоящему репозиторию и рецепт с `self.tdir`/
`self.root` песочницы `tests/sandbox.py`. AC-9: долгоживущий файл,
строящий ветку документов во временной копии `RealGitSandbox` через
`artifact_branch` и проверяющий `tasks/<id>/acceptance_tests/` в ней,
проходит `long_lived_errors_from_files` без единой ошибки.

Группа: разовый
Красен до реализации: нынешние пояснения признаков — «долгоживущий файл не знает каталога задачи»/«git-история — факт задачи» без рецепта, а файл ветки документов в песочнице получает «git-модуль» на импорте и `tasks/` на литерале.

Почему разовый: фикстуры несут `tasks/`, `gitcmd`/`artifact_branch` и git
через `subprocess` — признаки, которые нынешний (до этой задачи) guard
запрещает долгоживущему файлу; долгоживущие тесты пишет разработчик
(требование 15 SPEC).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (errors_of, errors_on, honest_fixture, line_of,  # noqa: E402
                      long_lived_text)
from scripts import guard  # noqa: E402

SIGNED = long_lived_text('''
import subprocess
import unittest

from orchestrator import config, gitcmd


class PlainTest(unittest.TestCase):

    def test_ac8_plain(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        path = config.ROOT / "tasks/T1/SPEC.md"  # @tasks
        text, _ = gitcmd.show("main", "README.md")  # @git-module
        subprocess.run(["git", "status"])  # @git-call
        self.assertTrue(path and text)
''')

SIGN_OF_TAG = {"tasks": guard.SIGN_TASKS, "git-module": guard.SIGN_GIT_MODULE,
               "git-call": guard.SIGN_GIT_CALL}


class ErrorTextTest(unittest.TestCase):

    def test_ac8_error_names_real_repo_binding_and_sandbox_recipe(self):
        """Ошибка каждого из трёх признаков содержит указание на привязку к
        настоящему репозиторию и рецепт: путь от `self.tdir`/`self.root`
        песочницы `tests/sandbox.py`.

        Ловит мутацию: новый текст объяснения заведён только для `tasks/`,
        а «git-модуль»/«git-вызов» сохранили прежнее «git-история — факт
        задачи» — ошибка строки `@git-call` без рецепта.
        """
        errors = errors_of(SIGNED)
        for tag, sign in SIGN_OF_TAG.items():
            with self.subTest(sign=sign):
                found = errors_on(errors, line_of(SIGNED, tag), sign)
                self.assertTrue(found, f"нет признака «{sign}»: {errors!r}")
                text = found[0]
                self.assertIn("настоящ", text.lower(),
                              f"нет указания на настоящий репозиторий: {text}")
                self.assertIn("tests/sandbox.py", text)
                self.assertTrue("self.tdir" in text or "self.root" in text,
                                f"нет рецепта с self.tdir/self.root: {text}")


class DocsBranchFixtureTest(unittest.TestCase):

    def test_ac9_docs_branch_in_sandbox_copy_passes_check(self):
        """Файл пульта: наследник `RealGitSandbox`, `artifact_branch.
        commit_files` планки `tasks/<id>/acceptance_tests/test_x.py` в
        ветку документов временной копии, `gitcmd.ls_tree_files` по
        `tasks/<id>/acceptance_tests` — ни одной ошибки проверки
        долгоживущего файла.

        Ловит мутацию: литерал `tasks/` операндом пути от `self.root`
        остаётся признаком (или вызов `artifact_branch` в методе песочницы)
        — файл, ради которого правило менялось, снова отклонён.
        """
        self.assertEqual(errors_of(honest_fixture()), [])


if __name__ == "__main__":
    unittest.main()
