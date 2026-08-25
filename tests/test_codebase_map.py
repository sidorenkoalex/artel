"""Юнит-тесты функций scripts/codebase_map.py (tasks/T027/SPEC.md).

Поведение генератора целиком (запуск процессом, файл на диске, CI-джоб)
уже покрыто локальными приёмочными тестами задачи
(tasks/T027/acceptance_tests/test_codebase_map.py, AC-1..9) — это её
залоченный контракт, дублировать его тут смысла нет. Здесь — юниты на
отдельные функции разбора, которые эти приёмочные тесты проверяют только
косвенно (через итоговый markdown), напрямую на входах, которые сложно
собрать через фикстуру целого дерева: докстринг с внутренними пустыми
строками, импорт под `if`, относительный `from . import x`.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import codebase_map  # noqa: E402


def parse(source: str) -> ast.Module:
    return ast.parse(source)


class ExtractPurposeTest(unittest.TestCase):
    def test_first_line_of_multiline_docstring(self):
        tree = parse('"""Первая строка.\n\nВторая строка, не входит."""\n')
        self.assertEqual(codebase_map.extract_purpose(tree), "Первая строка.")

    def test_no_docstring_marker(self):
        tree = parse("x = 1\n")
        self.assertEqual(codebase_map.extract_purpose(tree),
                         codebase_map.NO_DOCSTRING_MARK)

    def test_blank_docstring_falls_back_to_marker(self):
        tree = parse('"""   """\n')
        self.assertEqual(codebase_map.extract_purpose(tree),
                         codebase_map.NO_DOCSTRING_MARK)


class ExtractPublicFunctionsTest(unittest.TestCase):
    def test_only_top_level_public_functions_sorted(self):
        tree = parse(
            "def zeta(): pass\n"
            "def _hidden(): pass\n"
            "async def alpha(): pass\n"
            "class C:\n"
            "    def method_not_top_level(self): pass\n"
            "def inner_holder():\n"
            "    def nested(): pass\n"
        )
        self.assertEqual(codebase_map.extract_public_functions(tree),
                         ["alpha", "inner_holder", "zeta"])

    def test_no_public_functions(self):
        tree = parse("def _only_private(): pass\n")
        self.assertEqual(codebase_map.extract_public_functions(tree), [])


class ExtractImportedDottedNamesTest(unittest.TestCase):
    def test_absolute_import_statement(self):
        tree = parse("import orchestrator.config\n")
        self.assertIn("orchestrator.config",
                      codebase_map.extract_imported_dotted_names(tree, "scripts"))

    def test_absolute_from_import(self):
        tree = parse("from scripts import guard\n")
        names = codebase_map.extract_imported_dotted_names(tree, "orchestrator")
        self.assertIn("scripts.guard", names)
        self.assertIn("scripts", names)

    def test_relative_from_import_resolves_against_own_package(self):
        tree = parse("from . import config, gitcmd\n")
        names = codebase_map.extract_imported_dotted_names(tree, "orchestrator")
        self.assertIn("orchestrator.config", names)
        self.assertIn("orchestrator.gitcmd", names)

    def test_import_inside_conditional_is_still_found(self):
        tree = parse(
            "if True:\n"
            "    from . import store\n"
        )
        names = codebase_map.extract_imported_dotted_names(tree, "orchestrator")
        self.assertIn("orchestrator.store", names)

    def test_import_of_unrelated_third_party_module_is_kept_unresolved(self):
        tree = parse("import json\n")
        names = codebase_map.extract_imported_dotted_names(tree, "scripts")
        self.assertIn("json", names)


class ModuleDottedNameTest(unittest.TestCase):
    def test_regular_module(self):
        self.assertEqual(
            codebase_map.module_dotted_name(Path("orchestrator/alpha.py")),
            "orchestrator.alpha")

    def test_package_init_named_after_directory(self):
        self.assertEqual(
            codebase_map.module_dotted_name(Path("orchestrator/__init__.py")),
            "orchestrator")


if __name__ == "__main__":
    unittest.main()
