"""AC-9 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Из найденных
требованием AC-8 сторож рассматривает только те, для чьей задачи нет
живого lease; на процесс с живым lease его задачи сторож не поднимает
алерт и не претендует его снять.»

Два подставных «зависших прогона» (`_sandbox.spawn_hung_test_run`,
одинаково старых — оба дальше `config.HUNG_TEST_RUN_AGE_SEC`), различие
ровно в одном: у задачи `TASK_WITH_LEASE` — живой lease (реальный,
управляемый тестом процесс-держатель), у `TASK_NO_LEASE` — lease не
заведён вовсе (тривиальный случай «нет живого lease»). `doctor --fix`
зовётся один раз — проверяются ОБА следствия критерия сразу: алерт не
поднят и процесс не снят для задачи с живым lease; для задачи без lease
— оба следствия наступают.

Красен до реализации: `config.HUNG_TEST_RUN_AGE_SEC` — то же допущение
имени константы, что и в `test_ac8_hung_test_run_age_threshold.py`
(`_sandbox.py`, «Допущения интерфейса»), которого сегодня в `config.py`
нет — `mock.patch.object` падает `AttributeError`. Реализована константа
под другим именем (чинится переименованием здесь) — тест покраснеет
содержательно: сторож ещё не существует вовсе, оба `assertNotIn`/
`assertTrue`(жив) по задаче с lease пройдут случайно (нечего
фильтровать), но встречные `assertIn`/`assertFalse`(жив) по задаче без
lease не найдут ни находки, ни снятия.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AgentStepSandbox, config, fake_claude_cli,  # noqa: E402
                      liveness, run_doctor)


class HungTestRunLeaseFilterTest(AgentStepSandbox):

    TASK_WITH_LEASE = "T-AC9-LEASED"
    TASK_NO_LEASE = "T-AC9-ORPHAN"

    def test_ac9_process_with_live_lease_is_neither_alerted_nor_killed(self):
        """Задача с живым lease — сторож проходит мимо; задача без lease
        (тот же возраст, та же cwd-механика) — находит и снимает.

        Ловит мутацию: если фильтрация по lease снята вовсе (сторож
        трогает ЛЮБОЙ старый прогон независимо от lease) —
        `assertNotIn`/`assertTrue` по задаче с lease покраснеют, хотя
        задача без lease обработается штатно; если фильтрация
        инвертирована (снимает только процессы С живым lease) — обе
        задачи покажут результат наоборот.
        """
        self.bootstrap_doctor_environment()

        self.ensure_task(self.TASK_WITH_LEASE)
        holder = self.spawn_placeholder_process()
        self.install_dummy_lease(holder.pid, session_id="ac9-leased-session",
                                 task_id=self.TASK_WITH_LEASE)
        leased_proc = self.spawn_hung(self.TASK_WITH_LEASE, sleep_sec=60)

        self.ensure_task(self.TASK_NO_LEASE)
        orphan_proc = self.spawn_hung(self.TASK_NO_LEASE, sleep_sec=60)

        with mock.patch.object(config, "HUNG_TEST_RUN_AGE_SEC", 1), \
             fake_claude_cli():
            # Целые секунды, не доли: `ps`/`etime` (BSD/macOS) меряют
            # возраст процесса с разрешением в целую секунду — см.
            # docstring `test_ac8_hung_test_run_age_threshold.py`.
            time.sleep(1.5)
            run_doctor(fix=True)

        messages = " | ".join(self.all_alert_messages())
        self.assertNotIn(
            str(leased_proc.pid), messages,
            "сторож поднял алерт по прогону задачи с живым lease — "
            "фильтрация AC-9 отсутствует или сработала не в ту сторону")
        self.assertTrue(
            liveness._pid_alive(leased_proc.pid),
            "сторож снял прогон задачи с живым lease под --fix — "
            "фильтрация AC-9 отсутствует или сработала не в ту сторону")

        self.assertIn(
            str(orphan_proc.pid), messages,
            "сторож не поднял алерт по прогону задачи БЕЗ lease")
        self.assertFalse(
            liveness._pid_alive(orphan_proc.pid),
            "сторож не снял под --fix прогон задачи БЕЗ lease")


if __name__ == "__main__":
    unittest.main()
