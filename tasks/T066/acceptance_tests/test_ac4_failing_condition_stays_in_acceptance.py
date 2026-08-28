"""AC-4 (tasks/T066/SPEC.md): при наличии хотя бы одного из
manual-критерий / skip-критерий / красный тест приёмочных / красный тест
полного набора / превышенный бюджет задачи / пробитый порог A1 —
задача останавливается и ждёт Оператора; причина «почему не автогейт»
присутствует в выводе команды и в журнале одной строкой.

Политика во всех сценариях этого файла — `acceptance: auto`
(`GATES_ACCEPTANCE_AUTO`): автогейт оценивается и явно не проходит по
названному условию, а не молчит из-за политики manual (это отдельный
критерий, AC-5).

Особый случай — красный тест ПРИЁМОЧНЫХ ЗАДАЧИ (не полного набора): по
существующей, не введённой этой задачей механике
(`orchestrator/fsm.py`, переход `review`, ветка "green, tail =
acceptance.run(...)"; регрессия — `tests/test_acceptance_tests_flow.py::
CriteriaGreenTransitionTest.test_timeout_blocks_the_transition_and_names_the_limit`)
красные/зависшие приёмочные тесты ЗАДАЧИ отклоняют сам переход
`review -> acceptance` целиком — задача остаётся в `review`, до
состояния `acceptance` в этом случае дело не доходит вообще, ни при
какой политике (это же поведение и при `acceptance: manual` — AC-5).
SPEC требование 2, условие "б" в этом смысле уже гарантировано самим
фактом входа в оценку автогейта — тем же приёмом, что и условие "д"
(вердикт REVIEW), для которого SPEC прямо говорит «уже гарантируется
переходом, условие фиксируется явно». Проверяется поэтому не буквальное
«останавливается в acceptance» для этой конкретной причины, а то, что
имеет значение по существу критерия — автогейт НИКОГДА не проносит
задачу мимо этого отказа в `merge_gate`.

Красен до реализации (пять классов — manual/skip/красный полный набор/
бюджет/порог A1): условия автопрохода SPEC требования 2 сегодня никто
не проверяет и не журналирует «почему не автогейт» — до кода задачи
падает именно проверка причины (слово «автогейт» в выводе/журнале),
при уже верном (структурно неизменном) состоянии `acceptance`.

Зелёный с рождения (`RedOwnAcceptanceTestsNeverReachesMergeGateTest`):
кодирует СУЩЕСТВУЮЩУЮ, не введённую этой задачей механику (красные
приёмочные тесты задачи блокируют сам переход `review -> acceptance`
целиком, см. докстринг выше) — сохранение поведения, а не новое.
"""
import unittest

from _sandbox import (FAILING_ACCEPTANCE_TEST, FAILING_FULL_SUITE_TEST,  # noqa: E402
                      MANUAL_MARKER_ACCEPTANCE_TEST,
                      SKIP_MARKER_ACCEPTANCE_TEST, AutogateSandbox)
from orchestrator import fsm  # noqa: E402


class _StoppedForOperatorMixin:

    def assert_autogate_reason_present(self, out: str) -> None:
        low = out.lower()
        self.assertIn("автогейт", low,
                      f"AC-4 требует причину «почему не автогейт» в "
                      f"выводе команды: {out!r}")
        reason_rows = [r for r in self.journal_rows()
                      if "автогейт" in r[2].lower()]
        self.assertTrue(
            reason_rows,
            f"AC-4 требует причину «почему не автогейт» в журнале: "
            f"{self.journal_rows()}")
        for _, _, detail in reason_rows:
            self.assertNotIn("\n", detail,
                             f"AC-4: причина обязана быть одной строкой: "
                             f"{detail!r}")


class ManualCriterionBlocksAutogateTest(_StoppedForOperatorMixin, AutogateSandbox):

    def test_ac4_manual_criterion_stays_in_acceptance(self):
        self.prepare_scenario(acceptance_content=MANUAL_MARKER_ACCEPTANCE_TEST)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")
        self.assert_autogate_reason_present(out)


class SkipCriterionBlocksAutogateTest(_StoppedForOperatorMixin, AutogateSandbox):

    def test_ac4_skip_criterion_stays_in_acceptance(self):
        self.prepare_scenario(acceptance_content=SKIP_MARKER_ACCEPTANCE_TEST)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")
        self.assert_autogate_reason_present(out)


class RedFullSuiteBlocksAutogateTest(_StoppedForOperatorMixin, AutogateSandbox):

    def test_ac4_red_full_suite_stays_in_acceptance(self):
        self.prepare_scenario(full_suite_content=FAILING_FULL_SUITE_TEST)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")
        self.assert_autogate_reason_present(out)


class ExceededTaskBudgetBlocksAutogateTest(_StoppedForOperatorMixin, AutogateSandbox):

    def test_ac4_exceeded_budget_stays_in_acceptance(self):
        self.prepare_scenario(budget_usd=10.0, spent_usd=10.0)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")
        self.assert_autogate_reason_present(out)


class ProgramThresholdBreachBlocksAutogateTest(_StoppedForOperatorMixin, AutogateSandbox):

    def test_ac4_a1_program_threshold_breach_stays_in_acceptance(self):
        self.seed_program_overspend()
        self.prepare_scenario()

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")
        self.assert_autogate_reason_present(out)


class RedOwnAcceptanceTestsNeverReachesMergeGateTest(AutogateSandbox):

    def test_ac4_red_own_acceptance_tests_never_autogates_to_merge_gate(self):
        self.prepare_scenario(acceptance_content=FAILING_ACCEPTANCE_TEST)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertNotEqual(
            self.state(), "merge_gate",
            "красные приёмочные тесты задачи не имеют права быть "
            "пронесены автогейтом дальше review")
        self.assertEqual(
            self.state(), "review",
            "существующая механика (не введённая этой задачей) держит "
            "задачу в review, пока её собственные приёмочные тесты "
            "красные — см. докстринг модуля")


if __name__ == "__main__":
    unittest.main()
