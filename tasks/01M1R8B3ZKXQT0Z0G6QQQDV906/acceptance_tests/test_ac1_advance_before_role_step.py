"""AC-1 (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906): на каждой итерации цикла
`auto`, где у текущего состояния есть агентная роль (кроме `verifying`),
`auto` вызывает `fsm.cmd_advance` для этого состояния ДО `runner.cmd_run`.

Красен до реализации: нынешний `orchestrator/auto.py::_cmd_auto`
(до этой задачи) зовёт `runner.cmd_run`, а `fsm.cmd_advance` — уже
ПОСЛЕ него (SPEC T038, «run+advance») — порядок обратный тому, что
требует AC-1; `self.events` содержал бы `["run", "advance"]`, не
`["advance", "run"]`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import AutoAdvanceOrderSandbox  # noqa: E402

from orchestrator import auto, config  # noqa: E402


class Ac1AdvanceBeforeRoleStepTest(AutoAdvanceOrderSandbox):

    def setUp(self) -> None:
        super().setUp()
        # Один шаг за вызов: и `advance`, и `run` (если он вообще
        # случится) обязаны попасть в `self.events` ровно по разу —
        # лимит выше усложнил бы чтение порядка второй парой вызовов.
        self.patch_object(config, "AUTO_MAX_STEPS", 1)

    def test_ac1_advance_is_called_before_run_for_every_role_state(self):
        """Для каждого состояния из `config.STATE_ROLE` («tests_writing»,
        «in_dev», «review» — `verifying` требование 1 исключает явно,
        своя механика `_advance_verifying_poll`) один шаг цикла — при
        отказе advance классом «артефакт не готов» — вызывает `fsm.
        cmd_advance` раньше `runner.cmd_run`.

        Ловит мутацию: цикл, сохранивший старый порядок «run, затем
        advance» (T038) хотя бы для одного состояния — `self.events`
        для него начинался бы с `("run", ...)`, а не с `("advance", ...)`.
        """
        for state in config.STATE_ROLE:
            with self.subTest(состояние=state):
                self.events.clear()
                self.advance.script = []
                self.advance.arm_not_ready()
                self.set_state(state)

                self.capture(auto.cmd_auto, self.TASK)

                self.assertEqual(
                    [kind for kind, _ in self.events], ["advance", "run"],
                    f"состояние {state}: порядок вызовов — {self.events}")


if __name__ == "__main__":
    unittest.main()
