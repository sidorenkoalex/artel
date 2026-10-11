"""Приёмочные тесты T070 — AC-1, AC-2 (SPEC.md).

Красен до реализации: `orchestrator.pause` ещё не существует — импорт
из `_sandbox.py` падает `ModuleNotFoundError` до тех пор, пока
разработчик не заведёт модуль (требования 1-2 SPEC).

Допущения интерфейса — см. `_sandbox.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PauseSandbox, invoke, mock, pause, runner  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import auto  # noqa: E402


class Ac1PauseBlocksRunFromStartingAgentStepTest(PauseSandbox):
    """AC-1: `pause <id>` ставит пометку так, что запущенный после этого
    `run` (одиночный или как часть `auto`) не начинает агентный шаг."""

    def test_ac1_run_does_not_start_agent_step_after_pause(self):
        self.set_state("in_dev")

        out_pause, _ = invoke(lambda: pause.cmd_pause(self.TASK))

        out_run, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK))

        popen.assert_not_called()
        self.assertEqual(
            self.state(), "in_dev",
            f"run на паузе не должен был сдвинуть состояние: "
            f"pause={out_pause!r}, run={out_run!r}")

    def test_ac1_auto_does_not_start_agent_step_after_pause(self):
        self.set_state("in_dev")

        invoke(lambda: pause.cmd_pause(self.TASK))

        out, popen = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id="session-auto"))

        popen.assert_not_called()
        self.assertEqual(
            self.state(), "in_dev",
            f"auto на паузе не должен был сдвинуть состояние: {out!r}")


class Ac2RunRefusalIsFriendlyAndJournalledTest(PauseSandbox):
    """AC-2: отказ `run`/`auto` запустить агентный шаг из-за паузы
    сопровождается понятным сообщением (без стектрейса) и записью в
    журнале задачи."""

    def _assert_clean_refusal(self, call) -> str:
        """Зовёт `call` напрямую (не через `invoke`) — любое исключение,
        кроме `SystemExit`, здесь и есть дефект: SPEC явно требует «без
        ошибки/стектрейса». Отказ мог уйти любым из двух путей — печатью
        в stdout или текстом `sys.exit` (как `budget_block`) — оба
        собираются в одну строку, тот же приём, что и `_invoke` в
        `tasks/T062/acceptance_tests/test_ac1_ac2_ac3_ac5_release_command.py`."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                call()
        except SystemExit as exc:
            return buf.getvalue() + str(exc)
        except Exception as exc:  # noqa: BLE001 — сам предмет критерия
            self.fail(f"отказ паузы упал исключением вместо штатного "
                     f"сообщения: {exc!r}")
        return buf.getvalue()

    def test_ac2_run_refusal_prints_message_and_journals_without_traceback(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))
        journalled_before = self.journal_len()

        with mock.patch.object(runner, "spawn_agent") as popen:
            out = self._assert_clean_refusal(lambda: runner.cmd_run(self.TASK))

        popen.assert_not_called()
        self.assertTrue(out.strip(),
                        "run на паузе не напечатал понятное сообщение")
        self.assertNotIn("Traceback", out)
        journal = self.journal_tail_text(journalled_before)
        self.assertTrue(journal.strip(),
                        "run на паузе не записал отказ в журнал задачи")

    def test_ac2_auto_refusal_prints_message_and_journals_without_traceback(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))
        journalled_before = self.journal_len()

        with mock.patch.object(runner, "spawn_agent") as popen:
            out = self._assert_clean_refusal(
                lambda: auto.cmd_auto(self.TASK, session_id="session-auto"))

        popen.assert_not_called()
        self.assertTrue(out.strip(),
                        "auto на паузе не напечатал понятное сообщение")
        self.assertNotIn("Traceback", out)
        journal = self.journal_tail_text(journalled_before)
        self.assertTrue(journal.strip(),
                        "auto на паузе не записал отказ в журнал задачи")


if __name__ == "__main__":
    import unittest
    unittest.main()
