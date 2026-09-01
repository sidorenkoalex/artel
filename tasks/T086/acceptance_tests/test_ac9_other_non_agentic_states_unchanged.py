"""AC-9 (tasks/T086/SPEC.md): поведение `auto` на состояниях без
агентной роли, отличных от `verifying` (`spec_gate`, `acceptance`,
`merge_gate`, `escalated`, `done`, `killed`), не меняется: цикл
останавливается на входе в них, как и раньше.

Список состояний — дословно из формулировки AC-9, не домысел свипа по
всем состояниям FSM (тот уже существует в `tests/test_auto_cycle.py`
как часть основного набора и после этой задачи станет обязанностью
разработчика поправить под новую верифицирующую ветку — здесь же
предмет ИМЕННО шести названных состояний).

Зелёный с рождения: ни `spec_gate`, `acceptance`, `merge_gate`,
`escalated`, `done`, ни `killed` эта задача не трогает (требование 6
SPEC, «поведение auto на прочих состояниях без агентной роли... не
меняется») — сегодняшний код уже останавливает цикл на входе в любое из
них (`runner.step_role` возвращает `None`, тело `while role is not
None` не выполняется). Тест фиксирует это поведение как планку: если
реализация требования 1 (новая ветка для verifying) случайно захватит
более широкое условие и погонит цикл дальше входа в одно из ЭТИХ шести
состояний, тест покраснеет.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import auto  # noqa: E402
from _sandbox import VerifyingTest  # noqa: E402

# Дословно из AC-9.
OTHER_NON_AGENTIC_STATES = ("spec_gate", "acceptance", "merge_gate",
                            "escalated", "done", "killed")


class VerifyingOtherNonAgenticStatesUnchangedTest(VerifyingTest):

    def test_ac9_cycle_stops_immediately_on_each_state(self):
        # `VerifyingTest.setUp` патчит `runner.cmd_run` на бросок
        # `AssertionError` при любом вызове (см. `_sandbox.py`) — если
        # цикл ошибочно погонит агента из одного из этих состояний,
        # subTest упадёт этим исключением раньше, чем дойдёт до
        # ассертов ниже; отдельно проверять «агент не звался» тут
        # незачем — сам факт возврата из `auto.cmd_auto` это доказывает.
        for state in OTHER_NON_AGENTIC_STATES:
            with self.subTest(состояние=state):
                self.set_state(state)

                auto.cmd_auto(self.TASK)

                self.assertEqual(
                    self.state(), state,
                    f"цикл не имеет права сдвинуть задачу из {state} — "
                    f"это состояние без агентной роли, вне зоны этой "
                    f"задачи (AC-9)")


if __name__ == "__main__":
    unittest.main()
