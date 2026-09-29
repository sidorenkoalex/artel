"""Юнит-тесты набора ролей канарейки (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5):
разбор `canary_sets:`/`role_providers:` локального слоя, отказы команды
`canary --set` ДО эфемерного клона, сборка локального слоя клона,
переопределение провайдера роли, ключ бейзлайна и строк прогонов по паре
(шаблон, набор) и разбор флага `--set`. С SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG
слой клона собирается из слоя пульта, а набор переводит только свои роли
записями `role_models:`/`role_providers:` — тесты прежнего сдвига яруса
переписаны под это (перечень — в PLAN.md задачи).

Каталог моделей, карта исполнителей и локальный слой здесь — ВРЕМЕННЫЕ
файлы под патчами `config`, а не боевые `models.yaml`/`roles.yaml`: оба
боевых файла — защищённые пути и крутилки Оператора (сегодня все четыре
agent-роли на ярусе `strong`), и тест, опирающийся на их сегодняшнее
содержимое, краснел бы от правки, к его предмету отношения не имеющей.
Тождество набора по умолчанию сегодняшнему поведению и живой прогон в
настоящем клоне — предмет приёмочной планки задачи, не этого файла.

Живой CLI провайдера не запускается ни в одном тесте: предмет здесь —
разбор, сборка текста слоя и запросы к БД.
"""
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artel, canary, config, models,  # noqa: E402
                          roles, store, yamlmini)
from tests.sandbox import TmpDirTest  # noqa: E402

# Каталог двух провайдеров: у `claude` модель `supported`, у `codex` — две
# `experimental`. Обе половины нужны сценариям: `experimental` собирается в
# разрешение слоя клона, а разные провайдеры дают расхождение требования 6д.
CATALOG_TEXT = """\
providers:
  claude:
    cli: claude
    min_cli_version: 1.0.0
    cost_from_cli: true
    models:
      model-claude:
        min_cli_version: 1.0.0
        status: supported
        list_price_usd_per_mtok:
          input: 5.0
          output: 25.0
          cache_write: 6.25
          cache_read: 0.50
        price_date: 2026-09-20
  codex:
    cli: codex
    min_cli_version: 0.155.1
    cost_from_cli: false
    models:
      model-codex-a:
        min_cli_version: 0.155.1
        status: experimental
        list_price_usd_per_mtok:
          input: 2.0
          output: 12.0
          cache_write: 2.0
          cache_read: 0.20
        price_date: 2026-09-21
      model-codex-b:
        min_cli_version: 0.155.1
        status: experimental
        list_price_usd_per_mtok:
          input: 0.20
          output: 1.20
          cache_write: 0.20
          cache_read: 0.02
        price_date: 2026-09-21
"""

# Карта исполнителей: `developer`/`reviewer` на одном ярусе (сценарий
# «две роли одного яруса»), `analyst` — на том же ярусе и НЕ названный
# набором (сценарий провайдера у роли-соседа по ярусу), `writer` — на
# другом ярусе (сценарий «ярус не тронут»), `verifier` — не agent.
ROLES_TEXT = """\
roles:
  developer:
    executor: agent
    skills: [conventions-core]
    model_tier: strong
  reviewer:
    executor: agent
    skills: [conventions-core]
    model_tier: strong
  analyst:
    executor: agent
    skills: [conventions-core]
    model_tier: strong
  writer:
    executor: agent
    skills: [conventions-core]
    model_tier: cheap
    provider: claude
  verifier:
    executor: none
token_fallback: artel-token
"""

TIERS_TEXT = """\
tiers:
  strong: model-claude
  standard: model-claude
  cheap: model-claude
"""

SET_NAME = "codex-strong"


def sets_block(*entries: tuple) -> str:
    """Раздел `canary_sets:` с одним набором `SET_NAME` из записей
    (роль, провайдер, модель) — вложенными блочными отображениями, той
    формой, которую разбирает `orchestrator/yamlmini.py`."""
    lines = ["canary_sets:", f"  {SET_NAME}:"]
    for role, provider, model in entries:
        lines += [f"    {role}:", f"      provider: {provider}",
                  f"      model: {model}"]
    return "\n".join(lines) + "\n"


class _SetLayersTest(TmpDirTest):
    """Каталог, карта исполнителей и локальный слой — временными файлами
    под патчами `config`."""

    def setUp(self):
        super().setUp()
        self.use("MODELS", "models.yaml", CATALOG_TEXT)
        self.use("ROLES", "roles.yaml", ROLES_TEXT)
        self.local_path = self.use("MODELS_LOCAL", "local.yaml", TIERS_TEXT)

    def use(self, attr: str, name: str, text: str) -> Path:
        path = self.tdir / name
        path.write_text(text, encoding="utf-8")
        patcher = mock.patch.object(config, attr, path)
        patcher.start()
        self.addCleanup(patcher.stop)
        return path

    def write_local(self, *blocks: str) -> None:
        self.local_path.write_text(TIERS_TEXT + "\n" + "\n".join(blocks),
                                   encoding="utf-8")


class CanarySetsParsingTest(_SetLayersTest):
    """Требование 2: формат `canary_sets:` локального слоя."""

    def test_nested_block_mapping_parses_into_role_entries(self):
        """Ловит мутацию: разбор читает только имена наборов и не
        собирает записи ролей — прогон получил бы имя набора без
        провайдера и модели, и сборка слоя клона молча пошла бы по
        шаблону."""
        self.write_local(sets_block(("developer", "codex", "model-codex-a")))

        sets = models.load_canary_sets()

        self.assertEqual(
            {SET_NAME: {"developer": models.CanarySetRole(
                "developer", "codex", "model-codex-a")}}, sets)

    def test_layer_without_the_section_has_no_sets_at_all(self):
        """Ловит мутацию: отсутствие раздела читается как отказ разбора —
        сегодняшний слой пульта (шаблон раздела наборов не несёт) ронял бы
        и строку `doctor`, и прогон без `--set`."""
        self.assertEqual({}, models.load_canary_sets())

    def test_entry_without_provider_is_a_named_refusal(self):
        """Ловит мутацию: половины записи необязательны — роль с моделью
        без провайдера уехала бы в клон, а это ровно то расхождение, за
        которым следит `doctor.check_model_provider_cli`."""
        self.write_local("canary_sets:\n"
                         f"  {SET_NAME}:\n"
                         "    developer:\n"
                         "      model: model-codex-a\n")

        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_canary_sets()

        self.assertIn(models.PROVIDER_KEY, str(ctx.exception))
        self.assertIn("developer", str(ctx.exception))

    def test_entry_that_is_not_a_mapping_is_a_named_refusal(self):
        """Ловит мутацию: запись роли берётся без сверки типа — строка
        `developer: codex` вместо пары полей уехала бы в `.get()` и
        упала бы `AttributeError` из глубины разбора вместо причины."""
        self.write_local("canary_sets:\n"
                         f"  {SET_NAME}:\n"
                         "    developer: codex\n")

        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_canary_sets()

        self.assertIn("developer", str(ctx.exception))

    def test_empty_set_is_a_named_refusal(self):
        """Ловит мутацию: пустой набор проходит разбор — прогон по нему
        отчитался бы «набор codex-strong», не сдвинув ни одного яруса, то
        есть соврал бы о том, чем шёл."""
        self.write_local("canary_sets:\n"
                         f"  {SET_NAME}:\n")

        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_canary_sets()

        self.assertIn(SET_NAME, str(ctx.exception))


class RoleProvidersLayerTest(_SetLayersTest):
    """Требование 5: раздел `role_providers:` локального слоя."""

    def test_section_parses_into_a_role_to_provider_map(self):
        """Ловит мутацию: раздел разбирается, но наружу не отдаётся
        (`LocalLayer` его теряет) — `roles.provider` читать переопределение
        было бы негде, и набор доезжал бы до клона только моделями."""
        self.write_local("role_providers:\n  developer: codex\n")

        self.assertEqual({"developer": "codex"},
                         models.load_local().role_providers)

    def test_missing_section_is_an_empty_map(self):
        """Ловит мутацию: отсутствие раздела читается как отказ разбора —
        локальный слой сегодняшнего пульта перестал бы читаться вовсе, а
        с ним и каждый шаг любой роли."""
        self.assertEqual({}, models.load_local().role_providers)

    def test_non_string_provider_is_a_named_refusal(self):
        """Ловит мутацию: значение берётся без сверки типа — пустое
        значение (`developer:`) стало бы именем провайдера `None`, и шаг
        ушёл бы в реестр с этим именем."""
        self.write_local("role_providers:\n  developer:\n")

        with self.assertRaises(models.LocalLayerError) as ctx:
            models.load_local()

        self.assertIn(models.ROLE_PROVIDERS_KEY, str(ctx.exception))

    def test_template_layer_parses_with_no_sets_and_no_overrides(self):
        """Ловит мутацию: `local_template_layer` читает слой С ДИСКА, а не
        текст шаблона — ярусы «как в шаблоне» для слоя клона брались бы из
        слоя пульта, и прогон по набору увозил бы в клон чужие ярусы."""
        template = models.local_template_layer()

        self.assertEqual({"strong", "standard", "cheap"},
                         set(template.tiers))
        self.assertEqual({}, template.role_providers)
        self.assertNotEqual(models.load_local().tiers, template.tiers)


class RoleProviderOverrideTest(_SetLayersTest):
    """Требование 5: `roles.provider` читает переопределение слоя."""

    def test_layer_override_wins_over_the_roles_yaml_field(self):
        """Ловит мутацию: переопределение читается ДО поля роли или не
        читается вовсе — шаг в клоне ушёл бы Claude'ом с идентификатором
        модели Codex, то есть оплаченной попыткой чужого CLI."""
        self.write_local("role_providers:\n  writer: codex\n")

        self.assertEqual("codex", roles.provider("writer"))

    def test_role_without_an_override_keeps_todays_value(self):
        """Ловит мутацию: переопределение пишется для всех ролей (например
        провайдером по умолчанию литералом) — перевод роли пульта на
        другого исполнителя правкой `roles.yaml` перестал бы действовать."""
        self.write_local("role_providers:\n  developer: codex\n")

        self.assertEqual("claude", roles.provider("writer"))
        self.assertEqual("claude", roles.provider("analyst"))

    def test_unreadable_layer_degrades_to_the_roles_yaml_value(self):
        """Ловит мутацию: нечитаемый слой уходит исключением наружу — шаг
        любой роли падал бы трейсбеком из чтения провайдера вместо своей
        названной причины, и `doctor` не успевал бы её назвать."""
        self.local_path.unlink()

        self.assertEqual("claude", roles.provider("developer"))

    def test_role_models_entry_without_role_providers_takes_the_model_provider(self):
        """Запись `role_models:` без записи `role_providers:` ведёт роль
        провайдером модели записи в каталоге — тем же, что называет
        `models.resolve_role` (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование
        2); запись `role_providers:` по-прежнему главнее.

        Ловит мутацию: `roles.provider` читает только `role_providers:` —
        роль, переведённая Оператором на модель Codex одной записью
        `role_models:`, ушла бы CLI `claude` с идентификатором модели
        Codex, то есть оплаченной попыткой чужого CLI.
        """
        self.write_local("role_models:\n  writer: model-codex-a\n"
                         "  developer: model-codex-a\n"
                         "role_providers:\n  developer: claude\n")

        self.assertEqual("codex", roles.provider("writer"))
        self.assertEqual("claude", roles.provider("developer"))
        self.assertEqual("claude", roles.provider("analyst"))

    def test_role_outside_roles_yaml_still_refuses_even_with_an_override(self):
        """Ловит мутацию: переопределение читается ПЕРВЫМ — роль, которой в
        карте исполнителей нет вовсе, получила бы провайдера из слоя, и
        опечатка в имени роли перестала бы быть отказом."""
        self.write_local("role_providers:\n  desiner: codex\n")

        with self.assertRaises(roles.RolesError):
            roles.provider("desiner")


class SetPlanRefusalsTest(_SetLayersTest):
    """Требование 6: каждый случай битого набора — отказ команды."""

    def refusal(self, *entries: tuple) -> str:
        self.write_local(sets_block(*entries))
        with self.assertRaises(SystemExit) as ctx:
            canary._set_plan(SET_NAME)
        return str(ctx.exception)

    def test_unknown_set_name_refusal_lists_the_known_names(self):
        """Ловит мутацию: отказ называет только запрошенное имя — Оператор
        с опечаткой в имени не видел бы, из чего выбирать, и шёл бы читать
        файл вне git руками."""
        self.write_local(sets_block(("developer", "codex", "model-codex-a")))

        with self.assertRaises(SystemExit) as ctx:
            canary._set_plan("net-takogo")

        self.assertIn("net-takogo", str(ctx.exception))
        self.assertIn(SET_NAME, str(ctx.exception))

    def test_role_outside_the_roles_map_is_refused_by_name(self):
        """Ловит мутацию: неизвестная роль молча пропускается при сборке
        слоя — набор с опечаткой в имени роли ушёл бы в клон как набор по
        умолчанию, и прогон отчитался бы о Codex, идя на Claude."""
        self.assertIn("desiner", self.refusal(("desiner", "codex",
                                               "model-codex-a")))

    def test_model_outside_the_catalog_is_refused_by_name(self):
        """Ловит мутацию: модель кладётся в `tiers:` слоя клона без сверки
        с каталогом — отказ всплыл бы уже ВНУТРИ клона, на первом шаге
        роли, и причина умерла бы вместе с уничтоженным клоном."""
        self.assertIn("model-net-v-kataloge",
                      self.refusal(("developer", "codex",
                                    "model-net-v-kataloge")))

    def test_two_roles_of_one_tier_with_different_models_are_refused(self):
        """Две роли одного яруса на разных моделях — больше НЕ отказ (SPEC
        01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 3): каждая роль получает в
        слое клона свою модель. Имя метода — прежнее: тест переписан под
        новое требование, а не удалён (AC-14).

        Ловит мутацию: остался отказ «набор даёт ярусу две разные модели»
        (прогон отказывает до клона), либо запись `role_models:` идёт
        присваиванием по ярусу — вторая роль перебивала бы первую.
        """
        self.write_local(sets_block(("developer", "codex", "model-codex-a"),
                                    ("reviewer", "codex", "model-codex-b")))

        plan = canary._set_plan(SET_NAME)

        path = self.tdir / "clone.yaml"
        path.write_text(plan.layer_text, encoding="utf-8")
        self.assertEqual({"developer": "model-codex-a",
                          "reviewer": "model-codex-b"},
                         models.load_local(path).role_models)

    def test_role_provider_not_matching_the_model_provider_is_refused(self):
        """Ловит мутацию: половины записи проверяются по отдельности, но не
        друг против друга — шаг ушёл бы `claude --model model-codex-a`:
        оплаченная попытка чужим CLI по чужому тарифу."""
        message = self.refusal(("developer", "claude", "model-codex-a"))

        self.assertIn("developer", message)
        self.assertIn("model-codex-a", message)

    def test_two_roles_of_one_tier_with_the_same_model_are_not_refused(self):
        """Ловит мутацию: сверка яруса срабатывает на ЛЮБОЙ второй роли
        того же яруса, а не только на другой модели — набор из примера
        документации (обе роли на одной модели) был бы невозможен."""
        self.write_local(sets_block(("developer", "codex", "model-codex-a"),
                                    ("reviewer", "codex", "model-codex-a")))

        plan = canary._set_plan(SET_NAME)

        self.assertEqual(SET_NAME, plan.name)


class DefaultSetPlanTest(_SetLayersTest):
    """Требование 3: набор по умолчанию в `canary_sets:` не заглядывает;
    слой клона при этом — слой пульта (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG,
    требование 1)."""

    def test_default_set_plan_never_reads_the_local_layer(self):
        """Ловит мутацию: имя набора по умолчанию ищется в `canary_sets:`
        наравне с остальными — прогон без `--set` отказывал бы на любом
        пульте, чей слой наборов не несёт (то есть на сегодняшнем)."""
        def explode():
            raise AssertionError("локальный слой прочитан на наборе "
                                 "по умолчанию")

        with mock.patch.object(canary.models, "load_canary_sets", explode):
            plan = canary._set_plan(config.CANARY_DEFAULT_SET)

        self.assertEqual(config.CANARY_DEFAULT_SET, plan.name)

    def test_default_set_plan_carries_no_clone_layer_and_no_summary(self):
        """Набор по умолчанию на читаемом слое пульта несёт слой клона с
        ярусами ПУЛЬТА и сводку всех агентских ролей с источником «слой
        пульта» (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG, требования 1, 4; имя
        метода — прежнее, тест переписан, а не удалён, AC-14).

        Ловит мутацию: слой клона из шаблона — набор по умолчанию снова
        оставляет `layer_text` пустым, и клон идёт на моделях шаблона, а не
        пульта; либо сводка набора по умолчанию пуста.
        """
        plan = canary._set_plan(config.CANARY_DEFAULT_SET)

        path = self.tdir / "clone.yaml"
        path.write_text(plan.layer_text, encoding="utf-8")
        self.assertEqual(models.load_local().tiers,
                         models.load_local(path).tiers)
        self.assertEqual(
            "developer → model-claude, reviewer → model-claude, "
            "analyst → model-claude, writer → model-claude; "
            "источник: слой пульта", plan.summary)
        self.assertIn(plan.summary, canary._summary_note(plan))


    def test_set_over_an_unparseable_pult_layer_names_the_template_base(self):
        """Слой пульта не разбирается (`tiers:` не отображение), но раздел
        наборов в нём читается: набор ложится поверх ШАБЛОНА, и источник
        сводки называет это прямо (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG,
        требования 1, 4).

        Ловит мутацию: источник набора называется «набор <имя>» и при
        нечитаемом слое пульта — Оператор принял бы прогон на ярусах
        шаблона за прогон на ярусах пульта.
        """
        self.local_path.write_text("tiers: ne-otobrazhenie\n\n"
                                   + sets_block(("developer", "claude",
                                                 "model-claude")),
                                   encoding="utf-8")

        plan = canary._set_plan(SET_NAME)

        source = plan.summary.split(canary._SUMMARY_SOURCE_SEP, 1)[1]
        self.assertIn(f"набор {SET_NAME}", source)
        self.assertIn("шаблон", source)
        self.assertIn("не прочитан", source)
        path = self.tdir / "clone.yaml"
        path.write_text(plan.layer_text, encoding="utf-8")
        self.assertEqual(models.local_template_layer().tiers,
                         models.load_local(path).tiers)


class CloneLocalLayerTextTest(_SetLayersTest):
    """Требования 4-5: локальный слой клона, собранный из набора."""

    OVERRIDE_BLOCK = """\
overrides:
  model-codex-a:
    input: 1.5
    output: 9.0
    cache_write: 1.5
    cache_read: 0.15
    calibrated_at: 2026-09-26
    source: сверено с фактом CLI 26.09
"""

    def plan(self, *entries: tuple, overrides: bool = True):
        blocks = [sets_block(*entries)]
        if overrides:
            blocks.insert(0, self.OVERRIDE_BLOCK)
        self.write_local(*blocks)
        return canary._set_plan(SET_NAME)

    def layer(self, *entries: tuple, overrides: bool = True):
        plan = self.plan(*entries, overrides=overrides)
        path = self.tdir / "clone.yaml"
        path.write_text(plan.layer_text, encoding="utf-8")
        return plan, models.load_local(path)

    def test_named_tier_points_at_the_set_model_and_the_rest_at_the_template(self):
        """Ярусы слоя клона — ярусы слоя ПУЛЬТА при любом наборе, а роль
        набора получает модель записью `role_models:` (SPEC
        01M3PYMQ6N4SCAJ9WWTTKH6XNG, требования 1, 3; имя метода — прежнее,
        тест переписан, а не удалён, AC-14).

        Ловит мутацию: набор применяется сдвигом яруса (ярус `strong` клона
        — модель набора) либо ярусы, не названные набором, берутся из
        шаблона, а не из слоя пульта.
        """
        _plan, layer = self.layer(("developer", "codex", "model-codex-a"))

        self.assertEqual(models.load_local().tiers, layer.tiers)
        self.assertEqual({"developer": "model-codex-a"}, layer.role_models)

    def test_experimental_model_of_the_set_is_allowed(self):
        """Ловит мутацию: разрешение не собирается (или собирается
        значением, отличным от `true`) — каждый шаг роли в клоне отказывал
        бы «модель имеет статус experimental и не разрешена явно»."""
        _plan, layer = self.layer(("developer", "codex", "model-codex-a"))

        self.assertIn("model-codex-a", layer.allow_experimental)

    def test_supported_model_of_the_set_gets_no_allowance(self):
        """Ловит мутацию: разрешение пишется для КАЖДОЙ модели набора —
        `allow_experimental` перестал бы что-либо значить, и статус
        каталога `experimental` можно было бы не замечать вовсе."""
        _plan, layer = self.layer(("writer", "claude", "model-claude"))

        self.assertEqual(set(), layer.allow_experimental)

    def test_pult_tariff_override_of_the_set_model_is_carried_over(self):
        """Ловит мутацию: `overrides:` слоя клона собирается пустым —
        стоимость шага в клоне считалась бы по прейскуранту каталога, и
        метрика прогона разошлась бы с тарифом пульта, на который её же и
        сравнивают с бейзлайном."""
        _plan, layer = self.layer(("developer", "codex", "model-codex-a"))

        override = layer.overrides["model-codex-a"]
        self.assertEqual(models.Tariff(1.5, 9.0, 1.5, 0.15), override.tariff)
        self.assertEqual("2026-09-26", override.calibrated_at)

    def test_override_of_a_model_outside_the_set_is_not_carried_over(self):
        """Ловит мутацию: переносятся ВСЕ переопределения пульта — в слой
        клона уехал бы тариф модели, на которую в клоне не идёт ни одна
        роль и не ссылается ни один ярус (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG,
        требование 1: тарифы — для моделей, на которых идут роли)."""
        _plan, layer = self.layer(("writer", "claude", "model-claude"))

        self.assertEqual({}, layer.overrides)

    def test_missing_pult_layer_leaves_the_clone_layer_without_overrides(self):
        """Ловит мутацию: отсутствие переопределений у пульта роняет сборку
        — прогон по набору отказывал бы на пульте, который своего тарифа не
        заводил, то есть на большинстве пультов."""
        _plan, layer = self.layer(("developer", "codex", "model-codex-a"),
                                  overrides=False)

        self.assertEqual({}, layer.overrides)

    def test_every_role_of_a_moved_tier_gets_the_set_provider(self):
        """Провайдер набора получает РОВНО роль набора; соседи по ярусу
        остаются на своём провайдере и модели яруса (SPEC
        01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 3; имя метода — прежнее,
        тест переписан, а не удалён, AC-14).

        Ловит мутацию: карта провайдеров собирается по ролям сдвинутого
        яруса — сосед по ярусу, набором не названный, ушёл бы провайдером
        Codex.
        """
        _plan, layer = self.layer(("developer", "codex", "model-codex-a"))

        self.assertEqual({"developer": "codex"}, layer.role_providers)

    def test_role_of_an_untouched_tier_gets_no_provider_override(self):
        """Ловит мутацию: провайдер набора пишется всем agent-ролям —
        роль, чей ярус набор не сдвинул, ушла бы чужим CLI с моделью
        шаблона, то есть тем самым расхождением, которое набор обязан
        исключать."""
        _plan, layer = self.layer(("developer", "codex", "model-codex-a"))

        self.assertNotIn("writer", layer.role_providers)

    def test_summary_names_every_role_that_really_goes_on_the_set_model(self):
        """Сводка называет модель КАЖДОЙ агентской роли прогона — роли
        набора на модели набора, прочие на модели слоя пульта — и источник
        «набор <имя>» (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 4; имя
        метода — прежнее, тест переписан, а не удалён, AC-14).

        Ловит мутацию: сводка собирается только по записям набора (роли,
        идущие по слою пульта, не названы) либо без источника.
        """
        plan, _layer = self.layer(("developer", "codex", "model-codex-a"))

        self.assertEqual(
            "developer → model-codex-a, reviewer → model-claude, "
            "analyst → model-claude, writer → model-claude; "
            f"источник: набор {SET_NAME}", plan.summary)
        self.assertIn(plan.summary, canary._summary_note(plan))

    def test_clone_layer_is_not_the_template_text(self):
        """Ловит мутацию: ветка набора собрана, но в клон уходит шаблон
        (слой пишется до `cmd_init`, который его перекрывает) — прогон «на
        Codex» шёл бы на модели шаблона, и метрики приписались бы набору,
        которым не шли."""
        plan = self.plan(("developer", "codex", "model-codex-a"))

        self.assertNotEqual(models.local_template_text(), plan.layer_text)


class ScalarTextTest(unittest.TestCase):
    """Значения слоя клона переживают обратный разбор `yamlmini`."""

    def test_value_with_a_hash_round_trips_through_the_parser(self):
        """Ловит мутацию: значение печатается без кавычек — `#` после
        пробела начинает комментарий, и `source` тарифа в слое клона
        обрезался бы до пустого, а разбор слоя внутри клона отказал бы
        «source не задан»."""
        text = "сверено с фактом CLI 26.09 # прогон 3"

        self.assertEqual(text, yamlmini.scalar(canary._scalar_text(text)))

    def test_plain_value_is_printed_without_quotes(self):
        """Ловит мутацию: кавычки ставятся всегда — текст слоя клона стал
        бы отличаться от того, как тот же тариф записан у пульта, и
        сравнивать их глазом Оператор больше не смог бы."""
        self.assertEqual("codex", canary._scalar_text("codex"))


class SetArgTest(unittest.TestCase):
    """Требование 1: разбор флага `--set` диспетчером."""

    def test_missing_flag_gives_the_default_set_name(self):
        """Ловит мутацию: отсутствие флага даёт `None` (буквальная копия
        `_sha_arg`) — набором по умолчанию пришлось бы считать пустое
        значение, и бейзлайн ключевался бы `NULL`."""
        self.assertEqual(config.CANARY_DEFAULT_SET,
                         artel._set_arg(["--k", "1"]))

    def test_flag_value_is_returned_verbatim(self):
        """Ловит мутацию: значение берётся не тем индексом (или из `--sha`)
        — прогон шёл бы не тем набором, который назвал Оператор."""
        self.assertEqual(
            SET_NAME,
            artel._set_arg(["--k", "1", "--sha", "abc", "--set", SET_NAME]))

    def test_flag_without_a_value_is_a_named_refusal(self):
        """Ловит мутацию: значение берётся `rest[idx + 1]` без сверки длины
        — Оператор получил бы `IndexError` из глубины разбора вместо
        названной причины."""
        with self.assertRaises(SystemExit) as ctx:
            artel._set_arg(["--k", "1", "--set"])

        self.assertIn("--set", str(ctx.exception))


class _CanaryStoreTest(TmpDirTest):
    """БД со схемой во временном каталоге: предмет — ключи таблиц метрик
    канарейки."""

    def setUp(self):
        super().setUp()
        for attr, value in (("ROOT", self.tdir),
                            ("DB", self.tdir / ".artel" / "state.db")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()

    def insert_run(self, run_stamp: str, set_name: str,
                   verdict: str = "green", main_sha: str = "sha") -> None:
        store.insert_canary_run(
            self.conn, run_stamp, "shablon", f"01{run_stamp}", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=main_sha, verdict=verdict, set_name=set_name,
            models_summary="developer → model-codex-a")


class CanaryBaselinePerSetTest(_CanaryStoreTest):
    """Требование 7: бейзлайн ключуется парой (шаблон, набор)."""

    def test_baseline_of_one_set_is_invisible_to_another(self):
        """Ловит мутацию: бейзлайн читается по одному `title` — прогон
        набора B сравнился бы с бейзлайном A и поднял бы отклонение на
        ожидаемой разнице моделей, а этот алерт — вход гейта сдвига пина."""
        store.set_canary_baseline(self.conn, "shablon", 3, 1.0, 0,
                                  SET_NAME)

        self.assertIsNone(store.canary_baseline(self.conn, "shablon"))
        row = store.canary_baseline(self.conn, "shablon", SET_NAME)
        self.assertEqual((3, 1.0), (row["steps"], row["cost_usd"]))

    def test_write_of_one_set_does_not_overwrite_another(self):
        """Ловит мутацию: `ON CONFLICT` остался по одному `title` — прогон
        второго набора затёр бы бейзлайн первого своими числами, и точка
        сравнения прежнего набора исчезла бы."""
        store.set_canary_baseline(self.conn, "shablon", 3, 1.0, 0, SET_NAME)
        store.set_canary_baseline(self.conn, "shablon", 9, 7.0, 2, "other")

        first = store.canary_baseline(self.conn, "shablon", SET_NAME)
        self.assertEqual((3, 1.0), (first["steps"], first["cost_usd"]))
        second = store.canary_baseline(self.conn, "shablon", "other")
        self.assertEqual((9, 7.0), (second["steps"], second["cost_usd"]))

    def test_second_write_of_the_same_pair_overwrites_it(self):
        """Ловит мутацию: ключ стал тройкой (или `ON CONFLICT` пропал) —
        бейзлайн той же пары копился бы строками, и `canary_baseline`
        отдавал бы произвольную из них."""
        store.set_canary_baseline(self.conn, "shablon", 3, 1.0, 0, SET_NAME)
        store.set_canary_baseline(self.conn, "shablon", 9, 2.0, 1, SET_NAME)

        rows = self.conn.execute("SELECT * FROM canary_baseline").fetchall()
        self.assertEqual(1, len(rows))
        self.assertEqual(9, rows[0]["steps"])


class GreenRunsOfTheDefaultSetTest(_CanaryStoreTest):
    """Требование 10: зелёной канарейкой для пина годится только набор по
    умолчанию."""

    def test_run_of_another_set_is_not_a_green_run_for_the_pin(self):
        """Ловит мутацию: фильтр по набору отсутствует — прогон на моделях
        другого провайдера годился бы для сдвига пина, то есть пин двигался
        бы по прогону конвейера, которым пульт не работает."""
        self.insert_run("20260927T000000Z", SET_NAME)

        self.assertEqual([], store.green_canary_runs(self.conn))
        self.assertIsNone(store.latest_green_canary_run(self.conn))

    def test_run_of_the_default_set_stays_a_green_run(self):
        """Ловит мутацию: фильтр сравнивает не с тем значением (например с
        `NULL`) — годным для пина не оказался бы НИ ОДИН прогон, и гейт
        сдвига пина заклинило бы намертво."""
        self.insert_run("20260927T000001Z", config.CANARY_DEFAULT_SET)

        rows = store.green_canary_runs(self.conn)

        self.assertEqual(["20260927T000001Z"],
                         [row["run_stamp"] for row in rows])

    def test_run_row_carries_the_set_name_and_the_models_summary(self):
        """Ловит мутацию: колонки набора и сводки не пишутся — журнал
        прогонов перестал бы различать наборы, а модели за набором в тот
        прогон восстановить было бы негде (сам набор — файл вне git)."""
        self.insert_run("20260927T000002Z", SET_NAME)

        row = self.conn.execute("SELECT * FROM canary_runs").fetchone()

        self.assertEqual(SET_NAME, row["set_name"])
        self.assertIn("model-codex-a", row["models_summary"])

    def test_insert_without_a_set_name_lands_in_the_default_set(self):
        """Ловит мутацию: у параметра набора нет значения по умолчанию —
        вызыватели кода до этой задачи (`tests/test_pin.py`) писали бы
        `NULL`, и их прогоны выпали бы из гейта пина."""
        store.insert_canary_run(
            self.conn, "20260927T000003Z", "shablon", "01X", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha="sha", verdict="green")

        row = self.conn.execute("SELECT * FROM canary_runs").fetchone()

        self.assertEqual(config.CANARY_DEFAULT_SET, row["set_name"])


class CanaryTablesMigrationTest(TmpDirTest):
    """Требование 7, AC-8: миграция таблиц метрик сохраняет строки."""

    BASELINE_CREATE_BEFORE = (
        "CREATE TABLE canary_baseline ("
        "  title TEXT PRIMARY KEY, steps INTEGER, cost_usd REAL,"
        "  review_iterations INTEGER, updated_at TEXT)")
    RUNS_CREATE_BEFORE = (
        "CREATE TABLE canary_runs ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT, run_stamp TEXT, title TEXT,"
        "  task_id TEXT, steps INTEGER, cost_usd REAL, review_iterations INTEGER,"
        "  escalations INTEGER, outcome TEXT, expected_escalation TEXT,"
        "  actual_escalation INTEGER, marker_mismatch INTEGER, created_at TEXT,"
        "  main_sha TEXT, verdict TEXT)")

    def setUp(self):
        super().setUp()
        self.conn = sqlite3.connect(self.tdir / "state.db")
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        store.create_schema(self.conn)
        self.conn.execute(self.BASELINE_CREATE_BEFORE)
        self.conn.execute(self.RUNS_CREATE_BEFORE)
        self.conn.execute(
            "INSERT INTO canary_baseline (title, steps, cost_usd,"
            " review_iterations, updated_at)"
            " VALUES ('canary-version-json', 5, 6.54, 0, '2026-09-13')")
        self.conn.execute(
            "INSERT INTO canary_runs (run_stamp, title, task_id, steps,"
            " cost_usd, review_iterations, escalations, outcome,"
            " expected_escalation, actual_escalation, marker_mismatch,"
            " created_at, main_sha, verdict)"
            " VALUES ('20260913T090000Z', 'canary-version-json', '01AAA', 5,"
            " 6.54, 0, 0, 'killed', 'no', 0, 0, '2026-09-13', 'deadbeef',"
            " 'green')")
        self.conn.commit()

    def test_baseline_row_survives_under_the_default_set(self):
        """Ловит мутацию: миграция меняет ключ пересозданием таблицы без
        переноса строк — бейзлайны, снятые на живых прогонах (13.09,
        $6.54), исчезли бы, и первый прогон после мержа завёл бы их заново
        уже по другой цене."""
        store._ensure_canary_tables(self.conn)

        rows = self.conn.execute("SELECT * FROM canary_baseline").fetchall()
        self.assertEqual(1, len(rows))
        self.assertEqual(
            ("canary-version-json", config.CANARY_DEFAULT_SET, 5, 6.54, 0),
            (rows[0]["title"], rows[0]["set_name"], rows[0]["steps"],
             rows[0]["cost_usd"], rows[0]["review_iterations"]))

    def test_run_row_survives_under_the_default_set(self):
        """Ловит мутацию: колонка набора добавлена `add_column` и остаётся
        `NULL` у старых строк — журнал прогонов до мержа перестал бы
        принадлежать какому-либо набору, и гейт сдвига пина не увидел бы ни
        одного зелёного прогона."""
        store._ensure_canary_tables(self.conn)

        row = self.conn.execute("SELECT * FROM canary_runs").fetchone()
        self.assertEqual(config.CANARY_DEFAULT_SET, row["set_name"])
        self.assertEqual((5, 6.54, 0), (row["steps"], row["cost_usd"],
                                        row["review_iterations"]))

    def test_migration_is_idempotent_on_the_second_call(self):
        """Ловит мутацию: перенос идёт без сверки «колонка уже есть» —
        второй вызов (а их по одному на каждое обращение к таблицам)
        падал бы `duplicate table`/`no such table`, то есть роняла бы любую
        команду, читающую метрики канарейки."""
        store._ensure_canary_tables(self.conn)
        store._ensure_canary_tables(self.conn)

        rows = self.conn.execute("SELECT * FROM canary_baseline").fetchall()
        self.assertEqual(1, len(rows))
        self.assertEqual(config.CANARY_DEFAULT_SET, rows[0]["set_name"])

    def test_fresh_schema_needs_no_alter_table_at_all(self):
        """Ловит мутацию: новые колонки живут ТОЛЬКО в цепочке
        `add_column` — на свежей БД сверка «есть/нет колонки» гонялась бы с
        самим `ALTER TABLE` при параллельных `store.db()` (класс дефекта
        tests/test_store_schema_migration_parity.py)."""
        fresh = sqlite3.connect(self.tdir / "fresh.db")
        fresh.row_factory = sqlite3.Row
        self.addCleanup(fresh.close)
        store.create_schema(fresh)

        store._ensure_canary_tables(fresh)
        before = store.table_columns(fresh, "canary_runs")
        store._ensure_canary_tables(fresh)

        self.assertEqual(before, store.table_columns(fresh, "canary_runs"))
        self.assertIn("set_name", before)
        self.assertIn("models_summary", before)


if __name__ == "__main__":
    unittest.main()
