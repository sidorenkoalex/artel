"""AC-11: Обрыв отвязанного цикла сигналом или необработанным исключением
(не через `stop`) оставляет в журнале задачи запись с причиной обрыва —
если цикл успевает её записать до своего завершения.

`SIGINT` — сигнал, у которого сегодня нет собственного обработчика в
`auto.cmd_auto` (в отличие от будущего `SIGTERM`/`stop`, требование 5):
обработчик Python по умолчанию превращает его в `KeyboardInterrupt`,
которое пробивает тело `cmd_auto` и обязано попасть в общий
`except BaseException` цикла (требование 7) — именно тот класс обрыва
«сигнал ... не через stop», который называет критерий.

Красен до реализации: сегодня `auto <id>` без `--attach` не отвязывается
— `run_cli("auto", ..., timeout=LAUNCH_TIMEOUT_SEC)` этого теста
(короткий таймаут) не дождётся возврата вызывающей команды
(`timed_out=True`) раньше, чем тест дойдёт до отправки `SIGINT`. Даже
минуя этот шаг, `auto.cmd_auto` сегодня не оборачивает
`lease.run_locked(...)` ни в какой `try/except` — необработанное
исключение (в т.ч. `KeyboardInterrupt` от `SIGINT`) пробивает функцию
насквозь без единой записи в журнал задачи.
"""
import signal
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import CLAUDE_SLEEP_SEC, DetachedCycleSandbox  # noqa: E402

LAUNCH_TIMEOUT_SEC = 8.0


class Ac11CrashLeavesJournalRecordTest(DetachedCycleSandbox):

    def test_ac11_signal_crash_leaves_a_journal_record_before_dying(self):
        """Отправляет `SIGINT` (не `stop`/`SIGTERM`) отвязанному циклу,
        пока его шаг ещё выполняется, и проверяет, что до своей гибели
        цикл успевает оставить в журнале НОВУЮ запись, называющую причину
        обрыва (класс исключения/сигнала), а не просто исчезает молча.

        Ловит мутацию: `except BaseException` вокруг цикла отсутствует
        (или ловит только `Exception`, не `BaseException` —
        `KeyboardInterrupt` наследуется от `BaseException`, не от
        `Exception`) — тест покраснеет на отсутствии новой записи в
        журнале между отправкой сигнала и гибелью процесса. Мутация
        «журналирует ДО повторного raise, но по факту убивает процесс
        раньше, чем успевает записать» — тест ловит именно наблюдаемый
        итог (запись есть или нет), а не порядок строк кода.
        """
        task_id = self.new_task()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC * 3)

        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, timeout=LAUNCH_TIMEOUT_SEC)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        cycle_pid = self.extract_pid(out)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(cycle_pid)

        started = self.wait_until(
            lambda: any(r["action"] == "agent run started"
                       for r in self.journal(task_id)),
            timeout=5.0)
        self.assertTrue(
            started,
            f"шаг не успел начаться до отправки SIGINT: "
            f"{self.journal_text(task_id)}")
        journalled_before = len(self.journal(task_id))

        self.kill_pid(cycle_pid, signal.SIGINT)

        died = self.wait_until(lambda: not self.is_alive(cycle_pid),
                               timeout=10.0)
        self.assertTrue(
            died, f"цикл (pid={cycle_pid}) не завершился после SIGINT")

        tail = self.journal(task_id)[journalled_before:]
        tail_text = "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                              for r in tail)
        self.assertTrue(
            tail,
            f"после SIGINT в журнал не попало ни одной новой записи — "
            f"цикл оборвался молча (полный журнал: "
            f"{self.journal_text(task_id)})")
        lowered_tail = tail_text.lower()
        self.assertTrue(
            any(k in lowered_tail
               for k in ("оборван", "interrupt", "прерван", "baseexception")),
            f"новая запись журнала не называет причину обрыва цикла: "
            f"{tail_text!r}")
        self.assertNotIn(
            "auto остановлен", tail_text,
            f"запись похожа на штатную остановку (stop), а не на обрыв "
            f"сигналом: {tail_text!r}")


if __name__ == "__main__":
    unittest.main()
