"""AC-10: `artel.py kill <id>` немедленно прерывает работу задачи, в том
числе принудительно завершает отвязанный процесс цикла, если тот ещё
жив.

Красен до реализации: сегодня `auto <id>` без `--attach` не отвязывается
вовсе — `run_cli("auto", ...)` этого теста (короткий таймаут) сама не
дождётся возврата вызывающей команды (`timed_out=True`), раньше, чем
тест дойдёт до вызова `kill`. Даже если бы деtach как-то уже был готов,
`cleanup.cmd_kill` сегодня берёт lease БЕЗ `force=True`
(`lease.run_locked(conn, task_id, session_id, lambda sid: _cmd_kill(conn,
task_id))`, `orchestrator/cleanup.py::cmd_kill`) — lease живого цикла со
свежим heartbeat отказывает ЛЮБОЙ незнакомой сессии («занята сессия …
подожди её»), и `on_refusal` по умолчанию — `sys.exit`: `kill` откажет
НЕМЕДЛЕННО, не дойдя до самого убийства процесса.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

LAUNCH_TIMEOUT_SEC = 8.0
KILL_TIMEOUT_SEC = 15.0


class Ac10KillTerminatesDetachedProcessTest(DetachedCycleSandbox):

    def test_ac10_kill_terminates_the_live_detached_cycle_immediately(self):
        """Запускает `auto <id>` без `--attach`, ловит момент, когда
        отвязанный цикл ещё жив и держит свежий lease, затем зовёт
        `artel.py kill <id>` и проверяет: (1) `kill` завершается успешно,
        не отказывает «занята другой сессией»; (2) задача переходит в
        `killed`; (3) отвязанный процесс цикла (pid из вывода `auto`)
        реально мёртв после `kill`, а не продолжает исполняться в фоне.

        Ловит мутацию: `kill` берёт lease без `force=True` (текущее
        поведение) — тест покраснеет на ненулевом коде возврата `kill`
        (отказ «занята сессия … подожди её») раньше, чем дойдёт до
        проверки живости процесса. Мутация «`force=True` есть, но
        SIGKILL прежнему держателю не посылается» — покраснеет на том,
        что задача помечена `killed`, а pid цикла всё ещё жив.
        """
        task_id = self.new_task()

        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, timeout=LAUNCH_TIMEOUT_SEC)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        cycle_pid = self.extract_pid(out)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(cycle_pid)

        self.assertTrue(
            self.wait_until(lambda: self.lease_row(task_id) is not None,
                            timeout=5.0),
            f"lease задачи не появился: {self.journal_text(task_id)}")
        self.assertTrue(
            self.is_alive(cycle_pid),
            "цикл должен быть ещё жив к моменту вызова kill — иначе "
            "проверка не о том, что заявлено критерием")

        kill_out, kill_rc, _, _, kill_timed_out = self.run_cli(
            "kill", task_id, timeout=KILL_TIMEOUT_SEC)
        self.assertFalse(kill_timed_out, f"kill зависла:\n{kill_out}")
        self.assertEqual(
            kill_rc, 0,
            f"kill отказала на задаче с живым отвязанным циклом: {kill_out}")

        self.assertEqual(self.task_state(task_id), "killed")

        died = self.wait_until(lambda: not self.is_alive(cycle_pid),
                               timeout=10.0)
        self.assertTrue(
            died,
            f"отвязанный процесс цикла (pid={cycle_pid}) остался жив "
            f"после artel.py kill {task_id}")


if __name__ == "__main__":
    unittest.main()
