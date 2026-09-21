"""AC-10: `models.resolve_role(role)` отдаёт ярус, идентификатор модели,
провайдера, минимум версии CLI и действующий тариф с источником —
переопределение локального слоя, иначе прейскурант каталога.

Результат сверяется по ЗНАЧЕНИЯМ (`_models.has_value`): имён полей
результата SPEC не называет, планка — лок и не вправе их назначать.

Красен до реализации: фикстура падает на отсутствующем `models.yaml`
(каталог создаёт эта задача), а собирать цепочку «роль → ярус → модель →
провайдер» всё равно нечем — `models.resolve_role` не существует.
"""
import unittest

import _models
from _sandbox import CatalogSandbox

ROLE = "developer"
OVERRIDE_PRICES = {"input": 4.0, "output": 20.0,
                   "cache_write": 5.5, "cache_read": 0.4}
CALIBRATED_AT = "2026-09-20"
SOURCE = "kalibrovka-po-zhurnalu"


class ResolveChainTest(CatalogSandbox):
    """Настоящий каталог, локальный слой и карта исполнителей с ярусом."""

    def setUp(self):
        super().setUp()
        self.write_catalog()
        self.set_roles_tiers({ROLE: "strong"})
        self.tiers = {"strong": _models.OPUS, "standard": _models.SONNET,
                      "cheap": _models.SONNET}
        _path, self.entry = _models.model_entries(
            _models.catalog_document())[_models.OPUS]

    def catalog_min_cli(self) -> str:
        versions = [v for v in self.entry.values()
                    if isinstance(v, str) and _models.VERSION_RE.match(v)]
        self.assertTrue(versions, f"у {_models.OPUS} нет минимума CLI")
        return versions[0]

    def resolve_plain(self):
        self.write_local(_models.local_texts(self.tiers)[0])
        return _models.resolve(ROLE)

    def test_ac10_chain_carries_tier_model_provider_and_cli_minimum(self):
        """Разрешение роли `developer` с ярусом `strong` отдаёт сам ярус,
        идентификатор модели яруса, провайдера этой модели и минимум
        версии CLI из каталога.

        Ловит мутацию: разрешение отдаёт одну лишь модель (как сегодня
        отдавало поле `model:`) — `runner` остаётся без минимума версии
        CLI и провайдера, и предполётная сверка версии, ради которой
        каталог заведён, делается снова по старой таблице.
        """
        resolved = self.resolve_plain()

        for wanted in ("strong", _models.OPUS, "claude", self.catalog_min_cli()):
            with self.subTest(value=wanted):
                self.assertTrue(
                    _models.has_value(resolved, wanted),
                    f"{wanted!r} нет в разрешённой цепочке: {resolved!r}")

    def test_ac10_without_override_the_rate_is_the_catalog_list_price(self):
        """Без переопределения в локальном слое действующий тариф — четыре
        цены прейскуранта каталога.

        Ловит мутацию: тариф не отдаётся вовсе (разрешение ограничено
        моделью и провайдером) — потребитель тарифа из части 2 линии
        получил бы пустое место там, где SPEC обещает действующий тариф.
        """
        resolved = self.resolve_plain()

        for kind, price in self.entry[_models.PRICE_KEY].items():
            with self.subTest(kind=kind):
                self.assertTrue(
                    _models.has_value(resolved, float(price)),
                    f"цены {kind}={price} нет в разрешении: {resolved!r}")

    def test_ac10_override_of_the_local_layer_wins_over_the_list_price(self):
        """Переопределение по модели в локальном слое становится
        действующим тарифом, и источник тарифа отличается от случая без
        переопределения.

        Ловит мутацию: переопределение разбирается, но действующим
        тарифом остаётся прейскурант каталога (или источник тарифа —
        константа «каталог») — калибровка Оператора не доезжает до
        потребителя, и отличить её от прейскуранта нельзя.
        """
        plain = self.resolve_plain()
        override = (_models.OPUS, OVERRIDE_PRICES, CALIBRATED_AT, SOURCE)
        texts = _models.local_texts(self.tiers, override=override)

        def attempt(text):
            self.write_local(text)
            resolved = _models.resolve(ROLE)
            for price in OVERRIDE_PRICES.values():
                assert _models.has_value(resolved, price), (
                    f"тариф переопределения {price} не стал действующим: "
                    f"{resolved!r}")
            return resolved

        resolved = _models.first_success(texts, attempt)

        self.assertNotEqual(
            _models.nonnumeric(resolved), _models.nonnumeric(plain),
            f"источник тарифа не отличает переопределение от прейскуранта "
            f"каталога: {resolved!r}")


if __name__ == "__main__":
    unittest.main()
