"""Приёмочные тесты T070 — AC-8 (SPEC.md).

Красен до реализации: `orchestrator.pause` ещё не существует — см.
`_sandbox.py`.

Допущения интерфейса — см. `_sandbox.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PauseSandbox, invoke, pause  # noqa: E402


class Ac8SuccessfulPauseAndResumeJournalActorOperatorTest(PauseSandbox):
    """AC-8: успешные `pause` и `resume` добавляют в журнал задачи запись
    с actor `operator`."""

    def test_ac8_successful_pause_journals_actor_operator(self):
        self.set_state("in_dev")
        journalled_before = self.journal_len()

        invoke(lambda: pause.cmd_pause(self.TASK))

        rows = self.journal_tail(journalled_before)
        self.assertTrue(rows, "успешный pause не записал в журнал задачи")
        self.assertTrue(
            any(r["actor"] == "operator" for r in rows),
            f"ни одна запись журнала после pause не несёт actor=operator: "
            f"{[dict(r) for r in rows]}")

    def test_ac8_successful_resume_journals_actor_operator(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))
        journalled_before = self.journal_len()

        invoke(lambda: pause.cmd_resume(self.TASK))

        rows = self.journal_tail(journalled_before)
        self.assertTrue(rows, "успешный resume не записал в журнал задачи")
        self.assertTrue(
            any(r["actor"] == "operator" for r in rows),
            f"ни одна запись журнала после resume не несёт actor=operator: "
            f"{[dict(r) for r in rows]}")


if __name__ == "__main__":
    import unittest
    unittest.main()
