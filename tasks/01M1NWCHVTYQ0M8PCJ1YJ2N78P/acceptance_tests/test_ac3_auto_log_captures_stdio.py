"""AC-3: стандартные потоки (stdout/stderr) отвязанного цикла `auto`
пишутся в файл `.artel/logs/<id>-auto-<n>.log`.

Красен до реализации: `run`/`auto` сегодня печатают весь ход цикла в
stdout вызывающей команды (наследуемый терминал), а файла
`<id>-auto-<n>.log` не существует вовсе — тест либо не находит такой
путь в выводе (см. AC-1), либо не находит его на диске.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

CLAUDE_SLEEP_SEC = 3
# Маркер, которым `_cmd_auto` (orchestrator/auto.py) печатает старт цикла
# — тот же текст, что уже используют существующие тесты цикла
# (tests/test_auto_cycle.py читает журнал по тому же событию «auto
# старт»); здесь читается печать, а не журнал, ровно то, что AC-3 и
# называет «стандартные потоки».
STDOUT_MARKER = "auto: старт из"


class Ac3AutoLogCapturesStdioTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def test_ac3_cycle_stdio_lands_in_the_auto_log_file(self):
        """Запускает `auto <id>` без `--attach`, дожидается, пока
        отвязанный процесс успеет напечатать хотя бы старт цикла, и
        проверяет: (1) текст старта цикла есть в файле лога, названном
        AC-1 (`<id>-auto-<n>.log`); (2) того же текста НЕТ в stdout,
        которое реально увидела короткоживущая вызывающая команда — иначе
        поток не «уходит в лог», а дублируется/остаётся у вызывающей
        стороны.

        Ловит мутацию: отвязанный процесс продолжает наследовать
        stdout/stderr вызывающей команды (`subprocess.Popen(...)` без
        `stdout=`/`stderr=` в файл) — тогда файл лога останется пустым
        (или вовсе не будет создан), а маркер старта цикла либо не
        появится нигде, либо просочится в stdout самой вызывающей
        команды, которую тест читает отдельно.
        """
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", self.TASK, timeout=5.0)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)

        pid = self.extract_pid(out)
        self.track_pid(pid)
        self.assertIsNotNone(pid, f"вывод не назвал pid: {out!r}")

        log_path = self.extract_log_path(out)
        self.assertIsNotNone(
            log_path, f"вывод не назвал путь лога цикла: {out!r}")
        log_file = Path(log_path)

        def log_has_marker():
            try:
                return STDOUT_MARKER in log_file.read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                return False

        found = self.wait_until(log_has_marker,
                                timeout=CLAUDE_SLEEP_SEC + 3)
        self.assertTrue(
            found,
            f"файл лога {log_path} не получил вывод цикла (маркер "
            f"{STDOUT_MARKER!r} не появился) — стандартные потоки "
            f"отвязанного процесса не уходят в него")

        self.assertNotIn(
            STDOUT_MARKER, out,
            f"вывод цикла попал в stdout короткоживущей вызывающей "
            f"команды вместо файла лога: {out!r}")


if __name__ == "__main__":
    unittest.main()
