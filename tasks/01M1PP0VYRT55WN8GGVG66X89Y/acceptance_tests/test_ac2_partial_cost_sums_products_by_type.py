"""AC-2 (SPEC: «Частичная стоимость шага по видам токенов, калибровка
курса») — «Частичная стоимость шага с известной по видам разбивкой
usage считается суммой произведений «количество токенов вида × цена
этого вида по курсу роли», а не средней ставкой по сумме всех видов
токенов сразу.»

Интерфейс зафиксирован этим тестом: `spend.partial_cost_usd(role,
tokens_by_type)`, где `tokens_by_type` — словарь по ключам
`config.USAGE_TOKEN_KEYS` (сегодня функция принимает второй аргумент
`partial_tokens: int` — уже просуммированное число, см.
orchestrator/spend.py:143-159; SPEC требование 2 явно требует отказаться
именно от этой суммы одним числом в пользу разбивки по видам — сигнатура
меняется по формулировке требования, не по прихоти теста).

Ставки роли в тесте — свои собственные (`mock.patch.dict`), не значения
`config.TOKEN_RATES` из AC-1: критерий обязан различать формулы
независимо от того, окажутся ли реальные откалиброванные цены четырёх
видов равны друг другу — если бы тест читал `config.TOKEN_RATES`
буквально и разработчик (ошибочно, но не нарушая AC-1 дословно) сделал
все четыре цены одинаковыми, средняя ставка и сумма произведений дали бы
один и тот же результат, и тест не поймал бы мутацию.

Красен до реализации: `spend.partial_cost_usd` сегодня принимает
`partial_tokens: int` и берёт `(input_rate + output_rate) / 2 *
partial_tokens` — вызов с `tokens_by_type` (словарь) на месте `int`
падает уже внутри функции на `partial_tokens * effective`
(`TypeError: unsupported operand type(s) for *: 'dict' and 'float'`).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, spend  # noqa: E402

# Ставки специально различны и не пропорциональны друг другу — среднее
# входа/выхода ((0.000010+0.000020)/2=0.000015) НИКАК не совпадает с
# ценой чтения кэша (0.000001), поэтому старая формула «сумма * среднее»
# и новая «сумма произведений» дают заведомо разные числа.
FAKE_RATES = {
    "input_usd_per_token": 0.000010,
    "output_usd_per_token": 0.000020,
    "cache_creation_usd_per_token": 0.000005,
    "cache_read_usd_per_token": 0.000001,
    "calibrated_at": "2026-09-04",
}

# Разбивка, повторяющая форму реального инцидента 04.09: основной объём
# — дешёвые чтения кэша, а не вход/выход.
TOKENS_BY_TYPE = {
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 9000,
}


class PartialCostSumsProductsByTypeTest(unittest.TestCase):

    def test_ac2_cost_is_the_sum_of_per_type_products_not_the_average_rate(self):
        """Частичная стоимость по известной разбивке usage равна сумме
        «количество × цена вида», не средней ставке, умноженной на
        сумму всех токенов.

        Ловит мутацию: реализация продолжает считать эффективную ставку
        как среднее цены входа/выхода и умножает на общую сумму токенов
        (сегодняшняя формула `spend.partial_cost_usd`) — тогда
        результат совпадёт с `wrong_average_formula` (≈$0.1374), а не с
        `expected` (≈$0.01105), `assertAlmostEqual` провалится.
        """
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            result = spend.partial_cost_usd("test_author", TOKENS_BY_TYPE)

        expected = (
            TOKENS_BY_TYPE["input_tokens"] * FAKE_RATES["input_usd_per_token"]
            + TOKENS_BY_TYPE["output_tokens"] * FAKE_RATES["output_usd_per_token"]
            + TOKENS_BY_TYPE["cache_creation_input_tokens"]
              * FAKE_RATES["cache_creation_usd_per_token"]
            + TOKENS_BY_TYPE["cache_read_input_tokens"]
              * FAKE_RATES["cache_read_usd_per_token"]
        )
        wrong_average_formula = (
            sum(TOKENS_BY_TYPE.values())
            * (FAKE_RATES["input_usd_per_token"] + FAKE_RATES["output_usd_per_token"]) / 2
        )
        self.assertNotAlmostEqual(expected, wrong_average_formula,
                                  msg="сценарий обязан различать формулы — "
                                      "иначе тест ничего не ловит")
        self.assertAlmostEqual(result, expected)

    def test_ac2_zero_tokens_of_every_type_cost_nothing(self):
        """Нулевая разбивка по всем видам стоит ровно $0 — граница
        суммы произведений на пустом наборе слагаемых.

        Ловит мутацию: реализация прибавляет фиксированную «базовую»
        составляющую вне зависимости от количества токенов (например,
        по ошибке использует `calibrated_at`/иное поле как часть
        расчёта) — `assertEqual` с `0.0` провалится.
        """
        zero_tokens = {k: 0 for k in config.USAGE_TOKEN_KEYS}
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            result = spend.partial_cost_usd("test_author", zero_tokens)
        self.assertEqual(result, 0.0)


if __name__ == "__main__":
    unittest.main()
