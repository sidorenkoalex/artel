"""AC-1 (SPEC: «Стоимость частичного шага при таймауте: курс токенов
вместо тишины») — «orchestrator/config.py несёт именованную таблицу
курса токенов по идентификатору роли (analyst, test_author, developer,
reviewer) с ценой входного токена, ценой выходного токена и датой
калибровки на роль; roles.yaml не изменён.»

Эскалация вопроса 1 (конфликт требования 1 для роли `developer` с
локнутыми тестами T040) разрешена Оператором в ANSWER-2.md: вариант A —
курс заводится на все четыре роли, включая `developer`; два теста T040
(`tests/test_step_cost.py:319` и `:634`) переписывает под новое поведение
разработчик в `in_dev` (ADR-0002, решение Оператора), test_author их не
трогает — этот файл их не касается.

Интерфейс таблицы (`config.TOKEN_RATES`, ключ — идентификатор роли,
значение — словарь с полями `input_usd_per_token`, `output_usd_per_token`,
`calibrated_at`) задан этим тестом: SPEC называет только состав данных
(«цена входного токена, цена выходного токена, дата калибровки на
роль»), не имя атрибута/полей — разработчик реализует под эту форму.

Красен до реализации: `orchestrator/config.py` сегодня не несёт
атрибута `TOKEN_RATES` (константы модуля — только пути и лимиты, курса
токенов нет) — обращение к `config.TOKEN_RATES` падает `AttributeError`
на первой же строке тела каждого теста.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, roles  # noqa: E402

PIPELINE_ROLES = ("analyst", "test_author", "developer", "reviewer")

# Набор полей, который roles.yaml несёт для каждой из четырёх ролей
# сегодня (снимок на момент написания теста — orchestrator/roles.py::load(),
# roles.yaml:14-29). Требование 1 запрещает править roles.yaml: курс
# живёт только в config.py, поэтому набор полей каждой роли в roles.yaml
# обязан остаться ровно таким же — без добавленных ценовых полей.
ROLES_YAML_FIELDS_BEFORE = {"executor", "token_slot", "skills"}


class TokenRateTableTest(unittest.TestCase):

    def test_ac1_token_rates_cover_all_four_pipeline_roles(self):
        """`config.TOKEN_RATES` несёт запись на каждую из четырёх ролей
        конвейера (analyst, test_author, developer, reviewer) —
        идентификатор роли ровно в том виде, в каком он есть в
        roles.yaml сегодня.

        Ловит мутацию: разработчик заводит курс только для части ролей
        (например, пропускает `developer`, следуя старому поведению
        T040, вместо решения ANSWER-2/вариант A) — `assertIn` для
        пропущенной роли падает.
        """
        for role in PIPELINE_ROLES:
            with self.subTest(role=role):
                self.assertIn(role, config.TOKEN_RATES,
                              f"курс для роли {role!r} отсутствует в таблице")

    def test_ac1_token_rate_entry_carries_input_output_price_and_date(self):
        """Запись курса каждой из четырёх ролей несёт положительную цену
        входного токена, положительную цену выходного токена и
        непустую дату калибровки.

        Ловит мутацию: разработчик заводит запись-заглушку с нулевой
        или отсутствующей ценой (`input_usd_per_token=0` либо поле не
        задано) — вместо реального курса калибровки; `assertGreater`
        на нулевой цене падает, `assertIn`/`assertTrue` на дате — на
        пустой строке.
        """
        for role in PIPELINE_ROLES:
            with self.subTest(role=role):
                entry = config.TOKEN_RATES[role]
                self.assertGreater(entry["input_usd_per_token"], 0.0,
                                   f"{role}: цена входного токена должна быть > 0")
                self.assertGreater(entry["output_usd_per_token"], 0.0,
                                   f"{role}: цена выходного токена должна быть > 0")
                self.assertTrue(str(entry["calibrated_at"]).strip(),
                                f"{role}: дата калибровки не может быть пустой")

    def test_ac1_roles_yaml_pricing_fields_not_added(self):
        """roles.yaml не изменён курсом: набор полей каждой из четырёх
        ролей в roles.yaml остаётся ровно `{executor, token_slot,
        skills}` — без добавленных ценовых полей, курс живёт только в
        `config.py`.

        Ловит мутацию: разработчик заводит курс прямо в roles.yaml
        (например, добавляет `input_usd_per_token:` под записью роли)
        вместо `config.py` — набор ключей роли расширяется сверх
        `ROLES_YAML_FIELDS_BEFORE`, `assertEqual` падает.
        """
        document = roles.load()
        for role in PIPELINE_ROLES:
            with self.subTest(role=role):
                self.assertEqual(set(document[role].keys()),
                                 ROLES_YAML_FIELDS_BEFORE,
                                 f"{role}: набор полей roles.yaml изменился")


if __name__ == "__main__":
    unittest.main()
