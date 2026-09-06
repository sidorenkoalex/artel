"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-4 (`budget.spec_budget`/
`budget.apply_spec_budget`: на переходе spec_writing -> spec_gate значение
SPEC применяется потолком задачи и выше, и ниже сегодняшнего дефолта, при
`0 < value <= ROLE_BUDGET_CAP`; потолок с `budget_source = operator`
значением из SPEC не перебивается).

Прямой вызов `budget.spec_budget`/`_sandbox.BudgetCeilingTest.apply`
(== `budget.apply_spec_budget` над строкой задачи) — тот же угол, что уже
использует `tests/test_spec_budget.py::SpecBudgetParseTest` для разбора
и `SpentWithEstimateGateTest` для строки `tasks` без git/ветки.

Красен до реализации: сегодня `budget.spec_budget` отказывает любое
значение выше `config.DEFAULT_BUDGET_USD` («выше дефолта») — тест на
применение значения ВЫШЕ дефолта (но в пределах потолка ролей) красен
именно потому, что сегодняшняя реализация ещё не знает о потолке ролей;
`config.ROLE_BUDGET_CAP`, на которую опирается сравнение сравнения теста,
сама не существует до кода задачи (`AttributeError`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import budget, config  # noqa: E402
from _sandbox import BudgetCeilingTest  # noqa: E402


class SpecBudgetParsingRangeTest(unittest.TestCase):
    """`budget.spec_budget` — сумма ниже потолка ролей принимается, выше
    — отказана с указанием потолка ролей.

    Ловит мутацию: верхняя граница сравнения осталась привязана к
    `config.DEFAULT_BUDGET_USD` (старая семантика) — тогда значение
    между дефолтом и потолком ролей (например, 80 при дефолте 50 и
    потолке 100) по-прежнему отказывалось бы, хотя AC-4 прямо требует
    его принять.
    """

    def test_ac4_value_above_default_but_within_cap_is_accepted(self):
        value = (config.DEFAULT_BUDGET_USD + config.ROLE_BUDGET_CAP) / 2

        result, refused = budget.spec_budget({"budget_usd": f"{value:g}"})

        self.assertEqual(refused, "")
        self.assertAlmostEqual(result, value)

    def test_ac4_value_above_the_cap_is_refused(self):
        over_cap = config.ROLE_BUDGET_CAP + 1

        result, refused = budget.spec_budget({"budget_usd": f"{over_cap:g}"})

        self.assertIsNone(result)
        self.assertIn(f"{config.ROLE_BUDGET_CAP:.2f}", refused)

    def test_ac4_value_equal_to_the_cap_is_accepted(self):
        result, refused = budget.spec_budget(
            {"budget_usd": f"{config.ROLE_BUDGET_CAP:g}"})

        self.assertEqual(refused, "")
        self.assertAlmostEqual(result, config.ROLE_BUDGET_CAP)


class ApplySpecBudgetBothDirectionsTest(BudgetCeilingTest):
    """`apply_spec_budget` на строке задачи с текущим потолком-дефолтом —
    значение SPEC применяется и когда оно выше, и когда оно ниже.

    Ловит мутацию: `apply_spec_budget` продолжает молча пропускать
    («не применён») значения ниже текущего потолка задачи, считая это
    попыткой опустить потолок задним числом, — тогда
    `test_ac4_lower_value_is_applied` найдёт прежний потолок вместо
    нового, более низкого.
    """

    def test_ac4_higher_value_within_cap_is_applied(self):
        higher = config.DEFAULT_BUDGET_USD + 20  # < ROLE_BUDGET_CAP

        self.apply(f"{higher:g}")

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], higher)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_SPEC)

    def test_ac4_lower_value_is_applied(self):
        lower = config.DEFAULT_BUDGET_USD - 20
        self.assertGreater(lower, 0, "фикстура: дефолт слишком мал для теста")

        self.apply(f"{lower:g}")

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], lower)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_SPEC)

    def test_ac4_value_above_cap_does_not_change_the_ceiling(self):
        over_cap = config.ROLE_BUDGET_CAP + 1

        self.apply(f"{over_cap:g}")

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], config.DEFAULT_BUDGET_USD,
                               msg="потолок не должен был подняться")
        self.assertIsNone(row["budget_source"])

    def test_ac4_operator_ceiling_is_not_overridden_by_spec(self):
        self.set_task(budget_usd=60.0,
                      budget_source=config.BUDGET_SOURCE_OPERATOR)

        self.apply("25")

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], 60.0)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_OPERATOR)


if __name__ == "__main__":
    unittest.main()
