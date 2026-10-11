"""AC-7 (tasks/T050/SPEC.md): `kill`, вызванный для задачи, уже
находящейся в `done` или `killed`, сообщает об этом и завершается без
ошибки.

Песочница — `tests.test_invariants.FsmTest`, тем же приёмом, что
`tasks/T044/acceptance_tests/test_lease_enforcement.py`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import cleanup  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402


class KillOnTerminalStateTest(FsmTest):

    def _kill_output(self) -> str:
        # `self.capture` не глотает исключения — sys.exit/иное здесь
        # обвалит тест, что и требуется («без ошибки»).
        return self.capture(cleanup.cmd_kill, self.TASK)

    def test_ac7_kill_on_done_task_reports_and_does_not_raise(self):
        self.set_state("done")

        output = self._kill_output()

        self.assertEqual(self.state(), "done")
        self.assertTrue(output.strip(),
                        "kill не сообщил, что задача уже done")

    def test_ac7_kill_on_already_killed_task_reports_and_does_not_raise(self):
        self.set_state("killed")

        output = self._kill_output()

        self.assertEqual(self.state(), "killed")
        self.assertTrue(output.strip(),
                        "kill не сообщил, что задача уже killed")


if __name__ == "__main__":
    unittest.main()
