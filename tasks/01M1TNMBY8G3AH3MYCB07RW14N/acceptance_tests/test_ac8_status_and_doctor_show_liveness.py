"""AC-8: `artel.py status <id>` и `doctor` показывают живость цикла на
основе pid/heartbeat отвязанного процесса, а не факта существования
вызывающей оболочки.

`catalog.cmd_status`/`doctor.check_leases` читают ТОЛЬКО таблицу `leases`
(pid, heartbeat, hostname) — тот же физический файл БД, который делят
тестовый процесс (обычный импорт `orchestrator`, пути `config` патчены
на `self.root`) и физически скопированный CLI отвязанного цикла (тот же
`self.root`, см. докстринг `_sandbox.py`). Обе функции зовутся здесь
ПРЯМО, в процессе теста — предмет проверки (чтение lease по pid/
heartbeat) не завязан на текст CLI-обёртки `artel.py status`/
`artel.py doctor`, которую эта задача не меняет вовсе (SPEC AC-13:
`catalog._lease_holder_suffix`/`doctor.check_leases` — существующий код).

Красен до реализации: сегодня `auto <id>` не отвязывается — вызывающая
команда И ЕСТЬ цикл, `run_cli` (короткий таймаут) не дожидается её
возврата вовсе (`timed_out=True`), поэтому уже первая проверка этого
файла (`не timed_out`) красна.
"""
import signal
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox, capture, catalog, doctor, store  # noqa: E402

LAUNCH_TIMEOUT_SEC = 8.0


class Ac8StatusAndDoctorShowLivenessTest(DetachedCycleSandbox):

    def test_ac8_status_and_doctor_report_the_detached_cycle_by_its_own_pid(self):
        """Запускает `auto <id>` без `--attach`, ловит момент, пока
        отвязанный процесс ещё жив, и проверяет: (1) `catalog.cmd_status`
        помечает lease задачи «жив»; (2) `doctor.check_leases` не заводит
        по этой задаче ни одного `fail`-чека. Затем убивает отвязанный
        процесс СИГНАЛОМ НАПРЯМУЮ (в обход `artel.py kill`, строка lease
        остаётся с уже мёртвым pid) и проверяет разворот обоих: (3)
        `cmd_status` помечает тот же lease «мёртв»; (4) `doctor.
        check_leases` заводит `fail`-чек именно по этой задаче.

        Ловит мутацию: `status`/`doctor` продолжают опираться на факт
        существования ВЫЗЫВАЮЩЕЙ команды (например, читают pid из
        какого-то отдельного «последнего запуска», не из `leases.pid`)
        — тест покраснеет на несовпадении текста «жив»/«мёртв» с реальной
        живостью pid: после SIGKILL прямого держателя `status`/`doctor`
        должны прочитать именно ЕГО смерть, не смерть вызывающей команды
        (та уже умерла задолго до этого, при возврате `run_cli`).
        """
        task_id = self.new_task()

        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, timeout=LAUNCH_TIMEOUT_SEC)
        self.assertFalse(timed_out, f"auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        cycle_pid = self.extract_pid(out)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(cycle_pid)

        self.assertTrue(
            self.wait_until(lambda: self.lease_row(task_id) is not None,
                            timeout=5.0),
            f"lease задачи не появился: {self.journal_text(task_id)}")
        self.assertTrue(
            self.is_alive(cycle_pid),
            "цикл должен быть ещё жив сразу после запуска — иначе окно "
            "проверки «жив» упущено")

        conn = store.db()
        status_out = capture(catalog.cmd_status)
        self.assertIn(
            f"{task_id}", status_out,
            f"status не назвал задачу {task_id} вовсе: {status_out!r}")
        self.assertIn(
            "жив", status_out,
            f"status не пометил lease живым, пока цикл (pid={cycle_pid}) "
            f"реально жив: {status_out!r}")

        alive_checks = doctor.check_leases(conn)
        self.assertFalse(
            any(c.status == "fail" and task_id in c.detail
               for c in alive_checks),
            f"doctor.check_leases уже считает живой lease мёртвым: "
            f"{alive_checks}")

        # Убиваем ДЕРЖАТЕЛЯ напрямую, в обход `artel.py kill` (AC-10 —
        # предмет отдельного теста): здесь важно только то, что pid
        # реально умер, а строка `leases` осталась с ним.
        self.kill_pid(cycle_pid, signal.SIGKILL)
        self.assertTrue(
            self.wait_until(lambda: not self.is_alive(cycle_pid), timeout=5.0),
            f"pid {cycle_pid} не умер после SIGKILL")

        status_out_after = capture(catalog.cmd_status)
        self.assertIn(
            "мёртв", status_out_after,
            f"status не пометил lease мёртвым после гибели его "
            f"держателя (pid={cycle_pid}): {status_out_after!r}")

        dead_checks = doctor.check_leases(conn)
        self.assertTrue(
            any(c.status == "fail" and task_id in c.detail
               for c in dead_checks),
            f"doctor.check_leases не завёл fail-чек по задаче {task_id} "
            f"после гибели держателя lease: {dead_checks}")


if __name__ == "__main__":
    unittest.main()
