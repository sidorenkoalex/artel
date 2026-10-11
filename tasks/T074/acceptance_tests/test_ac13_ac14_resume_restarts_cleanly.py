"""Приёмочные тесты T074 — AC-13, AC-14.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-13. После `resume <id>` команда `auto <id>` (или `run <id>`)
перезапускает шаг заново, стартуя от зачекпоинченного состояния
worktree — как после таймаута T041.

AC-14. Сверка целостности (`fixation.check_integrity`) на рестарте после
`pause --now` не порождает инцидент «грязная копия артефактов»: чекпоинт
закрывает дерево до выхода команды `pause --now`.

Тот же сценарий и тот же довод, что `tasks/T041/acceptance_tests/
test_checkpoint_after_timeout.py::test_ac2_restart_after_checkpoint_does_not_escalate`
— только прерывание бегущего шага здесь идёт `pause --now` на РЕАЛЬНОМ
процессе, а не таймаутом `proc.wait()`.

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, fixation, pause, runner, store  # noqa: E402

from tests.sandbox import FakeProc  # noqa: E402


class ResumeRestartsCleanlyTest(InterruptSandbox):

    def interrupt_running_step(self) -> None:
        self.enter_in_dev()
        proc = self.spawn_sleep_process()
        self.install_lease(proc.pid)
        self.write_dirty_wip()
        self.capture(pause.cmd_pause_now, self.TASK)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass

    def test_ac14_integrity_check_reports_no_incident_right_after_pause_now(self):
        self.interrupt_running_step()

        incident = fixation.check_integrity(store.db(), self.TASK)

        self.assertIsNone(
            incident,
            f"AC-14: сверка целостности сразу после pause --now не "
            f"должна находить инцидент «грязная копия артефактов» — "
            f"фактически: {incident!r}")

    def test_ac13_run_after_resume_restarts_from_the_checkpoint(self):
        self.interrupt_running_step()
        self.capture(pause.cmd_resume, self.TASK)

        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = self.capture(runner.cmd_run, self.TASK)

        popen.assert_called_once()
        self.assertNotIn(
            "инцидент целостности", out,
            f"AC-13: рестарт после pause --now не должен эскалировать "
            f"задачу по «грязной копии» хвостов прерванного шага — "
            f"фактический вывод: {out!r}")
        self.assertEqual(
            self.task_row()["state"], "in_dev",
            f"AC-13: рестарт шага после чекпоинта обязан пройти без "
            f"эскалации — фактический вывод: {out!r}")


if __name__ == "__main__":
    unittest.main()
