"""AC-9, AC-11 — 01M31ZHSA6HMH40C2JTDPQJQNZ: стоимость шага без цены от
CLI считается по действующему тарифу модели, а модель без тарифа на том
же пути не проходит молча.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Итог запуска получен без цены (либо модель шага — у провайдера с
`cost_from_cli: false`): `spent_usd` задачи растёт на
`spend.tariff_cost_usd` по действующему тарифу модели шага, в журнале
появляется «agent cost KNOWN» с `источник=расчёт по тарифу`, коэффициент
расхождения в строке не считается и алерт расхождения курса не заводится.

AC-11. Модель без разрешённого тарифа на пути AC-9: `spent_usd` не
увеличивается на ноль молча — в журнале есть именованная запись о
неучтённой стоимости шага, и открыт алерт.

Образец здесь — `_sample.STREAM_RESULT_USAGE_ONLY`: usage несёт только
итог запуска, поэтому сумма по тарифу одна и та же, считать её по
разбивке итога или по накопленным за шаг токенам (SPEC выбор не
фиксирует).

Красен до реализации: сегодня итог запуска без `total_cost_usd` —
это `spend.parse_cost_event() is None`, то есть ветка «agent cost
UNKNOWN» (orchestrator/spend.py:156-159): `spent_usd` не меняется,
строки KNOWN нет вовсе, признак каталога `cost_from_cli` пульт не
читает.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _run  # noqa: E402
import _sample  # noqa: E402
from orchestrator import alerts, config, models, spend  # noqa: E402


def prices_of(tariff) -> dict:
    """Четыре цены действующего тарифа словарём по видам."""
    return {kind: getattr(tariff, kind) for kind in models.PRICE_KINDS}


class TariffCostPathTest(_run.StepRunSandbox):

    def divergence_alerts(self) -> list:
        return [a for a in self.alerts()
                if a["source"] == alerts.TOKEN_RATE_DIVERGENCE_SOURCE]

    def test_ac9_run_result_without_a_price_is_charged_by_the_tariff(self):
        """Итог запуска без цены списывается по действующему тарифу
        модели шага: `spent_usd` вырос ровно на расчёт, строка KNOWN
        называет источник расчётом, коэффициента сверки в ней нет и
        алерт расхождения курса не заводится.

        Ловит мутацию: разработчик оставил для итога без цены прежнюю
        ветку «agent cost UNKNOWN» (или списал ноль) — `spent_usd`
        остаётся нулевым, и шаг второго провайдера не стоит ничего,
        сколько бы токенов он ни сжёг.
        """
        effective = spend.role_tariff(self.ROLE)
        expected = _provider.expected_tariff_usd(_sample.USAGE_RESULT,
                                                 prices_of(effective.tariff))

        self.run_stream(_sample.STREAM_RESULT_USAGE_ONLY)

        self.assertAlmostEqual(self.task_row()["spent_usd"], expected)
        self.assertGreater(expected, 0.0, "образец обязан стоить денег")
        detail = self.details(_run.KNOWN)[-1]
        self.assertIn(_run.SOURCE_TARIFF, detail)
        self.assertNotIn(_run.SOURCE_CLI, detail)
        self.assertNotIn("коэффициент", detail,
                         "сверять расчёт не с чем: факта CLI у этого шага нет")
        self.assertEqual(self.divergence_alerts(), [])

    def test_ac9_provider_marked_cost_from_cli_false_uses_the_tariff(self):
        """Модель провайдера, помеченного в каталоге `cost_from_cli:
        false`, считается по тарифу даже тогда, когда цена в итоге
        запуска есть.

        Ловит мутацию: признак каталога по-прежнему не читается — шаг
        списывается ценой, которую CLI сообщил «для себя», и `spent_usd`
        расходится с действительным счётом ровно там, где SPEC требует
        считать по тарифу.
        """
        stub = _provider.CliPriceFreeProvider()
        _provider.register(self, stub, self.ROLE)
        _provider.use_catalog(self, _provider.catalog_text(cost_from_cli=False))
        config.MODELS_LOCAL.write_text(
            _provider.local_text(_provider.PRICE_FREE_MODEL), encoding="utf-8")
        expected = _provider.expected_tariff_usd(_sample.USAGE_RESULT)

        self.run_stream(_sample.STREAM_RESULT_USAGE_ONLY_PRICED)

        self.assertAlmostEqual(self.task_row()["spent_usd"], expected)
        self.assertNotAlmostEqual(expected, _sample.EXPECTED_COST_USD,
                                  msg="тариф планки обязан отличаться от "
                                      "цены CLI образца — иначе сходство "
                                      "сумм ничего не доказывает")
        detail = self.details(_run.KNOWN)[-1]
        self.assertIn(_run.SOURCE_TARIFF, detail)
        self.assertEqual(self.divergence_alerts(), [])

    def test_ac11_model_without_a_tariff_is_journaled_and_alerted(self):
        """Тот же путь, но тариф модели шага не разрешается: `spent_usd`
        не растёт на ноль молча — в журнале именованная запись о
        неучтённой стоимости, и открыт алерт.

        Ловит мутацию: расчёт по тарифу написан как `usd = tariff_cost(
        tariff or 0)` — модель без тарифа даёт тихий ноль, шаг выглядит
        учтённым, и недоучёт копится до конца программы без единого
        сигнала.

        Тариф гасится в трёх точках его разрешения внутри `spend.py`
        (`role_tariff`, `model_tariff`) и под ними — в
        `models.resolve_model`: цепочку РОЛИ гасить нельзя, без неё шаг
        отказал бы ещё до старта агента, по другой причине.
        """
        for target, attr, value in (
                (spend, "role_tariff", lambda *a, **k: None),
                (spend, "model_tariff", lambda *a, **k: None)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        def unresolved(*args, **kwargs):
            raise models.ModelsError("тариф модели планки не разрешён")

        patcher = mock.patch.object(models, "resolve_model", unresolved)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.run_stream(_sample.STREAM_RESULT_USAGE_ONLY)

        self.assertEqual(self.task_row()["spent_usd"], 0.0)
        named = [action for action in self.actions()
                 if "cost" in action.lower() and action != _run.KNOWN]
        self.assertTrue(named,
                        f"нет именованной записи о неучтённой стоимости "
                        f"шага:\n{self.journal_text()}")
        self.assertTrue(self.alerts(),
                        f"стоимость шага не учтена, а алерта нет:\n"
                        f"{self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
