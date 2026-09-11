"""AC-3: Стандартные потоки (stdout/stderr) отвязанного цикла `auto`
пишутся в файл `.artel/logs/<id>-auto-<n>.log`.

Красен до реализации: сегодня `auto <id>` пишет весь свой вывод в
stdout ВЫЗЫВАЮЩЕГО процесса (никакого файла `.artel/logs/<id>-auto-*.log`
не заводится вовсе) — `run_cli` дожидается ПОЛНОГО естественного
завершения цикла (несколько шагов подряд без перехода,
`natural_stall_timeout`) и получает весь текст через pipe, а не через
файл на диске, который эта планка ищет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox, natural_stall_timeout  # noqa: E402


class Ac3LogCapturesStdioTest(DetachedCycleSandbox):

    def test_ac3_detached_auto_stdio_goes_to_the_log_file(self):
        """Запускает `auto <id>` без `--attach` и ждёт, пока цикл сам
        остановится стоп-краном «N шагов без перехода» (черновой SPEC.md
        никогда не становится `ready`, см. докстринг `_sandbox.py`).
        Файл `.artel/logs/<id>-auto-1.log` к этому моменту несёт узнаваемые
        строки прогресса цикла («auto: старт», «agent run finished»,
        «auto остановлен») — те же, что цикл печатал бы в stdout вызывающей
        команды до этой задачи.

        Ловит мутацию: детач порождает процесс, но его `stdout`/`stderr`
        не перенаправлены в файл (например, оставлены `subprocess.PIPE`
        без чтения, или `DEVNULL`) — тест покраснеет на том, что файл лога
        либо не появляется, либо появляется пустым/без узнаваемых строк,
        хотя цикл (проверяемый отдельно по журналу задачи) реально
        отработал шаги.
        """
        task_id = self.new_task()

        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, timeout=10.0)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        cycle_pid = self.extract_pid(out)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(cycle_pid)

        log_path = self.root / ".artel" / "logs" / f"{task_id}-auto-1.log"
        self.assertTrue(
            self.wait_until(log_path.is_file, timeout=5.0),
            f"лог {log_path} не появился на диске")

        stopped = self.wait_until(
            lambda: not self.is_alive(cycle_pid),
            timeout=natural_stall_timeout())
        self.assertTrue(
            stopped,
            f"цикл (pid={cycle_pid}) не остановился сам за отведённое "
            f"время — журнал: {self.journal_text(task_id)}")

        text = log_path.read_text(encoding="utf-8", errors="replace")
        self.assertTrue(
            text.strip(),
            f"лог {log_path} пуст, хотя цикл реально отработал шаги "
            f"(журнал: {self.journal_text(task_id)})")
        for marker in ("auto: старт", "auto остановлен"):
            self.assertIn(
                marker, text,
                f"лог не содержит ожидаемую строку прогресса «{marker}»: "
                f"{text!r}")


if __name__ == "__main__":
    unittest.main()
