"""Юнит-тесты признака «свой долгоживущий файл» обязательного артефакта
test_author (`orchestrator/runner.py::_missing_required_artifact`, SPEC
01M3Y8570H9Y57YTP3M7E1AMHG, требование 1).

Сквозной путь шага (AC-1..AC-5) держит долгоживущая планка задачи; здесь —
свойства самого признака «новый или изменённый относительно базы ветки»
на настоящем git: файл, закоммиченный ролью, файл базы, удалённый файл и
молчание git.
"""
import unittest
from unittest import mock

from orchestrator import config, gitcmd, runner
from tests.sandbox import RealGitSandbox

TASK = "01M3Y8570H9Y57YTP3M7E1AMHG"
OWN = f"tests/test_{TASK.lower()}_plank.py"
BRANCH = f"task/{TASK.lower()}-zadacha"


class OwnLongLivedTestSignTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.git("checkout", "-q", "-b", BRANCH)

    def write(self, rel: str) -> None:
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("import unittest\n", encoding="utf-8")

    def missing(self):
        return runner._missing_required_artifact("test_author", self.root, TASK)

    def test_file_committed_by_role_counts(self):
        """Роль сама закоммитила свой долгоживущий файл — рабочее дерево
        чистое, но файл новый относительно базы ветки: шаг сдан.

        Ловит мутацию: признак смотрит только на `git status` (незакоммиченные
        изменения), как чекпоинт, — закоммиченный ролью файл не засчитается,
        и проверка вернёт имя отсутствующего артефакта вместо `None`."""
        self.write(OWN)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "планка")
        self.assertIsNone(self.missing())

    def test_file_already_in_base_does_not_count(self):
        """Долгоживущий файл задачи уже есть в базе ветки и не менялся —
        это не результат шага: отказ «без артефакта».

        Ловит мутацию: признак проверяет только наличие файла
        `tests/test_<префикс>_*.py` на диске, без сравнения с базой ветки, —
        старый файл засчитается, и проверка вернёт `None`."""
        self.git("checkout", "-q", config.MAIN_BRANCH)
        self.write(OWN)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "планка в main")
        self.git("checkout", "-q", BRANCH)
        self.git("merge", "-q", "--ff-only", config.MAIN_BRANCH)
        missing = self.missing()
        self.assertIsNotNone(missing)
        self.assertIn("acceptance_tests/", missing)

    def test_deleted_file_does_not_count(self):
        """Роль удалила долгоживущий файл базы — путь есть в диффе с базой,
        но файла на диске нет: отказ «без артефакта».

        Ловит мутацию: из признака убрана проверка, что путь — файл на диске,
        — удаление засчитается как сданный артефакт, и проверка вернёт
        `None`."""
        self.git("checkout", "-q", config.MAIN_BRANCH)
        self.write(OWN)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "планка в main")
        self.git("checkout", "-q", BRANCH)
        self.git("merge", "-q", "--ff-only", config.MAIN_BRANCH)
        (self.root / OWN).unlink()
        self.assertIsNotNone(self.missing())

    def test_git_silence_refuses(self):
        """git не ответил на базу ветки — признак не засчитывает файл
        вслепую: прежний отказ, хотя новый долгоживущий файл на диске есть.

        Ловит мутацию: при `diff_base is None` признак отвечает «есть»
        (fail-open) — проверка вернёт `None` при неответившем git."""
        self.write(OWN)
        with mock.patch.object(gitcmd, "diff_base", lambda *a, **k: None):
            self.assertIsNotNone(self.missing())


if __name__ == "__main__":
    unittest.main()
