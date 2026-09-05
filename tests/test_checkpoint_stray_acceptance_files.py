"""Юнит-тесты `checkpoint._is_stray_acceptance_test_file` (SPEC
01M1SAA01YRRTWAVADT2F81RRQ, AC-1).

Интеграционное поведение автокоммита на реальной песочнице (перенос в
артефактную ветку, журнал) уже покрыто залоченной планкой приёмки
(tasks/01M1SAA01YRRTWAVADT2F81RRQ/acceptance_tests/
test_checkpoint_stray_acceptance_test_files.py, AC-1/AC-2/AC-5) —
дублировать её тут смысла нет. Здесь — юниты на сам предикат, изолированно
от git/store, на входах, которые фикстуре целого дерева собирать дороже:
границы регулярки для каждого разрешённого имени по отдельности, файлы
вне acceptance_tests/, пустое имя после каталога.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import checkpoint  # noqa: E402


class IsStrayAcceptanceTestFileTest(unittest.TestCase):

    def test_files_outside_acceptance_tests_are_never_stray(self):
        for rel in ("PLAN.md", "SPEC.md", "acceptance_tests_notes.md",
                   "docs/notes.md"):
            with self.subTest(файл=rel):
                self.assertFalse(checkpoint._is_stray_acceptance_test_file(rel))

    def test_each_allowed_top_level_name_is_not_stray(self):
        for rel in ("acceptance_tests/test_x.py",
                   "acceptance_tests/test_ac1_something.py",
                   "acceptance_tests/_sandbox.py",
                   "acceptance_tests/markers.py",
                   "acceptance_tests/__init__.py",
                   "acceptance_tests/NOTES.md",
                   "acceptance_tests/README.txt"):
            with self.subTest(файл=rel):
                self.assertFalse(checkpoint._is_stray_acceptance_test_file(rel))

    def test_disallowed_top_level_extension_is_stray(self):
        for rel in ("acceptance_tests/fixtures.json",
                   "acceptance_tests/helper.py.bak",
                   "acceptance_tests/notes",
                   "acceptance_tests/_sandbox.pyc"):
            with self.subTest(файл=rel):
                self.assertTrue(checkpoint._is_stray_acceptance_test_file(rel))

    def test_python_file_not_matching_test_prefix_is_stray(self):
        # Только `test_*.py`/`_sandbox.py`/`markers.py`/`__init__.py` — не
        # любой `.py` первого уровня.
        self.assertTrue(
            checkpoint._is_stray_acceptance_test_file("acceptance_tests/helpers.py"))

    def test_any_nested_path_is_stray_even_with_allowed_extension(self):
        for rel in ("acceptance_tests/docs/codebase-map.md",
                   "acceptance_tests/helpers/util.py",
                   "acceptance_tests/nested/test_x.py"):
            with self.subTest(файл=rel):
                self.assertTrue(checkpoint._is_stray_acceptance_test_file(rel))


if __name__ == "__main__":
    unittest.main()
