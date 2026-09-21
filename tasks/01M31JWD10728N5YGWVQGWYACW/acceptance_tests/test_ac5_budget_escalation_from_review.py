"""Приёмочный тест 01M31JWD10728N5YGWVQGWYACW — AC-5: эскалация по бюджету
из состояния `review` ведёт себя как сегодня — запись возврата анкером
рубежа не становится, и шаг роли, отработанный ДО эскалации,
засчитывается.

Зелёный с рождения: это существующее поведение (SPEC
01M1VBEDGMEXHVGWAH42FTDZ4X, требование 2), которое правка обязана
сохранить — эскалация по бюджету собственного основания переделки не
несёт, разрешать ей нечего, кроме поднятого потолка. Тест фиксирует
границу правки: маркер ставит ИМЕННО `_review_escalate`, а не любой
переход в `escalated` из `review`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ReviewEscalationSandbox  # noqa: E402
from orchestrator import auto, budget, fsm, store  # noqa: E402

REVIEW_ENTRY_DETAIL = "CI зелёный — вход в ревью"


class BudgetEscalationFromReviewKeepsItsBehaviourTest(ReviewEscalationSandbox):

    def test_ac5_budget_escalation_from_review_return_is_not_an_anchor(self):
        """Задача вошла в `review`, ревьювер отработал шаг, потолок
        исчерпан — `enforce_budget` уводит её в `escalated` из `review`;
        Оператор возвращает её `approve`. Маркера «ответ должен дойти до
        роли» в журнале нет, а рубеж по-прежнему отвечает «шаг роли был»,
        считая анкером вход в `review`, а не запись возврата.

        Ловит мутацию: `_mark_artifact_escalation` вызван не в
        `_review_escalate`, а выше по стеку — в `fsm_advance.review` до
        разбора вердикта или в общем узле перехода в `escalated` — тогда
        маркер поставит и бюджетная эскалация, запись возврата станет
        анкером, и `ran` станет `False`: пульт потребует лишнего шага роли
        там, где раньше продолжал работу.
        """
        self.journal("fsm", "state -> review", REVIEW_ENTRY_DETAIL)
        self.journal("reviewer", "agent run finished", "rc=0")
        self.set_state("review", budget_usd=1.0, spent_usd=2.0)

        conn = store.db()
        escalated = budget.enforce_budget(conn, self.TASK, "review")

        self.assertTrue(escalated, "потолок не сработал — сценарий не "
                        "воспроизведён")
        self.assertEqual(self.state(), "escalated")
        self.assertNotIn(
            fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER, self.actions(),
            "эскалация по бюджету пометила себя маркером «ответ Оператора "
            "должен дойти до роли» — она такого основания не несёт")

        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "review",
                         "бюджетная эскалация вернула задачу не туда, "
                         "откуда эскалировала")

        ran, anchor_detail = auto._role_step_since_state_entry(
            conn, self.TASK, "review", "reviewer")

        self.assertTrue(
            ran, "запись возврата из бюджетной эскалации стала анкером — "
            "шаг ревьювера, отработанный до эскалации, перестал "
            "засчитываться")
        self.assertEqual(
            anchor_detail, REVIEW_ENTRY_DETAIL,
            "анкером рубежа стала не запись входа в review")


if __name__ == "__main__":
    unittest.main()
