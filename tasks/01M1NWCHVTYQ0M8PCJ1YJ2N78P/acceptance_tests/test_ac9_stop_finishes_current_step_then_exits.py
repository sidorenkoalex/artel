"""AC-9: `artel.py stop <id>` посылает отвязанному циклу задачи штатный
сигнал завершения; текущий шаг роли (включая автокоммит и переход FSM),
уже начатый к моменту сигнала, доигрывается до конца, после чего цикл
пишет в журнал задачи запись о своём завершении и выходит сам — `stop`
не прерывает уже идущий шаг.

Красен до реализации: команды `stop` не существует
(`Неизвестная команда stop` — `orchestrator/artel.py::main`, безусловный
`sys.exit`). Тест ловит это как ненулевой код возврата `stop` и
отсутствие дальнейшего эффекта.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

CLAUDE_SLEEP_SEC = 6


class Ac9StopFinishesCurrentStepThenExitsTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def test_ac9_stop_mid_step_lets_the_step_finish_then_journals_and_exits(self):
        """Отправляет `stop` ровно тогда, когда подставной шаг уже
        начался, но ещё не закончился (запись «agent run started» в
        журнале уже есть, подставной `claude` ещё спит), и проверяет по
        порядку: (1) `stop` не роняет уже идущий шаг — журнал получает
        «agent run finished» уже ПОСЛЕ отправки `stop`, а не обрывается;
        (2) цикл затем сам, без внешнего kill, завершает свой процесс;
        (3) в журнале появляется запись о штатном завершении цикла.

        Ловит мутацию: `stop` реализован как немедленное прерывание
        (равносильно `kill` текущего шага) — тест покраснеет на
        отсутствии «agent run finished» ПОСЛЕ `stop` (шаг оборвался, не
        доигрался). Мутация «`stop` ничего не делает» (команда есть, но
        не шлёт сигнал) — покраснеет на том, что цикл не завершается сам
        (`is_alive(cycle_pid)` остаётся `True` намного дольше, чем нужно
        одному шагу).
        """
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", self.TASK, timeout=5.0)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        cycle_pid = self.extract_pid(out)
        self.track_pid(cycle_pid)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")

        started = self.wait_until(
            lambda: any(r["action"] == "agent run started"
                       for r in self.journal()),
            timeout=5.0)
        self.assertTrue(
            started,
            f"шаг не успел начаться до отправки stop: {self.journal_text()}")
        journalled_before_stop = len(self.journal())

        stop_out, stop_rc, _, _, stop_timed_out = self.run_cli(
            "stop", self.TASK, timeout=10.0)
        self.assertFalse(stop_timed_out, f"stop зависла:\n{stop_out}")
        self.assertEqual(
            stop_rc, 0,
            f"stop отказала (команда должна существовать и посылать "
            f"сигнал живому циклу): {stop_out}")

        finished = self.wait_until(
            lambda: any(r["action"] == "agent run finished"
                       for r in self.journal()[journalled_before_stop:]),
            timeout=CLAUDE_SLEEP_SEC + 5)
        self.assertTrue(
            finished,
            f"уже идущий шаг не доигрался до конца после stop (нет "
            f"«agent run finished» среди записей ПОСЛЕ отправки stop): "
            f"{self.journal_text()}")

        died = self.wait_until(lambda: not self.is_alive(cycle_pid),
                               timeout=10.0)
        self.assertTrue(
            died,
            f"цикл (pid={cycle_pid}) не завершился сам после того, как "
            f"доиграл шаг и получил stop")

        tail_text = "\n".join(
            f"{r['action']} {r['detail']}".lower()
            for r in self.journal()[journalled_before_stop:])
        self.assertTrue(
            any(k in tail_text for k in ("останов", "stop", "штатн")),
            f"журнал не получил запись о штатном завершении цикла после "
            f"stop: {self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
