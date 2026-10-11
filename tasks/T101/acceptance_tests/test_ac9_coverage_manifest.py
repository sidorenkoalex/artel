"""AC-9 (SPEC T101) — тесты покрывают: сбор с доступными инструментами;
сбор при недоступном инструменте; сбор при таймауте внешнего вызова;
попадание fingerprint в журнальное событие агентного шага; попадание
fingerprint в журнальное событие прогона приёмочных тестов;
отсутствие влияния сбоя сбора на исход шага.

Это требование о ПОЛНОТЕ набора приёмочных тестов этой самой задачи, а
не о поведении кода T101 — по существу оно уже выполнено фактом, что
`test_ac1_ac4_ac6_agent_step_available.py` и
`test_ac2_ac3_agent_step_failure_isolation.py` содержат по одному тесту
на каждый из шести пунктов (тот же приём, что «часть 1» AC-8 в
`tasks/T033/acceptance_tests/test_advance_fixation.py`: структурное
покрытие не нуждается в отдельной проверке ПОВЕДЕНИЯ, но фактическое
наличие соответствующих `test_ac<n>_...` методов сверяется здесь
статически, чтобы будущая правка этого каталога не могла молча
потерять один из шести сценариев).

Зелёный с рождения: методы, перечисленные ниже, уже существуют в этом
же каталоге на момент написания этого теста — проверка не зависит от
кода задачи T101, только от структуры набора приёмочных тестов.
"""
import re
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

REQUIRED_SCENARIOS = {
    "сбор с доступными инструментами": re.compile(r"def test_ac1_\w*available\w*\("),
    "сбор при недоступном инструменте": re.compile(r"def test_ac2_\w*missing\w*\("),
    "сбор при таймауте внешнего вызова": re.compile(r"def test_ac2_\w*timeout\w*\("),
    "попадание в событие агентного шага (AC-4)": re.compile(r"def test_ac4_\w*\("),
    "попадание в событие приёмочных тестов (AC-5)": re.compile(r"def test_ac5_\w*\("),
    "отсутствие влияния сбоя на исход шага (AC-3)": re.compile(r"def test_ac3_\w*\("),
}


class RequiredScenariosCoverageTest(unittest.TestCase):

    def test_ac9_required_scenarios_have_corresponding_test_methods(self):
        source = "\n".join(
            p.read_text(encoding="utf-8")
            for p in sorted(TESTS_DIR.glob("test_*.py")))

        missing = [label for label, pattern in REQUIRED_SCENARIOS.items()
                  if not pattern.search(source)]

        self.assertEqual(
            missing, [],
            f"требование 7/AC-9 называет сценарии, для которых в "
            f"acceptance_tests/ не нашлось соответствующего "
            f"test_ac<n>_... метода: {missing}")


if __name__ == "__main__":
    unittest.main()
