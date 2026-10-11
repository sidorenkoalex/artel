"""Приёмочные тесты T070 — AC-12, AC-13 (SPEC.md).

Красен до реализации: `orchestrator.pause` ещё не существует — см.
`_sandbox.py`.

Допущения интерфейса — см. `_sandbox.py`.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PauseSandbox, invoke, pause, runner  # noqa: E402


def _call_without_traceback(test: PauseSandbox, call) -> str:
    """Зовёт `call` напрямую (не через `invoke`) — любое исключение,
    кроме `SystemExit`, здесь дефект: оба критерия явно требуют «не
    завершается ошибкой/стектрейсом». Сообщение могло уйти любым из двух
    путей — печатью в stdout или текстом `sys.exit` — оба собираются в
    одну строку, тот же приём, что и `_invoke` в `tasks/T062/
    acceptance_tests/test_ac1_ac2_ac3_ac5_release_command.py`."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        return buf.getvalue() + str(exc)
    except Exception as exc:  # noqa: BLE001 — сам предмет критерия
        test.fail(f"команда упала исключением вместо штатного "
                 f"отказа/no-op: {exc!r}")
    return buf.getvalue()


class Ac12RepeatedPauseIsNotAnErrorTest(PauseSandbox):
    """AC-12: повторный `pause` уже приостановленной задачи не
    завершается ошибкой/стектрейсом — печатает понятное сообщение, что
    задача уже на паузе."""

    def test_ac12_pause_of_an_already_paused_task_prints_friendly_message(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))

        out = _call_without_traceback(self, lambda: pause.cmd_pause(self.TASK))

        self.assertTrue(out.strip(),
                        "повторный pause не напечатал сообщение")
        self.assertNotIn("Traceback", out)

    def test_ac12_task_remains_paused_after_the_repeated_pause(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))
        _call_without_traceback(self, lambda: pause.cmd_pause(self.TASK))

        _, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK))

        popen.assert_not_called()


class Ac13ResumeOfNotPausedTaskIsNotAnErrorTest(PauseSandbox):
    """AC-13: `resume` задачи, не находящейся на паузе, не завершается
    ошибкой/стектрейсом — печатает понятное сообщение, что задача не
    была на паузе."""

    def test_ac13_resume_of_a_not_paused_task_prints_friendly_message(self):
        self.set_state("in_dev")

        out = _call_without_traceback(self, lambda: pause.cmd_resume(self.TASK))

        self.assertTrue(out.strip(),
                        "resume не приостановленной задачи не напечатал "
                        "сообщение")
        self.assertNotIn("Traceback", out)

    def test_ac13_run_still_works_normally_after_the_noop_resume(self):
        self.set_state("in_dev")
        _call_without_traceback(self, lambda: pause.cmd_resume(self.TASK))

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK))

        self.assertTrue(
            popen.called,
            f"resume неприостановленной задачи не должен был помешать "
            f"обычному run: {out!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
