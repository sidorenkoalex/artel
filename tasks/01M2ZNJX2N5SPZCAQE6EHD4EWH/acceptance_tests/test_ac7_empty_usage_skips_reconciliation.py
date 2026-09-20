"""AC-7: CLI не отдал usage (`tokens_by_type` пуст) — сверка курса
пропускается молча: ни коэффициента в журнале, ни алерта, учёт шага не
прерывается.

Зелёный с рождения: сегодня `spend.charge_step` при пустой разбивке
просто начисляет факт CLI и не пишет строку KNOWN вовсе, а сверки нет ни
у одного шага — ни коэффициентов, ни алертов в журнале не появляется, и
все ассерты ниже (они сравнивают состояние ДО и ПОСЛЕ шагов без usage)
выполняются. Тест стоит барьером под будущую сверку: она обязана
появиться ЗА проверкой пустой разбивки, а не перед ней — расчёт по курсу
от пустого usage равен нулю и дал бы коэффициент ровно 1.0 (расхождение
«на все сто») на каждом таком шаге.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rates  # noqa: E402

# Факт CLI шага, по которому usage не приехал: цена есть, разбивки нет.
ACTUAL_USD = 3.75

# Два вида «usage не отдан»: пустая разбивка и её отсутствие вовсе —
# ровно то, что кладёт `spend.parse_cost_event` в событие без счётчиков.
EMPTY_USAGE_COSTS = (
    ("попытка 2/3", {"usd": ACTUAL_USD, "tokens": None, "tokens_by_type": {}}),
    ("попытка 3/3", {"usd": ACTUAL_USD, "tokens": None, "tokens_by_type": None}),
)


class EmptyUsageTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def task_row(self):
        return self.conn.execute("SELECT * FROM tasks WHERE id=?",
                                 (self.TASK,)).fetchone()

    def coefficient_details(self) -> list:
        """Детали журнала, несущие коэффициент расхождения."""
        return [detail for _, _, detail in _rates.journal(self.conn, self.TASK)
                if "коэффициент" in detail]

    def test_ac7_step_without_usage_is_charged_without_coefficient_or_alert(self):
        """У роли уже есть полноценный шаг с разбивкой usage; следом
        идут два шага без разбивки (пустой словарь и её отсутствие
        вовсе). Факт CLI начислен обоим, ни одного НОВОГО коэффициента
        в журнале не появилось, уже записанная строка KNOWN не тронута,
        алерт расхождения не заведён, `charge_step` вернул обычную
        заметку о стоимости.

        Ловит мутацию: разработчик считает сверку безусловно, до
        проверки пустой разбивки — `spend.partial_cost_usd` по пустому
        usage вернёт 0.0 (законный ноль известного курса, не `None`), и
        шаг без usage либо допишет коэффициент туда, где его быть не
        должно, либо перепишет им чужую, уже закрытую строку KNOWN
        предыдущего шага, да ещё и откроет ложный алерт по роли.
        """
        spend.charge_step(
            self.conn, self.TASK, _rates.ROLE,
            _rates.cost(_rates.actual_usd_for_coefficient(
                _rates.threshold() / 2)),
            "попытка 1/3")
        known_before = _rates.details(self.conn, self.TASK, _rates.KNOWN_ACTION)
        coefficients_before = self.coefficient_details()
        spent_before = self.task_row()["spent_usd"]

        for numbered, cost in EMPTY_USAGE_COSTS:
            with self.subTest(tokens_by_type=cost["tokens_by_type"]):
                note = spend.charge_step(self.conn, self.TASK, _rates.ROLE,
                                         cost, numbered)

                self.assertIn("стоимость", note,
                              "AC-7: учёт шага не прерывается — заметка о "
                              "стоимости возвращается как обычно")

        self.assertAlmostEqual(
            self.task_row()["spent_usd"], spent_before + 2 * ACTUAL_USD,
            places=6, msg="AC-7: факт CLI обоих шагов без usage начислен")
        self.assertEqual(
            _rates.details(self.conn, self.TASK, _rates.KNOWN_ACTION),
            known_before,
            "AC-7: шаг без разбивки usage не правит уже записанные строки "
            "KNOWN")
        self.assertEqual(
            self.coefficient_details(), coefficients_before,
            "AC-7: без разбивки usage новых коэффициентов в журнале не "
            "появляется")
        self.assertEqual(_rates.divergence_alerts(self.conn), [],
                         "AC-7: без разбивки usage алерт не заводится")


if __name__ == "__main__":
    unittest.main()
