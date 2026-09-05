"""AC-4 (SPEC: «Частичная стоимость шага по видам токенов, калибровка
курса») — «Токены чтения кэша (cache_read_input_tokens) тарифицируются
по своей цене чтения кэша, а не по цене входного токена.»

Использует тот же интерфейс `spend.partial_cost_usd(role,
tokens_by_type)`, зафиксированный AC-2/AC-3. Здесь разбивка состоит
ИСКЛЮЧИТЕЛЬНО из чтений кэша — цена входа/выхода/записи кэша роли не
участвует в правильном ответе вовсе, поэтому любая формула, хоть
отдалённо путающая чтение кэша со входом, будет поймана.

Красен до реализации: `spend.partial_cost_usd` сегодня принимает
`partial_tokens: int`, а не разбивку — вызов падает той же ошибкой, что
в AC-2 (`TypeError` на `partial_tokens * effective`), до того как
дойдёт до вопроса «по какой цене посчитан cache_read».
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, spend  # noqa: E402

# Цена входа заведомо дороже цены чтения кэша (в 100 раз) — если чтение
# кэша по ошибке тарифицируется как вход, результат будет отличаться на
# два порядка, а не на проценты.
FAKE_RATES = {
    "input_usd_per_token": 0.000100,
    "output_usd_per_token": 0.000100,
    "cache_creation_usd_per_token": 0.000100,
    "cache_read_usd_per_token": 0.000001,
    "calibrated_at": "2026-09-04",
}

CACHE_READ_ONLY_TOKENS = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 9000,
}


class CacheReadPricedAtItsOwnRateTest(unittest.TestCase):

    def test_ac4_cache_read_only_usage_costs_the_cache_read_rate(self):
        """Разбивка usage, состоящая ТОЛЬКО из чтений кэша, стоит ровно
        `count * cache_read_usd_per_token` — цена входа роли к ответу
        не примешивается.

        Ловит мутацию: расчёт по-прежнему использует цену входа для
        всех токенов, не входящих в явный «выход» (типичная путаница —
        «всё, что не выход, считаем входом») — результат совпадёт с
        `priced_as_input`, а не с `expected`, а они различаются в 100
        раз.
        """
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            result = spend.partial_cost_usd("test_author", CACHE_READ_ONLY_TOKENS)

        expected = (CACHE_READ_ONLY_TOKENS["cache_read_input_tokens"]
                   * FAKE_RATES["cache_read_usd_per_token"])
        priced_as_input = (CACHE_READ_ONLY_TOKENS["cache_read_input_tokens"]
                          * FAKE_RATES["input_usd_per_token"])

        self.assertAlmostEqual(result, expected)
        self.assertNotAlmostEqual(result, priced_as_input,
                                  msg="цена чтения кэша не должна совпасть "
                                      "с ценой входа — иначе тест ничего не "
                                      "ловит")

    def test_ac4_lowering_only_the_cache_read_rate_changes_the_result(self):
        """Изменение ТОЛЬКО цены чтения кэша (все остальные три цены
        неизменны) меняет расчётную стоимость той же разбивки — прямое
        доказательство, что чтение кэша тарифицируется своей ценой, а
        не какой-то из трёх остальных (которые в этом сценарии не
        меняются).

        Ловит мутацию: реализация вообще не читает
        `cache_read_usd_per_token` (например, копирует старое поведение
        и использует цену входа для ЛЮБОГО счётчика, кроме
        `output_tokens`) — понижение только цены чтения кэша не
        изменит результат, `assertLess` провалится.
        """
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": FAKE_RATES}):
            before = spend.partial_cost_usd("test_author", CACHE_READ_ONLY_TOKENS)

        cheaper_cache_read = dict(FAKE_RATES, cache_read_usd_per_token=0.0000001)
        with mock.patch.dict(config.TOKEN_RATES, {"test_author": cheaper_cache_read}):
            after = spend.partial_cost_usd("test_author", CACHE_READ_ONLY_TOKENS)

        self.assertLess(after, before,
                        "понижение цены чтения кэша обязано понизить "
                        "стоимость разбивки, состоящей только из чтений кэша")


if __name__ == "__main__":
    unittest.main()
