"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-10 (тесты в `tests/`:
guard отказывает SPEC (`schema_version >= 5`) без `budget_usd`; SPEC
`budget_usd: 80` на гейте SPEC даёт потолок $80 (`budget_source = spec`);
SPEC `budget_usd: 120` — отказ guard; потолок $60, выставленный командой
`budget`, не перебивается значением из SPEC).

Четыре конкретных сценария AC-10 — те же классы поведения, что уже
проверяют AC-2/AC-3/AC-4 этой планки под своими числами, но AC-10 фиксирует
СВОИ буквальные значения (80/120/60) отдельным критерием — трассируемость
читает имя метода теста, а не факт покрытия behaviour где-то ещё.
«Существующие tests/test_spec_budget.py, test_step_cost.py,
test_invariants.py остаются зелёными без ослабления ассертов» — часть
того же AC-10, но это условие регрессии всего набора `tests/`, а не
новое наблюдаемое свойство: его continuous покрывает штатный CI-джоб
`python` на каждом коммите ветки (см. `test_ac_manual_and_skip_markers.py`,
разбор AC-6 — тот же класс критерия).

Красен до реализации: `config.ROLE_BUDGET_CAP` не существует — тесты
про 80/120 падают `AttributeError` при сравнении «120 — сколько именно
выше потолка» не нужно (сами числа литеральны), но guard ещё не знает о
потолке ролей вовсе, так что `test_ac10_budget_120_is_refused` находит
пустой список ошибок; `apply_spec_budget` сегодня отказывает 80
(«выше дефолта 50»), так что `test_ac10_budget_80_becomes_the_ceiling`
тоже красен.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from _sandbox import BudgetCeilingTest, check_spec  # noqa: E402


class GuardRefusesV5WithoutBudgetTest(unittest.TestCase):

    def test_ac10_spec_v5_without_budget_usd_is_refused(self):
        errors = check_spec(schema_version=5, budget=None)

        self.assertTrue(errors, "SPEC v5 без budget_usd обязан быть отказан")


class GateAppliesConcreteValuesTest(BudgetCeilingTest):

    def test_ac10_budget_80_becomes_the_ceiling_with_spec_source(self):
        self.apply("80")

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], 80.0)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_SPEC)

    def test_ac10_budget_120_is_refused_by_guard(self):
        errors = check_spec(schema_version=5, budget=120)

        self.assertTrue(errors, "SPEC с budget_usd: 120 обязан быть "
                                "отказан guard'ом")

    def test_ac10_operator_ceiling_60_is_not_overridden_by_spec(self):
        self.set_task(budget_usd=60.0,
                      budget_source=config.BUDGET_SOURCE_OPERATOR)

        self.apply("25")

        row = self.task_row()
        self.assertAlmostEqual(row["budget_usd"], 60.0)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_OPERATOR)


if __name__ == "__main__":
    unittest.main()
