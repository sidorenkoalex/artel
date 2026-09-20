"""AC-9: `spent_usd` после `charge_step` растёт на факт CLI
(`cost["usd"]`), а не на расчёт по курсу, и `tests/test_step_cost.py`
проходит зелёным.

Зелёный с рождения: сегодня `spend.charge_step` начисляет ровно
`cost["usd"]` (`store.charge`), а `tests/test_step_cost.py` зелёный. Обе
проверки стоят барьером под правку этой задачи: рядом с начислением
появляется расчёт по курсу той же разбивки usage, и он не имеет права
подменить собой факт — с ним же и сверяется (AC-4).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rates  # noqa: E402

# Модуль существующего набора, который эта задача правит по числам курса
# (SPEC требование 9): его прогон — источник истины «остался зелёным», а
# не пересказ. Полный `tests/` здесь не гоняется намеренно — его держит
# CI, а бюджет прогона приёмки один на все файлы планки.
STEP_COST_MODULE = "tests.test_step_cost"


class SpentUsdIsTheFactTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def task_row(self):
        return self.conn.execute("SELECT * FROM tasks WHERE id=?",
                                 (self.TASK,)).fetchone()

    def test_ac9_charge_step_adds_the_cli_fact_not_the_rate_calculation(self):
        """Шаг, чей факт CLI заметно расходится с расчётом по курсу:
        в `spent_usd` уходит факт, расчёт остаётся только в журнале.

        Ловит мутацию: разработчик, добавляя сверку, подменяет
        начисление расчётом по курсу (или прибавляет обе величины —
        `store.charge` вызывается дважды) — `spent_usd` разъедется с
        суммой, которую реально выставил CLI, и весь бюджетный контур
        задачи начнёт считать деньги по калибровочной таблице вместо
        счёта.
        """
        calculated = _rates.calculated_usd()
        actual = _rates.actual_usd_for_coefficient(2 * _rates.threshold())
        self.assertGreater(
            abs(calculated - actual), 0.01,
            "фикстура бессмысленна: факт CLI обязан отличаться от расчёта")

        spend.charge_step(self.conn, self.TASK, _rates.ROLE,
                          _rates.cost(actual), "попытка 1/3")

        self.assertAlmostEqual(
            self.task_row()["spent_usd"], actual, places=6,
            msg="AC-9: в spent_usd идёт факт CLI (`cost['usd']`)")

    def test_ac9_existing_step_cost_suite_stays_green(self):
        """Существующий `tests/test_step_cost.py` проходит зелёным —
        настоящим прогоном, не пересказом.

        Ловит мутацию: разработчик поднимает курс до opus-5, но не
        обновляет ожидаемые числа тех тестов набора, что привязаны к
        ценам Sonnet (SPEC требование 9), — прогон вернёт ненулевой
        код, и планка покажет это здесь, а не на CI после мержа.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", STEP_COST_MODULE],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=100)

        self.assertEqual(
            result.returncode, 0,
            f"AC-9: {STEP_COST_MODULE} обязан остаться зелёным:\n"
            f"{result.stdout[-3000:]}\n{result.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main()
