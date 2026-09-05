"""AC-3 (SPEC: «Частичная стоимость шага по видам токенов, калибровка
курса») — «Частичная стоимость ТАЙМАУТА шага
(orchestrator.spend.charge_missing_result, сценарий обрыва потока без
финального события) с известной по видам разбивкой usage равна сумме
стоимостей по видам (регресс-проверка AC-2 в этом конкретном сценарии —
источник эскалации 04.09).»

Интерфейс: пятый позиционный/именованный параметр
`spend.charge_missing_result` — `partial_tokens` — меняет тип с
просуммированного `int` (сегодня, orchestrator/spend.py:162-226) на
словарь-разбивку по `config.USAGE_TOKEN_KEYS`, тем же приёмом, что
`spend.partial_cost_usd` в AC-2 — именно эта пара функций и была
источником эскалации 04.09 (SPEC «Контекст»): `charge_missing_result`
зовёт `partial_cost_usd` напрямую (докстрока функции, тест
`tests/test_step_cost.py::test_known_rate_charge_matches_partial_cost_usd`
— «одна формула на обе точки, не две рассинхронные»), поэтому регресс
здесь проверяется тем же приёмом — сверкой с независимо вычисленным
`partial_cost_usd`.

Роль сценария — `test_author`, не `developer`: тот же довод, что в
предшествующей задаче 01M1NWCM3TDY0YABEKE8DYQA1C
(`test_ac2_known_rate_partial_charge.py`) — `developer` несёt отдельно
залоченные тесты T040 (`tests/test_step_cost.py:322,393`), эта задача их
не трогает.

Красен до реализации: `spend.charge_missing_result` сегодня зовёт
`partial_cost_usd(role, partial_tokens)` с `partial_tokens` как единым
`int`; передача словаря-разбивки на это место падает той же ошибкой,
что и AC-2 (`TypeError` внутри `partial_cost_usd` на `partial_tokens *
effective`), до того как дойдёт до `store.charge`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, spend  # noqa: E402
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


class TimeoutCostMatchesTypeBreakdownTest(TokenRateTmpRootTest):

    def test_ac3_timeout_partial_spend_equals_partial_cost_usd_of_the_breakdown(self):
        """Сумма, прибавленная к `spent_usd` при таймауте с известной
        по видам разбивкой usage, — ровно та, что независимо считает
        `spend.partial_cost_usd` по той же роли и той же разбивке.

        Ловит мутацию: `charge_missing_result` при переходе на разбивку
        суммирует токены сам и применяет старую среднюю ставку (не
        зовёт `partial_cost_usd` по видам) — `assertAlmostEqual` разойдётся
        с независимо посчитанным `expected` (≈$0.01105 против ≈$0.1374
        по старой формуле).
        """
        conn = self.conn
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            spend.charge_missing_result(
                conn, self.TASK, "test_author", "попытка 1/3", "таймаут шага",
                TOKENS_BY_TYPE, saw_usage_event=True)
            expected = spend.partial_cost_usd("test_author", TOKENS_BY_TYPE)

        self.assertAlmostEqual(self.task_row()["spent_usd"], expected)

    def test_ac3_cache_read_heavy_timeout_costs_much_less_than_the_old_average_rate(self):
        """Регресс-проверка самого инцидента 04.09: таймаут с объёмом,
        в основном состоящим из дешёвых чтений кэша, обходится на
        порядок дешевле, чем при старой средней ставке входа/выхода.

        Ловит мутацию: возврат к сумме одним числом и средней ставке —
        `spent_usd` окажется примерно в 12 раз больше `expected`
        (≈$0.1374 вместо ≈$0.01105), `assertLess` провалится.
        """
        conn = self.conn
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            spend.charge_missing_result(
                conn, self.TASK, "test_author", "попытка 1/3", "таймаут шага",
                TOKENS_BY_TYPE, saw_usage_event=True)

        old_average_formula = (
            sum(TOKENS_BY_TYPE.values())
            * (FAKE_RATES["input_usd_per_token"] + FAKE_RATES["output_usd_per_token"]) / 2
        )
        self.assertLess(self.task_row()["spent_usd"], old_average_formula / 5,
                        "разбивка по видам обязана давать заметно меньшую "
                        "сумму, чем старая средняя ставка на объёме, где "
                        "большинство токенов — дешёвые чтения кэша")


if __name__ == "__main__":
    unittest.main()
