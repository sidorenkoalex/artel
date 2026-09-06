"""AC-6: lease, взятый отвязанным циклом, несёт pid ЭТОГО отвязанного
процесса, а не pid короткоживущей вызывающей команды.

AC-7: heartbeat lease отвязанного цикла обновляется самим циклом по ходу
его шагов, а не вызывающей командой.

Красен до реализации: сегодня lease задачи берёт САМА вызывающая команда
(`run`/`auto` не отвязаны — они и есть «цикл»), поэтому `leases.pid`
сегодня буквально совпадает с pid вызывающей команды — AC-6 нарушен по
построению. AC-7 сегодня формально не нарушен (heartbeat и правда
обновляет тот же процесс, который несёт цикл) — но в этом стенде
`run_cli` дожидается ПОЛНОГО завершения вызывающей команды перед тем, как
тест начинает опрашивать lease, а сегодня «вызывающая команда» и «цикл»
— один и тот же процесс: он не может продлить heartbeat ПОСЛЕ того, как
уже завершился (см. `test_ac7_...` — не найдёт ни одной строки `leases`
вовсе, потому что до реализации она удаляется вместе с освобождением
lease при выходе `run_locked`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

CLAUDE_SLEEP_SEC = 6


class Ac6Ac7LeasePidAndHeartbeatOwnedByCycleTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def _launch_auto(self):
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", self.TASK, timeout=5.0)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        pid = self.extract_pid(out)
        self.track_pid(pid)
        self.assertIsNotNone(pid, f"вывод не назвал pid: {out!r}")
        return launcher_pid, pid

    def test_ac6_lease_pid_belongs_to_the_detached_process(self):
        """`leases.pid` задачи после запуска `auto` без `--attach` равен
        pid, напечатанному как pid отвязанного процесса, и НЕ равен pid
        короткоживущей вызывающей команды.

        Ловит мутацию: lease продолжает браться ВЫЗЫВАЮЩЕЙ командой ДО
        того, как она порождает отвязанный процесс (и передаётся ему уже
        готовым) — тест покраснеет на `row["pid"] == launcher_pid`.
        """
        launcher_pid, cycle_pid = self._launch_auto()

        row = self.wait_until(lambda: self.lease_row() is not None,
                              timeout=5.0) and self.lease_row()
        self.assertIsNotNone(
            row, f"lease задачи не появился после старта цикла: "
            f"{self.journal_text()}")
        self.assertEqual(
            row["pid"], cycle_pid,
            f"lease.pid={row['pid']} не совпадает с напечатанным pid "
            f"отвязанного процесса {cycle_pid}")
        self.assertNotEqual(
            row["pid"], launcher_pid,
            f"lease.pid совпал с pid короткоживущей вызывающей команды "
            f"({launcher_pid}) — lease взят не тем процессом")

    def test_ac7_heartbeat_advances_after_the_caller_has_already_exited(self):
        """Вызывающая команда `auto <id>` (без `--attach`) уже полностью
        завершилась (`run_cli` дожидается именно ЕЁ, не цикла) к моменту,
        когда тест впервые читает lease. Несмотря на это, heartbeat lease
        продолжает продвигаться — значит, его поддерживает ДРУГОЙ,
        отвязанный процесс, а не давно завершившаяся вызывающая команда.

        Ловит мутацию: heartbeat продлевается только внутри вызывающей
        команды (детач сделан «наполовину» — сама печать pid/лога уходит
        в отвязанный процесс, а lease/heartbeat по-прежнему держит вызов,
        который уже завершился) — тест покраснеет либо на отсутствии
        lease вовсе, либо на heartbeat, который не продвигается дальше
        значения на момент первого чтения.
        """
        self._launch_auto()

        row1 = self.wait_until(lambda: self.lease_row() is not None,
                               timeout=5.0) and self.lease_row()
        self.assertIsNotNone(
            row1, f"lease задачи не появился: {self.journal_text()}")
        heartbeat_1 = row1["heartbeat_ts"]

        def heartbeat_advanced():
            row = self.lease_row()
            return row is not None and row["heartbeat_ts"] > heartbeat_1

        advanced = self.wait_until(
            heartbeat_advanced, timeout=CLAUDE_SLEEP_SEC + 5)
        self.assertTrue(
            advanced,
            f"heartbeat lease не продвинулся дальше {heartbeat_1!r} за "
            f"{CLAUDE_SLEEP_SEC + 5}с ПОСЛЕ того, как вызывающая команда "
            f"уже завершилась — его больше некому продлевать:\n"
            f"{self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
