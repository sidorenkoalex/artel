"""AC-4: константа `config.CI_STUCK_CHECK_MINUTES` = 45; AC-9: каждый тест
нового файла `tests/test_ci_stuck_check_run.py` несёт «Ловит мутацию: …».

Оба — факты этой задачи: значение порога — крутилка Оператора, которую он
вправе повернуть после мержа, а состав файла тестов задачи после мержа
живёт по общим правилам `tests/`.

Группа: разовый
Красен до реализации: константы `CI_STUCK_CHECK_MINUTES` в `orchestrator/config.py` нет, файла `tests/test_ci_stuck_check_run.py` ещё нет — оба теста падают.
"""
import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402

TEST_FILE = REPO_ROOT / "tests" / "test_ci_stuck_check_run.py"


class ConfigAndTestFileTest(unittest.TestCase):

    def test_ac4_stuck_threshold_constant_is_45_minutes(self):
        """В `orchestrator/config.py` есть `CI_STUCK_CHECK_MINUTES` = 45.

        Ловит мутацию: порог заведён в секундах (`45 * 60`) или под другим
        именем (`CI_STUCK_MINUTES`) — значение или атрибут не сойдутся.
        """
        self.assertTrue(hasattr(config, "CI_STUCK_CHECK_MINUTES"),
                        "в orchestrator/config.py нет CI_STUCK_CHECK_MINUTES")
        self.assertEqual(config.CI_STUCK_CHECK_MINUTES, 45)

    def test_ac9_every_test_in_new_file_claims_a_mutation(self):
        """Каждый тест `tests/test_ci_stuck_check_run.py` заявляет мутацию.

        Файл существует, в нём есть хотя бы один тест, и узел гейта
        `guard.test_functions_without_mutation_claim` (файл новый — base
        `None`) не находит ни одного теста без «Ловит мутацию: …».

        Ловит мутацию: разработчик пишет тесты задачи в существующий файл
        (`tests/test_ci_status.py`) или один из методов несёт «Зелёный с
        рождения» вместо заявки — файла не будет либо метод попадёт в
        список.
        """
        self.assertTrue(TEST_FILE.is_file(), f"нет файла {TEST_FILE}")
        source = TEST_FILE.read_text(encoding="utf-8")
        tests = [n.name for n in ast.walk(ast.parse(source))
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name.startswith("test")]
        self.assertTrue(tests, f"в {TEST_FILE.name} нет ни одного теста")
        self.assertEqual(guard.test_functions_without_mutation_claim(None, source),
                         [])


if __name__ == "__main__":
    unittest.main()
