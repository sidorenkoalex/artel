"""Приёмочные тесты T061 — AC-1 (SPEC.md, «Критерии приёмки»):
`class FakeProc` определена один раз — в `tests/sandbox.py`.

Статическая (AST) проверка, без запуска самих тестовых файлов — та же
техника, что и `tasks/T037/acceptance_tests/test_sandbox.py`
(`NoLeftoverCopiesOutsideSandboxTest`), которым эта задача продолжает
дедупликацию.
"""
import ast
import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

TESTS_DIR = REPO_ROOT / "tests"
SANDBOX_PATH = TESTS_DIR / "sandbox.py"


def _defines_class(py_file: Path, name: str) -> bool:
    """True, если `py_file` где-либо (в т.ч. вложенно — метод, функция)
    определяет `class <name>`."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    return any(isinstance(node, ast.ClassDef) and node.name == name
               for node in ast.walk(tree))


class FakeProcSingleDefinitionTest(unittest.TestCase):
    """AC-1: `class FakeProc` определён один раз — в `tests/sandbox.py`;
    grep по `tests/*.py` (вне `tasks/`) не находит других определений."""

    def test_ac1_sandbox_defines_fakeproc(self):
        self.assertTrue(SANDBOX_PATH.is_file(),
                        "tests/sandbox.py не найден")
        self.assertTrue(
            _defines_class(SANDBOX_PATH, "FakeProc"),
            "tests/sandbox.py не определяет class FakeProc")

        sandbox = importlib.import_module("tests.sandbox")
        self.assertTrue(hasattr(sandbox, "FakeProc"),
                        "tests.sandbox не экспортирует FakeProc")

    def test_ac1_no_other_test_file_defines_its_own_fakeproc(self):
        offenders = []
        for py_file in sorted(TESTS_DIR.glob("*.py")):
            if py_file.name in ("sandbox.py", "__init__.py"):
                continue
            if _defines_class(py_file, "FakeProc"):
                offenders.append(py_file.name)

        self.assertEqual(
            offenders, [],
            f"локальные определения class FakeProc остались вместо "
            f"импорта из tests.sandbox: {offenders}")


if __name__ == "__main__":
    unittest.main()
