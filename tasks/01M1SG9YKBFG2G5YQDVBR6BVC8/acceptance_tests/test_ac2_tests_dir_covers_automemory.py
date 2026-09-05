"""Приёмочный тест 01M1SG9YKBFG2G5YQDVBR6BVC8 — AC-2: в `tests/` есть
тест, проверяющий ключ `autoMemoryEnabled` референсного settings.json.

Красен до реализации: в `tests/` сейчас нет ни одного тестового метода,
чьё тело упоминает `autoMemoryEnabled` — `_matching_test_ids()` вернёт
пустой список, и первый `assertTrue` упадёт до появления такого теста
у разработчика.
"""
import ast
import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS_DIR = REPO_ROOT / "tests"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _matching_test_ids():
    """(module, класс, метод) тестов `tests/test_*.py`, чьё ТЕЛО (не файл
    целиком) упоминает `autoMemoryEnabled` — тело, а не файл, чтобы не
    подхватить случайный тест-сосед в том же модуле, не имеющий к этому
    ключу отношения."""
    ids = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if "autoMemoryEnabled" not in source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        module_name = f"tests.{path.stem}"
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not item.name.startswith("test"):
                    continue
                segment = ast.get_source_segment(source, item) or ""
                if "autoMemoryEnabled" in segment:
                    ids.append((module_name, node.name, item.name))
    return ids


class TestsDirCoversAutoMemorySettingTest(unittest.TestCase):
    def test_ac2_tests_dir_has_passing_automemory_settings_test(self):
        """В `tests/` существует тестовый метод, читающий референсный
        `docs/reference/role-home/claude/settings.json` и проверяющий
        значение ключа `autoMemoryEnabled` — и этот тест проходит.

        Ловит мутацию: такой тест в `tests/` отсутствует или удалён без
        замены (список пуст — первый `assertTrue` падает), либо
        присутствует, но его собственная проверка не проходит на
        текущем содержимом settings.json (второй `assertTrue` падает).
        """
        ids = _matching_test_ids()
        self.assertTrue(
            ids,
            "в tests/ нет тестового метода, упоминающего autoMemoryEnabled "
            "— добавь тест, читающий "
            "docs/reference/role-home/claude/settings.json (AC-2 SPEC)")

        suite = unittest.TestSuite()
        for module_name, class_name, method_name in ids:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            suite.addTest(cls(method_name))

        result = unittest.TestResult()
        suite.run(result)

        self.assertTrue(
            result.wasSuccessful(),
            f"найденный(е) в tests/ тест(ы) autoMemoryEnabled не "
            f"проходят: {result.failures + result.errors}")


if __name__ == "__main__":
    unittest.main()
