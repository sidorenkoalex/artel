"""AC-11 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «doctor --fix снимает
процессы, найденные сторожем (AC-8, AC-9), группой — SIGTERM, грейс,
SIGKILL — с записью перечня снятых процессов в журнал алертов.»

Подставной «зависший прогон» — вариант С РЕАЛЬНЫМ потомком
(`_sandbox.spawn_hung_test_run(..., with_child=True)`, аналог
pytest-xdist воркера): «группой», а не «одним pid», проверяется тем, что
ОБА — и leader (сам `python -m unittest`), и его потомок — не переживают
`doctor --fix`. «Перечень снятых процессов в журнал алертов» — допущение
техники наблюдения: `store.alerts_older_than` с заведомо будущим cutoff
(`_sandbox.AgentStepSandbox.all_alert_messages`) возвращает АБСОЛЮТНО ВСЕ
строки `alerts`, открытые и уже подтверждённые доктором самим же
`--fix`-прогоном — перечень ищется среди них всех, а не только среди
ещё открытых (сам факт снятия мог закрыть исходный алерт).

Красен до реализации: `config.HUNG_TEST_RUN_AGE_SEC` — допущение имени
(`_sandbox.py`), которого пока нет — `AttributeError` на подмене.
Реализована константа под другим именем — падает содержательно: сторож
не существует, `doctor --fix` не трогает ни leader, ни потомка, и
перечень в `alerts` не появляется.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AgentStepSandbox, config, fake_claude_cli,  # noqa: E402
                      run_doctor, wait_while_alive)


class DoctorFixGroupKillsHungTestRunTest(AgentStepSandbox):

    TASK_HUNG = "T-AC11-HUNG"

    def test_ac11_fix_kills_leader_and_child_and_journals_the_tally(self):
        """`doctor --fix` на подставном зависшем прогоне с РЕАЛЬНЫМ
        потомком — снимает ОБОИХ (группой), а не только сам `python -m
        unittest`; перечень снятых процессов появляется в `alerts`.

        Ловит мутацию: если снятие адресует только сам найденный pid
        (`os.kill`, не группу через pgid) — потомок переживёт `--fix`,
        второй `assertTrue`(wait_while_alive потомка) покраснеет при
        зелёном первом (сам leader корректно снят); если снятие
        реализовано, но перечень killed-pid никуда не пишется — третий
        `assertTrue` (упоминание leader-pid среди ВСЕХ сообщений alerts)
        покраснеет при живых первых двух.
        """
        self.bootstrap_doctor_environment()
        self.ensure_task(self.TASK_HUNG)
        leader = self.spawn_hung(self.TASK_HUNG, with_child=True, sleep_sec=60)
        _, child_pid = self.read_hung_child_pid(self.TASK_HUNG)

        with mock.patch.object(config, "HUNG_TEST_RUN_AGE_SEC", 1), \
             fake_claude_cli():
            # Целые секунды: `ps`/`etime` (BSD/macOS) — разрешение в
            # целую секунду, см. `test_ac8_hung_test_run_age_threshold.py`.
            time.sleep(1.5)
            run_doctor(fix=True)

        self.assertTrue(
            wait_while_alive(leader.pid, timeout=5.0),
            "лидер подставного зависшего прогона пережил `doctor --fix`")
        self.assertTrue(
            wait_while_alive(child_pid, timeout=5.0),
            "потомок подставного зависшего прогона пережил `doctor "
            "--fix` — снята не вся группа, а только сам найденный pid")

        messages = " | ".join(self.all_alert_messages())
        self.assertIn(
            str(leader.pid), messages,
            "перечень снятых `doctor --fix` процессов не появился ни в "
            "одной строке `alerts` (ни открытой, ни подтверждённой)")


if __name__ == "__main__":
    unittest.main()
