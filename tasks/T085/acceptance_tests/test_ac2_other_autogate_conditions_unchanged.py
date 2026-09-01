"""AC-2 (tasks/T085/SPEC.md): остальной состав условий автогейта
acceptance (полный набор `tests/`, приёмочные тесты задачи, бюджет
задачи, вердикт REVIEW) не изменён относительно T066 — только условие
порога программы (A1) убирается (AC-1), всё остальное блокирует
автогейт так же, как и до этой задачи.

Зелёный с рождения: все пять тестов этого файла зелены с рождения —
ни один из четырёх сценариев отказа (manual/skip/красный полный
набор/бюджет) не задет удалением условия A1 в
`orchestrator/fsm.py::_autogate_conditions` — эти проверки идут раньше
проверки порога программы и код задачи их не трогает (SPEC требование
1: «остальные условия автогейта не менять»). Пятый тест (зелёный
сценарий без пробитого порога — единственное отличие от AC-1 в том,
что расход программы здесь по умолчанию нулевой) — регрессия успешного
пути, тоже не тронутого этой задачей.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AutogateSandbox, FAILING_FULL_SUITE_TEST,  # noqa: E402
                      MANUAL_MARKER_ACCEPTANCE_TEST,
                      SKIP_MARKER_ACCEPTANCE_TEST)


class _StaysInAcceptanceMixin:

    def assert_blocks_autogate(self, out: str) -> None:
        self.assertEqual(
            self.state(), "acceptance",
            f"AC-2: условие не входит в удаляемый этой задачей состав "
            f"(A1) — обязано останавливать автогейт, как и до T085: "
            f"{out!r}")
        self.assertIn("автогейт", out.lower())


class ManualCriterionStillBlocksAutogateTest(_StaysInAcceptanceMixin,
                                             AutogateSandbox):

    def test_ac2_manual_criterion_still_blocks_autogate(self):
        self.prepare_scenario(acceptance_content=MANUAL_MARKER_ACCEPTANCE_TEST)

        out = self.advance_to_autogate()

        self.assert_blocks_autogate(out)


class SkipCriterionStillBlocksAutogateTest(_StaysInAcceptanceMixin,
                                           AutogateSandbox):

    def test_ac2_skip_criterion_still_blocks_autogate(self):
        self.prepare_scenario(acceptance_content=SKIP_MARKER_ACCEPTANCE_TEST)

        out = self.advance_to_autogate()

        self.assert_blocks_autogate(out)


class RedFullSuiteStillBlocksAutogateTest(_StaysInAcceptanceMixin,
                                          AutogateSandbox):

    def test_ac2_red_full_suite_still_blocks_autogate(self):
        self.prepare_scenario(full_suite_content=FAILING_FULL_SUITE_TEST)

        out = self.advance_to_autogate()

        self.assert_blocks_autogate(out)


class ExceededTaskBudgetStillBlocksAutogateTest(_StaysInAcceptanceMixin,
                                                AutogateSandbox):

    def test_ac2_exceeded_task_budget_still_blocks_autogate(self):
        self.prepare_scenario(budget_usd=10.0, spent_usd=10.0)

        out = self.advance_to_autogate()

        self.assert_blocks_autogate(out)


class AllConditionsGreenStillPassesAutogateTest(AutogateSandbox):

    def test_ac2_all_conditions_green_still_reach_merge_gate(self):
        self.prepare_green_scenario()

        out = self.advance_to_autogate()

        self.assertEqual(
            self.state(), "merge_gate",
            f"AC-2: сценарий со всеми условиями выполненными (порог "
            f"программы здесь не пробит вовсе) обязан по-прежнему "
            f"проходить автогейтом одним прогоном advance: {out!r}")


if __name__ == "__main__":
    unittest.main()
