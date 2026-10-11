"""Приёмочные тесты T070 — AC-9, AC-10, AC-11 (SPEC.md).

Красен до реализации: `orchestrator.pause` ещё не существует — см.
`_sandbox.py`.

Допущения интерфейса — см. `_sandbox.py`. Переходы `acceptance ->
merge_gate` (`approve`) и `acceptance -> in_dev` (`reject`) — тот же
сквозной путь, что уже проверяет `tasks/T060/acceptance_tests/
test_max_parallel_tasks.py::Ac5GateAndReadonlyCommandsIgnoreLimiterTest`;
переход `spec_writing -> spec_gate` (`advance`) по готовому SPEC.md — тот
же путь, что `tests/test_invariants.py::FreshVerdictGuardsAcceptanceTest`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PauseSandbox, cleanup, fsm, invoke, pause  # noqa: E402


class Ac9KillIgnoresPauseTest(PauseSandbox):
    """AC-9: `kill` приостановленной задачи выполняется как обычно,
    независимо от пометки паузы."""

    def test_ac9_kill_works_on_a_paused_task_as_usual(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))

        invoke(lambda: cleanup.cmd_kill(self.TASK))

        self.assertEqual(self.state(), "killed",
                         "kill не сработал на приостановленной задаче")


class Ac10ApproveAndRejectIgnorePauseTest(PauseSandbox):
    """AC-10: `approve`/`reject` на ручном гейте приостановленной задачи
    выполняются как обычно, независимо от пометки паузы."""

    def test_ac10_approve_works_on_a_paused_task_as_usual(self):
        self.set_state("acceptance")
        invoke(lambda: pause.cmd_pause(self.TASK))

        invoke(lambda: fsm.cmd_approve(self.TASK))

        self.assertEqual(self.state(), "merge_gate",
                         "approve не сработал на приостановленной задаче")

    def test_ac10_reject_works_on_a_paused_task_as_usual(self):
        self.set_state("acceptance")
        invoke(lambda: pause.cmd_pause(self.TASK))

        invoke(lambda: fsm.cmd_reject(self.TASK, "критерий не выполнен"))

        self.assertEqual(self.state(), "in_dev",
                         "reject не сработал на приостановленной задаче")


class Ac11AdvanceIgnoresPauseTest(PauseSandbox):
    """AC-11: `advance` приостановленной задачи выполняется как обычно —
    переход по готовому артефакту не блокируется пометкой паузы."""

    def test_ac11_advance_works_on_a_paused_task_as_usual(self):
        self.write_spec("ready")
        invoke(lambda: pause.cmd_pause(self.TASK))

        invoke(lambda: fsm.cmd_advance(self.TASK))

        self.assertEqual(
            self.state(), "spec_gate",
            "advance не сработал (готовый SPEC.md) на приостановленной "
            "задаче")


if __name__ == "__main__":
    import unittest
    unittest.main()
