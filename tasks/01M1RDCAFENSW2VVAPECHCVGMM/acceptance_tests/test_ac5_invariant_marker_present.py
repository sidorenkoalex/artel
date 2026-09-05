"""AC-5 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md, требование 3):
инвариант «только стандартная библиотека» появился в
`tests/test_invariants.py`.

Красен до реализации: `tests/test_invariants.py` ещё не содержит ссылку
на `sys.stdlib_module_names` — разработчик тест инварианта (требование
3) ещё не добавил.

Сам неослабляемый тест — код разработчика в `tests/test_invariants.py`
(в зоне этой задачи, правка вне `acceptance_tests/` этой роли запрещена,
скил test-authoring). Здесь — структурная метка появления теста, тем же
приёмом, что `tasks/T056/acceptance_tests/
test_ac3_invariant_locked_in_test_suite.py`: поиск отличительной строки
требования — `sys.stdlib_module_names` названа в требовании 3 SPEC
дословно и до этой задачи в файле не встречается.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class InvariantMarkerPresentTest(unittest.TestCase):

    def test_ac5_invariant_test_references_stdlib_module_names(self):
        """`tests/test_invariants.py` разбирает импорты через сверку со
        `sys.stdlib_module_names` — единственный текстовый след появления
        нового инвариантного теста требования 3.

        Ловит мутацию: разработчик не добавил тест инварианта вовсе,
        либо реализовал проверку без сверки со `sys.stdlib_module_names`
        (например, захардкодил свой список stdlib-модулей) — строка не
        появится, `assertIn` откажет.
        """
        source = (REPO_ROOT / "tests" / "test_invariants.py").read_text(
            encoding="utf-8")
        self.assertIn(
            "stdlib_module_names", source,
            "tests/test_invariants.py не разбирает импорты через "
            "sys.stdlib_module_names (требование 3) — тест инварианта "
            "«только стандартная библиотека» не найден")


if __name__ == "__main__":
    unittest.main()
