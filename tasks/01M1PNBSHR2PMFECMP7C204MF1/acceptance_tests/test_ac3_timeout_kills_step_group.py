"""AC-3 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Таймаут шага
(orchestrator/runner.py, истечение AGENT_TIMEOUT_SEC) при срабатывании
шлёт SIGTERM всей группе процессов агентного шага, а не только его
непосредственному pid; после короткого грейса не завершившимся членам
группы — SIGKILL.»

Красен до реализации: `run_agent_once` сегодня на таймауте делает только
`proc.kill()` — снимает исключительно сам агентный процесс; потомок,
заведённый скриптом-пробой (аналог pytest/unittest, запущенного ролью,
см. «Контекст» SPEC — инцидент с шестью висящими прогонами тестов),
остаётся жив под тем же приёмным родителем (launchd) — `assertFalse`
ниже находит его живым.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AgentStepSandbox, liveness, wait_while_alive  # noqa: E402


class TimeoutKillsStepGroupTest(AgentStepSandbox):

    def test_ac3_timeout_kills_the_whole_process_group_not_just_the_child(self):
        """Шаг с коротким таймаутом (`AGENT_TIMEOUT_SEC`, подменённым на
        доли секунды) заводит агентный процесс, который сам заводит
        потомка и оба надолго засыпают; таймаут обязан снять ОБОИХ.

        Ловит мутацию: если реализация группового снятия таймаута снимает
        только `proc` (текущее поведение) — потомок переживёт завершение
        шага, и `assertFalse(liveness._pid_alive(child_pid))` покраснеет
        при зелёном `assertFalse` на самом агентном процессе (тот и
        сегодня корректно снимается `proc.kill()`).
        """
        outcome, reason, _ = self.run_step(
            self.agent_with_child_cmd(), timeout_sec=0.3)

        self.assertEqual(outcome, "timeout", reason)
        agent_pid, child_pid = self.read_agent_and_child_pid()

        self.assertTrue(wait_while_alive(agent_pid, timeout=5.0),
                        "сам агентный процесс пережил таймаут шага")
        self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                        "потомок агентного процесса (аналог pytest/"
                        "unittest, запущенного ролью) пережил таймаут "
                        "шага — снят только его непосредственный pid, "
                        "не вся группа")


if __name__ == "__main__":
    unittest.main()
