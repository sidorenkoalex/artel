"""AC-1/AC-2: каталог `models.yaml` в корне репозитория — состав и числа.

Красен до реализации: `models.yaml` в корне репозитория ещё нет (его
создаёт эта задача) — чтение файла падает `FileNotFoundError`, а модуля
`orchestrator/models.py`, который его разбирает, не существует.
"""
import unittest

import _models


class CatalogStructureTest(unittest.TestCase):
    """Настоящий `models.yaml` рабочей копии, разобранный разбором пульта
    (`orchestrator/yamlmini.py`) и модулем задачи."""

    def setUp(self):
        self.doc = _models.catalog_document()
        self.entries = _models.model_entries(self.doc)

    def test_ac1_provider_section_carries_cli_tool_version_and_cost_flag(self):
        """Раздел провайдера `claude` несёт имя инструмента CLI,
        минимальную версию CLI провайдера и признак `cost_from_cli`.

        Ловит мутацию: раздел провайдера сведён к списку моделей (имя
        инструмента и минимум версии остались литералами в
        `orchestrator/providers/claude.py`/`stack.py`) — каталог перестаёт
        быть местом, где живёт провайдер, и второй провайдер снова правит
        код вместо файла.
        """
        sections = _models.provider_sections(self.doc)
        self.assertIn("claude", sections,
                      f"раздела провайдера claude нет в каталоге: "
                      f"{sorted(sections)}")
        section = sections["claude"]
        scalars = {k: v for k, v in section.items() if not isinstance(v, dict)}

        self.assertIn("claude", list(scalars.values()),
                      f"имени инструмента CLI нет среди полей раздела: "
                      f"{scalars}")
        versions = [v for v in scalars.values()
                    if isinstance(v, str) and _models.VERSION_RE.match(v)]
        self.assertTrue(versions,
                        f"минимума версии CLI провайдера нет среди полей "
                        f"раздела: {scalars}")
        self.assertIsInstance(
            scalars.get("cost_from_cli"), bool,
            f"признак cost_from_cli не булев: {scalars.get('cost_from_cli')!r}")

    def test_ac1_three_models_carry_id_min_cli_prices_date_and_status(self):
        """В разделе три модели — `claude-sonnet-5`, `claude-opus-5`,
        `claude-fable-5-1`; у каждой читаются идентификатор, минимальная
        версия CLI, четыре цены `list_price_usd_per_mtok`, дата
        прейскуранта и статус из перечня `supported | experimental`.

        Ловит мутацию: у части записей заполнен не весь набор полей
        (например, дата прейскуранта проставлена только у `claude-opus-5`,
        пересчитанного из таблицы курса, а у двух моделей по публичному
        прейскуранту её забыли) — `doctor` и `models` печатали бы
        полупустую строку, а разбор считал бы такую запись полной.
        """
        self.assertEqual(sorted(self.entries), sorted(_models.MODEL_IDS),
                         f"состав моделей каталога: {sorted(self.entries)}")
        for model in _models.MODEL_IDS:
            _path, entry = self.entries[model]
            with self.subTest(model=model):
                prices = entry[_models.PRICE_KEY]
                self.assertIsInstance(prices, dict)
                self.assertEqual(sorted(prices), sorted(_models.PRICE_KINDS),
                                 f"виды токенов {model}: {sorted(prices)}")
                for kind, value in prices.items():
                    self.assertIsInstance(value, (int, float),
                                          f"{model}.{kind} — не число")
                scalars = [v for v in entry.values() if not isinstance(v, dict)]
                self.assertTrue(
                    [v for v in scalars if isinstance(v, str)
                     and _models.VERSION_RE.match(v)],
                    f"у {model} нет минимальной версии CLI: {scalars}")
                self.assertTrue(
                    [v for v in scalars if isinstance(v, str)
                     and _models.DATE_RE.match(v)],
                    f"у {model} нет даты прейскуранта: {scalars}")
                self.assertTrue(
                    [v for v in scalars if v in _models.STATUSES],
                    f"у {model} нет статуса из перечня "
                    f"{_models.STATUSES}: {scalars}")

    def test_ac1_catalog_is_parsed_by_the_models_module(self):
        """Тот же файл разбирает `orchestrator/models.py`, и в разобранном
        каталоге видны все три модели.

        Ловит мутацию: разбор каталога сделан ad-hoc по месту (`doctor`
        или `runner` читают YAML сами), а новый модуль отдаёт пустую
        заготовку — схема каталога не проверяется ни на одном чтении.
        """
        parsed = _models.load_catalog(_models.CATALOG_PATH)

        self.assertIsNotNone(parsed)
        for model in _models.MODEL_IDS:
            self.assertTrue(
                _models.has_value(parsed, model),
                f"модели {model} нет в разобранном каталоге: {parsed!r}")


class CatalogNumbersTest(unittest.TestCase):
    """AC-2: числа каталога — из сегодняшних таблиц пульта."""

    def setUp(self):
        self.entries = _models.model_entries(_models.catalog_document())

    def test_ac2_opus_prices_match_the_calibrated_token_rate(self):
        """Прейскурант `claude-opus-5` — 5 / 25 / 6.25 / 0.5 USD за
        миллион токенов (вход / выход / запись кэша / чтение кэша), то
        есть таблица курса `orchestrator/config.py` калибровки 20.09 в
        пересчёте на миллион.

        Ловит мутацию: цены перенесены в каталог как есть, за ТОКЕН
        (0.000005 вместо 5) или с перепутанными местами записью и чтением
        кэша — тариф, который эта задача только отдаёт, приехал бы к
        потребителю части 2 заниженным на шесть порядков.
        """
        _path, entry = self.entries[_models.OPUS]
        prices = entry[_models.PRICE_KEY]
        for kind, expected in _models.OPUS_PRICES.items():
            with self.subTest(kind=kind):
                self.assertAlmostEqual(float(prices[kind]), expected, places=6)

    def test_ac2_fable_minimum_cli_version_matches_the_compatibility_table(self):
        """Минимум версии CLI `claude-fable-5-1` в каталоге — 2.1.251, то
        есть значение сегодняшней таблицы совместимости
        `orchestrator/stack.py`.

        Ловит мутацию: при переносе таблицы в каталог минимум модели
        подменён минимумом самого CLI (1.0.0 из
        `providers/claude.py::CLI_MINIMUM`) — предполёт шага перестал бы
        ловить инцидент 19.09, ради которого таблица и заведена.
        """
        _path, entry = self.entries[_models.FABLE]
        versions = [v for v in entry.values()
                    if isinstance(v, str) and _models.VERSION_RE.match(v)]

        self.assertIn(_models.FABLE_MIN_CLI, versions,
                      f"минимум CLI {_models.FABLE}: {versions}")

    def test_ac2_every_model_has_a_price_date(self):
        """У каждой из трёх записей проставлена дата прейскуранта.

        Ловит мутацию: дата стоит одна на весь раздел провайдера (или
        только у модели, пересчитанной из таблицы курса) — по записи без
        своей даты нельзя сказать, когда её цена в последний раз сверялась
        с публичным прейскурантом.
        """
        for model in _models.MODEL_IDS:
            _path, entry = self.entries[model]
            with self.subTest(model=model):
                dates = [v for v in entry.values()
                         if isinstance(v, str) and _models.DATE_RE.match(v)]
                self.assertTrue(dates, f"у {model} нет даты прейскуранта")


if __name__ == "__main__":
    unittest.main()
