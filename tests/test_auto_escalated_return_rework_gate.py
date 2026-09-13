"""Юнит-тесты `orchestrator.auto._role_step_since_state_entry` (SPEC
01M1VBEDGMEXHVGWAH42FTDZ4X, требование 2): анкер рубежа «возврат не
отработан» — ПОСЛЕДНИЙ возврат из `review`/reject, не запись возврата из
`escalated`, которая могла появиться позже него.

Приёмочные тесты (`tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/
test_ac5_ac6_ac7_escalated_return_gate.py`,
`test_ac12_ac13_escalated_return_regression.py`) кроют AC-5..AC-7/AC-12/
AC-13 сквозным путём через `auto.cmd_auto`; здесь — сама функция в
изоляции, без цикла `auto`/lease/FSM.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import auto, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

TASK_ID = "T001"


class RoleStepSinceStateEntryTest(SchemaConnTmpRootTest):

    def _journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(self.conn, TASK_ID, actor, action, detail)

    def test_no_entry_at_all_degrades_to_true(self):
        """Вырожденный случай: сверять нечем — не блокировать."""
        ran, detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertTrue(ran)
        self.assertIsNone(detail)

    def test_review_return_without_a_developer_step_blocks(self):
        self._journal("fsm", "state -> in_dev", "замечания ревью, итерация 1")

        ran, detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertFalse(ran)
        self.assertEqual(detail, "замечания ревью, итерация 1")

    def test_developer_step_after_the_review_return_unblocks(self):
        self._journal("fsm", "state -> in_dev", "замечания ревью, итерация 1")
        self._journal("developer", "agent run finished", "rc=0")

        ran, _detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertTrue(ran)

    def test_escalated_return_after_the_developer_step_does_not_hide_it(self):
        """AC-5: developer отработал ДО эскалации — запись возврата ИЗ
        escalated (`"эскалация разрешена, продолжаем"`), появившаяся
        ПОЗЖЕ, не должна маскировать уже засчитанный шаг."""
        self._journal("fsm", "state -> in_dev", "замечания ревью, итерация 1")
        self._journal("developer", "agent run finished", "rc=0")
        self._journal("fsm", "state -> escalated", "бюджет исчерпан")
        self._journal("operator", "state -> in_dev", "эскалация разрешена, продолжаем")

        ran, detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertTrue(
            ran, "запись возврата из escalated замаскировала уже "
            "отработанный шаг developer")
        self.assertEqual(detail, "замечания ревью, итерация 1")

    def test_budget_escalated_return_detail_is_ignored_the_same_way(self):
        """Второй известный текст возврата (`budget.cmd_budget`) — тот же
        класс, что и возврат `approve` из `escalated`."""
        self._journal("fsm", "state -> in_dev", "замечания ревью, итерация 1")
        self._journal("developer", "agent run finished", "rc=0")
        self._journal("fsm", "state -> escalated", "бюджет исчерпан")
        self._journal("operator", "state -> in_dev", "бюджет поднят, продолжаем")

        ran, detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertTrue(ran)
        self.assertEqual(detail, "замечания ревью, итерация 1")

    def test_escalated_return_with_no_developer_step_still_blocks(self):
        """AC-6/AC-7: без шага developer НИ ДО, ни ПОСЛЕ эскалации рубеж
        по-прежнему держит — возврат из escalated сам по себе не
        основание пропустить роль."""
        self._journal("fsm", "state -> in_dev", "замечания ревью, итерация 1")
        self._journal("fsm", "state -> escalated", "агент упал")
        self._journal("operator", "state -> in_dev", "эскалация разрешена, продолжаем")

        ran, detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertFalse(ran)
        self.assertEqual(detail, "замечания ревью, итерация 1")

    def test_developer_step_after_the_escalated_return_unblocks(self):
        """Симметрия AC-6: шаг, случившийся ПОСЛЕ возврата из escalated,
        засчитывается точно так же, как шаг до него."""
        self._journal("fsm", "state -> in_dev", "замечания ревью, итерация 1")
        self._journal("fsm", "state -> escalated", "агент упал")
        self._journal("operator", "state -> in_dev", "эскалация разрешена, продолжаем")
        self._journal("developer", "agent run finished", "rc=0")

        ran, _detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertTrue(ran)

    def test_legit_first_entry_detail_still_degrades_to_true(self):
        """ANSWER-3: легитимный первый вход не путается с возвратом из
        эскалации — правка не должна затронуть этот класс."""
        self._journal("fsm", "state -> in_dev",
                      "гейт SPEC пройден — приёмочные тесты до кода")

        ran, detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertTrue(ran)
        self.assertEqual(detail, "гейт SPEC пройден — приёмочные тесты до кода")

    def test_only_an_escalated_return_entry_is_the_degenerate_case(self):
        """Единственная запись `state -> in_dev` — сама запись возврата из
        escalated (первый вход задачи в in_dev минуя review вовсе, легаси
        песочницы без предшествующего review-возврата): анкера для
        рубежа нет — сверять не с чем, тот же вырожденный случай, что и
        полное отсутствие записи."""
        self._journal("operator", "state -> in_dev", "эскалация разрешена, продолжаем")

        ran, detail = auto._role_step_since_state_entry(
            self.conn, TASK_ID, "in_dev", "developer")

        self.assertTrue(ran)
        self.assertIsNone(detail)


if __name__ == "__main__":
    unittest.main()
