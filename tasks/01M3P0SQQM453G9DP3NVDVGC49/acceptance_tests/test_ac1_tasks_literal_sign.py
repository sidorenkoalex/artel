"""AC-1: признак `tasks/` долгоживущего файла — только у литерала,
привязанного к настоящему репозиторию; литерал пути от временного каталога
и литерал-аргумент публичной функции `orchestrator` в методе класса
песочницы признака не дают.

Фикстуры — текст долгоживущего файла, проверяемый публичным
`guard.long_lived_errors_from_files`; строки помечены `# @<метка>`.

Группа: разовый
Красен до реализации: нынешний `long_lived_sign_hits` ставит признак `tasks/` любому литералу с `tasks/`, в том числе от `self.tdir`/`self.root`/`tempfile` и в аргументе `gitcmd.show` метода песочницы — разрешённые строки получают ошибку. Метод запрещённых форм зелёный с рождения: безусловный признак их уже ловит — метод сторожит, что разрешение их не освободит.

Валидация стабом (временная реализация признаков в `scripts/guard.py`,
откачена): оба метода зелёные, как и все методы файлов AC-2…AC-9.

Почему разовый: фикстуры несут литералы `tasks/` и `gitcmd` — признаки,
которые нынешний (до этой задачи) guard запрещает долгоживущему файлу;
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
import unittest
from pathlib import Path

from orchestrator import config
from tests.sandbox import RealGitSandbox

REL = "tasks/T1/SPEC.md"  # @module-name
HERE = Path(__file__).resolve().parents[1]


class PlainTest(unittest.TestCase):

    def test_ac1_plain(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        path = config.ROOT / "tasks/T1/SPEC.md"  # @config-root-outside
        self.assertTrue(path)


class CopyTest(RealGitSandbox):

    def test_ac1_copy(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        repo = Path(__file__).parents[1] / "tasks/T1/SPEC.md"  # @file-anchor
        named = HERE / "tasks/T1/PLAN.md"  # @file-anchor-name
        rel = Path("tasks/T1/SPEC.md")  # @relative-path
        name = "T1"
        rel_f = Path(f"tasks/{name}/SPEC.md")  # @relative-fstring
        fh = open("tasks/T1/SPEC.md")  # @relative-open
        via_name = self.root / REL
        self.assertTrue(repo and named and rel and rel_f and fh and via_name)
''')

ALLOWED = long_lived_text('''
import os
import tempfile
from pathlib import Path

from orchestrator import gitcmd
from tests.sandbox import RealGitSandbox, TmpDirTest


class TdirTest(TmpDirTest):

    def test_ac1_tdir(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        path = self.tdir / "tasks/T1/SPEC.md"  # @tdir
        joined = self.tdir.joinpath("tasks/T1/PLAN.md")  # @tdir-joinpath
        os_joined = os.path.join(self.tdir, "tasks/T1/REVIEW.md")  # @tdir-os-join
        self.assertTrue(path and joined and os_joined)


class CopyTest(RealGitSandbox):

    def test_ac1_copy(self):
        """Фикстура.

        Ловит мутацию: фикстура.
        """
        spec = self.root / "tasks/T1/SPEC.md"  # @root
        name = "T1"
        plan = self.root / f"tasks/{name}/PLAN.md"  # @root-fstring
        base = self.root / "tasks" / "T1"
        text, _ = gitcmd.show("main", "tasks/T1/SPEC.md")  # @orchestrator-arg
        with tempfile.TemporaryDirectory() as d:
            inside = Path(d) / "tasks/T1/SPEC.md"  # @tempfile-as
        tmp = tempfile.mkdtemp()
        later = Path(tmp) / "tasks/T1/SPEC.md"  # @tempfile-name
        self.assertTrue(spec and plan and base and text and inside and later)
''')


class TasksLiteralSignTest(unittest.TestCase):

    def test_ac1_real_repo_anchored_literal_gets_sign(self):
        """Литерал `tasks/` от `Path(__file__)` (и имени, присвоенного от
        него), от `config.ROOT` вне класса песочницы, в относительном пути
        (`Path(...)`, f-строка, `open(...)`) и в имени уровня модуля даёт
        признак `tasks/` на строке литерала — в том числе в методе класса
        песочницы.

        Ловит мутацию: разрешение «метод класса песочницы» снимает признак
        со всех литералов метода, а не только с аргумента функции
        `orchestrator` — строки `@file-anchor`/`@relative-*` остаются без
        ошибки; либо литерал уровня модуля, употреблённый от `self.root`,
        засчитан разрешённым.
        """
        errors = errors_of(FORBIDDEN)
        for tag in tags_of(FORBIDDEN):
            with self.subTest(tag=tag):
                self.assertTrue(
                    errors_on(errors, line_of(FORBIDDEN, tag), guard.SIGN_TASKS),
                    f"нет признака «tasks/» на строке @{tag}: {errors!r}")

    def test_ac1_temp_dir_and_orchestrator_argument_have_no_sign(self):
        """Литерал `tasks/` в пути от `self.tdir` (операция `/`,
        `.joinpath`, `os.path.join`), от `self.root` (в т.ч. f-строкой), от
        якоря `tempfile` (`as`-цель и присвоенное имя) и литерал-аргумент
        `gitcmd.show` в методе класса песочницы — ни одной ошибки на своей
        строке.

        Ловит мутацию: признак `tasks/` остаётся безусловным (любой литерал
        с `tasks/`) или якорь `tempfile` не прослеживается через `as`/
        присваивание — разрешённая строка получает ошибку.
        """
        errors = errors_of(ALLOWED)
        for tag in tags_of(ALLOWED):
            with self.subTest(tag=tag):
                self.assertEqual(
                    errors_on(errors, line_of(ALLOWED, tag)), [],
                    f"разрешённая строка @{tag} получила ошибку")


if __name__ == "__main__":
    unittest.main()
