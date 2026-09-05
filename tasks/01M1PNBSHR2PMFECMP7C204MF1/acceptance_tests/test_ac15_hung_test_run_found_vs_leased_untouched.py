"""AC-15 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Тест подтверждает:
сторож находит старый тестовый прогон без lease его задачи и не трогает
(не алертит, не снимает) прогон с живым lease.»

В отличие от AC-9 (`test_ac9_hung_test_run_lease_filter.py`, гоняет
ИСКЛЮЧИТЕЛЬНО `doctor --fix`, где оба следствия фильтра — алерт и
снятие — наблюдаются в ОДНОМ режиме) — здесь ПРОСТОЙ прогон `doctor`
(`fix=False`, тот же режим, что AC-10/AC-12): снятия в этом режиме не
бывает вовсе независимо от lease (AC-12), поэтому содержательное,
проверяемое здесь следствие фильтра — ИСКЛЮЧИТЕЛЬНО алерт. Задача
ловит РЕАЛЬНУЮ реализацию, где фильтрация по lease встроена в код
ПОД `--fix` (тот, что AC-11 явно требует держать за флагом) и не
распространена на построение списка кандидатов на алерт, которое
происходит НЕЗАВИСИМО от флага.

Красен до реализации: `config.HUNG_TEST_RUN_AGE_SEC` — то же допущение
имени, что у AC-8..AC-12 (`_sandbox.py`, «Допущения интерфейса»),
которого пока нет — `mock.patch.object` падает `AttributeError`.
Реализована константа под другим именем, но сторожа ещё нет вовсе —
падает содержательно: `assertIn`/`assertNotIn` по обеим задачам не
находят никакого алерта (сторож не существует), а не только по одной из
них.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AgentStepSandbox, config, fake_claude_cli,  # noqa: E402
                      liveness, run_doctor)


class HungTestRunFoundVsLeasedUntouchedTest(AgentStepSandbox):

    TASK_WITH_LEASE = "T-AC15-LEASED"
    TASK_NO_LEASE = "T-AC15-ORPHAN"

    def test_ac15_plain_run_alerts_orphan_and_leaves_leased_process_unalerted(self):
        """Два подставных зависших прогона одинакового возраста, ПРОСТОЙ
        `doctor` (без `--fix`): по задаче без lease поднимается алерт; по
        задаче с живым lease — алерта нет и процесс остаётся жив (снятия
        в этом режиме не бывает вовсе, AC-12, — единственное отличимое
        здесь следствие фильтра именно алерт).

        Ловит мутацию: если фильтрация по lease реализована ТОЛЬКО внутри
        кода снятия под `--fix` (например, разработчик построил её как
        часть подготовки списка на убийство и не применил тот же фильтр
        к списку кандидатов на алерт, который строится независимо от
        флага `fix`) — здесь, при `fix=False`, алерт по задаче с живым
        lease поднимется ошибочно, и `assertNotIn` ниже покраснеет, хотя
        `test_ac9_...` (гоняет фильтр только под `--fix`, где сборка
        списка на алерт СОВПАДАЕТ со списком на убийство) этого не
        заметил бы.
        """
        self.bootstrap_doctor_environment()

        self.ensure_task(self.TASK_WITH_LEASE)
        holder = self.spawn_placeholder_process()
        self.install_dummy_lease(holder.pid, session_id="ac15-leased-session",
                                 task_id=self.TASK_WITH_LEASE)
        leased_proc = self.spawn_hung(self.TASK_WITH_LEASE, sleep_sec=60)

        self.ensure_task(self.TASK_NO_LEASE)
        orphan_proc = self.spawn_hung(self.TASK_NO_LEASE, sleep_sec=60)

        with mock.patch.object(config, "HUNG_TEST_RUN_AGE_SEC", 1), \
             fake_claude_cli():
            # Целые секунды: `ps`/`etime` (BSD/macOS) — разрешение в целую
            # секунду, см. `test_ac8_hung_test_run_age_threshold.py`.
            time.sleep(1.5)
            run_doctor(fix=False)

        messages = " | ".join(self.all_alert_messages())
        self.assertIn(
            str(orphan_proc.pid), messages,
            "сторож не поднял алерт по прогону задачи БЕЗ lease при "
            "простом (без --fix) прогоне")
        self.assertNotIn(
            str(leased_proc.pid), messages,
            "сторож поднял алерт по прогону задачи с живым lease при "
            "ПРОСТОМ прогоне — фильтрация по lease не распространена на "
            "путь алерта, независимый от --fix")
        self.assertTrue(
            liveness._pid_alive(leased_proc.pid),
            "простой прогон doctor снял прогон задачи с живым lease")
        self.assertTrue(
            liveness._pid_alive(orphan_proc.pid),
            "простой прогон doctor (без --fix) снял прогон — снятие "
            "обязано быть только под --fix (AC-12)")


if __name__ == "__main__":
    unittest.main()
