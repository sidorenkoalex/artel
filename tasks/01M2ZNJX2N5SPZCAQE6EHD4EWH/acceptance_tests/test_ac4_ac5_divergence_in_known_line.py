"""AC-4, AC-5: `charge_step` дописывает в строку KNOWN расчёт по курсу и
коэффициент расхождения роли с датой калибровки её курса, а в сверку
берёт только строки KNOWN этой роли начиная с той даты.

Красен до реализации: сверка курса с фактом сегодня живёт ТОЛЬКО в
`report.token_rate_divergence` и считается лишь при запуске отчёта —
`spend.charge_step` не дописывает в строку KNOWN ни расчёта по курсу,
ни коэффициента (`orchestrator/spend.py`, ветка `if tokens_by_type`),
поэтому оба разбора возвращают `None`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rates  # noqa: E402


class DivergenceWrittenAtChargeStepTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.calculated = _rates.calculated_usd()

    def charge(self, actual: float, numbered: str) -> None:
        spend.charge_step(self.conn, self.TASK, _rates.ROLE,
                          _rates.cost(actual), numbered)

    def last_known(self) -> str:
        known = _rates.details(self.conn, self.TASK, _rates.KNOWN_ACTION)
        self.assertTrue(known, "шаг обязан оставить строку KNOWN в журнале")
        return known[-1]

    def test_ac4_known_line_carries_the_rate_calculation_and_coefficient(self):
        """Один завершённый шаг: в его же строке KNOWN стоят расчёт по
        курсу роли и коэффициент расхождения, названный вместе с датой
        калибровки курса этой роли.

        Коэффициент фикстуры — половина порога алерта (порог берётся из
        `config`, не литералом): расхождение заметное, но алерта не
        заводит — эту границу проверяет AC-6, здесь мешать не должна.

        Ловит мутацию: разработчик пишет в строку коэффициент, но берёт
        дату не из курса РОЛИ, а из «сегодня» (`store.now`) или из
        жёсткого литерала — подпись перестанет отвечать на вопрос «с
        какой даты считана эта цифра», и при следующей смене модели
        (новая `calibrated_at`) сверка снова смешает две модели, не
        сказав об этом.
        """
        expected = _rates.threshold() / 2
        self.charge(_rates.actual_usd_for_coefficient(expected), "попытка 1/3")

        detail = self.last_known()
        self.assertIn(f"коэффициент роли с {_rates.rate_date()}=", detail,
                      "AC-4: коэффициент обязан стоять рядом с датой "
                      "калибровки курса роли")
        calculated = _rates.calculated_in(detail)
        self.assertIsNotNone(calculated,
                             f"AC-4: в строке KNOWN нет «расчёт по курсу=$…»: "
                             f"{detail}")
        self.assertAlmostEqual(
            calculated, self.calculated, places=2,
            msg="AC-4: расчёт по курсу обязан совпасть с "
                "`spend.partial_cost_usd` по той же разбивке")
        self.assertAlmostEqual(
            _rates.coefficient_in(detail), expected, places=2,
            msg="AC-4: коэффициент — расхождение расчёта с фактом CLI")

    def test_ac5_known_step_older_than_the_calibration_date_is_left_out(self):
        """Строка KNOWN, записанная РАНЬШЕ даты калибровки курса (шаг
        другой модели), на коэффициент свежих шагов не влияет.

        Сценарий: один сильно расходящийся шаг состарен на день раньше
        `calibrated_at`, затем два шага с фактом CLI ровно по курсу.
        Коэффициент последней строки — ноль; вошёл бы старый шаг,
        коэффициент был бы заметно другим (фикстура проверяет эту
        разницу до ассерта).

        Ловит мутацию: разработчик считает сверку по ВСЕМ строкам KNOWN
        роли, забыв фильтр по дате (или сравнивая дату не с `ts` строки,
        а с датой запуска) — тогда шаги Sonnet и opus-5 снова
        складываются в одну сумму, и коэффициент последней строки
        уедет с нуля.
        """
        stale_actual = _rates.actual_usd_for_coefficient(
            4 * _rates.threshold())
        self.charge(stale_actual, "попытка 1/3")
        _rates.backdate_known_rows(self.conn)
        self.charge(self.calculated, "попытка 2/3")
        self.charge(self.calculated, "попытка 3/3")

        with_stale = (abs(3 * self.calculated - (stale_actual + 2 * self.calculated))
                      / (stale_actual + 2 * self.calculated))
        self.assertGreater(
            with_stale, 0.05,
            "фикстура бессмысленна: со старым шагом коэффициент обязан "
            "заметно отличаться от нуля")
        coefficient = _rates.coefficient_in(self.last_known())
        self.assertIsNotNone(coefficient,
                             "AC-5: свежая строка KNOWN обязана нести коэффициент")
        self.assertAlmostEqual(
            coefficient, 0.0, places=2,
            msg="AC-5: в сверку входят только шаги с даты калибровки — "
                "факт CLI свежих шагов равен расчёту по курсу, коэффициент ноль")


if __name__ == "__main__":
    unittest.main()
