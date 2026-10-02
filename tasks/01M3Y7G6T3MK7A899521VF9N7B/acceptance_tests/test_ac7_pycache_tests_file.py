"""AC-7: тесты отведения кеша байткода лежат в tests/test_acceptance_pycache.py.

AC-1…AC-6 планка проверяет долгоживущим файлом
tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py (тот же прогон); здесь —
только факт этой задачи: разработчик положил свои тесты в файл, названный
SPEC, и каждый тестовый метод в нём несёт заявку «Ловит мутацию: …».

Файл читается из рабочей копии КОДА, в которой идёт прогон: планка лежит в
`<код>/tasks/<id>/acceptance_tests/` и в worktree, и после
`acceptance.materialize_from_branch`, поэтому корень кода — третий предок
каталога этого файла.

Группа: разовый
Красен до реализации: файла tests/test_acceptance_pycache.py ещё нет — разработчик его не написал.
"""

import ast
import unittest
from pathlib import Path

from scripts import guard

CODE_ROOT = Path(__file__).resolve().parents[3]
TESTS_FILE = CODE_ROOT / "tests" / "test_acceptance_pycache.py"


class PycacheTestsFileTest(unittest.TestCase):

    def source(self) -> str:
        self.assertTrue(TESTS_FILE.is_file(), f"нет файла {TESTS_FILE}")
        return TESTS_FILE.read_text(encoding="utf-8")

    def test_ac7_tests_file_covers_scenarios_with_mutation_claims(self):
        """Файл тестов есть, покрывает сценарии SPEC и у каждого метода есть заявка мутации.

        Файл `tests/test_acceptance_pycache.py` существует, разбирается,
        содержит хотя бы один тестовый метод; каждый `test_*` несёт в
        докстринге «Ловит мутацию: …» (тот же узел guard, что рубеж выхода
        из in_dev); в тексте файла названы три входа прогона, переменная
        `PYTHONPYCACHEPREFIX` и сценарий `TimeoutExpired`.

        Ловит мутацию: тесты положены в другой файл (или в
        `tests/test_acceptance.py`), один из методов без строки «Ловит
        мутацию: …», либо в файле нет сценария таймаута или вызова
        `collect`/`run_full_suite` — тест краснеет с причиной.
        """
        text = self.source()
        tree = ast.parse(text)
        methods = [node.name for node in ast.walk(tree)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name.startswith("test")]
        self.assertTrue(methods, f"в {TESTS_FILE} нет тестовых методов")
        missing = guard.test_functions_without_mutation_claim(None, text)
        self.assertEqual(missing, [],
                         f"методы без «Ловит мутацию: …»: {missing}")
        for needle in ("PYTHONPYCACHEPREFIX", "TimeoutExpired",
                       "acceptance.run", "acceptance.collect",
                       "acceptance.run_full_suite"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text,
                              f"в {TESTS_FILE.name} не упомянуто {needle}")


if __name__ == "__main__":
    unittest.main()
