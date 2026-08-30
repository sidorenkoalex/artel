"""Приёмочные тесты T070 — AC-4, AC-5 (SPEC.md).

Красен до реализации: `orchestrator.pause` ещё не существует — см.
`_sandbox.py`.

Допущения интерфейса — см. `_sandbox.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PauseSandbox, fsm, invoke, mock, pause, runner  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import auto  # noqa: E402


class Ac4ResumeLetsRunAndAutoStartAgainTest(PauseSandbox):
    """AC-4: `resume <id>` снимает пометку паузы — `auto`/`run`,
    запущенные после `resume`, снова начинают агентные шаги как обычно."""

    def test_ac4_run_starts_the_agent_step_after_resume(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))

        invoke(lambda: pause.cmd_resume(self.TASK))
        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK))

        self.assertTrue(
            popen.called,
            f"run не стартовал агентный шаг после resume: {out!r}")

    def test_ac4_auto_starts_the_agent_step_after_resume(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))

        invoke(lambda: pause.cmd_resume(self.TASK))
        out, popen = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id="session-auto"))

        self.assertTrue(
            popen.called,
            f"auto не стартовал агентный шаг после resume: {out!r}")


class Ac5ResumeItselfDoesNotRunStepOrAdvanceTest(PauseSandbox):
    """AC-5: `resume` сама по себе не запускает ни агентный шаг, ни
    `advance` — только снимает пометку и пишет журнал."""

    def test_ac5_resume_does_not_spawn_agent_or_call_advance(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))
        before_state = self.state()

        with mock.patch.object(runner, "spawn_agent") as popen, \
             mock.patch.object(fsm, "cmd_advance") as advance_mock:
            invoke(lambda: pause.cmd_resume(self.TASK))

        popen.assert_not_called()
        advance_mock.assert_not_called()
        self.assertEqual(self.state(), before_state,
                         "resume сам по себе не должен был сдвинуть состояние")


if __name__ == "__main__":
    import unittest
    unittest.main()
