"""AC-9 (SPEC.md, требование 6): корень репозитория несёт
`pyproject.toml` (либо `pytest.ini`) с `testpaths`, включающим `tests/`,
`python_files` по соглашению `test_*.py`, и таймаутом по умолчанию,
равным значению требования 4 (120 секунд — конкретное число самого
требования 4, а не производная от какой-то ещё не введённой константы).

Красен до реализации: ни `pyproject.toml`, ни `pytest.ini` в корне
репозитория ещё не существуют — `_util.read_pytest_config` возвращает
`None`, `assertIsNotNone` откажет первым же вызовом.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))

from _util import read_pytest_config  # noqa: E402


class PytestConfigTest(unittest.TestCase):

    def setUp(self):
        self.cfg = read_pytest_config(REPO_ROOT)
        self.assertIsNotNone(
            self.cfg,
            "требование 6: ни pyproject.toml с [tool.pytest.ini_options], "
            "ни pytest.ini с [pytest] не найдены в корне репозитория")

    def test_ac9_testpaths_includes_tests_dir(self):
        """`testpaths` конфигурации перечисляет `tests/` (значение из
        требования 6).

        Ловит мутацию: `testpaths` заведён пустым либо называет другой
        каталог (например, только `acceptance_tests` по аналогии с
        задачами) — `assertIn("tests", ...)` откажет.
        """
        testpaths = [p.strip("/") for p in self.cfg["testpaths"]]
        self.assertIn("tests", testpaths, self.cfg)

    def test_ac9_python_files_matches_test_star_convention(self):
        """`python_files` конфигурации несёт соглашение `test_*.py`
        (буквально, требование 6) — pytest соберёт существующие
        `tests/test_*.py` и `tasks/<id>/acceptance_tests/test_*.py` без
        отдельной правки имён файлов.

        Ловит мутацию: `python_files` заужен до нестандартного паттерна
        (например, только `test_ac*.py`, скопировано с шаблона планки
        приёмочных тестов) — существующие файлы `tests/test_amend.py` и
        т.п. перестали бы собираться, `assertIn` откажет.
        """
        self.assertIn("test_*.py", self.cfg["python_files"], self.cfg)

    def test_ac9_default_timeout_equals_requirement_4_value(self):
        """Таймаут по умолчанию конфигурации равен значению требования 4
        — 120 секунд.

        Ловит мутацию: конфигурация несёт таймаут, скопированный по
        ошибке с `config.ACCEPTANCE_TIMEOUT_SEC` (300) или
        `config.FULL_SUITE_TIMEOUT_SEC` (900) — таймаутов ВСЕГО прогона,
        не отдельного теста (SPEC, «Не входит») — `assertEqual(120, ...)`
        откажет.
        """
        self.assertEqual(self.cfg["timeout"], 120, self.cfg)


if __name__ == "__main__":
    unittest.main()
