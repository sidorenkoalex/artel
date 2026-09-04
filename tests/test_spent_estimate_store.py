"""Юнит-тесты `orchestrator.store.charge_estimate`/`total_estimate` (SPEC
01M1NWCM3TDY0YABEKE8DYQA1C, требования 1, 3, 6) — колонка
`tasks.spent_estimate_usd`, отдельная от `spent_usd`/`charge`/`total_spent`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class ChargeEstimateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, "T900", "Задача", "in_dev",
                          "task/t900-x", config.DEFAULT_TARGET, 50.0)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", ("T900",)).fetchone()

    def test_fresh_task_starts_at_zero(self):
        """Ловит мутацию: миграция задаёт колонке `spent_estimate_usd`
        DEFAULT NULL (или не задаёт DEFAULT вовсе) — тогда у свежей
        задачи значение будет `None`, а не 0.0."""
        self.assertEqual(self.task_row()["spent_estimate_usd"], 0.0)

    def test_charge_estimate_adds_to_the_column(self):
        """Ловит мутацию: `charge_estimate` по ошибке (копипаста
        `charge`) прибавляет сумму к `spent_usd` вместо
        `spent_estimate_usd` — тогда проверяемая колонка останется
        0.0."""
        store.charge_estimate(self.conn, "T900", 5.0)

        self.assertEqual(self.task_row()["spent_estimate_usd"], 5.0)

    def test_repeated_charges_accumulate(self):
        """Ловит мутацию: `charge_estimate` перезаписывает колонку
        (`SET spent_estimate_usd=?`) вместо накопления
        (`spent_estimate_usd=spent_estimate_usd+?`) — тогда после двух
        вызовов останется последнее значение 2.5 вместо суммы 7.5."""
        store.charge_estimate(self.conn, "T900", 5.0)
        store.charge_estimate(self.conn, "T900", 2.5)

        self.assertAlmostEqual(self.task_row()["spent_estimate_usd"], 7.5)

    def test_charge_estimate_does_not_touch_spent_usd(self):
        """Ловит мутацию: `charge_estimate` копирует SQL `charge` и
        обновляет обе колонки одним запросом — тогда `spent_usd`
        после вызова `charge_estimate` изменится сверх уже
        начисленных $3.00."""
        store.charge(self.conn, "T900", 3.0)
        store.charge_estimate(self.conn, "T900", 5.0)

        row = self.task_row()
        self.assertEqual(row["spent_usd"], 3.0)
        self.assertEqual(row["spent_estimate_usd"], 5.0)


class TotalEstimateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()

    def test_no_tasks_is_zero(self):
        """Ловит мутацию: `total_estimate` возвращает `row["total"]`
        без `or 0.0` — на пустой таблице `SUM()` даёт SQL `NULL`, и
        функция вернёт `None` вместо 0.0."""
        self.assertEqual(store.total_estimate(self.conn), 0.0)

    def test_sums_across_every_task_regardless_of_target(self):
        """Ловит мутацию: `total_estimate` фильтрует по одному target'у
        (как `WHERE target=?`) вместо суммы по ВСЕМ задачам всех
        target'ов — тогда результат будет 4.0 или 6.0, а не 10.0
        (сумма по обоим target'ам)."""
        store.insert_task(self.conn, "T900", "A", "in_dev", "task/t900-x",
                          config.DEFAULT_TARGET, 50.0)
        store.insert_task(self.conn, "T901", "B", "in_dev", "task/t901-x",
                          "other-target", 50.0)
        store.charge_estimate(self.conn, "T900", 4.0)
        store.charge_estimate(self.conn, "T901", 6.0)

        self.assertAlmostEqual(store.total_estimate(self.conn), 10.0)

    def test_does_not_include_spent_usd(self):
        """Ловит мутацию: `total_estimate` копирует SQL `total_spent`
        и суммирует `spent_usd` вместо `spent_estimate_usd` — тогда
        результат будет 9.0 вместо 0.0."""
        store.insert_task(self.conn, "T900", "A", "in_dev", "task/t900-x",
                          config.DEFAULT_TARGET, 50.0)
        store.charge(self.conn, "T900", 9.0)

        self.assertEqual(store.total_estimate(self.conn), 0.0)


if __name__ == "__main__":
    unittest.main()
