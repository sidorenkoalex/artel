"""AC-5 (tasks/01M1THKWFXFYNW28HDJGYHQWH6/SPEC.md, требование 5): потолок,
заданный Оператором командой `budget` (`budget_source = operator`), не
перебивается значением `budget_usd` из PLAN.md ни на первой, ни на любой
последующей сдаче PLAN.md.

Зелёный с рождения: сегодняшний `orchestrator/fsm_advance.py::in_dev`
вообще не читает `budget_usd` из PLAN.md — потолок и его источник не
меняются НИ ПРИ КАКОМ содержимом PLAN.md, так что оба сценария («потолок
Оператора» на первой и на последующей сдаче) уже проходят буквально так,
как требует AC-5, безо всякой новой ветки кода части 2. Тест ловит
будущую РЕГРЕССИЮ (код части 2, который начнёт применять `budget_usd` из
PLAN, но забудет сравнить `budget_source` с `operator` ДО применения —
только проверит `review_iters == 0`/счётчики однократности), не
сегодняшний дефект — тем же приёмом, что
`tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests/
test_ac1_head_already_pushed_unchanged.py`. Проверено временным стабом
корректной реализации (см. журнал шага test_author) — оба метода остаются
зелёными и со стабом, не только без него.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PlanBudgetSandbox  # noqa: E402


class Ac5OperatorCeilingFirstSubmissionTest(PlanBudgetSandbox):

    def test_ac5_operator_ceiling_not_overridden_on_first_submission(self):
        """Потолок $60 задан Оператором (`budget_source = operator`).
        Первая сдача PLAN.md несёт `budget_usd: 90` (выше потолка) — но
        потолок остаётся $60, источник остаётся `operator`.

        Ловит мутацию: код, который проверяет только «review_iters == 0»
        и применяет `budget_usd` из PLAN БЕЗ проверки `budget_source` —
        тест поймает по изменившемуся потолку/источнику задачи.
        """
        self.enter_in_dev()
        self.set_budget(60.0, "operator")

        self.submit_plan(budget_usd=90)

        self.assertEqual(self.state(), "review")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], 60.0)
        self.assertEqual(row["budget_source"], "operator")


class Ac5OperatorCeilingLaterSubmissionTest(PlanBudgetSandbox):

    def test_ac5_operator_ceiling_not_overridden_on_later_submission(self):
        """Потолок $60 Оператора выставлен ПОСЛЕ первой сдачи PLAN.md (уже
        поднявшей потолок переоценкой) — но это тот же самый инвариант:
        задача возвращена в `in_dev` (`changes_requested`), Оператор
        поднимает потолок командой `budget` до $60, вторая сдача PLAN.md
        несёт `budget_usd: 90` — потолок остаётся $60.

        Ловит мутацию: два независимых слоя защиты должны держать этот
        случай одновременно — гейт «однократности» (AC-4) и отдельная
        проверка `budget_source == operator`. Если разработчик по ошибке
        уронит проверку однократности (например, спутает счётчик после
        `changes_requested` — регрессия AC-4) — этот тест всё равно
        поймает применение PLAN поверх Оператора вторым, независимым
        слоем: по итоговому потолку/источнику после второй сдачи.
        """
        self.enter_in_dev()
        self.set_budget(45.0, "spec")
        self.submit_plan(budget_usd=50)
        self.assertEqual(self.state(), "review")

        self.request_changes(iteration=1)
        self.commit_code_branch_change()
        self.set_budget(60.0, "operator")

        self.submit_plan(budget_usd=90)

        self.assertEqual(self.state(), "review")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], 60.0)
        self.assertEqual(row["budget_source"], "operator")


if __name__ == "__main__":
    import unittest
    unittest.main()
