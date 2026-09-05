"""AC-14 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Тест подтверждает:
таймаут шага, kill и pause --now каждый снимает запущенного ролью потомка
(тестовый стаб — команда sleep в дочерней оболочке, по образцу
spawn_sleep_process из tests/test_pause_now.py), и этот потомок не
переживает завершение шага.»

В отличие от AC-3/AC-4/AC-5 (`test_ac3_timeout_kills_step_group.py`,
`test_ac4_kill_command_kills_lease_group.py`,
`test_ac5_pause_now_kills_step_group.py` — потомок там: python-подпроцесс,
заведённый скриптом-агентом через `subprocess.Popen`, а сам агентный
скрипт после этого продолжает жить своим отдельным `time.sleep`) — здесь
потомок РЕАЛЬНАЯ команда `sleep`, которую дочерняя оболочка бэкграундит
(`&`) и сама остаётся ждать (`wait`) — тот стаб, что SPEC называет
буквально («Материалы», образец `spawn_sleep_process`). Три немедленных
пути требования 2 (таймаут/kill/pause --now) проверяются в одном файле —
тем же вызовам продакшен-кода, что и AC-3/4/5, но на другом дереве
процессов: лидер группы — оболочка (`/bin/sh`), не Python.

Красен до реализации: та же причина, что и AC-3/AC-4/AC-5 по каждому
пути — `run_agent_once` на таймауте зовёт только `proc.kill()` (снимает
исключительно pid оболочки), `cmd_kill`/`cmd_pause_now` сегодня вообще не
адресуют OS-процесс группы. Дополнительно этот файл ловит и такую
реализацию требования 2, что перечисляет для снятия только УЖЕ ИЗВЕСТНЫЕ
коду pid'ы (например, pid самого агентного процесса плюс pid, отдельно
записанный тем же кодом, что завёл python-потомка в AC-3..AC-7) вместо
настоящего `os.killpg(pgid, ...)` по ВСЕЙ группе — `sleep`, чей pid
адресующий код никогда явно не узнаёт, пережил бы завершение шага, хотя
AC-3..AC-7 (с их python-потомком) были бы уже зелёными.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AgentStepSandbox, cleanup, pause, wait_while_alive  # noqa: E402


class AgentStepGroupKillShellStubTest(AgentStepSandbox):
    """Общий стаб дерева процессов для всех трёх немедленных путей AC-14 —
    реальная `sleep`, забэкграунженная дочерней оболочкой (образец SPEC,
    `spawn_sleep_process`)."""

    def test_ac14_timeout_kills_the_backgrounded_shell_sleep(self):
        """Шаг с коротким таймаутом заводит агентную оболочку, которая
        бэкграундит `sleep` и сама остаётся её ждать; таймаут обязан снять
        ОБОИХ — саму оболочку и забэкграунженный `sleep`.

        Ловит мутацию: если групповое снятие таймаута реализовано через
        перечисление известных pid'ов вместо `os.killpg` по pgid (см.
        докстринг модуля) — `sleep` переживёт таймаут, и второй
        `assertTrue` ниже покраснеет при зелёном первом.
        """
        outcome, reason, _ = self.run_step(
            self.shell_sleep_agent_cmd(), timeout_sec=0.3)

        self.assertEqual(outcome, "timeout", reason)
        leader_pid, child_pid = self.read_shell_leader_and_child_pid()

        self.assertTrue(wait_while_alive(leader_pid, timeout=5.0),
                        "оболочка агентного шага пережила таймаут шага")
        self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                        "команда sleep, забэкграунженная оболочкой, "
                        "пережила таймаут шага — снят не весь дочерний "
                        "стаб, а только его часть")

    def test_ac14_kill_kills_the_backgrounded_shell_sleep(self):
        """`kill` бьёт задачу, чей шаг сейчас реально бежит (держатель
        lease + агентная оболочка с забэкграунженным `sleep`, заведённая
        настоящим `run_agent_once` в фоне); оба обязаны не пережить `kill`.

        Ловит мутацию: тот же класс, что у таймаута выше — если развязка
        AC-4 находит и снимает только pid оболочки (или только
        python-потомков, специфично отслеженных для AC-3..AC-7), `sleep`
        останется жив, хотя лиза корректно снимется.
        """
        session = "ac14-kill-session"
        holder = self.spawn_placeholder_process()
        self.install_dummy_lease(holder.pid, session_id=session)

        thread = self.run_step_in_background(self.shell_sleep_agent_cmd())
        leader_pid, child_pid = self.read_shell_leader_and_child_pid()
        self.assert_lease_pid_unchanged(holder.pid)

        cleanup.cmd_kill(self.TASK, session_id=session)
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive(), "фоновый шаг не завершился "
                         "после kill")

        self.assertTrue(wait_while_alive(leader_pid, timeout=5.0),
                        "оболочка агентного шага пережила kill")
        self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                        "команда sleep, забэкграунженная оболочкой, "
                        "пережила kill — снята не вся группа")

    def test_ac14_pause_now_kills_the_backgrounded_shell_sleep(self):
        """`pause --now` на задаче, чей шаг реально бежит (держатель lease
        + агентная оболочка с забэкграунженным `sleep`, заведённая
        настоящим `run_agent_once` в фоне); оба обязаны не пережить
        прерывание.

        Ловит мутацию: тот же класс — если `cmd_pause_now` по-прежнему
        сигналит только `row['pid']` (существующий `_terminate_pid`,
        T074) или снимает лишь известные pid'ы python-потомков, `sleep`
        останется жив.
        """
        session = "ac14-pause-now-session"
        holder = self.spawn_placeholder_process()
        self.install_dummy_lease(holder.pid, session_id=session)

        thread = self.run_step_in_background(self.shell_sleep_agent_cmd())
        leader_pid, child_pid = self.read_shell_leader_and_child_pid()
        self.assert_lease_pid_unchanged(holder.pid)

        pause.cmd_pause_now(self.TASK)
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive(), "фоновый шаг не завершился "
                         "после pause --now")

        self.assertTrue(wait_while_alive(leader_pid, timeout=5.0),
                        "оболочка агентного шага пережила pause --now")
        self.assertTrue(wait_while_alive(child_pid, timeout=5.0),
                        "команда sleep, забэкграунженная оболочкой, "
                        "пережила pause --now — снята не вся группа")


if __name__ == "__main__":
    unittest.main()
