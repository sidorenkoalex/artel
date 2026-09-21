"""AC-2 — 01M300A14KRHCFB0DQXVCBJEKF: `spend.partial_cost_usd` считает по
действующему тарифу МОДЕЛИ, каждый вид токенов — своей ценой.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. `spend.partial_cost_usd` считает стоимость разбивки usage по
четырём ценам действующего тарифа МОДЕЛИ (каждый вид токенов — своей
ценой): подмена тарифа модели меняет результат, а смена роли при той же
модели — нет.

Песочница: каталог с двумя моделями разной цены, ярусы, где `developer`
и `reviewer` приходят на одну модель, а `test_author` — на другую.

Красен до реализации: `spend.partial_cost_usd` берёт цену из
`config.TOKEN_RATES[role]` (`orchestrator/spend.py:253`), где у всех
четырёх ролей одна и та же ставка, — сумма не зависит ни от модели, ни
от её тарифа, и совпасть с ожиданием по прейскуранту планки может только
случайно.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import spend  # noqa: E402


class PartialCostFollowsTheModelTariffTest(_tariff.TariffSandbox):

    def test_ac2_each_token_kind_is_priced_by_the_tariff_of_the_model(self):
        """Сумма по разбивке usage равна сумме произведений «счётчик вида
        × цена этого вида тарифа модели», а не расчёту по любой другой
        цене.

        Ловит мутацию: все четыре счётчика тарифицируются одной ценой
        (входа) либо цены сопоставлены видам со сдвигом — в разбивке
        планки 2 млн чтений кэша по $0.30/млн против 20 тыс. выхода по
        $15/млн, поэтому любая перестановка цен уводит сумму на порядок,
        и `assertAlmostEqual` разойдётся.
        """
        expected = _tariff.expected_cost_usd(_tariff.MODEL_ALFA)

        actual = spend.partial_cost_usd(_tariff.ROLE_ON_ALFA, _tariff.TOKENS)

        self.assertAlmostEqual(actual, expected, places=9)

    def test_ac2_another_role_on_the_same_model_gets_the_same_sum(self):
        """Две роли одного яруса (одна и та же модель) считают одну и ту
        же стоимость одной и той же разбивки usage.

        Ловит мутацию: цена по-прежнему ищется по роли (словарь «роль →
        тариф» переехал из `config` в `models.py`, но остался по роли) —
        как только у двух ролей записи разойдутся, одинаковые шаги на
        одной модели станут стоить по-разному, а смена модели опять
        пройдёт молча.
        """
        tokens = _tariff.TOKENS

        own = spend.partial_cost_usd(_tariff.ROLE_ON_ALFA, tokens)
        other = spend.partial_cost_usd(_tariff.OTHER_ROLE_ON_ALFA, tokens)

        self.assertAlmostEqual(own, other, places=9)
        self.assertAlmostEqual(
            spend.partial_cost_usd(_tariff.ROLE_ON_BETA, tokens),
            _tariff.expected_cost_usd(_tariff.MODEL_BETA), places=9)

    def test_ac2_substituting_the_model_tariff_changes_the_sum(self):
        """Собственный тариф локального слоя поверх прейскуранта той же
        модели меняет результат ровно во столько раз, во сколько подняты
        цены, — и одинаково для обеих ролей на этой модели.

        Ловит мутацию: расчёт берёт ПРЕЙСКУРАНТ каталога вместо
        действующего тарифа (`Resolution.list_price` вместо
        `Resolution.tariff`) — переопределение Оператора (прокси, скидка,
        свой счёт) не влияло бы на учёт расхода вовсе, и сумма осталась
        бы прежней.
        """
        expected = _tariff.expected_cost_usd(_tariff.MODEL_ALFA)
        self.use_local(overrides={_tariff.MODEL_ALFA:
                                  _tariff.scaled(_tariff.MODEL_ALFA, 2.0)})

        own = spend.partial_cost_usd(_tariff.ROLE_ON_ALFA, _tariff.TOKENS)
        other = spend.partial_cost_usd(_tariff.OTHER_ROLE_ON_ALFA,
                                       _tariff.TOKENS)

        self.assertAlmostEqual(own, expected * 2.0, places=9)
        self.assertAlmostEqual(other, expected * 2.0, places=9)
        self.assertAlmostEqual(
            spend.partial_cost_usd(_tariff.ROLE_ON_BETA, _tariff.TOKENS),
            _tariff.expected_cost_usd(_tariff.MODEL_BETA), places=9)


if __name__ == "__main__":
    unittest.main()
