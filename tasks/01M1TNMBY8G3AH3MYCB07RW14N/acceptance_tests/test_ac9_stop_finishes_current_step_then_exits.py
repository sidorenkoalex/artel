"""AC-9: `artel.py stop <id>` посылает отвязанному циклу задачи штатный
сигнал завершения; текущий шаг роли (включая автокоммит и переход FSM),
уже начатый к моменту сигнала, доигрывается до конца, после чего цикл
пишет в журнал задачи запись о своём завершении и выходит сам — `stop`
не прерывает уже идущий шаг.

Красен до реализации: сегодня `auto <id>` без `--attach` не отвязывается
— вызывающая команда сама исполняет цикл в переднем плане, и
`run_cli("auto", ..., timeout=LAUNCH_TIMEOUT_SEC)` этого теста (короткий
таймаут) не дождётся её возврата (`timed_out=True`) раньше, чем тест
дойдёт до отправки `stop`. Даже минуя этот шаг, команды `stop` не
существует вовсе — `orchestrator/artel.py::main` отвечает безусловным
`sys.exit(f"Неизвестная команда {cmd}...")` (код возврата 1) на любое имя
команды не из своей диспетчерской таблицы.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import CLAUDE_SLEEP_SEC, DetachedCycleSandbox  # noqa: E402

LAUNCH_TIMEOUT_SEC = 8.0
STOP_TIMEOUT_SEC = 10.0


class Ac9StopFinishesCurrentStepThenExitsTest(DetachedCycleSandbox):

    def test_ac9_stop_lets_the_in_progress_step_finish_then_exits(self):
        """Отправляет `stop` ровно тогда, когда подставной шаг роли уже
        начался, но ещё не закончился (запись «agent run started» в
        журнале уже есть, подставной `claude` ещё спит), и проверяет по
        порядку: (1) `stop` не роняет уже идущий шаг — журнал получает
        РОВНО ОДНУ новую запись «agent run finished» уже ПОСЛЕ отправки
        `stop` (не ноль — шаг доигрался; не больше одной — цикл не
        продолжил со следующего шага); (2) цикл затем сам, без внешнего
        kill, завершает свой процесс; (3) в журнале появляется запись о
        штатном завершении цикла.

        Ловит мутацию: `stop` реализован как немедленное прерывание
        (равносильно `kill` текущего шага) — тест покраснеет на
        отсутствии «agent run finished» ПОСЛЕ `stop` (шаг оборвался, не
        доигрался). Мутация «флаг проверяется не на границе, а сразу
        внутри уже идущего шага» или «`stop` ничего не делает» —
        покраснеет на том, что цикл не завершается сам
        (`is_alive(cycle_pid)` остаётся `True` намного дольше одного
        шага). Мутация «после `stop` цикл всё равно делает ещё один шаг
        сверху» — покраснеет на количестве новых «agent run finished»
        (2, не 1).
        """
        task_id = self.new_task()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC * 2)

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
            f"шаг не успел начаться до отправки stop: "
            f"{self.journal_text(task_id)}")
        journalled_before_stop = len(self.journal(task_id))

        stop_out, stop_rc, _, _, stop_timed_out = self.run_cli(
            "stop", task_id, timeout=STOP_TIMEOUT_SEC)
        self.assertFalse(stop_timed_out, f"stop зависла:\n{stop_out}")
        self.assertEqual(
            stop_rc, 0,
            f"stop отказала (команда должна существовать и посылать "
            f"сигнал живому циклу): {stop_out}")

        finished = self.wait_until(
            lambda: any(r["action"] == "agent run finished"
                       for r in self.journal(task_id)[journalled_before_stop:]),
            timeout=CLAUDE_SLEEP_SEC * 2 + 10.0)
        tail = self.journal(task_id)[journalled_before_stop:]
        self.assertTrue(
            finished,
            f"уже идущий шаг не доигрался до конца после stop (нет "
            f"«agent run finished» среди записей ПОСЛЕ отправки stop): "
            f"{self.journal_text(task_id)}")
        finished_count = sum(1 for r in tail if r["action"] == "agent run finished")
        self.assertEqual(
            finished_count, 1,
            f"после stop должен доиграть РОВНО текущий шаг, не начинать "
            f"следующий: {self.journal_text(task_id)}")

        died = self.wait_until(lambda: not self.is_alive(cycle_pid),
                               timeout=10.0)
        self.assertTrue(
            died,
            f"цикл (pid={cycle_pid}) не завершился сам после того, как "
            f"доиграл шаг и получил stop")

        tail_text = "\n".join(f"{r['action']} {r['detail']}".lower()
                              for r in self.journal(task_id)[journalled_before_stop:])
        self.assertTrue(
            any(k in tail_text for k in ("останов", "stop", "штатн")),
            f"журнал не получил запись о штатном завершении цикла после "
            f"stop: {self.journal_text(task_id)}")


if __name__ == "__main__":
    unittest.main()
