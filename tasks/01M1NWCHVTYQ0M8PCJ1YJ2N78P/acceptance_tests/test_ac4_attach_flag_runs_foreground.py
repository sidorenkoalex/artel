"""AC-4: `artel.py auto <id> --attach` и `artel.py run <id> --attach`
выполняются в переднем плане вызывающего процесса — прежнее (до этой
задачи) поведение команд, без отвязки.

Зелёный с рождения: `orchestrator/artel.py` сегодня зовёт
`auto.cmd_auto(rest[0])`/`runner.cmd_run(rest[0])`, где `rest[0]` — id
задачи, а лишний хвостовой токен `rest[1]` (`--attach`) молча
игнорируется — то есть СЕГОДНЯШНЕЕ поведение команды без какой-либо
поддержки флага уже совпадает с тем, что требует AC-4 (передний план,
без отвязки), потому что до этой задачи ничего, кроме переднего плана,
и не было. Это подтверждено прогоном (см. PLAN/REVIEW этой задачи) — не
случайность, а прямое следствие того, что `--attach` обязан
ВОСПРОИЗВЕСТИ старое поведение, а не изменить его: тест — планка
сохранения существующего поведения (skills/test-authoring, «Зелёный с
рождения»), которая обязана остаться зелёной ДО, ВО ВРЕМЯ (частичная
реализация, флаг ещё не подключён к развилке) и ПОСЛЕ реализации этой
задачи. Красным он станет, только если реализация СЛОМАЕТ передний план
под `--attach` — например, подключит detach безусловно, не разбирая
флаг (см. «Ловит мутацию» ниже).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

CLAUDE_SLEEP_SEC = 3
STDOUT_MARKER = "auto: старт из"


class Ac4AttachRunsForegroundTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def test_ac4_auto_attach_blocks_until_the_step_is_done(self):
        """`auto <id> --attach`: команда не возвращается, пока подставной
        шаг ({CLAUDE_SLEEP_SEC}с) не отработает — тот же ход вывода,
        который видел бы Оператор до этой задачи, прямо в СВОЁМ stdout,
        не в файле лога цикла.

        Ловит мутацию: `--attach` не подключён к развилке (детач
        срабатывает всегда, флаг молча игнорируется) — тест покраснеет
        на `elapsed` (команда снова вернётся почти мгновенно) и на
        отсутствии `STDOUT_MARKER` в захваченном stdout.
        """
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", self.TASK, "--attach", timeout=CLAUDE_SLEEP_SEC + 15)

        self.assertFalse(
            timed_out,
            f"auto --attach не завершилась за разумное время:\n{out}")
        self.assertEqual(rc, 0, out)
        self.assertGreaterEqual(
            elapsed, CLAUDE_SLEEP_SEC * 0.7,
            f"auto --attach вернулась через {elapsed:.2f}с — короче, чем "
            f"занимает сам подставной шаг ({CLAUDE_SLEEP_SEC}с): команда "
            f"не дождалась шага в переднем плане, поведение похоже на "
            f"отвязанное:\n{out}")
        self.assertIn(
            STDOUT_MARKER, out,
            f"вывод цикла не попал в stdout вызывающего процесса при "
            f"--attach — прежнее поведение (печать в передний план) не "
            f"сохранилось: {out!r}")

    def test_ac4_run_attach_blocks_until_the_step_is_done(self):
        """`run <id> --attach`: тот же передний план, что и у `auto`
        --attach — один шаг агента, без отвязки.

        Ловит мутацию: `--attach` реализован только для `auto`, `run`
        забыт — тест покраснеет на `elapsed`/отсутствии живого вывода
        шага в stdout, тем же способом, что и для `auto` выше.
        """
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "run", self.TASK, "--attach", timeout=CLAUDE_SLEEP_SEC + 15)

        self.assertFalse(
            timed_out, f"run --attach не завершилась за разумное время:\n{out}")
        self.assertEqual(rc, 0, out)
        self.assertGreaterEqual(
            elapsed, CLAUDE_SLEEP_SEC * 0.7,
            f"run --attach вернулась через {elapsed:.2f}с — короче "
            f"подставного шага ({CLAUDE_SLEEP_SEC}с):\n{out}")
        self.assertIn(
            "developer завершил", out,
            f"вывод шага (существующая печать `cmd_run` по завершении "
            f"агента) не попал в stdout вызывающего процесса при "
            f"--attach: {out!r}")


if __name__ == "__main__":
    unittest.main()
