"""Приёмочные тесты T074 — AC-1, AC-6.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-1. `pause --now <id>` на задаче с бегущим агентным шагом в другом
процессе той же машины (параллельная CLI-сессия или фоновый `auto`)
корректно завершает процесс агента.

AC-6. Адресация бегущего шага в другом процессе выполняется через данные
lease задачи (pid, host).

Оба критерия проверяются одним сценарием: два РЕАЛЬНЫХ дочерних процесса
(`InterruptSandbox.spawn_sleep_process`, тот же приём, что `tests/
test_doctor.py::dead_pid`, только без немедленного `wait()`) — один
записан в lease задачи, другой нет. `pause --now` обязана прервать ТОЛЬКО
адресованный по lease процесс: если бы адресация шла как-то иначе (весь
процесс-дерево машины, текущий pid вызывающего и т.п.), тест поймал бы
это по выжившему адресованному процессу или убитому постороннему.

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, pause  # noqa: E402


class TerminatesProcessAddressedByLeaseTest(InterruptSandbox):

    def test_ac1_running_agent_process_is_terminated(self):
        self.enter_in_dev()
        target = self.spawn_sleep_process()
        self.install_lease(target.pid)
        self.assertIsNone(target.poll(), "предусловие: процесс ещё жив")

        self.capture(pause.cmd_pause_now, self.TASK)

        try:
            target.wait(timeout=10)
        except Exception:
            pass
        self.assertIsNotNone(
            target.poll(),
            "AC-1: процесс, адресованный по lease задачи, обязан быть "
            "завершён `pause --now`")

    def test_ac6_addressing_uses_lease_pid_not_something_else(self):
        self.enter_in_dev()
        addressed = self.spawn_sleep_process()
        bystander = self.spawn_sleep_process()
        self.install_lease(addressed.pid)

        self.capture(pause.cmd_pause_now, self.TASK)

        try:
            addressed.wait(timeout=10)
        except Exception:
            pass
        self.assertIsNotNone(
            addressed.poll(),
            "AC-6: процесс с pid, лежащим в lease задачи, обязан быть "
            "завершён")
        self.assertIsNone(
            bystander.poll(),
            "AC-6: посторонний процесс, не адресованный lease задачи, "
            "не должен быть тронут — адресация обязана идти строго по "
            "данным lease, не по всему дереву процессов машины")


if __name__ == "__main__":
    unittest.main()
