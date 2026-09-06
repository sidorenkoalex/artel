"""AC-12: `doctor` различает по pid и последней журнальной записи цикла
три состояния: цикл жив, цикл завершился штатно, цикл умер.

Красен до реализации: сегодня `auto <id>` не отвязывается — короткий
`run_cli` ловит `timed_out=True` уже на запуске «живой» задачи (цикл
исполняется в переднем плане вызывающей команды), а `stop` (нужна для
сценария «завершился штатно») — неизвестная команда. Обе проверки этого
файла красны раньше, чем тест доходит до самого `doctor`.
"""
import signal
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox, doctor, store  # noqa: E402

LAUNCH_TIMEOUT_SEC = 8.0
ALIVE_CLAUDE_SLEEP_SEC = 60.0


class Ac12DoctorThreeStatesTest(DetachedCycleSandbox):

    def _launch(self, task_id: str, timeout: float = LAUNCH_TIMEOUT_SEC):
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, timeout=timeout)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        pid = self.extract_pid(out)
        self.assertIsNotNone(pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(pid)
        return pid

    def test_ac12_doctor_distinguishes_alive_finished_and_dead_cycles(self):
        """Заводит три отдельные задачи, каждая со своим отвязанным
        циклом `auto`, доводит их до трёх разных исходов — (а) штатно
        остановлена командой `stop` и цикл уже вышел сам; (б) убита
        сигналом напрямую, минуя `stop` (осиротевшая lease с мёртвым
        pid); (в) оставлена работать — и проверяет, что `doctor.
        check_leases` (тот же код, что уже используют `artel.py status`/
        `artel.py doctor`, SPEC AC-13) видит все три исхода по-разному:
        (а) в таблице `leases` для неё нет строки вовсе, журнал несёт
        запись о штатном завершении цикла; (б) строка `leases` есть, pid
        мёртв, `doctor` заводит по ней `fail`; (в) строка `leases` есть,
        pid жив, `doctor` НЕ заводит по ней `fail`.

        Ловит мутацию: `doctor.check_leases` (либо lease-механика,
        которую эта задача трогает — `force`/`holder_before`) перестаёт
        отличать «умер» от «жив» (например, всегда flag'ает fail для
        любой существующей lease-строки, или никогда) — тест покраснеет
        на том, что задача (б) не получает `fail`, либо задача (в) его
        получает. Мутация «stop не освобождает lease» — покраснеет на
        том, что задача (а) всё ещё несёт строку `leases`.
        """
        finished_task = self.new_task("Цикл, завершённый штатно")
        dead_task = self.new_task("Цикл, оборванный сигналом")

        finished_pid = self._launch(finished_task)
        dead_pid = self._launch(dead_task)

        # (а) штатно останавливаем: доигрывает шаг, журналирует
        # завершение, освобождает lease сам.
        started = self.wait_until(
            lambda: any(r["action"] == "agent run started"
                       for r in self.journal(finished_task)),
            timeout=5.0)
        self.assertTrue(started, "штатный цикл не успел начать шаг")
        stop_out, stop_rc, _, _, stop_timed_out = self.run_cli(
            "stop", finished_task, timeout=15.0)
        self.assertFalse(stop_timed_out, f"stop зависла:\n{stop_out}")
        self.assertEqual(stop_rc, 0, stop_out)
        self.assertTrue(
            self.wait_until(lambda: not self.is_alive(finished_pid), timeout=15.0),
            f"штатно останавливаемый цикл (pid={finished_pid}) не вышел сам")
        self.assertTrue(
            self.wait_until(lambda: self.lease_row(finished_task) is None,
                            timeout=5.0),
            "lease штатно завершённого цикла не освободилась")

        # (б) убиваем сигналом напрямую — lease осиротевшая, с мёртвым pid.
        self.wait_until(
            lambda: any(r["action"] == "agent run started"
                       for r in self.journal(dead_task)),
            timeout=5.0)
        self.assertTrue(
            self.is_alive(dead_pid),
            "цикл, который должен умереть некрасиво, уже мёртв до SIGKILL")
        self.kill_pid(dead_pid, signal.SIGKILL)
        self.assertTrue(
            self.wait_until(lambda: not self.is_alive(dead_pid), timeout=10.0),
            f"pid {dead_pid} не умер после SIGKILL")
        self.assertIsNotNone(
            self.lease_row(dead_task),
            "lease убитого сигналом цикла не должна освобождаться сама "
            "— иначе нечем отличить «умер» от «завершился штатно»")

        # (в) третья задача — оставлена работать, с длинным сном, чтобы
        # заведомо пережить обработку (а)/(б) выше.
        alive_task = self.new_task("Цикл, оставленный работать")
        self.set_claude_sleep(ALIVE_CLAUDE_SLEEP_SEC)
        alive_pid = self._launch(alive_task)
        self.assertTrue(
            self.wait_until(lambda: self.lease_row(alive_task) is not None,
                            timeout=5.0),
            "lease живой задачи не появилась")
        self.assertTrue(self.is_alive(alive_pid), "живая задача уже не жива")

        conn = store.db()
        checks = doctor.check_leases(conn)
        fail_task_ids = {c.detail.split(":", 1)[0] for c in checks
                        if c.status == "fail"}

        self.assertNotIn(
            finished_task, fail_task_ids,
            f"doctor завёл fail по штатно завершённому циклу: {checks}")
        self.assertIn(
            dead_task, fail_task_ids,
            f"doctor не завёл fail по осиротевшему (умершему) циклу: {checks}")
        self.assertNotIn(
            alive_task, fail_task_ids,
            f"doctor завёл fail по реально живому циклу: {checks}")

        finished_tail = "\n".join(
            f"{r['action']} {r['detail']}" for r in self.journal(finished_task))
        self.assertTrue(
            any(k in finished_tail.lower()
               for k in ("останов", "stop", "штатн")),
            f"журнал штатно завершённого цикла не несёт записи о "
            f"завершении: {finished_tail!r}")


if __name__ == "__main__":
    unittest.main()
