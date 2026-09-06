"""Приёмочный тест 01M1VBEDGMEXHVGWAH42FTDZ4X — AC-16: `tests/test_budget*.py`,
`tests/test_fsm_review_rework*.py` и `tests/test_auto*.py` остаются
зелёными без правки утверждений.

Прогон через `unittest.TestLoader().discover(pattern=...)`, а не через
`from tests.xxx import ИмяКласса` (см. тот же приём `tasks/T065/
acceptance_tests/test_ac5_invariant_tests_stay_green.py`): discovery по
маске переживает и переименование существующих файлов, и появление
НОВОГО файла, которого на момент написания этого теста ещё нет —
`tests/test_budget*.py` сегодня не матчит НИ ОДНОГО файла (в дереве есть
только `tests/test_spec_budget.py`, чьё имя не начинается на
`test_budget`): зона этой задачи (`orchestrator/budget.py`) свежая, и
юнит-тесты требования 1 разработчик, скорее всего, положит именно в файл
с таким именем. Импортировать классы по имени значило бы гадать это имя
заранее и получить `ImportError` вместо содержательной проверки; маска
без файлов даёт `NO TESTS RAN` — `wasSuccessful()` там `True` (нечего
ослаблять, пока файла нет), а как только файл появится, тот же прогон
начнёт сверять его настоящими прогонами, без правки этого теста.

Зелёный с рождения: тест — не про код ЭТОЙ задачи, а про то, что её код
(когда он появится) не ослабит уже существующие regression-suite'ы
(ADR-0002). Сегодня два из трёх паттернов матчат существующие файлы (оба
зелёные), третий не матчит ничего («NO TESTS RAN» — тривиально успешно)
— тест обязан оставаться зелёным и до, и после реализации требований
1-3; красноту здесь создаст только само ослабление одной из трёх планок.
"""
import io
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

PATTERNS = ("test_budget*.py", "test_fsm_review_rework*.py", "test_auto*.py")


def _run_pattern(pattern: str) -> unittest.TestResult:
    suite = unittest.TestLoader().discover(
        start_dir=str(REPO_ROOT / "tests"), pattern=pattern,
        top_level_dir=str(REPO_ROOT))
    return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)


class RegressionSuitesStayGreenTest(unittest.TestCase):

    def test_ac16_named_test_file_patterns_stay_green(self):
        for pattern in PATTERNS:
            with self.subTest(маска=pattern):
                result = _run_pattern(pattern)
                self.assertTrue(
                    result.wasSuccessful(),
                    f"{pattern}: {len(result.failures)} провалов, "
                    f"{len(result.errors)} ошибок ({result.testsRun} тестов) — "
                    f"утверждения ослаблены "
                    f"({[t[0] for t in result.failures + result.errors]})")


if __name__ == "__main__":
    unittest.main()
