"""AC-12 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Обычный прогон
doctor (без --fix) сторожа зависших прогонов процессы не трогает —
только отчёт/алерт (AC-10).»

Подставной зависший прогон без lease (`_sandbox.spawn_hung_test_run`),
`doctor.cmd_doctor(fix=False)` — процесс обязан остаться живым: отчёт/
алерт (AC-10) — да, снятие — нет.

Красен до реализации: `config.HUNG_TEST_RUN_AGE_SEC` — допущение имени
(`_sandbox.py`), которого пока нет — `AttributeError` на подмене, та же
причина, что у AC-8..AC-11. Реализована константа под другим именем, но
сам сторож ещё нет — тест ПРОХОДИТ ЗЕЛЁНЫМ (нечего снимать, если сторож
вовсе не существует), хотя AC-12 этим не подтверждён; содержательность
теста в этом промежуточном состоянии проверяется временным стабом
корректной реализации (см. скил test-authoring — обязательная
валидация), а не собственной красной фазой этого файла.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AgentStepSandbox, config, fake_claude_cli,  # noqa: E402
                      run_doctor, wait_while_alive)


class DoctorWithoutFixLeavesHungTestRunAloneTest(AgentStepSandbox):

    TASK_HUNG = "T-AC12-HUNG"

    def test_ac12_plain_doctor_run_does_not_kill_the_hung_test_run(self):
        """`doctor` без `--fix` на подставном зависшем прогоне (без
        lease, дальше порога возраста) — процесс остаётся живым.

        Ловит мутацию: если снятие сторожа реализовано БЕЗ гейта
        `--fix` (тот же класс дефекта, что уже ловил `test_ac6_dead_
        lease_group_cleanup.py` для `check_leases`) — процесс погибнет
        уже на этом, «наблюдательном» прогоне, и `assertFalse` ниже
        покраснеет.
        """
        self.bootstrap_doctor_environment()
        self.ensure_task(self.TASK_HUNG)
        proc = self.spawn_hung(self.TASK_HUNG, sleep_sec=60)

        with mock.patch.object(config, "HUNG_TEST_RUN_AGE_SEC", 1), \
             fake_claude_cli():
            # Целые секунды: `ps`/`etime` (BSD/macOS) — разрешение в
            # целую секунду, см. `test_ac8_hung_test_run_age_threshold.py`.
            time.sleep(1.5)
            run_doctor(fix=False)

        died = wait_while_alive(proc.pid, timeout=1.0)
        self.assertFalse(
            died,
            "подставной зависший прогон снят ПРОСТЫМ `doctor` (без "
            "--fix) — снятие сторожа обязано быть под флагом")


if __name__ == "__main__":
    unittest.main()
