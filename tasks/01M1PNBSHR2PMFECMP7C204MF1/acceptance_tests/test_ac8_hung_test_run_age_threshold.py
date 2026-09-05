"""AC-8 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «doctor находит
процессы прогонов тестов (python -m unittest/pytest) с cwd внутри
.artel/worktrees/ и возрастом старше именованной константы (по умолчанию
10 минут).»

Наблюдается через `doctor.cmd_doctor()` (реальный CLI-путь) и появление
СТРОКИ `alerts`, упоминающей pid РЕАЛЬНОГО, заведомо не-агентного процесса
(`_sandbox.spawn_hung_test_run` — настоящий `python -m unittest`, cwd
внутри `config.WORKTREES/<task_id>` — см. докстринг `_sandbox.py`,
раздел «Допущения интерфейса»): факт алерта — необходимое следствие
«найден», а раздельно проверяемый предмет ИМЕННО этого теста — порог
ВОЗРАСТА (AC-10 отдельно проверяет форму/kind/авто-ack самого алерта,
AC-9 — фильтрацию по lease).

Один и тот же процесс проверяется ДВАЖДЫ прогоном `doctor` — сразу после
спавна (моложе порога, `config.HUNG_TEST_RUN_AGE_SEC` подменена на малое
число) и после того, как он этот порог пережил — так порог проверяется
без гонки между двумя параллельными процессами разного возраста. Порог
и выдержка — целые секунды, не доли: возраст процесса ОС обычно меряется
через `ps`/`etime` с разрешением в целую секунду (BSD/macOS `ps` не
несёт Linux-только `etimes` — доли секунды в принципе недоступны этим
путём), под-секундный порог не различил бы «до»/«после» на РЕАЛЬНОЙ
реализации независимо от корректности самой проверки.

Красен до реализации: `config.HUNG_TEST_RUN_AGE_SEC` — допущение имени
константы (`_sandbox.py`, «Допущения интерфейса»), которого сегодня в
`config.py` нет — `mock.patch.object` падает `AttributeError` при
попытке подмены (расхождение ИМЕНИ, а не поведения; ПОСЛЕ реализации
под другим именем константы тест чинится переименованием здесь, не
самим фактом красноты). Реализована константа под другим именем — тест
покраснеет уже содержательно: сторож зависших прогонов ещё не существует
вовсе, ни один прогон `doctor` не заводит алерт с pid подставного
процесса.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AgentStepSandbox, config, fake_claude_cli, run_doctor  # noqa: E402


class HungTestRunAgeThresholdTest(AgentStepSandbox):

    TASK_HUNG = "T-AC8-HUNG"

    def test_ac8_finds_test_run_only_after_it_crosses_the_age_threshold(self):
        """Один и тот же подставной `python -m unittest` в
        `.artel/worktrees/<task>` — до порога сторож молчит, после
        порога (`config.HUNG_TEST_RUN_AGE_SEC`, подменена на 2 с) —
        находит и заводит по нему алерт.

        Ловит мутацию: если проверка возраста снята вовсе (сторож
        находит процесс сразу, независимо от порога) — первый
        `assertNotIn` покраснеет; если проверка возраста инвертирована
        (находит только МОЛОЖЕ порога) — второй `assertIn` покраснеет.
        """
        self.bootstrap_doctor_environment()
        self.ensure_task(self.TASK_HUNG)
        proc = self.spawn_hung(self.TASK_HUNG, sleep_sec=60)

        with mock.patch.object(config, "HUNG_TEST_RUN_AGE_SEC", 2), \
             fake_claude_cli():
            run_doctor(fix=False)
            fresh_messages = " | ".join(self.all_alert_messages())
            self.assertNotIn(
                str(proc.pid), fresh_messages,
                "сторож нашёл подставной прогон тестов ДО истечения "
                "порога возраста — проверка возраста отсутствует или "
                "не задерживает находку")

            time.sleep(3)
            run_doctor(fix=False)
            aged_messages = " | ".join(self.all_alert_messages())
            self.assertIn(
                str(proc.pid), aged_messages,
                "сторож не нашёл подставной прогон тестов ПОСЛЕ "
                "истечения порога возраста — python -m unittest с cwd "
                "внутри .artel/worktrees/ не обнаружен")


if __name__ == "__main__":
    unittest.main()
