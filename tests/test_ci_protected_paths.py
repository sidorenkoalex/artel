"""Юнит-тесты `scripts/ci_protected_paths.py` (SPEC
01M31DRD81092HB69J0MAKZMGH, требования 1-4) — углы разбора и сверки, не
закрытые приёмочной планкой.

Планка (`tasks/01M31DRD81092HB69J0MAKZMGH/acceptance_tests/
test_ac1_ac4_ci_protected_paths_base.py`) гоняет скрипт целиком на живом
git-репозитории и отвечает на вопрос «тот ли вердикт». Здесь — чистые
функции без git: КАК разбирается текст `orchestrator/config.py` базы и по
какому правилу путь считается нарушением. Оба слоя нужны порознь: планка
не различает «список не разобрался» и «git не ответил» (оба ненулевые), а
именно это различие несёт причину в лог джоба.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config  # noqa: E402
from scripts import ci_protected_paths as cpp  # noqa: E402


class ProtectedPathsParsingTest(unittest.TestCase):
    """Разбор значения `PROTECTED_PATHS` из текста модуля."""

    def test_multiline_tuple_is_parsed_with_every_path(self):
        """Список базы записан многострочным кортежем — ровно так, как он
        записан в настоящем `orchestrator/config.py`.

        Ловит мутацию: разбор сведён к регулярке по одной строке — перенос
        кортежа на вторую строку теряет её пути, и защита молча
        сокращается до первых двух элементов.
        """
        source = ('PROTECTED_PATHS = ("gates.yaml", "roles.yaml",\n'
                  '                   "skills/", "templates/")\n')

        paths, reason = cpp.protected_paths_from_source(source)

        self.assertEqual(reason, "")
        self.assertEqual(paths, ["gates.yaml", "roles.yaml", "skills/",
                                 "templates/"])

    def test_real_config_text_yields_the_live_protected_paths(self):
        """Тот же разбор, применённый к настоящему тексту
        `orchestrator/config.py` рабочей копии, обязан дать в точности
        сегодняшний `config.PROTECTED_PATHS`.

        Ловит мутацию: разбор работает только на синтетическом образце
        тестов (скажем, требует кавычек одного вида или одной строки) и
        разъезжается с настоящим файлом — джоб на живом PR стал бы
        fail-closed на каждом прогоне.
        """
        source = Path(config.__file__).read_text(encoding="utf-8")

        paths, reason = cpp.protected_paths_from_source(source)

        self.assertEqual(reason, "")
        self.assertEqual(paths, list(config.PROTECTED_PATHS))

    def test_assignment_inside_a_function_is_not_the_module_list(self):
        """Одноимённая локальная переменная внутри функции списком
        защищённых путей не является — на верхнем уровне присваивания нет.

        Ловит мутацию: присваивание ищется обходом всего AST
        (`ast.walk`), и любая локальная переменная с этим именем — в том
        числе подставленная веткой — подменяет список базы.
        """
        source = ('def f():\n'
                  '    PROTECTED_PATHS = ("skills/",)\n'
                  '    return PROTECTED_PATHS\n')

        paths, reason = cpp.protected_paths_from_source(source)

        self.assertIsNone(paths)
        self.assertIn("PROTECTED_PATHS", reason)

    def test_empty_or_non_string_value_is_a_reason_not_an_empty_list(self):
        """Пустой кортеж и кортеж с не-строкой внутри — причина отказа, а
        не «нарушений нет»: пустой список означает снятую защиту.

        Ловит мутацию: непригодное значение сведено к пустому списку
        путей — `is_violation` не находит нарушений ни на одном пути, и
        джоб зеленеет, так и не проверив ничего (fail-open вместо
        fail-closed, ADR-0002).
        """
        for source in ('PROTECTED_PATHS = ()\n',
                       'PROTECTED_PATHS = ("skills/", 17)\n',
                       'PROTECTED_PATHS = ("", "skills/")\n'):
            with self.subTest(source=source):
                paths, reason = cpp.protected_paths_from_source(source)

                self.assertIsNone(paths)
                self.assertIn("PROTECTED_PATHS", reason)

    def test_computed_value_and_broken_syntax_are_named_reasons(self):
        """Значение, которое нельзя вычислить без исполнения кода, и текст,
        который вообще не парсится как Python, — оба с названной причиной.

        Ловит мутацию: неудача разбора проглочена общим `except` и
        возвращена пустой строкой причины — лог джоба перестаёт называть
        то, чего не смог прочитать, и разбирать красный джоб не по чему.
        """
        computed, computed_reason = cpp.protected_paths_from_source(
            'PROTECTED_PATHS = tuple(sorted(("skills/",)))\n')
        self.assertIsNone(computed)
        self.assertTrue(computed_reason.strip())

        broken, broken_reason = cpp.protected_paths_from_source(
            'PROTECTED_PATHS = ("skills/",\n')
        self.assertIsNone(broken)
        self.assertIn("orchestrator/config.py", broken_reason)


class ViolationMatchingTest(unittest.TestCase):
    """Правило «путь нарушает список» — то же, что нёс `grep -E "^(...)"`."""

    def test_directory_prefix_catches_files_inside_it(self):
        """Элемент-каталог ловит любой файл внутри себя на любой глубине,
        элемент-файл ловит сам себя.

        Ловит мутацию: сверка ослаблена до точного равенства пути элементу
        списка — `skills/spec-authoring.md` перестаёт быть нарушением, и
        защищённые каталоги защищают только сами себя.
        """
        protected = ["gates.yaml", "skills/", "docs/adr/"]

        self.assertTrue(cpp.is_violation("skills/spec-authoring.md", protected))
        self.assertTrue(cpp.is_violation("docs/adr/0014-budget.md", protected))
        self.assertTrue(cpp.is_violation("gates.yaml", protected))

    def test_unlisted_paths_are_not_violations(self):
        """Пути вне списка нарушениями не считаются — в том числе тёзка
        защищённого каталога в другом месте дерева.

        Ловит мутацию: префикс проверяется поиском подстроки в любом месте
        пути (`prefix in path`) — `tests/skills/x.md` начинает краснеть
        джоб, хотя защищён только корневой `skills/`.
        """
        protected = ["gates.yaml", "skills/"]

        self.assertFalse(cpp.is_violation("orchestrator/config.py", protected))
        self.assertFalse(cpp.is_violation("tests/skills/x.md", protected))
        self.assertFalse(cpp.is_violation("scripts/guard.py", protected))


if __name__ == "__main__":
    unittest.main()
