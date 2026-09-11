"""AC-1: `artel.py auto <id>` без `--attach` возвращает управление сразу,
напечатав pid отвязанного процесса, путь лога цикла
(`.artel/logs/<id>-auto-<n>.log`) и подсказку `artel.py log <id>`, а сам
цикл run+advance продолжает исполняться в отвязанном процессе после
возврата команды.

AC-2: `artel.py run <id>` без `--attach` так же возвращает управление
сразу, напечатав pid отвязанного процесса, путь собственного лога цикла
и ту же подсказку «наблюдать: artel.py log <id>».

Красен до реализации: `orchestrator/artel.py::main` сегодня диспетчерит
`run`/`auto` напрямую на `runner.cmd_run`/`auto.cmd_auto` (см. код,
строки диспетчера `table`) — без `--attach`, разбора detach-флага и без
`_launch_detached`, которого в модуле ещё нет вовсе. Вызывающий процесс
сам исполняет цикл в переднем плане до его естественной остановки
(`config.AUTO_STALL_STEPS_LIMIT` шагов подряд без перехода, см.
`_sandbox.py`) — `run_cli(..., timeout=...)` из этого файла с коротким
таймаутом обязан поймать `timed_out=True` (команда не вернула управление
вовремя), а не найти в выводе pid/лог/подсказку.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox, natural_stall_timeout  # noqa: E402

# «Возвращает управление сразу» — заведомо быстрее одного шага роли
# (подставной агент спит `CLAUDE_SLEEP_SEC` секунд): если детач работает,
# вызывающая команда успевает вернуться, пока агент ещё даже не начал
# спать; если нет — вызывающая команда САМА исполняет цикл и не вернётся
# до его естественной остановки (`natural_stall_timeout`, десятки секунд).
IMMEDIATE_RETURN_TIMEOUT_SEC = 5.0


class Ac1Ac2DetachedLaunchReturnsImmediatelyTest(DetachedCycleSandbox):

    def test_ac1_auto_without_attach_returns_immediately_with_pid_log_and_hint(self):
        """`artel.py auto <id>` (без `--attach`) на задаче в `spec_writing`
        печатает pid отвязанного процесса, путь
        `.artel/logs/<id>-auto-1.log` и подсказку `artel.py log <id>`, и
        возвращается ощутимо раньше, чем подставной агент успевает
        закончить хотя бы один шаг — цикл продолжает исполняться в фоне
        после возврата (лог файла растёт дальше первой проверки).

        Ловит мутацию: детач не реализован (`auto` вызывается напрямую в
        переднем плане) — тест покраснеет на `timed_out=True`
        (`run_cli` не дождалась возврата за `IMMEDIATE_RETURN_TIMEOUT_SEC`)
        либо, если детач есть, но лог не по формату `<id>-auto-<n>.log`
        или подсказка не называет `artel.py log <id>` — на отсутствии
        соответствующего текста в выводе.
        """
        task_id = self.new_task()

        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, timeout=IMMEDIATE_RETURN_TIMEOUT_SEC)

        self.assertFalse(
            timed_out,
            f"auto без --attach не вернула управление за "
            f"{IMMEDIATE_RETURN_TIMEOUT_SEC}с — похоже, цикл выполняется "
            f"в переднем плане вызывающей команды:\n{out}")
        self.assertEqual(rc, 0, out)
        self.assertLess(
            elapsed, IMMEDIATE_RETURN_TIMEOUT_SEC,
            "вызывающая команда вернулась, но заметно позже, чем можно "
            "было бы объяснить одной лишь отвязкой процесса")

        cycle_pid = self.extract_pid(out)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(cycle_pid)

        expected_log = f"{task_id}-auto-1.log"
        self.assertIn(
            expected_log, out,
            f"вывод не назвал путь лога `.artel/logs/{expected_log}`: {out!r}")
        self.assertIn(
            f"artel.py log {task_id}", out,
            f"вывод не содержит подсказку «artel.py log {task_id}»: {out!r}")

        log_path = self.root / ".artel" / "logs" / expected_log
        self.assertTrue(
            self.wait_until(log_path.is_file, timeout=IMMEDIATE_RETURN_TIMEOUT_SEC),
            f"лог {log_path} не появился на диске после возврата команды")

        size_after_return = log_path.stat().st_size
        grew = self.wait_until(
            lambda: log_path.stat().st_size > size_after_return
            or self.is_alive(cycle_pid),
            timeout=natural_stall_timeout())
        self.assertTrue(
            grew,
            f"после возврата вызывающей команды цикл (pid={cycle_pid}) "
            f"не подавал признаков продолжающейся работы (ни рост лога, "
            f"ни живой процесс)")

    def test_ac2_run_without_attach_returns_immediately_with_pid_log_and_hint(self):
        """`artel.py run <id>` (без `--attach`, одиночный шаг без цикла)
        так же возвращается немедленно, напечатав pid, путь
        `.artel/logs/<id>-run-1.log` и подсказку `artel.py log <id>`.

        Ловит мутацию: `run` детачится, но использует ОБЩИЙ с `auto`
        счётчик номера лога (или наоборот, не различает `run`/`auto` в
        имени файла) — тест покраснеет на отсутствии файла именно
        `<id>-run-1.log`, если разработчик перепутал команду в шаблоне
        имени. Мутация «детач есть только у auto» — покраснеет так же,
        как AC-1 red-до-реализации: `timed_out=True`.
        """
        task_id = self.new_task()

        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "run", task_id, timeout=IMMEDIATE_RETURN_TIMEOUT_SEC)

        self.assertFalse(
            timed_out,
            f"run без --attach не вернула управление за "
            f"{IMMEDIATE_RETURN_TIMEOUT_SEC}с — похоже, шаг выполняется "
            f"в переднем плане вызывающей команды:\n{out}")
        self.assertEqual(rc, 0, out)

        cycle_pid = self.extract_pid(out)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(cycle_pid)

        expected_log = f"{task_id}-run-1.log"
        self.assertIn(
            expected_log, out,
            f"вывод не назвал путь лога `.artel/logs/{expected_log}`: {out!r}")
        self.assertIn(
            f"artel.py log {task_id}", out,
            f"вывод не содержит подсказку «artel.py log {task_id}»: {out!r}")

        log_path = self.root / ".artel" / "logs" / expected_log
        self.assertTrue(
            self.wait_until(log_path.is_file, timeout=IMMEDIATE_RETURN_TIMEOUT_SEC),
            f"лог {log_path} не появился на диске после возврата команды")


if __name__ == "__main__":
    unittest.main()
