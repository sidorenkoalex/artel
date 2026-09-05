"""AC-7 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md) — случай СОВПАДАЮЩЕГО
значения: «...не перебивает — ни при совпадающем, ни при отличающемся
значении `budget_usd` в SPEC.» Случай отличающегося значения — отдельный
файл `test_ac7_differing_spec_budget_does_not_override.py` (там же —
обоснование красноты, актуальное для обоих файлов).

Зелёный с рождения: сегодня approve на spec_gate не зовёт `apply_spec_
budget` вовсе — потолок и источник остаются как были ($100/operator)
независимо от значения в SPEC, включая случай, когда оно совпадает с
уже применённым. Наблюдаемый исход («ничего не изменилось») здесь тот
же самый что до, что после реализации требования 4 — ценность теста не
в сегодняшней красноте, а в том, что он ловит будущий регресс: наивная
реализация, сравнивающая только ЧИСЛО (совпало — можно применить) без
проверки `budget_source`, тихо подменила бы источник на `spec`, хотя
Оператор уже владеет потолком. Прогнано: тест уже проходит на
сегодняшнем коде.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import budget, config, fsm, store  # noqa: E402

from _sandbox import ApproveSandbox  # noqa: E402


class MatchingSpecBudgetDoesNotOverrideOperatorCeilingTest(ApproveSandbox):

    def test_ac7_matching_spec_budget_does_not_override_operator_ceiling(self):
        """Значение в SPEC СОВПАДАЕТ с уже выставленным Оператором
        потолком ($100 в обоих местах) — источник обязан остаться
        `operator`, а не незаметно смениться на `spec` только потому,
        что числа равны.

        Ловит мутацию: реализация, сравнивающая только ЧИСЛО (а не
        `budget_source`) перед применением, увидела бы «$100 == $100» и
        решила, что перезаписывать нечего/можно, и подменила бы источник
        на `spec` — тест ловит именно смену `budget_source`, не только
        значение.
        """
        sha = self.enter_spec_gate()
        self.capture(budget.cmd_budget, self.TASK, "100")
        self.write_spec_budget_on_artifact_branch(100)

        self.capture(fsm.cmd_approve, self.TASK, sha)

        row = store.get_task(store.db(), self.TASK)
        self.assertAlmostEqual(row["budget_usd"], 100.0)
        self.assertEqual(row["budget_source"], config.BUDGET_SOURCE_OPERATOR,
                         "совпадение чисел не значит, что источник — SPEC")


if __name__ == "__main__":
    unittest.main()
