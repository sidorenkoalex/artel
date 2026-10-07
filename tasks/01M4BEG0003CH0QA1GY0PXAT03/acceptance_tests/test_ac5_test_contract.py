"""Проверка состава долгоживущей планки этой задачи.

Группа: разовый
Зелёный с рождения: файл планки создан до реализации и уже несёт сценарии AC-1–AC-4.
"""

import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402


class TestLongLivedContract(unittest.TestCase):
    def test_ac5_long_lived_mutation_claims_and_no_old_test_edits(self):
        """Новая планка несёт четыре сценария с заявками; чужие тесты не изменены.

        Ловит мутацию: один из сценариев или его заявка удалены либо задача
        переписала существующий тест вместо добавления своего файла.
        """
        prefix = "test_01m4beg0003ch0qa1gy0pxat03_"
        files = sorted((Path(CODE_ROOT) / "tests").glob(prefix + "*.py"))
        self.assertTrue(files, "долгоживущая планка отсутствует")
        methods = {}
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test_ac"):
                        methods[node.name] = ast.get_docstring(node) or ""
        for number in range(1, 5):
            matching = [claim for name, claim in methods.items()
                        if name.startswith(f"test_ac{number}_")]
            self.assertTrue(matching, f"нет долгоживущего AC-{number}")
            self.assertTrue(all("Ловит мутацию:" in claim for claim in matching),
                            f"нет заявки на мутацию AC-{number}")
        changed_tests = [path for path in changed_paths()
                         if path.startswith("tests/")]
        self.assertTrue(all(Path(path).name.startswith(prefix)
                            for path in changed_tests), changed_tests)
