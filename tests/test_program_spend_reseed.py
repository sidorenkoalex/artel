"""Юнит-тесты пересева программного расхода из RETRO (orchestrator/budget.
reseed_program_spend, SPEC T049, требования 4-5).

Сквозной путь (пересев учитывается порогом 90% через `cmd_init`) уже
покрыт `tasks/T049/acceptance_tests/test_ac3_program_spend_reseed.py` —
здесь только сама функция: журнал, идемпотентность, вырожденные случаи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import budget, config, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402


class ProgramSpendReseedTest(SchemaConnTmpRootTest):

    def write_retro(self, task_id: str, cost_usd: float) -> None:
        retro_dir = config.ROOT / "docs" / "retro"
        retro_dir.mkdir(parents=True, exist_ok=True)
        (retro_dir / f"{task_id}.md").write_text(
            f"# RETRO: {task_id} — тестовая задача\n\n"
            f"Итог: done, sha {'0' * 40}\n"
            f"Стоимость итого: ${cost_usd:.2f}\n", encoding="utf-8")

    def test_no_retro_dir_creates_no_row_and_no_journal(self):
        budget.reseed_program_spend(self.conn)

        self.assertFalse(store.task_exists(
            self.conn, config.PROGRAM_SPEND_RESEED_TASK_ID))
        self.assertEqual(store.total_spent(self.conn), 0.0)

    def test_empty_retro_dir_creates_no_row(self):
        (config.ROOT / "docs" / "retro").mkdir(parents=True)

        budget.reseed_program_spend(self.conn)

        self.assertFalse(store.task_exists(
            self.conn, config.PROGRAM_SPEND_RESEED_TASK_ID))

    def test_sums_cost_across_all_retro_files(self):
        self.write_retro("T001", 10.0)
        self.write_retro("T002", 5.5)

        budget.reseed_program_spend(self.conn)

        self.assertAlmostEqual(store.total_spent(self.conn), 15.5)

    def test_journal_records_exact_message_format(self):
        self.write_retro("T001", 10.0)
        self.write_retro("T002", 5.5)

        budget.reseed_program_spend(self.conn)

        steps = store.task_steps(self.conn, config.PROGRAM_SPEND_RESEED_TASK_ID)
        details = [s["detail"] for s in steps]
        self.assertIn("расход пересеян из RETRO: $15.50 по 2 задачам", details)

    def test_reseed_overwrites_not_accumulates_on_repeat(self):
        """Идемпотентность (требование 4): повторный пересев не задваивает
        сумму — перезаписывает, а не прибавляет к прежнему значению."""
        self.write_retro("T001", 10.0)
        budget.reseed_program_spend(self.conn)
        self.write_retro("T002", 5.0)

        budget.reseed_program_spend(self.conn)

        self.assertAlmostEqual(store.total_spent(self.conn), 15.0)

    def test_retro_file_without_a_parseable_total_is_skipped(self):
        retro_dir = config.ROOT / "docs" / "retro"
        retro_dir.mkdir(parents=True)
        (retro_dir / "T003.md").write_text(
            "# RETRO: T003 — без строки стоимости\n", encoding="utf-8")
        self.write_retro("T001", 10.0)

        budget.reseed_program_spend(self.conn)

        steps = store.task_steps(self.conn, config.PROGRAM_SPEND_RESEED_TASK_ID)
        self.assertIn("по 1 задачам", steps[-1]["detail"])
        self.assertAlmostEqual(store.total_spent(self.conn), 10.0)

    def test_retro_of_task_still_in_db_is_not_double_counted(self):
        """Regression REVIEW T049 итерации 1, замечание blocker: «тёплый»
        пульт (БД не потеряна) — задача с живой строкой `tasks` И своим
        RETRO не должна засчитываться в пересев второй раз поверх уже
        учтённого `tasks.spent_usd`."""
        store.insert_task(self.conn, "T001", "задача", "done", "",
                          config.DEFAULT_TARGET, 50.0)
        store.update_task(self.conn, "T001", spent_usd=50.0)
        self.write_retro("T001", 50.0)

        budget.reseed_program_spend(self.conn)

        self.assertFalse(store.task_exists(
            self.conn, config.PROGRAM_SPEND_RESEED_TASK_ID))
        self.assertAlmostEqual(store.total_spent(self.conn), 50.0)

    def test_mixes_lost_and_live_rows_without_double_counting(self):
        store.insert_task(self.conn, "T001", "задача", "done", "",
                          config.DEFAULT_TARGET, 50.0)
        store.update_task(self.conn, "T001", spent_usd=50.0)
        self.write_retro("T001", 50.0)
        self.write_retro("T002", 20.0)  # строки T002 в БД уже нет — потеряна

        budget.reseed_program_spend(self.conn)

        steps = store.task_steps(self.conn, config.PROGRAM_SPEND_RESEED_TASK_ID)
        self.assertIn("расход пересеян из RETRO: $20.00 по 1 задачам",
                     [s["detail"] for s in steps])
        self.assertAlmostEqual(store.total_spent(self.conn), 70.0)

    def test_reseed_row_id_is_outside_the_tnnn_numbering_space(self):
        self.write_retro("T001", 3.0)

        budget.reseed_program_spend(self.conn)

        self.assertEqual(
            store.task_number(config.PROGRAM_SPEND_RESEED_TASK_ID), 0)
        row = store.get_task(self.conn, config.PROGRAM_SPEND_RESEED_TASK_ID)
        self.assertEqual(row["state"], "done")


if __name__ == "__main__":
    unittest.main()
