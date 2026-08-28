"""AC-1, AC-2, AC-3 (tasks/T066/SPEC.md).

AC-1: политика `gates.yaml` acceptance=`auto` + все условия автопрохода
выполнены -> переход `review -> acceptance -> merge_gate` одним
действием, без операторского `approve`.

AC-2: та же ситуация -> в журнале запись с `actor=autogate` и перечнем
выполненных условий.

AC-3: та же ситуация -> вывод команды явно сообщает «acceptance пройден
автогейтом (политика gates.yaml)».

Общий сценарий (см. `_sandbox.py::prepare_green_scenario`): один реальный
прогон `fsm.cmd_advance` из состояния `review` со всеми пятью условиями
SPEC требования 2 выполненными — три критерия проверяют три разных
наблюдаемых следствия ОДНОГО и того же прогона.

Красен до реализации: политики `gates.yaml` сегодня никто не читает
(`orchestrator/fsm.py`, переход `review -> acceptance` безусловно
останавливается в `acceptance`, автогейта нет вовсе) — до кода задачи
все три теста падают именно на этом: состояние остаётся `acceptance`
(не `merge_gate`), журнал не несёт `actor=autogate`, вывод не содержит
фразу «пройден автогейтом».
"""
import re
import unittest

from _sandbox import AutogateSandbox  # noqa: E402
from orchestrator import fsm  # noqa: E402


class AutogatePassesAllConditionsTest(AutogateSandbox):

    def setUp(self):
        super().setUp()
        self.prepare_green_scenario()
        self.out = self.capture(fsm.cmd_advance, self.TASK)

    def test_ac1_review_to_merge_gate_in_one_action_without_operator_approve(self):
        self.assertEqual(
            self.state(), "merge_gate",
            "все условия SPEC требования 2 выполнены — автогейт обязан "
            "продвинуть задачу до merge_gate одним вызовом advance, без "
            "operator approve (который в этом тесте вовсе не вызывался)")

    def test_ac2_journal_carries_autogate_actor_and_a_list_of_conditions(self):
        autogate_rows = [r for r in self.journal_rows() if r[0] == "autogate"]
        self.assertTrue(
            autogate_rows,
            f"ожидалась хотя бы одна запись журнала с actor=autogate; "
            f"журнал: {self.journal_rows()}")
        detail = "\n".join(r[2] for r in autogate_rows)
        items = [x for x in re.split(r"[;\n]", detail) if x.strip()]
        self.assertGreaterEqual(
            len(items), 2,
            f"AC-2 требует «перечень выполненных условий» (не одну "
            f"фразу): {detail!r}")

    def test_ac3_output_names_the_autogate_pass_explicitly(self):
        self.assertIn("acceptance пройден автогейтом (политика gates.yaml)",
                      self.out)


if __name__ == "__main__":
    unittest.main()
