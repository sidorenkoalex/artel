"""AC-6: коэффициент выше порога заводит алерт расхождения прямо в
момент `charge_step` — без запуска `report`; ниже порога алерта нет;
повтор по той же роли второго открытого алерта не плодит.

`report` здесь не зовётся ни разу: сегодняшний контур
(`report.token_rate_divergence`) поднимает этот алерт только при
генерации отчёта, а отчёт с 13.09 не запускался — ровно эта тишина и
стоила недоучёта шага (SPEC, «Контекст»).

Красен до реализации: `spend.charge_step` сегодня вообще не считает
расхождение и не обращается к `alerts` — открытых алертов расхождения
после него нет ни при каком коэффициенте.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _rates  # noqa: E402


class DivergenceAlertAtChargeStepTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.assertGreater(
            _rates.threshold(), 0.0,
            "фикстуры ниже строятся от порога: при нулевом пороге "
            "«выше» и «ниже» неразличимы")

    def charge(self, coefficient: float, numbered: str) -> None:
        """Шаг, чей факт CLI расходится с расчётом по курсу ровно на
        заданный коэффициент."""
        spend.charge_step(
            self.conn, self.TASK, _rates.ROLE,
            _rates.cost(_rates.actual_usd_for_coefficient(coefficient)),
            numbered)

    def test_ac6_coefficient_above_threshold_raises_the_alert_right_away(self):
        """Шаг с расхождением вдвое выше порога заводит открытый алерт
        расхождения курса, хотя `report` не запускался.

        Ловит мутацию: разработчик считает коэффициент в `charge_step`,
        но заводить алерт оставляет прежнему месту — отчёту (или
        сравнивает с порогом через `>=`/`<` наоборот) — тогда сигнал
        снова ждёт запуска `report`, и список открытых алертов после
        шага пуст.
        """
        self.charge(2 * _rates.threshold(), "попытка 1/3")

        raised = _rates.divergence_alerts(self.conn)
        self.assertEqual(
            len(raised), 1,
            f"AC-6: коэффициент выше порога "
            f"{_rates.threshold()} обязан завести ровно один алерт "
            f"{alerts.TOKEN_RATE_DIVERGENCE_SOURCE}; открыто: {raised}")
        self.assertIsNone(raised[0]["target"],
                          "AC-6: расхождение курса — по роли поперёк задач")
        self.assertIn(_rates.ROLE, raised[0]["message"],
                      "AC-6: алерт обязан называть роль, чей курс разошёлся")

    def test_ac6_coefficient_below_threshold_raises_nothing(self):
        """Шаг с расхождением вдвое НИЖЕ порога алерта не заводит.

        Ловит мутацию: разработчик заводит алерт на любое ненулевое
        расхождение (сравнение с порогом потеряно при переносе кода из
        `report` в `charge_step`) — каждый шаг начинает открывать алерт,
        и порог перестаёт значить что-либо.
        """
        self.charge(_rates.threshold() / 2, "попытка 1/3")

        self.assertEqual(
            _rates.divergence_alerts(self.conn), [],
            f"AC-6: коэффициент ниже порога {_rates.threshold()} алерта "
            f"не заводит")

    def test_ac6_repeated_charge_step_of_the_same_role_keeps_one_alert(self):
        """Второй шаг той же роли с тем же превышением второго
        открытого алерта не открывает.

        Ловит мутацию: разработчик заводит алерт через `alerts.
        raise_alert` напрямую вместо `raise_token_rate_divergence_alert`
        — дедуп там идёт по точному тексту сообщения, а текст несёт
        растущие суммы и число шагов, поэтому каждый следующий шаг
        открывал бы ещё один алерт, и Оператор получил бы поток копий
        одного сигнала вместо одного устойчивого.
        """
        self.charge(2 * _rates.threshold(), "попытка 1/3")
        self.charge(2 * _rates.threshold(), "попытка 2/3")

        raised = _rates.divergence_alerts(self.conn)
        self.assertEqual(
            len(raised), 1,
            f"AC-6: дедуп по роли обязан держать ровно один открытый "
            f"алерт расхождения; открыто: {raised}")


if __name__ == "__main__":
    unittest.main()
