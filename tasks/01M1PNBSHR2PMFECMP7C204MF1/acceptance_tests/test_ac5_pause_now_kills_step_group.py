"""AC-5 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «pause --now
(orchestrator/pause.py::cmd_pause_now) при прерывании шлёт SIGTERM/
SIGKILL всей группе процессов лизы, а не только pid, который сегодня
получает _terminate_pid.»

Тот же приём, что AC-4 (`test_ac4_kill_command_kills_lease_group.py`):
шаг заводится РЕАЛЬНЫМ `run_agent_once` в фоновом потоке — `pause_now`
читает записанный AC-2 pgid тем же кодом, что его только что записал.

Красен до реализации: `cmd_pause_now` сегодня зовёт `_terminate_pid`
только на `row['pid']` (держатель lease, процесс пульта) — потомок
агентного процесса (аналог pytest/unittest) переживает прерывание.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AgentStepSandbox, pause, wait_while_alive  # noqa: E402


class PauseNowKillsStepGroupTest(AgentStepSandbox):

    SESSION = "pause-now-test-session"

    def test_ac5_pause_now_kills_the_process_group_not_just_the_lease_pid(self):
        """`pause --now` на задаче, чей шаг реально бежит (держатель lease
        + агентный процесс с потомком, заведённый настоящим
        `run_agent_once` в фоне); проверяется, что потомок агентного
        процесса не переживает прерывание.

        Ловит мутацию: если `cmd_pause_now` по-прежнему сигналит только
        `row['pid']` (существующий `_terminate_pid`, T074) и не находит
        записанную AC-2 группу агентного шага — потомок останется жив,
        хотя держатель lease корректно прерывается уже сегодня.
        """
        holder = self.spawn_placeholder_process()
        self.install_dummy_lease(holder.pid, session_id=self.SESSION)

        thread = self.run_step_in_background(self.agent_with_child_cmd())
        agent_pid, child_pid = self.read_agent_and_child_pid()
        self.assert_lease_pid_unchanged(holder.pid)

        pause.cmd_pause_now(self.TASK)
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive(), "фоновый шаг не завершился "
                         "после pause --now")

        self.assertTrue(wait_while_alive(agent_pid, timeout=5.0),
                        "сам агентный процесс пережил pause --now")
        self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                        "потомок агентного процесса (аналог pytest/"
                        "unittest) пережил pause --now — снята не вся "
                        "группа")


if __name__ == "__main__":
    unittest.main()
