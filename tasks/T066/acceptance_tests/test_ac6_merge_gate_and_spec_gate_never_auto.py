"""AC-6 (tasks/T066/SPEC.md): гейты `merge_gate` и `spec_gate` не получают
автоматического пути ни при какой политике, введённой этой задачей —
даже если `gates.yaml` по ошибке (или по будущему недосмотру) объявляет
для них `auto`, эта задача обязана не давать этому значению никакого
эффекта: `advance` двигает только `acceptance`, `spec_gate`/`merge_gate`
по-прежнему проходит только `approve` Оператора.

`gates.yaml` в этом файле намеренно объявляет `spec_gate: auto` и
`merge_gate: auto` вместе с `acceptance: manual` — сценарий специально
сталкивает наивную реализацию (которая читала бы политику ЛЮБОГО гейта
одинаково) с требованием SPEC «только acceptance», а не изобретает
несуществующий сценарий.

Зелёный с рождения: сегодня `gates.yaml` не читается вовсе — `advance`
из `spec_gate`/`merge_gate` уже безусловно падает в общую ветку
«двигается через approve/reject/run» (`orchestrator/fsm.py`), при любом
содержимом `gates.yaml`. Регрессионный якорь на «эта задача не имеет
права придать значение auto/merge_gate/spec_gate какой-либо эффект» —
обязан остаться зелёным и после кода задачи.
"""
import unittest

from _sandbox import GATES_MERGE_AND_SPEC_ALSO_AUTO, AutogateSandbox  # noqa: E402
from orchestrator import fsm  # noqa: E402

GENERIC_GATE_MESSAGE = "двигается через approve/reject/run"


class SpecGateAndMergeGateIgnoreAutoPolicyTest(AutogateSandbox):

    def setUp(self):
        super().setUp()
        self.write_gates_policy(GATES_MERGE_AND_SPEC_ALSO_AUTO)

    def test_ac6_spec_gate_with_auto_policy_still_needs_operator_approve(self):
        self.set_state("spec_gate")

        for _ in range(3):
            out = self.capture(fsm.cmd_advance, self.TASK)
            self.assertEqual(self.state(), "spec_gate")
            self.assertIn(GENERIC_GATE_MESSAGE, out)

    def test_ac6_merge_gate_with_auto_policy_still_needs_operator_approve(self):
        self.set_state("merge_gate")

        for _ in range(3):
            out = self.capture(fsm.cmd_advance, self.TASK)
            self.assertEqual(self.state(), "merge_gate")
            self.assertIn(GENERIC_GATE_MESSAGE, out)


if __name__ == "__main__":
    unittest.main()
