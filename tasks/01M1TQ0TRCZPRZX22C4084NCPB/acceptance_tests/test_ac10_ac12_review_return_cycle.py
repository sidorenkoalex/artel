"""Приёмочные тесты 01M1TQ0TRCZPRZX22C4084NCPB — AC-10, AC-11, AC-12:
возврат из ревью (`changes_requested`), повторный вход в ревью СНОВА
через `verifying`, счётчики итераций/лимит не меняются.

AC-10 (возврат `changes_requested -> in_dev`) сохраняет уже
существующее поведение `orchestrator/fsm_advance.py::review` (ветка
`elif status == "changes_requested"`, строки 271-283) — эта задача её
не трогает, тест зелёный уже сегодня (см. маркер класса ниже).

AC-11 (повторный вход СНОВА через verifying) и AC-12 (лимит итераций
как сегодня, только на новом маршруте) — красны до реализации:
`orchestrator/fsm_advance.py::in_dev` сегодня ведёт ЛЮБОЙ (не только
первый) выход из `in_dev` прямиком в `review` (строка 1005), минуя
`verifying`, — второй вход в review при действующем сегодня коде не
отличается от первого.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FsmOrderScenarioTest, green_ci  # noqa: E402
from orchestrator import config  # noqa: E402


class ReviewReturnCycleTest(FsmOrderScenarioTest):

    def enter_review_first_time(self) -> None:
        self.enter_in_dev_ready()
        self.advance()  # in_dev -> verifying
        with green_ci():
            self.advance()  # verifying -> review
        self.assertEqual(self.state(), "review",
                         "подготовка сценария не довела задачу до review")

    def reenter_review_via_verifying(self) -> None:
        self.advance()  # in_dev -> verifying (снова)
        self.assertEqual(self.state(), "verifying",
                         "повторный вход в in_dev не ведёт снова через "
                         "verifying")
        with green_ci():
            self.advance()  # verifying -> review (снова)

    def test_ac10_changes_requested_returns_to_in_dev(self):
        """Зелёный с рождения: ветка `changes_requested` в `review()`
        (fsm_advance.py:271-283) не входит в зону этой задачи и не
        меняется — этот тест закрепляет, что реорганизация переходов
        вокруг неё не сломала само правило «замечания — в in_dev».

        Ловит мутацию: возврат `changes_requested` ошибочно ведёт куда-то
        ещё (например, в `verifying` напрямую, минуя решение разработчика)
        — состояние после advance не совпало бы с 'in_dev'.
        """
        self.enter_review_first_time()

        self.write_review("changes_requested", 1)
        self.advance()

        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.task_row()["review_iters"], 1)

    def test_ac11_second_entry_into_review_goes_through_verifying_again(self):
        """После возврата с `changes_requested` и повторного выхода из
        `in_dev` задача СНОВА проходит через `verifying` (ждёт зелёного
        CI), а не попадает в `review` напрямую вторым заходом.

        Ловит мутацию: `in_dev` ведёт в `verifying` только на ПЕРВОМ
        выходе из состояния (например, по признаку «reviewed_iter == 0»),
        а повторные выходы после `changes_requested` по-старому идут
        прямиком в `review` — `reenter_review_via_verifying` упадёт на
        своём собственном assert, до второго `advance`.
        """
        self.enter_review_first_time()
        self.write_review("changes_requested", 1)
        self.advance()
        self.assertEqual(self.state(), "in_dev")

        self.reenter_review_via_verifying()

        self.assertEqual(self.state(), "review")

    def test_ac12_review_iteration_limit_still_applies_after_reorder(self):
        """Лимит `config.LIMIT_REVIEW_ITERS` итераций ревью и поведение на
        нём (эскалация, счётчик не растёт сверх лимита) — как сегодня,
        только каждый повторный заход теперь идёт через `verifying`.

        Ловит мутацию: лимит перестал срабатывать на новом маршруте
        (например, из-за путаницы, на каком именно "review" итерация
        считается) — финальный `changes_requested` увёл бы задачу назад
        в `in_dev` вместо `escalated`, либо счётчик вырос бы сверх
        `LIMIT_REVIEW_ITERS - 1`.
        """
        self.enter_review_first_time()
        limit = config.LIMIT_REVIEW_ITERS

        for iteration in range(1, limit):
            self.write_review("changes_requested", iteration)
            self.advance()
            self.assertEqual(self.state(), "in_dev")
            self.assertEqual(self.task_row()["review_iters"], iteration)

            self.reenter_review_via_verifying()
            self.assertEqual(self.state(), "review")

        self.write_review("changes_requested", limit)
        self.advance()

        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.task_row()["review_iters"], limit - 1,
                         "лимит достигнут — счётчик не должен вырасти "
                         "сверх значения до последней итерации")


if __name__ == "__main__":
    import unittest
    unittest.main()
