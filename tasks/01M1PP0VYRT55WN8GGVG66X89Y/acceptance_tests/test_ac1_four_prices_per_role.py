"""AC-1 (SPEC: «Частичная стоимость шага по видам токенов, калибровка
курса») — «config.TOKEN_RATES[role] несёт четыре цены за токен: вход,
выход, запись кэша, чтение кэша — по одной на каждый счётчик
config.USAGE_TOKEN_KEYS.»

Интерфейс полей зафиксирован этим тестом по буквальным примерам SPEC
(требование 1): `input_usd_per_token`, `output_usd_per_token` — уже
существующие два поля (задача 01M1NWCM3TDY0YABEKE8DYQA1C); к ним
добавляются `cache_creation_usd_per_token`, `cache_read_usd_per_token` —
ровно так, как SPEC называет их «например», продолжая уже принятую
конвенцию именования (см. `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/
acceptance_tests/test_ac1_token_rate_table.py`, тот же приём).

Красен до реализации: `config.TOKEN_RATES[role]` сегодня несёт только
`input_usd_per_token`/`output_usd_per_token`/`calibrated_at` (см.
orchestrator/config.py:318-327, калибровка 04.09) — на каждой роли
`assertIn`/`assertEqual` первого и третьего теста находят отсутствие
`cache_creation_usd_per_token`/`cache_read_usd_per_token`
(`AssertionError`), а прямая индексация `entry[rate_field]` во втором
тесте падает `KeyError`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

PIPELINE_ROLES = ("analyst", "test_author", "developer", "reviewer")

# Счётчик usage (config.USAGE_TOKEN_KEYS) -> поле цены TOKEN_RATES[role],
# которое эта задача обязана считать за него (требование 1 буквально).
RATE_FIELD_FOR_USAGE_KEY = {
    "input_tokens": "input_usd_per_token",
    "output_tokens": "output_usd_per_token",
    "cache_creation_input_tokens": "cache_creation_usd_per_token",
    "cache_read_input_tokens": "cache_read_usd_per_token",
}


class FourPricesPerRoleTest(unittest.TestCase):

    def test_ac1_rate_field_exists_for_every_usage_counter(self):
        """Для каждой из четырёх ролей конвейера и каждого счётчика
        `config.USAGE_TOKEN_KEYS` в `config.TOKEN_RATES[role]` есть
        отдельное поле цены — по одной на счётчик, не общее на несколько.

        Ловит мутацию: разработчик оставляет только цену входа/выхода
        и не заводит отдельных полей для записи/чтения кэша (продолжая
        временную меру 04.09, где обоим типам назначалась одна ставка
        через `input_usd_per_token`) — `assertIn` для
        `cache_creation_usd_per_token`/`cache_read_usd_per_token`
        падает.
        """
        for role in PIPELINE_ROLES:
            entry = config.TOKEN_RATES[role]
            for usage_key, rate_field in RATE_FIELD_FOR_USAGE_KEY.items():
                with self.subTest(role=role, usage_key=usage_key):
                    self.assertIn(rate_field, entry,
                                 f"{role}: нет поля цены {rate_field!r} "
                                 f"для счётчика {usage_key!r}")

    def test_ac1_all_four_prices_are_positive_numbers(self):
        """Все четыре цены каждой роли — положительные числа, не
        нулевые заглушки и не пропуски.

        Ловит мутацию: разработчик заводит поле `cache_read_usd_per_token`
        со значением `0` как заглушку вместо реальной калибровки —
        `assertGreater` на нулевой цене падает.
        """
        for role in PIPELINE_ROLES:
            entry = config.TOKEN_RATES[role]
            for usage_key, rate_field in RATE_FIELD_FOR_USAGE_KEY.items():
                with self.subTest(role=role, usage_key=usage_key):
                    self.assertGreater(entry[rate_field], 0.0,
                                       f"{role}: цена {rate_field!r} должна быть > 0")

    def test_ac1_four_distinct_fields_cover_all_usage_keys_one_to_one(self):
        """Ровно четыре поля цены на роль, по одному на каждый счётчик
        `config.USAGE_TOKEN_KEYS` — не меньше (какой-то вид токена не
        учтён) и не смешаны в одно общее поле.

        Ловит мутацию: разработчик считает запись и чтение кэша одной
        общей ценой (например, оставляет только `cache_usd_per_token`
        на оба счётчика вместо раздельных `cache_creation_usd_per_token`/
        `cache_read_usd_per_token`) — множество полей цены не совпадёт
        с ожидаемым набором, `assertEqual` ниже упадёт.
        """
        expected_fields = set(RATE_FIELD_FOR_USAGE_KEY.values())
        self.assertEqual(len(expected_fields), len(config.USAGE_TOKEN_KEYS),
                         "по одному полю цены на каждый счётчик usage")
        for role in PIPELINE_ROLES:
            with self.subTest(role=role):
                entry = config.TOKEN_RATES[role]
                price_fields = {k for k in entry if k.endswith("_usd_per_token")}
                self.assertEqual(price_fields, expected_fields,
                                 f"{role}: набор ценовых полей не совпадает "
                                 f"с четырьмя счётчиками usage")


if __name__ == "__main__":
    unittest.main()
