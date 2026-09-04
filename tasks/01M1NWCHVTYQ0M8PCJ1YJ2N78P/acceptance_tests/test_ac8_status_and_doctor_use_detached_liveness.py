"""AC-8: `artel.py status <id>` и `doctor` показывают живость цикла,
определённую по pid и heartbeat lease ОТВЯЗАННОГО процесса, а не по
факту существования вызывающей оболочки.

`status` уже сегодня печатает `[lease: <session_id> жив|мёртв]` по pid
lease (`orchestrator/catalog.py::_lease_holder_suffix`, существующий
код — эта задача его не меняет). Красным этот тест делает не сама
печать «жив/мёртв» (она уже работает), а то, ЧЕЙ pid она сверяет:
сегодня lease несёт pid вызывающей команды (см. AC-6) — тест ловит
именно то, что `status` продолжает показывать «жив», даже когда убит
процесс, реально несущий шаг (потому что lease.pid до этой задачи
указывает не на него).

Красен до реализации: `run_cli("auto", ...)` сегодня не возвращается за
5 секунд (AC-1 ещё не реализован — команда не отвязывается и держит
вызывающий процесс до конца цикла), поэтому `timed_out` истинен и тест
падает на первом `assertFalse` до того, как вообще дойдёт до проверки
lease.pid.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

CLAUDE_SLEEP_SEC = 6


class Ac8StatusUsesDetachedLivenessTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def _task_status_line(self, out: str) -> str:
        lines = [ln for ln in out.splitlines() if self.TASK in ln]
        self.assertEqual(
            len(lines), 1,
            f"строка задачи {self.TASK} не найдена (или неоднозначна) в "
            f"выводе status: {out!r}")
        return lines[0]

    def test_ac8_status_flips_from_alive_to_dead_with_the_detached_pid(self):
        """`status` называет держателя lease «жив», пока отвязанный
        процесс реально жив, и «мёртв» сразу после того, как ИМЕННО ЭТОТ
        процесс убит напрямую (в обход `stop`/`kill`, чтобы исключить,
        что «мёртв» появляется из-за освобождения lease самой командой
        остановки, а не из-за проверки живости по pid).

        Ловит мутацию: `status`/`_lease_holder_suffix` продолжают сверять
        живость по pid ВЫЗЫВАЮЩЕЙ команды (который к этому моменту давно
        не существует независимо от того, жив ли цикл) — тест покраснеет
        уже на первой проверке «жив» сразу после запуска, если lease.pid
        в принципе не адресует реальный процесс, либо на второй, если
        смерть отвязанного процесса не отражается.
        """
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", self.TASK, timeout=5.0)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        cycle_pid = self.extract_pid(out)
        self.track_pid(cycle_pid)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.wait_until(lambda: self.lease_row() is not None, timeout=5.0)

        status_out, rc1, _, _, timed_out1 = self.run_cli("status", timeout=10)
        self.assertFalse(timed_out1)
        self.assertEqual(rc1, 0, status_out)
        line_alive = self._task_status_line(status_out)
        self.assertIn(
            "жив", line_alive,
            f"status не назвал держателя lease живым, пока отвязанный "
            f"процесс {cycle_pid} реально жив: {line_alive!r}")

        self.kill_pid(cycle_pid)
        died = self.wait_until(lambda: not self.is_alive(cycle_pid),
                               timeout=5.0)
        self.assertTrue(died, f"процесс {cycle_pid} не удалось убить")

        status_out2, rc2, _, _, timed_out2 = self.run_cli("status", timeout=10)
        self.assertFalse(timed_out2)
        self.assertEqual(rc2, 0, status_out2)
        line_dead = self._task_status_line(status_out2)
        self.assertIn(
            "мёртв", line_dead,
            f"status не заметил смерть отвязанного процесса {cycle_pid} "
            f"— lease.pid, видимо, не адресует его напрямую: "
            f"{line_dead!r}")


if __name__ == "__main__":
    unittest.main()
