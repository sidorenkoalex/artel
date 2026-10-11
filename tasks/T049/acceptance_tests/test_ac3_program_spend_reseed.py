"""AC-3 (tasks/T049/SPEC.md): пересев программного расхода из
`docs/retro/T*.md`.

«Пересев расхода из `docs/retro/T*.md` попадает в учёт порогов программы
(70%/90%) и оставляет в журнале БД запись «расход пересеян из RETRO: $X
по N задачам».»

Требование 4/5 SPEC оставляет команду-триггер пересева на усмотрение
разработчика («исполняется тем же `init`/отдельной командой пересева») —
AC-3 сам не называет команду, поэтому тест не имеет права её угадывать
(test-authoring: «тест ТОЛЬКО из формулировки критерия»). Вместо этого
тест зовёт саму операцию пересева напрямую — `budget.reseed_program_
spend(conn)`, новая функция, по тому же приёму, что и `doctor.check_
leases` в tasks/T044/acceptance_tests/test_lease_readonly_and_doctor.py
(новая функция на момент написания её теста, по образцу существующих
`budget.check_program_spend`/`budget.enforce_budget` в том же модуле).

Формат «Стоимость итого: $X.XX» — дословно из `orchestrator/retro.py`
`_cost_block` (образец `docs/retro/T043.md`, названный в «Материалы»
SPEC.md этой задачи).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, budget, catalog, config, spend, store  # noqa: E402
from _sandbox import TmpRootTest, capture  # noqa: E402


class ProgramSpendReseedSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        (config.ROOT / "docs" / "retro").mkdir(parents=True)

    def write_retro(self, task_id: str, cost_usd: float) -> None:
        (config.ROOT / "docs" / "retro" / f"{task_id}.md").write_text(
            f"# RETRO: {task_id} — тестовая задача\n\n"
            f"Итог: done, sha 0000000000000000000000000000000000000000\n"
            f"Стоимость итого: ${cost_usd:.2f}\n", encoding="utf-8")


class ReseedJournalTest(ProgramSpendReseedSandbox):

    def test_ac3_journal_records_the_exact_reseed_message(self):
        self.write_retro("T001", 10.00)
        self.write_retro("T002", 5.50)

        budget.reseed_program_spend(store.db())

        rows = store.db().execute(
            "SELECT detail FROM steps ORDER BY id").fetchall()
        details = [r["detail"] or "" for r in rows]
        self.assertTrue(
            any("расход пересеян из RETRO: $15.50 по 2 задачам" in d
                for d in details),
            f"журнал БД не содержит записи о пересеве расхода из RETRO "
            f"(ожидалось «расход пересеян из RETRO: $15.50 по 2 "
            f"задачам»): {details}")


class ReseedThresholdAccountingTest(ProgramSpendReseedSandbox):

    def test_ac3_reseeded_sum_counts_toward_program_thresholds(self):
        self.write_retro("T001", 10.00)
        self.write_retro("T002", 5.50)  # сумма $15.50

        with mock.patch.object(config, "PROGRAM_STOP_LOSS_USD", 20.0):
            budget.reseed_program_spend(store.db())

            store.insert_task(store.db(), "T900", "После холодного старта",
                              "in_dev", "task/t900-x", config.DEFAULT_TARGET,
                              25.0)
            conn = store.db()
            cost = {"usd": 3.0, "tokens": None}
            # Тот же порядок, что и в runner.run_agent_once (см.
            # tests/test_doctor.py ProgramThresholdAlertTest): расход
            # прибавляется к spent_usd ДО проверки порога.
            spend.charge_step(conn, "T900", "developer", cost, "1/1")
            budget.check_program_spend(conn, "T900", cost)

        thresholds = alerts.open_alerts(store.db(), "threshold")
        self.assertTrue(
            any("90%" in (a["message"] or "") for a in thresholds),
            "$15.50, пересеянных из RETRO, не оказались в сумме, от "
            "которой считаются пороги программы: реальная трата $3 "
            "поверх них (итого $18.50 из потолка $20) обязана пересечь "
            "порог 90% ($18), но алерт не появился")


if __name__ == "__main__":
    unittest.main()
