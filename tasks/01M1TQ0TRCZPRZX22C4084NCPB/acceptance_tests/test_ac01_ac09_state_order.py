"""Приёмочные тесты 01M1TQ0TRCZPRZX22C4084NCPB — AC-1, AC-9: новый порядок
переходов FSM `in_dev -> verifying -> review -> acceptance -> merge_gate`
(ADR-0015) и условие перехода `verifying -> review` (зелёный CI).

Красен до реализации: сегодняшний `orchestrator/fsm_advance.py::in_dev`
переводит задачу с готовым PLAN.md прямиком в `review` (строка 1005:
`store.set_state(conn, task_id, "review", ...)`), а `review()` на
вердикте `approved` переводит в `verifying` (строка 268); `verifying()`
на зелёном CI переводит в `acceptance` (строка 312), не в `review`.
Оба теста ниже покраснеют именно на несовпадении СОСТОЯНИЯ-НАЗНАЧЕНИЯ
каждого перехода, не на побочной причине (гейты in_dev УЖЕ проходят
пусто на фикстуре этого файла — см. `_sandbox.FsmOrderScenarioTest`).

Переход `acceptance -> merge_gate` (ручной `approve` Оператора, не
`advance`) этой задачей не меняется (SPEC «Не входит») — тестами этого
файла не покрыт, дальше `acceptance` намеренно не идём.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FsmOrderScenarioTest, green_ci, none_ci,  # noqa: E402
                      red_ci, running_ci)


class NewRouteOrderTest(FsmOrderScenarioTest):

    def test_ac1_full_route_goes_in_dev_verifying_review_acceptance(self):
        """Задача с готовым PLAN.md и одобренным REVIEW.md проходит через
        всю новую цепочку `in_dev -> verifying -> review -> acceptance`,
        а не старую `in_dev -> review -> verifying -> acceptance`.

        Ловит мутацию: порядок переходов не изменён (in_dev по-прежнему
        ведёт прямиком в review, а review(approved) — в verifying) —
        первый advance уже не попадёт в 'verifying', и тест покраснеет
        на первой же проверке, не дожидаясь до конца цепочки.
        """
        self.enter_in_dev_ready()

        self.advance()
        self.assertEqual(self.state(), "verifying",
                         "in_dev не ведёт первым шагом в verifying")

        with green_ci():
            self.advance()
        self.assertEqual(self.state(), "review",
                         "verifying (зелёный CI) не ведёт в review")

        self.write_review("approved", 1)
        self.advance()
        self.assertEqual(self.state(), "acceptance",
                         "review (approved) не ведёт в acceptance")

    def test_ac9_verifying_advances_to_review_only_on_green_ci(self):
        """Из состояния `verifying` (заведённого напрямую, без прогона
        in_dev) переход в `review` случается только при зелёном статусе
        CI подтянутой головы; красный/отсутствующий/идущий CI оставляют
        задачу в `verifying`.

        Ловит мутацию: `verifying` продолжает вести в 'acceptance' на
        зелёном CI вместо 'review' (старый маршрут не поменяли), либо
        какой-то не-зелёный исход CI ошибочно тоже продвигает задачу.
        """
        self.set_state("verifying")

        for make_ci in (red_ci, none_ci, running_ci):
            with self.subTest(ci=make_ci.__name__):
                with make_ci():
                    self.advance()
                self.assertEqual(self.state(), "verifying",
                                 f"{make_ci.__name__}: verifying сдвинулась "
                                 f"с места без зелёного CI")

        with green_ci():
            self.advance()
        self.assertEqual(self.state(), "review",
                         "зелёный CI не перевёл verifying в review")


if __name__ == "__main__":
    import unittest
    unittest.main()
