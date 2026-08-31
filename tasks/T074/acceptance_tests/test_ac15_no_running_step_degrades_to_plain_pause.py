"""Приёмочные тесты T074 — AC-15.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-15. `pause --now <id>` на задаче без бегущего агентного шага
деградирует до обычного `pause` и печатает сообщение об этой
деградации.

Отличается от AC-7 (`test_ac7_missing_or_dead_lease_degrades_to_pause.py`)
предусловием: там задача в агентном состоянии (`in_dev`), но lease
случайно нет/протух; здесь задача в состоянии, где агентного шага в
принципе НЕТ (`spec_gate` — гейт решения Оператора, не роль,
`orchestrator/config.py::STATE_ROLE`) — тот же наблюдаемый механизм
(деградация до `cmd_pause`), но другое предусловие критерия.

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, pause  # noqa: E402


class NoRunningStepDegradesTest(InterruptSandbox):

    def test_ac15_task_without_agent_step_degrades_to_plain_pause(self):
        self.enter_spec_gate()
        self.assertIsNone(
            self.lease_row(), "предусловие: гейт — не агентный шаг, lease нет")

        out = self.capture(pause.cmd_pause_now, self.TASK)

        self.assertTrue(
            pause.is_paused(self.task_row()),
            "AC-15: без бегущего агентного шага pause --now обязана "
            "деградировать до обычной pause — пометка паузы должна "
            "стоять")
        self.assertTrue(
            out.strip(),
            "AC-15: деградация обязана быть честно напечатана Оператору, "
            "не пройти молча")


if __name__ == "__main__":
    unittest.main()
