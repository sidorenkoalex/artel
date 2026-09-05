"""AC-4 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Команда kill
(orchestrator/cleanup.py::cmd_kill) при живом процессе лизы шлёт SIGTERM
всей его группе процессов, после грейса — SIGKILL, до снятия lease и
уборки worktree/ветки задачи.»

Шаг заводится РЕАЛЬНЫМ `run_agent_once` в фоновом потоке (эмулирует
«шаг сейчас бежит в другом процессе той же машины, кто-то параллельно
зовёт kill из своего терминала») — только так тест не зависит от того,
КАК именно записывается pgid шага (AC-2, «в lease и/или журнал»):
`cmd_kill` читает его тем же кодом, что его только что записал
настоящий прогон.

Красен до реализации: `_cmd_kill` сегодня вообще не трогает OS-процесс
(SPEC «Контекст») — потомок агентного шага (аналог pytest/unittest)
переживает `kill` целиком, `assertFalse` ниже находит его живым.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AgentStepSandbox, cleanup, liveness,  # noqa: E402
                      wait_for, wait_while_alive)


class KillCommandKillsLeaseGroupTest(AgentStepSandbox):

    SESSION = "kill-test-session"

    def test_ac4_kill_kills_the_process_group_of_a_live_lease(self):
        """`kill` бьёт задачу, чей шаг сейчас реально бежит (отдельный
        управляемый процесс — держатель lease, — плюс агентный процесс
        с потомком, заведённый настоящим `run_agent_once` в фоне);
        проверяется, что потомок агентного процесса не переживает `kill`.

        Ловит мутацию: если развязка AC-4 сигналит только
        `row['pid']` (держатель lease, представляющий процесс пульта) и
        не находит/не снимает записанную AC-2 группу агентного шага —
        потомок агентного процесса останется жив, `assertFalse`
        покраснеет, хотя лиза корректно снимется (уже сегодняшнее
        поведение по другим причинам).
        """
        holder = self.spawn_placeholder_process()
        self.install_dummy_lease(holder.pid, session_id=self.SESSION)

        thread = self.run_step_in_background(self.agent_with_child_cmd())
        agent_pid, child_pid = self.read_agent_and_child_pid()
        self.assert_lease_pid_unchanged(holder.pid)

        cleanup.cmd_kill(self.TASK, session_id=self.SESSION)
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive(), "фоновый шаг не завершился "
                         "после kill")

        self.assertTrue(wait_while_alive(agent_pid, timeout=5.0),
                        "сам агентный процесс пережил kill")
        self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                        "потомок агентного процесса (аналог pytest/"
                        "unittest) пережил kill — снята не вся группа")


if __name__ == "__main__":
    unittest.main()
