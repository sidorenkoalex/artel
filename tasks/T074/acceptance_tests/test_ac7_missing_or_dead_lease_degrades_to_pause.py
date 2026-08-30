"""Приёмочные тесты T074 — AC-7.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-7. Lease задачи не найден или его процесс уже мёртв — `pause --now`
не завершается ошибкой: печатает честное сообщение и деградирует до
обычного `pause`.

Два независимых предусловия критерия («lease нет» И «lease есть, но его
процесс мёртв») — двумя тестовыми методами: `dead_pid()` (тот же приём,
что `tests/test_doctor.py::dead_pid` — реальный процесс, запущенный и
тут же дождавшийся своего конца) даёт заведомо мёртвый, но синтаксически
валидный pid.

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, pause  # noqa: E402


class MissingOrDeadLeaseDegradesTest(InterruptSandbox):

    def test_ac7_no_lease_degrades_to_plain_pause_without_error(self):
        self.enter_in_dev()
        self.assertIsNone(self.lease_row(), "предусловие: lease не заведён")

        out = self.capture(pause.cmd_pause_now, self.TASK)

        self.assertTrue(
            pause.is_paused(self.task_row()),
            "AC-7: без lease pause --now обязана деградировать до "
            "обычной pause — пометка паузы должна стоять")
        self.assertTrue(
            out.strip(),
            "AC-7: отсутствие lease должно быть честно сообщено, не "
            "провалено молча")

    def test_ac7_dead_lease_process_degrades_to_plain_pause_without_error(self):
        self.enter_in_dev()
        self.install_lease(self.dead_pid())

        out = self.capture(pause.cmd_pause_now, self.TASK)

        self.assertTrue(
            pause.is_paused(self.task_row()),
            "AC-7: мёртвый процесс lease обязан деградировать до "
            "обычной pause — пометка паузы должна стоять")
        self.assertTrue(
            out.strip(),
            "AC-7: мёртвый lease-процесс должен быть честно сообщён, не "
            "провален молча")


if __name__ == "__main__":
    unittest.main()
