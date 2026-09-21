"""AC-8: `orchestrator/models.py` разбирает локальный слой
`.artel/models.yaml` — `tiers:`, необязательный `overrides:` и
необязательное явное разрешение модели со статусом `experimental`.

Разобранное сверяется по ЗНАЧЕНИЯМ (`_models.has_value`): имён полей
результата разбора SPEC не называет, а планка — лок и не вправе их
назначать. Формы записи `overrides:` и явного разрешения (плоский тариф
против вложенного прейскуранта; список против отображения) перебираются
`_models.first_success` — законна любая.

Красен до реализации: фикстура падает на отсутствующем `models.yaml`
(каталог создаёт эта задача), а разбирать локальный слой всё равно нечем —
модуля `orchestrator/models.py` нет.
"""
import unittest

import _models
from _sandbox import CatalogSandbox

ROLE = "developer"
OVERRIDE_PRICES = {"input": 4.0, "output": 20.0,
                   "cache_write": 5.0, "cache_read": 0.4}
CALIBRATED_AT = "2026-09-20"
SOURCE = "kalibrovka-po-zhurnalu"


class LocalLayerParsingTest(CatalogSandbox):
    """Локальный слой во временном корне пульта, каталог — настоящий."""

    def setUp(self):
        super().setUp()
        self.write_catalog()

    def parse(self, text: str):
        self.write_local(text)
        return _models.load_local(self.local_path)

    def test_ac8_tiers_map_each_tier_to_a_model_identifier(self):
        """`tiers:` читается как «ярус → идентификатор модели» — каждый из
        трёх ярусов и его модель видны в разборе.

        Ловит мутацию: разбор берёт из `tiers:` только первый ярус (или
        схлопывает три яруса в одну модель) — ярусы `standard`/`cheap`
        молча указывали бы на модель `strong`, и вся вилка «дорогая/
        дешёвая роль» существовала бы только в файле.
        """
        tiers = {"strong": _models.OPUS, "standard": _models.SONNET,
                 "cheap": _models.FABLE}

        parsed = self.parse(_models.local_texts(tiers)[0])

        for tier, model in tiers.items():
            with self.subTest(tier=tier):
                self.assertTrue(_models.has_value(parsed, tier),
                                f"ярус {tier} не виден в разборе: {parsed!r}")
                self.assertTrue(_models.has_value(parsed, model),
                                f"модель {model} не видна в разборе: {parsed!r}")

    def test_ac8_optional_sections_may_be_absent(self):
        """Локальный слой из одних только `tiers:` разбирается без отказа —
        `overrides:` и разрешение `experimental` необязательны.

        Ловит мутацию: схема требует `overrides:` (или явного разрешения)
        всегда — шаблон, который кладут `init`/`doctor --fix` (без
        переопределений), не разобрался бы собственным разбором пульта, и
        свежий пульт вставал бы на первом же шаге роли.
        """
        parsed = self.parse(_models.local_texts(self.default_tiers())[0])

        self.assertIsNotNone(parsed)
        self.assertTrue(_models.has_value(parsed, _models.OPUS))

    def test_ac8_override_carries_four_token_kinds_calibration_and_source(self):
        """`overrides:` по модели несёт собственный тариф по тем же четырём
        видам токенов и поля `calibrated_at` и `source` — все шесть
        значений видны в разборе.

        Ловит мутацию: разбор переопределения берёт только цены, а
        `calibrated_at`/`source` отбрасывает — действующий тариф нельзя
        отличить от прейскуранта каталога ни по дате, ни по происхождению,
        то есть «с указанием источника тарифа» (требование 8) становится
        невыполнимым.
        """
        override = (_models.OPUS, OVERRIDE_PRICES, CALIBRATED_AT, SOURCE)
        texts = _models.local_texts(self.default_tiers(), override=override)

        def attempt(text):
            parsed = self.parse(text)
            for wanted in (*OVERRIDE_PRICES.values(), CALIBRATED_AT, SOURCE):
                assert _models.has_value(parsed, wanted), (
                    f"{wanted!r} не видно в разборе переопределения: {parsed!r}")
            return parsed

        self.assertIsNotNone(_models.first_success(texts, attempt))

    def test_ac8_experimental_model_may_be_allowed_explicitly(self):
        """Модель со статусом `experimental`, явно разрешённая локальным
        слоем, разрешается цепочкой (а без разрешения — отказ, AC-11).

        Ловит мутацию: разрешение разобрано, но ни на что не влияет —
        `resolve_role` по-прежнему отказывает, и разрешение остаётся
        мёртвым разделом файла, который Оператор заполняет впустую.
        """
        self.write_catalog(_models.with_experimental(_models.FABLE))
        self.set_roles_tiers({ROLE: "strong"})
        tiers = {tier: _models.FABLE for tier in _models.TIERS}
        texts = _models.local_texts(tiers, allow=_models.FABLE)

        def attempt(text):
            self.write_local(text)
            resolved = _models.resolve(ROLE)
            assert _models.has_value(resolved, _models.FABLE), (
                f"разрешение не отдало модель {_models.FABLE}: {resolved!r}")
            return resolved

        self.assertIsNotNone(_models.first_success(texts, attempt))


if __name__ == "__main__":
    unittest.main()
