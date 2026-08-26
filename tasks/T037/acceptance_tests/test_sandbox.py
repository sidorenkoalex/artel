"""Приёмочные тесты T037 — общий модуль тестовой песочницы `tests/sandbox.py`
(SPEC.md, критерии AC-1, AC-2).

Требование 1 просит вынести `TmpRootTest`/`capture`/`fake_git` в один
модуль и перевести существующие тестовые файлы на импорт из него. Оба
теста ниже статические (AST/файловая система), без запуска самих
тестовых файлов — содержательность самого рефакторинга (зелёный набор,
неизменность ассертов) проверяют AC-5/AC-6, не эти два теста.
"""
import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

TESTS_DIR = REPO_ROOT / "tests"
SANDBOX_PATH = TESTS_DIR / "sandbox.py"

FIXTURE_NAMES = ("TmpRootTest", "capture", "fake_git")


def _own_fixture_definitions(py_file: Path) -> set:
    """Имена из FIXTURE_NAMES, определённые НЕПОСРЕДСТВЕННО в файле —
    классом/функцией/методом верхнего уровня или вложенным в класс, а не
    импортированные из другого модуля."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in FIXTURE_NAMES:
                found.add(node.name)
    return found


class SandboxModuleDefinesSharedFixturesTest(unittest.TestCase):
    """AC-1: TmpRootTest, capture и fake_git определены в tests/sandbox.py."""

    def test_ac1_sandbox_module_defines_the_three_fixtures(self):
        self.assertTrue(
            SANDBOX_PATH.is_file(),
            "tests/sandbox.py не найден — общий модуль песочницы отсутствует")

        import importlib
        sandbox = importlib.import_module("tests.sandbox")
        for name in FIXTURE_NAMES:
            self.assertTrue(hasattr(sandbox, name),
                            f"tests/sandbox.py не определяет {name}")


class NoLeftoverCopiesOutsideSandboxTest(unittest.TestCase):
    """AC-1: в тестовых файлах, использующих эти фикстуры, остаются только
    импорт/наследование/вызов — не собственные копии классов/функций."""

    def test_ac1_no_other_test_file_keeps_its_own_copy(self):
        offenders = {}
        for py_file in sorted(TESTS_DIR.glob("*.py")):
            if py_file.name in ("sandbox.py", "__init__.py"):
                continue
            found = _own_fixture_definitions(py_file)
            if found:
                offenders[py_file.name] = sorted(found)
        self.assertEqual(
            offenders, {},
            f"в тестовых файлах остались собственные копии "
            f"TmpRootTest/capture/fake_git вместо импорта из "
            f"tests/sandbox.py: {offenders}")


class SandboxDefaultPatchesCoverAllConfigPathsTest(unittest.TestCase):
    """AC-2: набор патчей по умолчанию в tests/sandbox.py покрывает все
    девять путей `config`, используемые песочницами сегодня."""

    REQUIRED_ATTRS = ("DB", "TASKS", "LOGS", "ROOT", "PROJECTS", "TARGETS",
                      "ROLE_HOME", "ROLE_CONFIG_DIR", "BACKUP_MARKER")

    def test_ac2_default_sandbox_patches_all_nine_config_paths(self):
        import importlib
        sandbox = importlib.import_module("tests.sandbox")
        from orchestrator import config

        originals = {attr: getattr(config, attr) for attr in self.REQUIRED_ATTRS}
        probe = self

        class _Probe(sandbox.TmpRootTest):
            def test_probe(self):
                probe.observed = {
                    attr: getattr(config, attr) for attr in probe.REQUIRED_ATTRS}

        case = _Probe("test_probe")
        result = unittest.TestResult()
        case.run(result)

        self.assertEqual(
            result.errors, [],
            f"tests.sandbox.TmpRootTest.setUp упал: {result.errors}")
        self.assertEqual(
            result.failures, [],
            f"tests.sandbox.TmpRootTest упал в тесте-пробе: {result.failures}")

        unpatched = [attr for attr in self.REQUIRED_ATTRS
                    if self.observed[attr] == originals[attr]]
        self.assertEqual(
            unpatched, [],
            f"tests/sandbox.py по умолчанию не патчит config.{unpatched} — "
            f"утечка теста на реальное дерево пульта")


if __name__ == "__main__":
    unittest.main()
