"""AC-5: шаг роли на модели провайдера `codex` списывается расчётом по
действующему тарифу модели, а запись шага несёт разбивку по четырём видам
цены.

Учёт шага берётся штатной точкой пульта (`spend.charge_step` — та же, что
зовёт `runner._account_step`), а стоимость шага — итогом запуска, который
отдал разбор строки `turn.completed` провайдером: ветка расчёта по тарифу
выбирается ровно этими двумя входами (нет цены в итоге + `cost_from_cli:
false` у раздела каталога).

Красен до реализации: `CodexProvider.parse_output_line` ещё не реализован — итога запуска и разбивки токенов, из которых считается стоимость шага, взять негде.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stream import (PROVIDER, TURN_COMPLETED_TZ, codex_model_id,  # noqa: E402
                     provider)
from orchestrator import config, models, spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402


class StepCostTest(TaskSeededTmpRootTest):
    """Деньги шага роли на модели раздела `codex` каталога."""

    ROLE = "developer"

    def details(self, action: str) -> list:
        return [row["detail"]
                for row in store.task_steps(store.db(), self.TASK)
                if row["action"] == action]

    def test_ac5_the_step_is_charged_by_the_tariff_and_not_by_zero(self):
        """Итог запуска codex без цены + `cost_from_cli: false` в каталоге:
        в `spent_usd` идёт расчёт по действующему тарифу модели (не ноль,
        не «не учтено»), а запись «agent cost KNOWN» несёт разбивку по
        всем четырём видам цены.

        Ожидаемая сумма считается ОТ каталога (`spend.model_tariff` +
        `spend.tariff_cost_usd`), а не литералом: прейскурант — крутилка
        Оператора, и тест обязан пережить её поворот.

        Ловит мутацию: разбор отдаёт `usd = 0.0` вместо «цены нет» —
        `charge_step` уходит на путь факта CLI, списывает нулевую
        стоимость и пишет её как известную: каждый шаг роли на Codex
        оказывается бесплатным, потолок бюджета задачи не расходуется
        вовсе, и недоучёт копится без единой записи об этом.
        """
        model = codex_model_id()
        self.assertFalse(
            models.catalog_model(model).cost_from_cli,
            "предпосылка AC-5: раздел codex каталога несёт cost_from_cli: false")

        cost = spend.run_result_cost(
            provider().parse_output_line(TURN_COMPLETED_TZ).run_result)
        self.assertIsNotNone(cost, "итог запуска получен")
        self.assertIsNone(cost["usd"], "итог запуска цены не несёт")

        effective = spend.model_tariff(model)
        self.assertIsNotNone(effective, f"тариф модели {model} не разрешён")
        expected = spend.tariff_cost_usd(effective.tariff,
                                         cost["tokens_by_type"])
        self.assertGreater(expected, 0.0, "тариф каталога не нулевой")

        conn = store.db()
        numbered = (f"попытка 1/{config.AGENT_ATTEMPTS}, model={model}, "
                    f"provider={PROVIDER}")
        spend.charge_step(conn, self.TASK, self.ROLE, cost, numbered, model)

        spent = store.get_task(store.db(), self.TASK)["spent_usd"]
        self.assertAlmostEqual(spent, expected, places=6)
        self.assertGreater(spent, 0.0, "шаг списан не нулём")
        self.assertEqual(self.details(spend.UNCHARGED_COST_JOURNAL_ACTION), [],
                         "стоимость шага учтена, а не оставлена без учёта")

        known = self.details(spend.KNOWN_COST_JOURNAL_ACTION)
        self.assertTrue(known, "шаг записан известной стоимостью")
        self.assertIn(spend.SOURCE_TARIFF, known[-1])
        for kind in models.PRICE_KINDS:
            self.assertIn(f"{kind}={cost['tokens_by_type'][kind]}", known[-1],
                          f"вид {kind} не назван в записи шага")


if __name__ == "__main__":
    unittest.main()
