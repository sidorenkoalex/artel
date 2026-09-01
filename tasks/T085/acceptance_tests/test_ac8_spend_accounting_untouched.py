"""AC-8 (tasks/T085/SPEC.md): `store.total_spent`, стоимости в RETRO
(`orchestrator/retro.py`) и пересев холодного старта
(`orchestrator/budget.reseed_program_spend`, T049) не изменены этой
задачей.

Не текстовая проверка диффа (test_author её не видит — ещё нет кода),
а характеризующий прогон трёх функций на известной фикстуре: если
разработчик тронет форму учёта расхода (парсинг «Стоимость итого» в
RETRO, суммирование `total_spent`, идемпотентность пересева) в процессе
удаления условия A1 из автогейта, эти ассерты — уже существующие в
`tests/test_program_spend_reseed.py` и `tests/test_retro.py`
инварианты, дословно то же ожидаемое поведение — покраснеют первыми.

Зелёный с рождения: SPEC требование 5 прямо запрещает трогать этот
путь, и сегодня (до кода задачи) он ведёт себя именно так.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import budget, config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class SpendAccountingUntouchedTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()

    def write_retro(self, task_id: str, cost_usd: float) -> None:
        retro_dir = config.ROOT / "docs" / "retro"
        retro_dir.mkdir(parents=True, exist_ok=True)
        (retro_dir / f"{task_id}.md").write_text(
            f"# RETRO: {task_id} — тестовая задача\n\n"
            f"Итог: done, sha {'0' * 40}\n"
            f"Стоимость итого: ${cost_usd:.2f}\n", encoding="utf-8")

    def test_ac8_total_spent_sums_live_task_rows(self):
        store.insert_task(self.conn, "T001", "Задача 1", "done", "",
                          config.DEFAULT_TARGET, 10.0)
        store.update_task(self.conn, "T001", spent_usd=7.5)
        store.insert_task(self.conn, "T002", "Задача 2", "done", "",
                          config.DEFAULT_TARGET, 10.0)
        store.update_task(self.conn, "T002", spent_usd=2.5)

        self.assertAlmostEqual(store.total_spent(self.conn), 10.0)

    def test_ac8_reseed_sums_retro_of_rows_missing_from_the_db(self):
        self.write_retro("T003", 10.0)
        self.write_retro("T004", 5.5)

        budget.reseed_program_spend(self.conn)

        self.assertAlmostEqual(store.total_spent(self.conn), 15.5)

    def test_ac8_reseed_is_idempotent_not_additive_on_repeat(self):
        self.write_retro("T005", 10.0)
        budget.reseed_program_spend(self.conn)

        budget.reseed_program_spend(self.conn)

        self.assertAlmostEqual(
            store.total_spent(self.conn), 10.0,
            "AC-8: повторный пересев обязан перезаписывать сумму, не "
            "задваивать её")

    def test_ac8_reseed_skips_tasks_whose_row_is_still_alive(self):
        """Пересев учитывает только RETRO задач, чьей строки СЕЙЧАС нет
        в `tasks` — иначе живой `spent_usd` задваивается синтетической
        строкой пересева (ADR-0005 п.5)."""
        store.insert_task(self.conn, "T006", "Живая задача", "done", "",
                          config.DEFAULT_TARGET, 20.0)
        store.update_task(self.conn, "T006", spent_usd=20.0)
        self.write_retro("T006", 20.0)

        budget.reseed_program_spend(self.conn)

        self.assertAlmostEqual(
            store.total_spent(self.conn), 20.0,
            "AC-8: RETRO задачи с живой строкой в tasks не имеет права "
            "задваивать расход")


if __name__ == "__main__":
    unittest.main()
