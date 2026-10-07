"""Проверка доказательств и приложения, которые существуют только в PLAN задачи.

Группа: разовый
Красен до реализации: PLAN ещё не написан разработчиком.
"""

# AC-2: skip — решение Оператора 07.10 (вариант В): suite-run не пишет запись «прогон: время» в журнал задачи, это запрещает tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::FootprintTest::test_ac23_task_state_untouched_and_no_files_outside_state

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import artifact_text  # noqa: E402


class PlanEvidenceTest(unittest.TestCase):
    def test_ac9_logs_thresholds_and_trigger_appendix(self):
        """PLAN приводит октябрьский ряд по логам и прикладывает строку сигнала.

        Ловит мутацию: разработчик опускает число xdist либо сравнение
        внутри равных групп, и PLAN больше не обосновывает выбранный порог.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md отсутствует в ссылке документов")
        self.assertRegex(plan, r"02\.10[^\n]*\d+[.,]\d+")
        self.assertRegex(plan, r"04\.10[^\n]*\d+[.,]\d+")
        self.assertRegex(plan, r"07\.10[^\n]*\d+[.,]\d+")
        self.assertRegex(plan, r"(?i)(xdist|процесс(?:ов|а)?)")
        self.assertRegex(plan, r"(?i)(одинаков|равн)[^\n]*(xdist|процесс)")
        self.assertRegex(plan, r"(?i)04\.10[\s\S]*вечер")
        self.assertRegex(plan, r"(?i)02\.10[\s\S]*04\.10[\s\S]*утр")
        self.assertRegex(plan, r"(?i)(срабатыва|сигнал)")
        self.assertRegex(plan, r"(?i)(не срабатыва|без сигнала|сигнала нет)")
        self.assertIn("docs/triggers.md", plan)
        self.assertIn("suite.duration", plan)
        self.assertIn("SUITE_DURATION_CALIBRATION_RUNS", plan)
        self.assertIn("SUITE_DURATION_RATIO", plan)
        self.assertIn("прогон: время", plan)
        self.assertIn("doctor", plan)
        self.assertIn("kind=trigger", plan)


if __name__ == "__main__":
    unittest.main()
