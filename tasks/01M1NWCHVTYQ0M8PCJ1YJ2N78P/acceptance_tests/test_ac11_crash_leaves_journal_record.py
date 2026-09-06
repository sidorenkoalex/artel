"""AC-11: обрыв отвязанного цикла сигналом или необработанным исключением
(не через `stop`) оставляет в журнале задачи запись с причиной обрыва —
если цикл успевает её записать до своего завершения.

Сигнал этого теста — SIGINT (не тот, которым команда `stop` штатно
завершает цикл, AC-9): Python по умолчанию превращает его в
`KeyboardInterrupt`, то есть цикл ФИЗИЧЕСКИ успевает выполнить код перед
завершением (в отличие от SIGKILL/аварийного убийства ОС, где «успевает»
буквально нечему быть) — оговорка AC-11 «если успевает» относится к
действительно неперехватываемым обрывам, не к этому случаю: тест
проверяет ровно тот сценарий, где записать причину физически возможно.

Красен до реализации: сегодня `auto`/`run` — не отвязанные процессы, а
прямые потомки вызывающей команды (SPEC «Контекст») — тест не находит
искомый pid тем же способом, что и AC-1..AC-10 (нет печати pid/лога
цикла), и падает уже на этом шаге, не добираясь до самого сигнала.
"""
import signal
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

CLAUDE_SLEEP_SEC = 6


class Ac11CrashLeavesJournalRecordTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def test_ac11_sigint_not_via_stop_leaves_a_journalled_reason(self):
        """Посылает отвязанному циклу SIGINT напрямую (`os.kill`, В ОБХОД
        команды `stop`) в середине подставного шага и проверяет: (1)
        процесс в итоге завершается; (2) в журнал задачи попадает НОВАЯ
        запись, добавленная уже ПОСЛЕ отправки сигнала, чей текст
        правдоподобно называет причину обрыва (сигнал/прерывание/крах —
        не пустая строка и не повтор существующих штатных записей шага).

        Ловит мутацию: необработанное исключение/сигнал приводят к
        молчаливому падению процесса без единой новой записи в журнале
        — тест покраснеет на том, что после смерти процесса список
        записей журнала не вырос ни на одну строку относительно снимка
        до отправки сигнала.
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
        journalled_before = len(self.journal())

        self.kill_pid(cycle_pid, signal.SIGINT)

        died = self.wait_until(lambda: not self.is_alive(cycle_pid),
                               timeout=10.0)
        self.assertTrue(
            died, f"процесс цикла (pid={cycle_pid}) не завершился после "
            f"SIGINT")

        new_rows = self.journal()[journalled_before:]
        self.assertTrue(
            new_rows,
            f"после обрыва сигналом (не через stop) в журнал не попало "
            f"ни одной новой записи — причина обрыва не сохранена:\n"
            f"{self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
