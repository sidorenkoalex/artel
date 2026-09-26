"""Юнит-тесты `orchestrator/models.py` (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,
требования 1-3, 6, 8, 12): разбор каталога `models.yaml` и локального слоя
`.artel/models.yaml`, именованные ошибки схемы, разрешение цепочки
«роль -> ярус -> модель -> провайдер» и команда `models`.

Каталог под тестом — боевой `models.yaml` репозитория там, где предмет
проверки именно он (AC-1/AC-2), и временный файл там, где предмет — отказ
схемы: ломать боевой каталог ради проверки отказа значило бы проверять
поведение на конфигурации, которой не бывает.
"""
import io
import sqlite3
import sys
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, models, providers, roles, store  # noqa: E402
from tests.sandbox import TmpDirTest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# Имя провайдера, которого в реестре нет и не будет: сценарий отказа
# разбора обязан опираться на заведомо невозможное имя, а не на имя
# провайдера, которого «пока» нет — второе стареет вместе с реестром.
UNREGISTERED_PROVIDER = "provaydera-s-takim-imenem-ne-byvaet"

# Минимальный валидный каталог: ровно те поля, без которых разбор
# отказывает — сценарии ниже портят по одному.
CATALOG_TEMPLATE = """\
providers:
  claude:
    cli: claude
    min_cli_version: 1.0.0
    cost_from_cli: true
    models:
      model-alfa:
        min_cli_version: 2.1.251
        status: {status}
        list_price_usd_per_mtok:
{prices}
        price_date: 2026-09-20
"""

FULL_PRICES = """\
          input: 3.0
          output: 15.0
          cache_write: 3.75
          cache_read: 0.30
"""

LOCAL_TEMPLATE = """\
tiers:
  strong: model-alfa
  standard: model-alfa
  cheap: model-alfa
"""

ROLES_TEMPLATE = """\
roles:
  developer:
    executor: agent
    token_slot: artel-developer
    skills: [conventions-core]
    model_tier: {tier}
token_fallback: artel-token
"""


class _LayersTest(TmpDirTest):
    """Каталог, локальный слой и карта исполнителей — временными файлами
    под патчами `config`."""

    def patch(self, attr: str, value) -> None:
        patcher = mock.patch.object(config, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def use_catalog(self, text: str) -> Path:
        path = self.tdir / "models.yaml"
        path.write_text(text, encoding="utf-8")
        self.patch("MODELS", path)
        return path

    def use_local(self, text: str) -> Path:
        path = self.tdir / "local-models.yaml"
        path.write_text(text, encoding="utf-8")
        self.patch("MODELS_LOCAL", path)
        return path

    def use_roles(self, text: str) -> Path:
        path = self.tdir / "roles.yaml"
        path.write_text(text, encoding="utf-8")
        self.patch("ROLES", path)
        return path

    def catalog_text(self, prices: str = FULL_PRICES,
                     status: str = models.STATUS_SUPPORTED) -> str:
        return CATALOG_TEMPLATE.format(prices=prices, status=status)


class CatalogTest(unittest.TestCase):
    """AC-1/AC-2: боевой `models.yaml` репозитория разбирается, и числа в
    нём — те, что названы SPEC."""

    def setUp(self):
        self.catalog = models.load_catalog()

    def test_provider_section_carries_cli_minimum_and_cost_flag(self):
        """Ловит мутацию: раздел провайдера читается без имени CLI,
        минимума версии или признака `cost_from_cli` — каталог перестал
        бы отвечать на вопрос «чем и с какой версии это запускать»."""
        section = self.catalog.providers["claude"]

        self.assertEqual(section.cli, "claude")
        self.assertEqual(section.min_cli_version, (1, 0, 0))
        self.assertIs(section.cost_from_cli, True)

    def test_claude_and_openai_models_with_status_and_price_date(self):
        """Ловит мутацию: из каталога пропала модель ЛЮБОГО из двух
        разделов, статус читается вне перечня, дата прейскуранта не
        проставлена либо запись модели уехала в чужой раздел (провайдер
        записи разошёлся с провайдером раздела).

        Перечень моделей — литералом по каждому разделу, а не счётчиком:
        каталог решает, на чём вообще идут роли, и «моделей столько же»
        не отличило бы замену одной модели другой. Раздел `codex` в
        ожидании появился вместе с приложением `models.yaml` части 1 линии
        провайдеров (SPEC 01M3EKCZJY9NGCW6VT878RX9JZ, требование 8): до
        него тест ждал ровно три модели Claude и краснел на фактическом
        каталоге.
        """
        self.assertEqual(
            sorted(self.catalog.providers["claude"].models),
            ["claude-fable-5-1", "claude-opus-5", "claude-sonnet-5"])
        self.assertEqual(
            sorted(self.catalog.providers["codex"].models),
            ["gpt-5.5", "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra",
             "gpt-6-astra"])
        self.assertEqual(sorted(self.catalog.models),
                         ["claude-fable-5-1", "claude-opus-5",
                          "claude-sonnet-5", "gpt-5.5", "gpt-5.6-luna",
                          "gpt-5.6-sol", "gpt-5.6-terra", "gpt-6-astra"])

        for name, section in sorted(self.catalog.providers.items()):
            for model_id in sorted(section.models):
                model = self.catalog.models[model_id]
                with self.subTest(model=model_id):
                    self.assertEqual(model.provider, name)
                    self.assertIn(model.status, models.STATUSES)
                    self.assertTrue(model.price_date, model_id)

    def test_opus_price_matches_the_calibrated_token_rate(self):
        """Ловит мутацию: прейскурант opus-5 в каталоге разошёлся с
        калибровкой 20.09 ($5/$25/$6.25/$0.50 за миллион токенов,
        сошедшейся с фактом CLI по 93 шагам с коэффициентом 1.009) — учёт
        расхода поехал бы на числах, которых никто не сверял (AC-2).

        Сверка идёт с литералом, а не с таблицей курса по роли: с задачи
        01M300A14KRHCFB0DQXVCBJEKF цена живёт ТОЛЬКО здесь, в каталоге, и
        второго источника тех же чисел, с которым её можно было бы
        сличить, в пульте больше нет."""
        opus = self.catalog.models["claude-opus-5"]

        self.assertEqual(opus.list_price, models.Tariff(5.0, 25.0, 6.25, 0.5))

    def test_fable_minimum_is_the_incident_version(self):
        """Ловит мутацию: минимум `claude-fable-5-1` уехал с 2.1.251 —
        запись инцидента 19.09 (три попытки по 120 с за 0 токенов) не
        пережила переезд таблицы совместимости в каталог (AC-2)."""
        self.assertEqual(self.catalog.models["claude-fable-5-1"].min_cli_version,
                         (2, 1, 251))


class CatalogErrorsTest(_LayersTest):
    """AC-3: четыре случая отказа разбора, каждый — своей ошибкой."""

    def test_unknown_provider_is_named(self):
        """Ловит мутацию: раздел провайдера, которого нет в реестре,
        разбирается молча — каталог обещал бы запуск модели, запускать
        которую нечем.

        Имя незарегистрированного провайдера в фикстуре было `codex` до
        21.09 — ровно до того дня, когда `codex` в реестре появился
        (SPEC 01M32NH6P053978AER66P0X4GN, требование 1), и тест
        покраснел не по своему предмету. Поэтому имя теперь заведомо
        невозможное, а его отсутствие в реестре проверяется прямо здесь:
        следующий настоящий провайдер эту фикстуру уже не сломает.
        """
        self.assertNotIn(UNREGISTERED_PROVIDER, providers.PROVIDERS)
        self.use_catalog(self.catalog_text().replace(
            "claude:", f"{UNREGISTERED_PROVIDER}:", 1))

        with self.assertRaises(models.UnknownProviderError) as ctx:
            models.load_catalog()

        self.assertIn(UNREGISTERED_PROVIDER, str(ctx.exception))

    def test_model_without_price_list_is_named(self):
        """Ловит мутацию: модель без прейскуранта принимается (тариф
        считался бы нулём или не считался вовсе)."""
        text = self.catalog_text()
        text = text.replace("        list_price_usd_per_mtok:\n", "")
        self.use_catalog(text.replace(FULL_PRICES, ""))

        with self.assertRaises(models.MissingPriceError) as ctx:
            models.load_catalog()

        self.assertIn("model-alfa", str(ctx.exception))

    def test_incomplete_price_list_is_named_by_missing_kinds(self):
        """Ловит мутацию: проверяется только НАЛИЧИЕ прейскуранта, а не
        полнота набора — модель с одной ценой из четырёх прошла бы, и
        стоимость шага считалась бы по трём нулям."""
        partial = "          input: 3.0\n          output: 15.0\n"
        self.use_catalog(self.catalog_text(prices=partial))

        with self.assertRaises(models.IncompletePriceError) as ctx:
            models.load_catalog()

        self.assertIn("cache_write", str(ctx.exception))
        self.assertIn("cache_read", str(ctx.exception))

    def test_zero_price_is_named_for_every_kind(self):
        """Ловит мутацию: ноль как цена принимается (модель «бесплатна»)
        — проверка написана на присутствие ключа, а не на значение."""
        for kind in models.PRICE_KINDS:
            with self.subTest(kind=kind):
                prices = FULL_PRICES.replace(f"{kind}: ", f"{kind}: 0  # ", 1)
                self.use_catalog(self.catalog_text(prices=prices))

                with self.assertRaises(models.ZeroPriceError) as ctx:
                    models.load_catalog()

                self.assertIn(kind, str(ctx.exception))

    def test_broken_yaml_and_missing_file_are_catalog_errors(self):
        """Ловит мутацию: нечитаемый или отсутствующий каталог уходит
        наружу трейсбеком парсера/`FileNotFoundError` вместо названной
        причины — отказ шага печатался бы стеком."""
        self.use_catalog("providers:\n  - claude\n")
        with self.assertRaises(models.CatalogError):
            models.load_catalog()

        self.patch("MODELS", self.tdir / "net-takogo-fayla.yaml")
        with self.assertRaises(models.CatalogError):
            models.load_catalog()


class LocalLayerTest(_LayersTest):
    """AC-8: разбор локального слоя `.artel/models.yaml`."""

    def test_tiers_overrides_and_experimental_allowance_are_read(self):
        """Ловит мутацию: читаются только `tiers:` — собственный тариф и
        явное разрешение `experimental` молча игнорируются, и пульт
        считает расход по прейскуранту вопреки настройке Оператора."""
        self.use_local("""\
tiers:
  strong: model-alfa
overrides:
  model-alfa:
    tariff_usd_per_mtok:
      input: 1.0
      output: 2.0
      cache_write: 3.0
      cache_read: 4.0
    calibrated_at: 2026-09-20
    source: свой счёт
allow_experimental:
  model-alfa: true
""")

        local = models.load_local()

        self.assertEqual(local.tiers, {"strong": "model-alfa"})
        override = local.overrides["model-alfa"]
        self.assertEqual(override.tariff, models.Tariff(1.0, 2.0, 3.0, 4.0))
        self.assertEqual(override.calibrated_at, "2026-09-20")
        self.assertEqual(override.source, "свой счёт")
        self.assertEqual(local.allow_experimental, {"model-alfa"})

    def test_overrides_and_allowance_are_optional(self):
        """Ловит мутацию: разделы объявлены обязательными — шаблон,
        который кладёт `init` (без переопределений), перестал бы
        разбираться."""
        self.use_local(LOCAL_TEMPLATE)

        local = models.load_local()

        self.assertEqual(local.overrides, {})
        self.assertEqual(local.allow_experimental, set())

    def test_template_of_init_parses_and_points_every_tier_at_opus(self):
        """Ловит мутацию: шаблон разошёлся со схемой собственного
        разбора либо перестал покрывать все три яруса — свежий пульт не
        запустил бы ни одного шага (AC-9)."""
        self.use_local(models.local_template_text())

        local = models.load_local()

        self.assertEqual(local.tiers,
                         {tier: "claude-opus-5" for tier in models.TIERS})

    def test_tier_outside_the_list_and_missing_file_are_named(self):
        """Ловит мутацию: ярус вне перечня принимается как свой (роль с
        `model_tier: strong` молча не находила бы его), либо отсутствие
        файла неотличимо от сломанного содержимого — `doctor --fix`
        чинил бы не то."""
        self.use_local("tiers:\n  turbo: model-alfa\n")
        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_local()
        self.assertIn("turbo", str(ctx.exception))

        self.patch("MODELS_LOCAL", self.tdir / "net-takogo-fayla.yaml")
        with self.assertRaises(models.LocalLayerMissingError):
            models.load_local()

    def test_override_tariff_is_read_in_all_three_written_forms(self):
        """Три написания собственного тарифа дают один и тот же разбор:
        четыре вида токенов записью модели, они же под ключом каталога
        `list_price_usd_per_mtok` и под `tariff_usd_per_mtok`.

        Ловит мутацию: принимается только одно написание из трёх (сегодня
        — `tariff_usd_per_mtok`) — локальный слой, написанный Оператором
        в другой форме, не разбирается вовсе, и пульт не запускает ни
        одного шага из-за имени ключа, которого требование 6 не
        фиксирует.
        """
        prices = ("      input: 1.0\n      output: 2.0\n"
                  "      cache_write: 3.0\n      cache_read: 4.0\n")
        flat = prices.replace("      ", "    ")
        forms = {
            "плоская": flat,
            models.LIST_PRICE_KEY: f"    {models.LIST_PRICE_KEY}:\n{prices}",
            models.TARIFF_KEY: f"    {models.TARIFF_KEY}:\n{prices}",
        }
        for name, block in forms.items():
            with self.subTest(form=name):
                self.use_local(
                    f"tiers:\n  strong: model-alfa\noverrides:\n"
                    f"  model-alfa:\n{block}"
                    f"    calibrated_at: 2026-09-20\n    source: свой счёт\n")

                override = models.load_local().overrides["model-alfa"]

                self.assertEqual(override.tariff,
                                 models.Tariff(1.0, 2.0, 3.0, 4.0))
                self.assertEqual(override.source, "свой счёт")

    def test_override_without_any_price_form_is_refused_by_name(self):
        """Запись переопределения без цен ни в одной из трёх форм — отказ,
        называющий и виды токенов, и оба ключа.

        Ловит мутацию: запись без цен разбирается в тариф из нулей (или
        молча пропускается) — вместо отказа Оператор получает модель,
        которая «стоит ноль», ровно то, что `ZeroPriceError` и запрещает
        в каталоге.
        """
        self.use_local("""\
tiers:
  strong: model-alfa
overrides:
  model-alfa:
    calibrated_at: 2026-09-20
    source: свой счёт
""")

        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_local()

        text = str(ctx.exception)
        self.assertIn(models.LIST_PRICE_KEY, text)
        self.assertIn(models.TARIFF_KEY, text)
        self.assertIn("cache_write", text)

    def test_incomplete_flat_override_names_the_missing_kinds(self):
        """Плоская форма с неполным набором видов токенов — отказ, а не
        добор недостающих цен из прейскуранта каталога.

        Ловит мутацию: недостающие виды молча берутся из прейскуранта —
        получается тариф-химера (часть цен Оператора, часть каталога),
        которого Оператор не задавал и по журналу не воспроизведёт.
        """
        self.use_local("""\
tiers:
  strong: model-alfa
overrides:
  model-alfa:
    input: 1.0
    output: 2.0
    calibrated_at: 2026-09-20
    source: свой счёт
""")

        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_local()

        text = str(ctx.exception)
        self.assertIn("cache_write", text)
        self.assertIn("cache_read", text)

    def test_override_without_calibration_fields_is_refused(self):
        """Ловит мутацию: собственный тариф принимается без
        `calibrated_at`/`source` — в учёте появилось бы число без даты и
        основания, неотличимое от опечатки."""
        self.use_local("""\
tiers:
  strong: model-alfa
overrides:
  model-alfa:
    tariff_usd_per_mtok:
      input: 1.0
      output: 2.0
      cache_write: 3.0
      cache_read: 4.0
""")

        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_local()

        self.assertIn(models.CALIBRATED_AT_KEY, str(ctx.exception))

    def test_zero_price_in_an_override_is_a_local_layer_error(self):
        """Ноль ценой в `overrides:` — отказ КЛАССА локального слоя, а не
        класса каталога (REVIEW итерации 1, R1-F8).

        Ловит мутацию: `_prices` рождает `ZeroPriceError` (потомок
        `CatalogError`) независимо от разбираемого файла — обработчик
        `except LocalLayerError`, который отличает «сломан файл
        Оператора» от «сломан каталог в git», пропустит ноль в
        `overrides:` мимо себя трейсбеком.
        """
        self.use_local("""\
tiers:
  strong: model-alfa
overrides:
  model-alfa:
    input: 1.0
    output: 0
    cache_write: 3.0
    cache_read: 4.0
    calibrated_at: 2026-09-20
    source: свой счёт
""")

        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_local()

        self.assertNotIsInstance(ctx.exception, models.CatalogError)
        self.assertIn("output", str(ctx.exception))


class LayersOrNoneTest(_LayersTest):
    """`models.layers_or_none` — оба слоя одним чтением для перебора
    ролей (REVIEW итерации 1, R1-F3)."""

    def setUp(self):
        super().setUp()
        self.use_catalog(self.catalog_text())
        self.use_local(LOCAL_TEMPLATE)
        self.use_roles(ROLES_TEMPLATE.format(tier="strong"))

    def test_passed_layers_spare_the_caller_a_reread_of_both_files(self):
        """Прочитанные слои, переданные `resolve_role`, и есть источник
        цепочки: файлы больше не открываются.

        Ловит мутацию: `resolve_role` игнорирует переданные слои и
        перечитывает файлы сам — цикл `doctor` по ролям снова читает оба
        файла по разу на роль, а докстринг обещает обратное. Файлы
        удаляются после чтения: перечитывание упало бы отказом.
        """
        catalog, local = models.layers_or_none()
        config.MODELS.unlink()
        config.MODELS_LOCAL.unlink()

        resolved = models.resolve_role("developer", catalog, local)

        self.assertEqual(resolved.model, "model-alfa")

    def test_unreadable_layer_comes_back_as_none_not_an_exception(self):
        """Ловит мутацию: помощник поднимает ошибку разбора вместо
        `None` — `doctor`/`check_stack` падали бы целиком на сломанном
        слое вместо красной строки по каждой роли."""
        self.use_local("tiers: не-отображение\n")

        catalog, local = models.layers_or_none()

        self.assertIsNotNone(catalog)
        self.assertIsNone(local)
        with self.assertRaises(models.ModelsError):
            models.resolve_role("developer", catalog, local)


class ResolveRoleTest(_LayersTest):
    """AC-10/AC-11: разрешение цепочки и отказ на каждом звене."""

    def setUp(self):
        super().setUp()
        self.use_catalog(self.catalog_text())
        self.use_local(LOCAL_TEMPLATE)
        self.use_roles(ROLES_TEMPLATE.format(tier="strong"))

    def test_chain_gives_tier_model_provider_minimum_and_list_price(self):
        """Ловит мутацию: разрешение отдаёт один идентификатор модели —
        предполёт шага остался бы без минимума версии CLI, а учёт (часть
        2 линии) без тарифа и его источника."""
        resolved = models.resolve_role("developer")

        self.assertEqual(resolved.tier, "strong")
        self.assertEqual(resolved.model, "model-alfa")
        self.assertEqual(resolved.provider, "claude")
        self.assertEqual(resolved.cli, "claude")
        self.assertEqual(resolved.min_cli_version, (2, 1, 251))
        self.assertEqual(resolved.tariff, models.Tariff(3.0, 15.0, 3.75, 0.3))
        self.assertEqual(resolved.tariff_source, models.TARIFF_SOURCE_CATALOG)
        self.assertEqual(resolved.calibrated_at, "2026-09-20")

    def test_local_override_wins_over_the_list_price_and_names_its_source(self):
        """Ловит мутацию: действующий тариф всегда берётся из каталога —
        переопределение Оператора не влияет ни на что; либо источник
        тарифа не называется, и по числу не понять, откуда оно."""
        self.use_local("""\
tiers:
  strong: model-alfa
overrides:
  model-alfa:
    tariff_usd_per_mtok:
      input: 1.0
      output: 2.0
      cache_write: 3.0
      cache_read: 4.0
    calibrated_at: 2026-09-19
    source: прокси Оператора
""")

        resolved = models.resolve_role("developer")

        self.assertEqual(resolved.tariff, models.Tariff(1.0, 2.0, 3.0, 4.0))
        self.assertEqual(resolved.list_price,
                         models.Tariff(3.0, 15.0, 3.75, 0.3))
        self.assertEqual(resolved.tariff_source, models.TARIFF_SOURCE_OVERRIDE)
        self.assertEqual(resolved.calibrated_at, "2026-09-19")
        self.assertEqual(resolved.source, "прокси Оператора")

    def test_role_without_tier_refuses(self):
        """Ловит мутацию: роль без `model_tier` идёт на дефолт CLI —
        ровно то молчаливое поведение, которое требование 5 заменяет
        отказом."""
        self.use_roles(ROLES_TEMPLATE.replace("    model_tier: {tier}\n", ""))

        with self.assertRaises(models.RoleTierError) as ctx:
            models.resolve_role("developer")

        self.assertIn("model_tier", str(ctx.exception))

    def test_tier_not_mapped_in_the_local_layer_refuses(self):
        """Ловит мутацию: ярус без модели резолвится «первой попавшейся»
        моделью каталога либо `None` — шаг ушёл бы в CLI без `--model`."""
        self.use_local("tiers:\n  cheap: model-alfa\n")

        with self.assertRaises(models.TierNotMappedError) as ctx:
            models.resolve_role("developer")

        self.assertIn("strong", str(ctx.exception))

    def test_model_outside_the_catalog_refuses(self):
        """Ловит мутацию: модель локального слоя не сверяется с каталогом
        — пульт запустил бы модель без минимума версии CLI и без тарифа
        (то самое «запуск как есть», ради которого и был инцидент
        19.09)."""
        self.use_local("tiers:\n  strong: model-net-v-kataloge\n")

        with self.assertRaises(models.ModelNotInCatalogError) as ctx:
            models.resolve_role("developer")

        self.assertIn("model-net-v-kataloge", str(ctx.exception))

    def test_experimental_model_needs_an_explicit_allowance(self):
        """Ловит мутацию: статус `experimental` ни на что не влияет —
        модель, объявленная непроверенной, запускалась бы наравне с
        поддержанной; либо разрешением считается любое значение, а не
        `true`."""
        self.use_catalog(self.catalog_text(status=models.STATUS_EXPERIMENTAL))

        with self.assertRaises(models.ExperimentalNotAllowedError):
            models.resolve_role("developer")

        self.use_local(LOCAL_TEMPLATE + "allow_experimental:\n"
                                        "  model-alfa: возможно\n")
        with self.assertRaises(models.ExperimentalNotAllowedError):
            models.resolve_role("developer")

        self.use_local(LOCAL_TEMPLATE + "allow_experimental:\n"
                                        "  model-alfa: true\n")
        self.assertEqual(models.resolve_role("developer").model, "model-alfa")

    def test_roles_tier_reads_the_closed_list(self):
        """Ловит мутацию: `roles.model_tier` принимает произвольную
        строку — опечатка в ярусе уехала бы в «ярус не назван в tiers:»,
        и Оператор чинил бы не тот файл (AC-6)."""
        self.use_roles(ROLES_TEMPLATE.format(tier="turbo"))

        with self.assertRaises(models.RoleTierError) as ctx:
            models.resolve_role("developer")

        self.assertIn("turbo", str(ctx.exception))
        for tier in models.TIERS:
            self.assertIn(tier, str(ctx.exception))


class CmdModelsTest(_LayersTest):
    """AC-16: команда `models` — таблица и ни одной записи на диск."""

    def setUp(self):
        super().setUp()
        self.use_catalog(self.catalog_text())
        self.use_local(LOCAL_TEMPLATE)
        self.use_roles(ROLES_TEMPLATE.format(tier="strong"))

    def run_cmd(self) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            models.cmd_models()
        return buf.getvalue()

    def test_table_carries_every_column_of_the_requirement(self):
        """Ловит мутацию: из таблицы пропал столбец (статус, минимум CLI,
        прейскурант, действующий тариф, его источник или роли по ярусам)
        — Оператор перестал бы видеть, по какому числу считается расход
        и кто на чём идёт."""
        out = self.run_cmd()

        for column in ("провайдер", "модель", "статус", "мин. CLI",
                       "прейскурант", "действующий тариф", "источник тарифа",
                       "роли по ярусам"):
            self.assertIn(column, out)
        self.assertIn("model-alfa", out)
        self.assertIn("2.1.251", out)
        self.assertIn("3/15/3.75/0.3", out)
        self.assertIn(models.TARIFF_SOURCE_CATALOG, out)
        self.assertIn("strong: developer", out)

    def test_source_column_names_the_basis_and_date_of_the_tariff(self):
        """Столбец источника несёт не только сторону (каталог против
        локального слоя), но и основание с датой калибровки.

        Ловит мутацию: источником печатается одно слово
        «переопределение» — Оператор видит, что тариф не из каталога, но
        не видит, ОТКУДА он и когда сверялся, то есть не может решить,
        доверять ли числу, по которому считается расход.
        """
        self.use_local("""\
tiers:
  strong: model-alfa
overrides:
  model-alfa:
    input: 1.0
    output: 2.0
    cache_write: 3.0
    cache_read: 4.0
    calibrated_at: 2026-09-19
    source: сверено по журналу шагов
""")

        out = self.run_cmd()

        self.assertIn(models.TARIFF_SOURCE_OVERRIDE, out)
        self.assertIn("сверено по журналу шагов", out)
        self.assertIn("2026-09-19", out)
        self.assertIn("1/2/3/4", out)

    def test_command_writes_nothing(self):
        """Ловит мутацию: команда чтения заводит файл (шаблон локального
        слоя, кэш) или пишет строку в журнал `steps` — `models` перестала
        бы быть безопасной в любом состоянии пульта.

        Журнал проверяется по НАСТОЯЩЕЙ таблице подменённой БД, а не
        косвенно по списку файлов (REVIEW итерации 1, R1-F6): БД пульта
        `TmpDirTest` не подменяет, поэтому до этой правки мутация с
        `store.journal(...)` оставалась зелёной и писала строки в боевую
        `state.db` прямо на прогоне тестов.

        Ловит мутацию: затравочное соединение отпускается удалением
        ссылки (`del conn`) вместо явного закрытия — снимок «до»
        делается при ЖИВОЙ БД, а закрывается она в неопределённый момент
        циклической сборки мусора, в том числе уже внутри `run_cmd()`.
        На Linux SQLite при закрытии последнего соединения убирает
        `state.db-wal`/`state.db-shm`, и список «после» оказывается
        короче списка «до»: тест краснеет на CI и зелен локально. Эту
        мутацию ловит `assertRaises(sqlite3.ProgrammingError)` ниже —
        одинаково на обеих платформах и независимо от того, удаляет ли
        SQLite служебные файлы WAL.
        """
        self.patch("DB", self.tdir / "state.db")
        # Затравочная строка: БД существует и не пуста — ровно то
        # состояние, в котором Оператор зовёт `models` на живом пульте.
        conn = store.db()
        with closing(conn):
            store.create_schema(conn)
            store.journal(conn, "T0", "тест", "затравка")
            conn.commit()
        # Закрытие обязано быть явным и доказанным ДО снимков ниже:
        # `store._AutoClosingConnection` участвует в ссылочном цикле со
        # своим кэшем подготовленных выражений, поэтому его `__del__` по
        # счётчику ссылок не срабатывает — отпускание ссылки закрывало бы
        # БД когда угодно, вплоть до середины `run_cmd()`.
        self.assertRaises(sqlite3.ProgrammingError, conn.execute, "SELECT 1")
        before = sorted(p.name for p in self.tdir.iterdir())
        mtimes = {p.name: p.stat().st_mtime_ns for p in self.tdir.iterdir()}

        self.run_cmd()

        self.assertEqual(sorted(p.name for p in self.tdir.iterdir()), before)
        self.assertEqual({p.name: p.stat().st_mtime_ns
                          for p in self.tdir.iterdir()}, mtimes)
        rows = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
        self.assertEqual(rows, 1)

    def test_unreadable_local_layer_still_prints_the_catalog(self):
        """Ловит мутацию: без локального слоя команда падает или молчит —
        Оператор свежего пульта не увидел бы каталог вовсе, хотя чинить
        ему надо именно слой."""
        self.patch("MODELS_LOCAL", self.tdir / "net-takogo-fayla.yaml")

        out = self.run_cmd()

        self.assertIn("model-alfa", out)
        self.assertIn(models.LOCAL_FIX_HINT, out)

    def test_unreadable_tier_is_named_above_the_table(self):
        """Ярус роли не прочитан — команда называет причину строкой над
        таблицей, а не оставляет молча пустой столбец ролей (REVIEW
        итерации 1, R1-F5).

        Ловит мутацию: нечитаемый ярус гасится молча — прочерк в столбце
        ролей читается как «ни одна роль сюда не указывает», хотя правда
        «ярус роли не прочитан»; различить эти два состояния Оператору
        больше негде, `models` — единственная команда обзора.
        """
        self.use_roles(ROLES_TEMPLATE.format(tier="богатырский"))

        out = self.run_cmd()

        self.assertIn("developer", out)
        self.assertIn("не полностью", out)
        self.assertIn("model-alfa", out)

    def test_unreadable_roles_map_is_named_above_the_table(self):
        """Ловит мутацию: нечитаемая карта исполнителей роняет команду
        либо гасится молча — в первом случае Оператор не видит каталог
        вовсе, во втором принимает пустой столбец за «ролей нет»."""
        self.use_roles("roles: не-отображение\n")

        out = self.run_cmd()

        self.assertIn("карта исполнителей не прочитана", out)
        self.assertIn("model-alfa", out)

    def test_broken_catalog_refuses_by_name(self):
        """Ловит мутацию: сломанный каталог печатает пустую таблицу
        вместо причины — отказ выглядел бы как «моделей нет»."""
        self.use_catalog("providers:\n  - claude\n")

        with self.assertRaises(SystemExit) as ctx:
            self.run_cmd()

        self.assertIn("models:", str(ctx.exception))


class DispatcherTest(unittest.TestCase):
    """AC-16: команда `models` подключена к диспетчеру `artel.py`."""

    def test_models_command_is_wired_into_the_dispatcher(self):
        """Ловит мутацию: команда написана, но в таблице диспетчера её
        нет — `artel.py models` отвечал бы «Неизвестная команда» (тот же
        приём, что `tests/test_doc_commit.py::DispatcherTest`)."""
        import inspect

        from orchestrator import artel

        source = inspect.getsource(artel.main)

        self.assertIn('"models": lambda: models.cmd_models()', source)


class DocsTemplateTest(unittest.TestCase):
    """AC-17: образец в `docs/reference/` — тот же текст, что кладёт
    `init`."""

    def test_example_file_equals_the_template(self):
        """Ловит мутацию: образец и шаблон разъехались — Оператор правил
        бы по документации файл, которого пульт не кладёт."""
        example = (REPO_ROOT / "docs" / "reference"
                   / "models-local.example.yaml").read_text(encoding="utf-8")

        self.assertEqual(example, models.local_template_text())


class RolesModelFieldTest(unittest.TestCase):
    """AC-6: поле `model` роли пультом больше не читается."""

    def test_roles_module_has_no_model_reader(self):
        """Ловит мутацию: `roles.model` оставлен «на всякий случай» —
        два источника модели роли разошлись бы молча, и какой из них
        действует, стало бы вопросом порядка чтения."""
        self.assertFalse(hasattr(roles, "model"))
        self.assertTrue(callable(roles.model_tier))


if __name__ == "__main__":
    unittest.main()
