"""AC-4: `artel.py auto <id> --attach` и `artel.py run <id> --attach`
выполняются в переднем плане вызывающего процесса — прежнее (до этой
задачи) поведение команд, без отвязки.

Зелёный с рождения: `--attach` обязан воспроизводить поведение, которое
`run`/`auto` несут СЕГОДНЯ (до этой задачи, требование 2 SPEC) — сегодня
`orchestrator/artel.py::main` диспетчерит `run <id> --attach`/
`auto <id> --attach` на `runner.cmd_run(rest[0])`/`auto.cmd_auto(rest[0])`
буквально (лишний позиционный аргумент `--attach` просто не читается,
`rest[0]` — id), то есть уже сегодня исполняет их в переднем плане без
какой-либо отвязки. Эта планка фиксирует именно это наблюдаемое
поведение как планку — она обязана остаться зелёной и ПОСЛЕ реализации
(разбора `--attach`), а не только до неё (skills/test-authoring: маркер
«зелёный с рождения» — тест сохранения существующего поведения).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import CLAUDE_SLEEP_SEC, DetachedCycleSandbox, natural_stall_timeout  # noqa: E402


class Ac4AttachRunsInForegroundTest(DetachedCycleSandbox):

    def test_ac4_auto_attach_blocks_in_the_foreground_until_the_cycle_stops(self):
        """`auto <id> --attach` не возвращает управление, пока цикл сам не
        остановится стоп-краном «N шагов без перехода» (см. докстринг
        `_sandbox.py`) — вызывающий процесс, а не отдельный отвязанный,
        реально исполняет весь цикл: заметно дольше одного шага роли, без
        pid/лога отвязанного процесса в выводе, без файла
        `.artel/logs/<id>-auto-*.log`.

        Ловит мутацию: `--attach` по ошибке всё равно отвязывает процесс
        (например, флаг разбирается, но ветка «attach» вызывает
        `_launch_detached` вместо прямого `auto.cmd_auto`) — тест
        покраснеет на том, что команда возвращается почти мгновенно
        (`elapsed` заметно меньше времени одного шага роли) и/или печатает
        pid отвязанного процесса, которого при `--attach` быть не должно.
        """
        task_id = self.new_task()

        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, "--attach", timeout=natural_stall_timeout())

        self.assertFalse(timed_out, f"auto --attach не завершилась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        self.assertGreaterEqual(
            elapsed, CLAUDE_SLEEP_SEC,
            f"auto --attach вернулась быстрее одного шага роли "
            f"({CLAUDE_SLEEP_SEC}с) — похоже, цикл выполнялся не в этом "
            f"процессе:\n{out}")
        self.assertIsNone(
            self.extract_pid(out),
            f"вывод --attach назвал pid отвязанного процесса — при "
            f"--attach отвязки быть не должно: {out!r}")

        log_path = self.root / ".artel" / "logs" / f"{task_id}-auto-1.log"
        self.assertFalse(
            log_path.exists(),
            f"--attach создал лог отвязанного цикла {log_path} — при "
            f"--attach вывод обязан идти в stdout вызывающего процесса, "
            f"не в файл")
        self.assertIn(
            "auto остановлен", out,
            f"вывод --attach не несёт финального сообщения цикла: {out!r}")
        self.assertEqual(self.task_state(task_id), "spec_writing")

    def test_ac4_run_attach_blocks_until_the_single_step_is_done(self):
        """`run <id> --attach` (одиночный шаг, без цикла `auto`) не
        возвращает управление, пока подставной агент не «доработает»
        (не раньше `CLAUDE_SLEEP_SEC` секунд) — журнал получает «agent
        run finished» уже к моменту возврата.

        Ловит мутацию: `--attach` у `run` по ошибке тоже уходит в детач
        — тест покраснеет на `elapsed` заметно меньше `CLAUDE_SLEEP_SEC`
        и на отсутствии pid `None` не выполняется (вывод назвал бы pid).
        """
        task_id = self.new_task()

        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "run", task_id, "--attach", timeout=CLAUDE_SLEEP_SEC + 15.0)

        self.assertFalse(timed_out, f"run --attach не завершилась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        self.assertGreaterEqual(
            elapsed, CLAUDE_SLEEP_SEC,
            f"run --attach вернулась быстрее одного шага роли "
            f"({CLAUDE_SLEEP_SEC}с):\n{out}")
        self.assertIsNone(
            self.extract_pid(out),
            f"вывод --attach назвал pid отвязанного процесса: {out!r}")
        self.assertTrue(
            any(r["action"] == "agent run finished"
               for r in self.journal(task_id)),
            f"журнал не несёт «agent run finished» после run --attach: "
            f"{self.journal_text(task_id)}")


if __name__ == "__main__":
    unittest.main()
