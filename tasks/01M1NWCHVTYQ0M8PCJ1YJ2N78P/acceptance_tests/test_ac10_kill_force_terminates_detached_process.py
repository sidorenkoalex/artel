"""AC-10: `artel.py kill <id>` немедленно прерывает работу задачи, в том
числе принудительно завершает отвязанный процесс цикла, если тот ещё жив.

Красен до реализации: сегодняшний `cleanup.cmd_kill` переводит задачу в
`killed`, снимает lease и убирает хвосты (каталог/ветку), но НИЧЕГО не
делает с живым процессом, реально несущим шаг, — до этой задачи он и не
мог: цикл был прямым потомком сессии Оператора и умирал вместе с ней
(SPEC «Контекст»). Тест ловит буквально то, что процесс, чей pid лежит
в lease, остаётся живым после `kill`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

CLAUDE_SLEEP_SEC = 8


class Ac10KillForceTerminatesDetachedProcessTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def test_ac10_kill_terminates_the_live_cycle_process_immediately(self):
        """`kill <id>`, отправленный СЕРЕДИНЕ подставного шага
        ({CLAUDE_SLEEP_SEC}с сна), возвращается управлением быстро (не
        дожидаясь конца шага — иначе это было бы поведением `stop`, не
        `kill`) и оставляет отвязанный процесс цикла мёртвым, а задачу —
        в состоянии `killed`.

        Ловит мутацию: `kill` продолжает не трогать живой процесс шага
        (старое поведение, актуальное только пока цикл был прямым
        потомком сессии) — тест покраснеет на `is_alive(cycle_pid)`,
        остающемся `True` после возврата `kill`.
        """
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", self.TASK, timeout=5.0)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        cycle_pid = self.extract_pid(out)
        self.track_pid(cycle_pid)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.wait_until(
            lambda: any(r["action"] == "agent run started"
                       for r in self.journal()),
            timeout=5.0)
        self.assertTrue(
            self.is_alive(cycle_pid),
            "процесс цикла должен быть жив непосредственно перед kill")

        kill_out, kill_rc, kill_elapsed, _, kill_timed_out = self.run_cli(
            "kill", self.TASK, timeout=15.0)
        self.assertFalse(kill_timed_out, f"kill зависла:\n{kill_out}")
        self.assertEqual(kill_rc, 0, f"kill отказала: {kill_out}")
        self.assertLess(
            kill_elapsed, CLAUDE_SLEEP_SEC * 0.7,
            f"kill вернулась только через {kill_elapsed:.2f}с — похоже, "
            f"она дождалась конца подставного шага, а не прервала его "
            f"немедленно: {kill_out}")

        died = self.wait_until(lambda: not self.is_alive(cycle_pid),
                               timeout=5.0)
        self.assertTrue(
            died,
            f"процесс цикла (pid={cycle_pid}) остался жив после kill")
        self.assertEqual(
            self.task_state(), "killed",
            f"задача не переведена в killed: {self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
