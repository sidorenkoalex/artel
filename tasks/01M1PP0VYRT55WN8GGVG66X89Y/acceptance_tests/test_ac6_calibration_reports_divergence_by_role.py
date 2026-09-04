"""AC-6 (SPEC: «Частичная стоимость шага по видам токенов, калибровка
курса») — «Пульт по завершённым шагам (журнал store.journal, записи с
фактической ценой из финального события потока type: result,
total_cost_usd) сравнивает эту фактическую цену с расчётной ценой по
видам токенов и печатает коэффициент расхождения по роли.»

Интерфейс зафиксирован этим тестом (требование 4 явно оставляет выбор
«новая команда либо часть report.py» разработчику — сама вычислительная
функция всё равно нужна в любом случае, тест пинует именно её):
`orchestrator/report.py::token_rate_divergence(conn) ->
dict[str, float]` — по каждой роли, по которой в журнале есть
завершённые шаги с известной стоимостью, коэффициент расхождения
`abs(расчётная_сумма - фактическая_сумма) / фактическая_сумма`.

Источник данных — журнал: завершённый шаг с известной стоимостью
журналируется действием `"agent cost KNOWN"` (`spend.charge_step`,
интерфейс AC-8) с фактической ценой (та же строка `cost_note`, что и
сегодня) и разбивкой usage по видам. Этот тест сам создаёт такие записи
через `spend.charge_step`, не полагаясь на разбор конкретного текста —
только на то, что `charge_step` с `cost["tokens_by_type"]` заданным
оставляет данные, которые `token_rate_divergence` умеет прочитать и
пересчитать.

«Печатает» (вторая половина критерия) проверяется через `report.
cmd_report()` — существующую команду пульта (`orchestrator/report.py`,
уже печатает `spent_usd`/`spent_estimate_usd`, см. предшествующую задачу
01M1NWCM3TDY0YABEKE8DYQA1C) — самый естественный выбор «части
существующей команды report», разрешённый требованием 4 буквально.

Красен до реализации: `orchestrator/report.py` не несёт атрибута
`token_rate_divergence` — `AttributeError` на первом обращении;
`spend.charge_step` не понимает ключ `cost["tokens_by_type"]` и не
журналирует действие `"agent cost KNOWN"` — до появления
`token_rate_divergence` это не проверяется отдельно, но без него
источника данных для калибровки тоже нет.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, report, spend  # noqa: E402
from _sandbox import TokenRateTmpRootTest  # noqa: E402

FAKE_RATES = {
    "input_usd_per_token": 0.000010,
    "output_usd_per_token": 0.000020,
    "cache_creation_usd_per_token": 0.000005,
    "cache_read_usd_per_token": 0.000001,
    "calibrated_at": "2026-09-04",
}

TOKENS_BY_TYPE = {
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 9000,
}
# Расчётная цена по FAKE_RATES/TOKENS_BY_TYPE — та же арифметика, что в
# AC-2/AC-3 (≈$0.01105). Фактическая цена ЗАВЕДОМО другая (в 2 раза
# больше расчётной) — реальный шаг потока сообщил total_cost_usd,
# отличную от того, что дал бы курс роли, — ровно ситуация, которую
# калибровка обязана заметить.
CALCULATED_USD = sum(
    TOKENS_BY_TYPE[k] * FAKE_RATES[rate_field] for k, rate_field in (
        ("input_tokens", "input_usd_per_token"),
        ("output_tokens", "output_usd_per_token"),
        ("cache_creation_input_tokens", "cache_creation_usd_per_token"),
        ("cache_read_input_tokens", "cache_read_usd_per_token"),
    ))
ACTUAL_USD = CALCULATED_USD * 2.0


class CalibrationReportsDivergenceByRoleTest(TokenRateTmpRootTest):

    def _seed_known_cost_step(self):
        cost = {"usd": ACTUAL_USD, "tokens": sum(TOKENS_BY_TYPE.values()),
               "tokens_by_type": dict(TOKENS_BY_TYPE)}
        spend.charge_step(self.conn, self.TASK, "test_author", cost, "попытка 1/3")

    def test_ac6_divergence_coefficient_matches_actual_vs_calculated_price(self):
        """Коэффициент расхождения роли `test_author` после одного
        завершённого шага с известной фактической ценой и разбивкой
        usage равен `|расчётная - фактическая| / фактическая`.

        Ловит мутацию: калибровка сравнивает фактическую цену с самой
        собой (например, по ошибке берёт `total_cost_usd` как
        «расчётную» тоже) — коэффициент окажется 0.0 вместо ожидаемого
        ≈0.5, `assertAlmostEqual` провалится.
        """
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            self._seed_known_cost_step()
            result = report.token_rate_divergence(self.conn)

        expected_coefficient = abs(CALCULATED_USD - ACTUAL_USD) / ACTUAL_USD
        self.assertIn("test_author", result)
        self.assertAlmostEqual(result["test_author"], expected_coefficient, places=4)

    def test_ac6_role_without_any_completed_known_cost_steps_is_absent(self):
        """Роль, для которой в журнале нет ни одного завершённого шага
        с известной стоимостью, не попадает в результат вовсе — не
        считается расхождением по умолчанию (например, 0.0).

        Ловит мутацию: калибровка заводит запись с коэффициентом 0.0
        для КАЖДОЙ роли `config.TOKEN_RATES`, а не только для тех, у
        кого реально есть данные, — `assertNotIn` провалится.
        """
        result = report.token_rate_divergence(self.conn)
        self.assertNotIn("test_author", result)

    def test_ac6_cmd_report_prints_the_divergence_label_and_the_role(self):
        """`report.cmd_report()` печатает коэффициент расхождения по
        роли в `.artel/report.html` — метка «коэффициент расхождения» и
        имя роли присутствуют в выводе.

        Ловит мутацию: `token_rate_divergence` реализована, но её
        результат никуда не выводится (посчитана, но не напечатана) —
        HTML не содержит ни метки, ни роли, `assertIn` провалится.
        """
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            self._seed_known_cost_step()
            report.cmd_report()

        html = (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")
        self.assertIn("коэффициент расхождения", html)
        self.assertIn("test_author", html)


if __name__ == "__main__":
    unittest.main()
