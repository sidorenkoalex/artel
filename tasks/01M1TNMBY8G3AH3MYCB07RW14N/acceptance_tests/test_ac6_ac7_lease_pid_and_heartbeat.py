"""AC-6: Lease, взятый отвязанным циклом, несёт pid этого отвязанного
процесса, а не pid короткоживущей вызывающей команды.

AC-7: Heartbeat lease отвязанного цикла обновляется самим циклом по ходу
его шагов, а не вызывающей командой.

Красен до реализации: сегодня lease задачи берёт САМА вызывающая команда
(`run`/`auto` не отвязаны — короткоживущая команда и есть «цикл» целиком),
поэтому `leases.pid` совпадает с pid вызывающей команды — AC-6 нарушен по
построению (`row["pid"] == launcher_pid`, не `!=`). AC-7 сегодня
формально не нарушен изнутри одного и того же процесса, но этот стенд
проверяет её другим краем: `run_cli` дожидается ПОЛНОГО завершения
вызывающей команды до первого чтения lease, а сегодня «вызывающая
команда» и «цикл» — один и тот же процесс: к моменту первого чтения
цикл уже отработал целиком и ОСВОБОДИЛ lease (`lease.run_locked`
отпускает строку в `finally`) — `test_ac7_...` не найдёт вовсе ни одной
строки `leases`, а не просто её незастывший heartbeat.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox, natural_stall_timeout  # noqa: E402

LAUNCH_TIMEOUT_SEC = 8.0


class Ac6Ac7LeasePidAndHeartbeatOwnedByCycleTest(DetachedCycleSandbox):

    def _launch_auto(self, task_id: str):
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, timeout=LAUNCH_TIMEOUT_SEC)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        cycle_pid = self.extract_pid(out)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(cycle_pid)
        return launcher_pid, cycle_pid

    def test_ac6_lease_pid_belongs_to_the_detached_process(self):
        """`leases.pid` задачи после запуска `auto` без `--attach` равен
        pid, напечатанному как pid отвязанного процесса, и НЕ равен pid
        короткоживущей вызывающей команды (`run_cli` вернула её собственный
        pid отдельно).

        Ловит мутацию: lease берётся ВЫЗЫВАЮЩЕЙ командой ДО того, как она
        порождает отвязанный процесс (вместо того, чтобы lease брал сам
        отвязанный процесс изнутри) — тест покраснеет на
        `row["pid"] == launcher_pid`.
        """
        task_id = self.new_task()
        launcher_pid, cycle_pid = self._launch_auto(task_id)

        row = self.wait_until(lambda: self.lease_row(task_id) is not None,
                              timeout=5.0) and self.lease_row(task_id)
        self.assertIsNotNone(
            row, f"lease задачи не появился после старта цикла: "
            f"{self.journal_text(task_id)}")
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
        продолжает продвигаться по мере того, как цикл проходит свои
        шаги — значит, его поддерживает ДРУГОЙ, отвязанный процесс, а не
        давно завершившаяся вызывающая команда.

        Ловит мутацию: heartbeat продлевается только внутри вызывающей
        команды (детач сделан «наполовину» — печать pid/лога уходит в
        отвязанный процесс, а lease/heartbeat по-прежнему держит вызов,
        который уже завершился) — тест покраснеет либо на отсутствии
        lease вовсе, либо на heartbeat, который не продвигается дальше
        значения на момент первого чтения.
        """
        task_id = self.new_task()
        self._launch_auto(task_id)

        row1 = self.wait_until(lambda: self.lease_row(task_id) is not None,
                               timeout=5.0) and self.lease_row(task_id)
        self.assertIsNotNone(
            row1, f"lease задачи не появился: {self.journal_text(task_id)}")
        heartbeat_1 = row1["heartbeat_ts"]

        def heartbeat_advanced():
            row = self.lease_row(task_id)
            return row is not None and row["heartbeat_ts"] > heartbeat_1

        advanced = self.wait_until(heartbeat_advanced,
                                   timeout=natural_stall_timeout())
        self.assertTrue(
            advanced,
            f"heartbeat lease не продвинулся дальше {heartbeat_1!r} за "
            f"отведённое время ПОСЛЕ того, как вызывающая команда уже "
            f"завершилась — его больше некому продлевать:\n"
            f"{self.journal_text(task_id)}")


if __name__ == "__main__":
    unittest.main()
