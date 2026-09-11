"""AC-4 (tasks/01M1THKWFXFYNW28HDJGYHQWH6/SPEC.md, требование 4): после
возврата задачи в `in_dev` из ревью (`changes_requested`) ИЛИ из приёмки
(`reject`) повторная сдача PLAN.md со `status: ready` — даже с более
высоким `budget_usd`, чем на первой сдаче — потолок не меняет. Критерий
называет оба возвратных пути явно («или») — оба покрыты отдельным методом.

Красен до реализации: `in_dev` этой ветки не читает `budget_usd` из PLAN.md
вовсе (см. докстринг test_ac1_ac2_ac3_first_submission.py — тот же дефицит
части 2 ADR-0014). Проверено временным стабом: реализация, которая
однократность выводит из СУЩЕСТВУЮЩИХ счётчиков (`review_iters == 0 and
accept_rejects == 0` — оба растут ровно на возвратных путях, которые
называет этот критерий, без новой колонки в БД), зеленит оба метода; стаб
подтверждает критерий исполним без домысливания реализации.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PlanBudgetSandbox  # noqa: E402


class Ac4ReviewChangesRequestedReturnTest(PlanBudgetSandbox):

    def test_ac4_second_submission_after_changes_requested_does_not_reraise(self):
        """Первая сдача PLAN.md ($90) уже подняла потолок с $45 до $90.
        Ревью возвращает задачу в `in_dev` вердиктом `changes_requested`;
        вторая сдача PLAN.md несёт `budget_usd: 100` — потолок остаётся
        $90, источник остаётся `plan`.

        Ловит мутацию: гейт «первая сдача» на одном лишь `review_iters ==
        0` без отдельной памяти о том, что переоценка уже случилась —
        здесь `review_iters` действительно становится 1 после
        `changes_requested`, так что даже наивная проверка `review_iters
        == 0` уже должна закрыть повтор; тест ловит РЕГРЕССИЮ этого же
        свойства (например, случайный сброс `review_iters` или отдельный
        флаг переоценки, который наивно снимается при возврате).
        """
        self.enter_in_dev()
        self.set_budget(45.0, "spec")
        self.submit_plan(budget_usd=90)
        self.assertEqual(self.state(), "review")
        self.assertEqual(self.task_row()["budget_usd"], 90.0)

        self.request_changes(iteration=1)
        self.assertEqual(self.task_row()["review_iters"], 1)
        self.commit_code_branch_change()

        self.submit_plan(budget_usd=100)

        self.assertEqual(self.state(), "review",
                         "PLAN.md ready второй сдачи всё равно обязан "
                         "провести переход — правило 4 отказывает только "
                         "переоценке бюджета, не самому переходу")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], 90.0,
                         "повторная сдача не должна поднимать потолок")
        self.assertEqual(row["budget_source"], "plan")


class Ac4AcceptanceRejectReturnTest(PlanBudgetSandbox):

    def test_ac4_second_submission_after_acceptance_reject_does_not_reraise(self):
        """Первая сдача PLAN.md ($90) уже подняла потолок с $45 до $90.
        Ревью одобряет (`approved`), CI зелёный, задача доходит до
        `acceptance`, Оператор делает `reject` — задача возвращается в
        `in_dev` БЕЗ роста `review_iters` (`accept_rejects` растёт вместо
        него). Вторая сдача PLAN.md несёт `budget_usd: 100` — потолок
        остаётся $90.

        Ловит мутацию: реализация, которая держит «первая сдача ли это»
        ТОЛЬКО через `review_iters == 0` (без учёта `accept_rejects`) —
        этот путь возврата НЕ трогает `review_iters` вовсе (см.
        `orchestrator/fsm.py::_cmd_reject`, ветка `state == "acceptance"`),
        поэтому наивная проверка одного `review_iters` пропустила бы
        повторную переоценку; тест ловит именно это расхождение.
        """
        self.enter_in_dev()
        self.set_budget(45.0, "spec")
        self.submit_plan(budget_usd=90)
        self.assertEqual(self.state(), "review")
        self.assertEqual(self.task_row()["budget_usd"], 90.0)

        self.reach_acceptance(iteration=1)
        self.assertEqual(self.task_row()["review_iters"], 0,
                         "предпосылка теста: reject из acceptance не "
                         "растит review_iters")
        self.reject_from_acceptance()
        self.assertEqual(self.task_row()["accept_rejects"], 1)

        self.submit_plan(budget_usd=100)

        self.assertEqual(self.state(), "review")
        row = self.task_row()
        self.assertEqual(row["budget_usd"], 90.0,
                         "повторная сдача после reject не должна поднимать "
                         "потолок")
        self.assertEqual(row["budget_source"], "plan")


if __name__ == "__main__":
    import unittest
    unittest.main()
