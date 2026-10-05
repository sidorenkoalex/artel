"""Три слоя данных о моделях: каталог `models.yaml`, локальный слой
`.artel/models.yaml` и разрешение цепочки «роль -> ярус -> модель ->
провайдер» (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD, требования 1, 3, 6, 8;
docs/research/providers-codex-plan.md §3).

До части 1 этой линии модель роли была строкой `model:` в `roles.yaml`, а
вердикт её совместимости с CLI — таблицей в `orchestrator/stack.py`. Цен
моделей в системе не было вовсе: курс токенов задавался по РОЛИ, таблицей
в `orchestrator/config.py`. Теперь модель шага — результат разрешения
цепочки, а провайдер, минимум версии CLI, прейскурант и статус модели
живут в каталоге.

Слои и их назначение:

- `config.MODELS` (`models.yaml` в корне, в git) — что пульт вообще
  умеет запускать: провайдер, минимум версии CLI, прейскурант, статус.
  Общее знание всех клонов. Правит его Оператор командой `doc-commit`
  (`notes.DOC_COMMIT_CONFIG_PATHS`); путь — защищённый
  (`config.PROTECTED_PATHS`).
- `config.MODELS_LOCAL` (`.artel/models.yaml`, ВНЕ git) — выбор
  конкретного пульта: ярус -> модель, при необходимости собственный тариф
  поверх прейскуранта и явное разрешение модели со статусом
  `experimental`. Шаблон кладут `init` и `doctor --fix`. Тот же слой
  несёт наборы ролей канарейки (`canary_sets:`) и переопределение
  провайдера роли (`role_providers:`, кладёт прогон канарейки в слой
  своего эфемерного клона) — SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5.
- `roles.yaml` (`model_tier` у роли) — ярус роли, читает
  `orchestrator/roles.py`.

Каждое звено fail-closed (принцип 5 плана провайдеров): ярус без модели,
модель вне каталога, `experimental` без явного разрешения — именованный
отказ ДО старта агента, а не молчаливый дефолт CLI.

Действующий тариф отдают два входа: `resolve_role` (цепочка целиком —
модель шага роли и её тариф) и `resolve_model` (тариф по идентификатору
модели, без роли — модель ПРОШЕДШЕГО шага, прочитанная из журнала).
Потребитель обоих — `orchestrator/spend.py` (SPEC
01M300A14KRHCFB0DQXVCBJEKF, требования 1-2).
"""
import json
import re
import sys
from collections import namedtuple

from . import config, yamlmini

#: Закрытый перечень ярусов (требование 5). Ярус вне перечня — отказ.
TIERS = ("strong", "standard", "cheap")

#: Виды токенов прейскуранта/тарифа — порядок задаёт порядок колонок
#: печати и порядок полей `Tariff`. Те же четыре вида, что считает
#: `config.USAGE_TOKEN_KEYS`, но в единицах «доллар за миллион токенов».
PRICE_KINDS = ("input", "output", "cache_write", "cache_read")

STATUS_SUPPORTED = "supported"
STATUS_EXPERIMENTAL = "experimental"
STATUSES = (STATUS_SUPPORTED, STATUS_EXPERIMENTAL)

#: Ключи записей каталога и локального слоя — литералами в одном месте,
#: чтобы текст ошибки называл ровно то имя, которое Оператор увидит в
#: файле.
PROVIDERS_KEY = "providers"
MODELS_KEY = "models"
LIST_PRICE_KEY = "list_price_usd_per_mtok"
PRICE_DATE_KEY = "price_date"
MIN_CLI_KEY = "min_cli_version"
COST_FROM_CLI_KEY = "cost_from_cli"
CLI_KEY = "cli"
STATUS_KEY = "status"
TIERS_KEY = "tiers"
OVERRIDES_KEY = "overrides"
TARIFF_KEY = "tariff_usd_per_mtok"
CALIBRATED_AT_KEY = "calibrated_at"
SOURCE_KEY = "source"
ALLOW_EXPERIMENTAL_KEY = "allow_experimental"
#: Наборы ролей канарейки и переопределение провайдера роли (SPEC
#: 01M3FQ2Z2PY0E9T5F5WQ207NP5, требования 2 и 5) — два ключа ОДНОГО слоя,
#: с разных его концов: `canary_sets:` Оператор пишет руками у себя
#: («какие подписки и CLI на этой машине»), `role_providers:` пишет сам
#: прогон канарейки в слой ЭФЕМЕРНОГО КЛОНА, собирая его из выбранного
#: набора. Читатель `role_providers:` — `orchestrator/roles.py::provider`.
CANARY_SETS_KEY = "canary_sets"
ROLE_PROVIDERS_KEY = "role_providers"
#: Модель одной роли мимо яруса (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG,
#: требование 2) — ручка Оператора того же рода, что `tiers:` и
#: `role_providers:`: ярус переводит все роли разом, а замер «одна роль
#: на проверяемой модели, остальные на боевой» без неё не собрать. Её же
#: пишет прогон канарейки в слой клона для ролей набора.
ROLE_MODELS_KEY = "role_models"
PROVIDER_KEY = "provider"
MODEL_KEY = "model"

#: Источник действующего тарифа (требование 8): `Resolution.tariff_source`
#: печатается `models` и `doctor`, поэтому текст — один литерал на всех.
TARIFF_SOURCE_CATALOG = "прейскурант каталога"
TARIFF_SOURCE_OVERRIDE = "переопределение локального слоя"

#: Подсказка починки, общая для отказов по отсутствующему локальному слою:
#: файл вне git, и его отсутствие — штатное состояние свежего клона.
LOCAL_FIX_HINT = "`artel.py doctor --fix` положит шаблон"


class ModelsError(Exception):
    """Данные о моделях взять неоткуда — общий предок всех отказов."""


class CatalogError(ModelsError):
    """Каталог `models.yaml` не прочитан, не разобран или не по схеме."""


class UnknownProviderError(CatalogError):
    """Раздел каталога назван провайдером, которого нет в реестре."""


class MissingPriceError(CatalogError):
    """У модели каталога нет прейскуранта вовсе."""


class IncompletePriceError(CatalogError):
    """В прейскуранте модели задан не весь набор из четырёх видов."""


class ZeroPriceError(CatalogError):
    """Цена вида токенов — ноль (или не положительное число)."""


class LocalLayerError(ModelsError):
    """Локальный слой `.artel/models.yaml` не прочитан или не по схеме."""


class LocalLayerMissingError(LocalLayerError):
    """Локального слоя нет на диске."""


class ResolutionError(ModelsError):
    """Цепочка «роль -> ярус -> модель -> провайдер» не разрешилась."""


class RoleTierError(ResolutionError):
    """Ярус роли не прочитан: поля нет либо значение вне перечня."""


class TierNotMappedError(ResolutionError):
    """Ярус роли не назван в `tiers:` локального слоя."""


class ModelNotInCatalogError(ResolutionError):
    """Модель яруса не найдена в каталоге."""


class ExperimentalNotAllowedError(ResolutionError):
    """Модель со статусом `experimental` не разрешена локальным слоем."""


class RoleModelNotInCatalogError(ModelNotInCatalogError):
    """Модель записи `role_models:` не найдена в каталоге. Отдельный
    класс, потому что текст отказа каталога знает только модель, а
    Оператору нужна и роль — строка раздела, которую править."""


class RoleModelExperimentalError(ExperimentalNotAllowedError):
    """Модель записи `role_models:` со статусом `experimental` не
    разрешена локальным слоем."""


Tariff = namedtuple("Tariff", " ".join(PRICE_KINDS))

CatalogModel = namedtuple(
    "CatalogModel",
    "id provider cli min_cli_version status list_price price_date "
    "cost_from_cli")

ProviderSection = namedtuple(
    "ProviderSection", "name cli min_cli_version cost_from_cli models")

Catalog = namedtuple("Catalog", "providers models")

Override = namedtuple("Override", "model tariff calibrated_at source")

LocalLayer = namedtuple(
    "LocalLayer",
    "tiers overrides allow_experimental role_providers role_models")

#: Одна запись набора ролей канарейки (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5,
#: требование 2): обе половины обязательны — роль с моделью без провайдера
#: (и наоборот) есть ровно то расхождение, за которым следит
#: `doctor.check_model_provider_cli`.
CanarySetRole = namedtuple("CanarySetRole", "role provider model")

Resolution = namedtuple(
    "Resolution",
    "role tier model provider cli min_cli_version status list_price "
    "tariff tariff_source calibrated_at source")

#: Действующий тариф ОДНОЙ модели без цепочки роли (SPEC
#: 01M300A14KRHCFB0DQXVCBJEKF, требование 1): те же четыре поля, что несёт
#: хвост `Resolution` — `resolve_role` и `resolve_model` собирают их одним
#: помощником `_effective_tariff`, чтобы формула «переопределение
#: локального слоя, иначе прейскурант каталога» не разошлась на две копии.
EffectiveTariff = namedtuple(
    "EffectiveTariff", "model tariff tariff_source calibrated_at source")


def version_tuple(raw, where: str) -> tuple:
    """`"2.1.251"` -> `(2, 1, 251)`. `where` — адрес значения в файле,
    он и уходит в текст ошибки: минимум версии, который не читается
    числами, сравнивать не с чем, и молчаливый пропуск здесь означал бы
    предполёт шага без сверки версии CLI — ровно то, ради чего таблица
    совместимости и заводилась (инцидент 19.09)."""
    if not isinstance(raw, str) or not raw:
        raise CatalogError(f"{where}: {MIN_CLI_KEY} не задан строкой вида "
                           f"2.1.251")
    parts = raw.split(".")
    if not all(part.isdigit() for part in parts) or len(parts) < 2:
        raise CatalogError(f"{where}: {MIN_CLI_KEY} = {raw!r} — не версия "
                           f"вида 2.1.251")
    return tuple(int(part) for part in parts)


def _document(path, error_cls, missing_cls=None) -> dict:
    """Файл слоя разобранным отображением. Отсутствие файла — отдельный
    класс ошибки там, где он значим (локальный слой): «файла нет» чинится
    командой, «файл не разобран» — руками."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise (missing_cls or error_cls)(f"{path} не найден") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise error_cls(f"{path} не прочитан: {exc}") from exc
    try:
        document = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        raise error_cls(f"{path} не разобран: {exc}") from exc
    if not isinstance(document, dict):
        raise error_cls(f"{path}: верхний уровень — не отображение")
    return document


def _prices(raw, where: str, error_missing, error_incomplete,
            error_zero) -> Tariff:
    """Четыре цены записи (`list_price_usd_per_mtok` каталога либо
    `tariff_usd_per_mtok` переопределения) — с тремя именованными
    отказами требования 3: прейскуранта нет вовсе, задан не весь набор,
    ноль как цена. Три разных отказа, а не один общий: Оператор чинит
    каждый из них по-своему.

    Класс КАЖДОГО из трёх приходит параметром, включая `error_zero`
    (REVIEW итерации 1, R1-F8): те же три проверки работают и на
    каталоге в git, и на локальном слое Оператора, но чинятся эти два
    файла по-разному — жёсткий `ZeroPriceError` (потомок `CatalogError`)
    уводил бы ноль в `overrides:` мимо будущего `except LocalLayerError`
    трейсбеком.
    """
    if raw is None:
        raise error_missing(f"{where}: прейскуранта нет "
                            f"({LIST_PRICE_KEY}/{TARIFF_KEY})")
    if not isinstance(raw, dict):
        raise error_incomplete(f"{where}: прейскурант — не отображение "
                               f"«вид токенов: цена»")
    missing = [kind for kind in PRICE_KINDS if raw.get(kind) is None]
    if missing:
        raise error_incomplete(
            f"{where}: в прейскуранте нет цен {', '.join(missing)} — "
            f"обязателен весь набор {', '.join(PRICE_KINDS)}")
    values = []
    for kind in PRICE_KINDS:
        value = raw[kind]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise error_incomplete(f"{where}: цена {kind} = {value!r} — "
                                   f"не число")
        if value <= 0:
            raise error_zero(
                f"{where}: цена {kind} = {value} — ноль ценой не бывает "
                f"(модель без тарифа не запускается, а не считается "
                f"бесплатной)")
        values.append(float(value))
    return Tariff(*values)


def _provider_section(name, raw, known_providers) -> ProviderSection:
    """Одна запись раздела `providers:` каталога (требование 1).

    Имя, которого нет в реестре `orchestrator/providers/`, — отказ
    разбора (требование 3): каталог обещает, что модель его раздела
    можно запустить, а запускать её нечем.
    """
    where = f"{config.MODELS}: провайдер {name}"
    if name not in known_providers:
        raise UnknownProviderError(
            f"{where} не зарегистрирован (известны: "
            f"{', '.join(sorted(known_providers))})")
    if not isinstance(raw, dict):
        raise CatalogError(f"{where}: запись — не отображение")
    cli = raw.get(CLI_KEY)
    if not isinstance(cli, str) or not cli:
        raise CatalogError(f"{where}: {CLI_KEY} — не имя инструмента CLI")
    minimum = version_tuple(raw.get(MIN_CLI_KEY), where)
    cost_from_cli = raw.get(COST_FROM_CLI_KEY)
    if not isinstance(cost_from_cli, bool):
        raise CatalogError(f"{where}: {COST_FROM_CLI_KEY} — не true/false")
    models = raw.get(MODELS_KEY)
    if not isinstance(models, dict) or not models:
        raise CatalogError(f"{where}: нет раздела '{MODELS_KEY}:' с моделями")
    return ProviderSection(name, cli, minimum, cost_from_cli, models)


def _catalog_model(section: ProviderSection, model_id, raw) -> CatalogModel:
    where = f"{config.MODELS}: модель {model_id} провайдера {section.name}"
    if not isinstance(raw, dict):
        raise CatalogError(f"{where}: запись — не отображение")
    minimum = version_tuple(raw.get(MIN_CLI_KEY), where)
    status = raw.get(STATUS_KEY)
    if status not in STATUSES:
        raise CatalogError(f"{where}: {STATUS_KEY} = {status!r} — не из "
                           f"перечня {', '.join(STATUSES)}")
    price_date = raw.get(PRICE_DATE_KEY)
    if not isinstance(price_date, str) or not price_date:
        raise CatalogError(f"{where}: {PRICE_DATE_KEY} не проставлена — "
                           f"цена без даты не проверяема на свежесть")
    prices = _prices(raw.get(LIST_PRICE_KEY), where, MissingPriceError,
                     IncompletePriceError, ZeroPriceError)
    return CatalogModel(model_id, section.name, section.cli, minimum, status,
                        prices, price_date, section.cost_from_cli)


def load_catalog(path=None) -> Catalog:
    """Каталог `models.yaml` разобранным (требования 1, 3).

    Модель адресуется идентификатором глобально, не парой «провайдер +
    идентификатор»: локальный слой называет ярусу именно идентификатор
    модели, а один и тот же идентификатор у двух провайдеров означал бы,
    что цепочка не разрешается однозначно — это отказ разбора, а не
    выбор «первого попавшегося».
    """
    from .providers import PROVIDERS
    path = path or config.MODELS
    document = _document(path, CatalogError)
    raw_providers = document.get(PROVIDERS_KEY)
    if not isinstance(raw_providers, dict) or not raw_providers:
        raise CatalogError(f"{path}: нет раздела '{PROVIDERS_KEY}:'")
    sections, models = {}, {}
    for name, raw in raw_providers.items():
        section = _provider_section(name, raw, PROVIDERS)
        sections[name] = section
        for model_id, raw_model in section.models.items():
            if model_id in models:
                raise CatalogError(
                    f"{path}: модель {model_id} описана дважды "
                    f"(провайдеры {models[model_id].provider} и {name})")
            models[model_id] = _catalog_model(section, model_id, raw_model)
    return Catalog(sections, models)


def catalog_model(model_id: str, catalog: Catalog = None) -> CatalogModel:
    """Запись модели каталога. `ModelNotInCatalogError` — модели нет:
    отказ, а не предупреждение (требование 10) — до этой задачи модель
    вне таблицы совместимости запускалась «как есть»."""
    catalog = catalog or load_catalog()
    try:
        return catalog.models[model_id]
    except KeyError:
        raise ModelNotInCatalogError(
            f"модель {model_id} не найдена в каталоге {config.MODELS} "
            f"(есть: {', '.join(sorted(catalog.models))})") from None


def _override_tariff(raw, where: str) -> Tariff:
    """Тариф переопределения — тремя равноправными формами записи.

    Требование 6 называет «собственный тариф по тем же четырём видам
    токенов», но КЛЮЧ, под которым он лежит, не фиксирует, и Оператор
    пишет этот файл руками. Поэтому принимаются все три написания, какие
    у него есть основания выбрать: четыре вида токенов прямо записью
    модели (рядом с `calibrated_at`/`source`), они же под ключом
    каталога `list_price_usd_per_mtok` (переопределение выглядит как
    запись, которую оно замещает) и под ключом `tariff_usd_per_mtok`
    (имя по смыслу: это тариф, а не прейскурант). Отвергать две формы из
    трёх значило бы ловить опечаткой то, что опечаткой не является.
    """
    for key in (TARIFF_KEY, LIST_PRICE_KEY):
        nested = raw.get(key)
        if nested is not None:
            return _prices(nested, f"{where}.{key}", LocalLayerError,
                           LocalLayerError, LocalLayerError)
    flat = {kind: raw.get(kind) for kind in PRICE_KINDS}
    if any(value is not None for value in flat.values()):
        # Хотя бы один вид токенов записью модели — форма выбрана
        # плоская, и неполнота набора здесь уже ошибка, а не «другая
        # форма»: `_prices` назовёт недостающие виды поимённо.
        return _prices(flat, where, LocalLayerError, LocalLayerError,
                       LocalLayerError)
    raise LocalLayerError(
        f"{where}: тарифа нет ни в одной из форм — задай четыре вида "
        f"токенов ({', '.join(PRICE_KINDS)}) записью модели либо под "
        f"ключом {LIST_PRICE_KEY}/{TARIFF_KEY}")


def _override(model_id, raw) -> Override:
    where = f"{config.MODELS_LOCAL}: {OVERRIDES_KEY}.{model_id}"
    if not isinstance(raw, dict):
        raise LocalLayerError(f"{where}: запись — не отображение")
    tariff = _override_tariff(raw, where)
    calibrated_at = raw.get(CALIBRATED_AT_KEY)
    source = raw.get(SOURCE_KEY)
    for key, value in ((CALIBRATED_AT_KEY, calibrated_at),
                       (SOURCE_KEY, source)):
        if not isinstance(value, str) or not value:
            raise LocalLayerError(
                f"{where}: {key} не задан — собственный тариф без даты "
                f"калибровки и основания не отличим от опечатки")
    return Override(model_id, tariff, calibrated_at, source)


def load_local(path=None) -> LocalLayer:
    """Локальный слой `.artel/models.yaml` разобранным (требование 6).

    Файла нет — `LocalLayerMissingError`: отдельный класс, потому что
    чинится он командой (`doctor --fix`), а не правкой содержимого.
    """
    path = path or config.MODELS_LOCAL
    return _local_layer(_document(path, LocalLayerError,
                                  LocalLayerMissingError), path)


def local_template_layer() -> LocalLayer:
    """Слой ШАБЛОНА (`LOCAL_TEMPLATE`) разобранным — тем же разбором, что
    и слой на диске (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 4).

    Нужен сборщику слоя эфемерного клона канарейки: ярусы, которых набор
    не называет, обязаны остаться «как в шаблоне», и повторять их в коде
    литералами значило бы завести вторую копию крутилки пульта — она
    разошлась бы с шаблоном на первой же правке.
    """
    try:
        document = yamlmini.mapping(LOCAL_TEMPLATE)
    except yamlmini.YamlError as exc:  # pragma: no cover - шаблон в коде
        raise LocalLayerError(
            f"шаблон локального слоя не разобран: {exc}") from exc
    return _local_layer(document, "шаблон локального слоя")


def _local_layer(document: dict, path) -> LocalLayer:
    """Разбор уже прочитанного документа локального слоя. `path` — адрес
    источника, он и уходит в текст каждого отказа."""
    raw_tiers = document.get(TIERS_KEY)
    if not isinstance(raw_tiers, dict) or not raw_tiers:
        raise LocalLayerError(f"{path}: нет раздела '{TIERS_KEY}:' "
                              f"(ярус -> идентификатор модели)")
    tiers = {}
    for tier, model_id in raw_tiers.items():
        if tier not in TIERS:
            raise LocalLayerError(
                f"{path}: ярус {tier!r} вне перечня {', '.join(TIERS)}")
        if not isinstance(model_id, str) or not model_id:
            raise LocalLayerError(
                f"{path}: ярус {tier} -> {model_id!r} — не идентификатор "
                f"модели")
        tiers[tier] = model_id
    raw_overrides = document.get(OVERRIDES_KEY) or {}
    if not isinstance(raw_overrides, dict):
        raise LocalLayerError(f"{path}: раздел '{OVERRIDES_KEY}:' — не "
                              f"отображение «модель: тариф»")
    overrides = {model_id: _override(model_id, raw)
                 for model_id, raw in raw_overrides.items()}
    raw_allowed = document.get(ALLOW_EXPERIMENTAL_KEY) or {}
    if not isinstance(raw_allowed, dict):
        raise LocalLayerError(f"{path}: раздел '{ALLOW_EXPERIMENTAL_KEY}:' — "
                              f"не отображение «модель: true»")
    # Разрешением считается РОВНО `true` (требование 6): любое другое
    # значение — не «почти разрешено», а неверная запись, и модель со
    # статусом `experimental` остаётся неразрешённой (fail-closed).
    allowed = {model_id for model_id, value in raw_allowed.items()
               if value is True}
    return LocalLayer(tiers, overrides, allowed,
                      _role_providers(document, path),
                      _role_models(document, path))


def _role_models(document: dict, path) -> dict:
    """Карта «роль -> модель каталога» раздела `role_models:` (SPEC
    01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 2); раздела нет — пустая.

    Модель здесь с каталогом НЕ сверяется: слой разбирает каждый шаг
    любой роли, и опечатка в записи одной роли не вправе останавливать
    соседей — её называет именованный отказ `resolve_role` этой роли и
    строка `doctor` о записи.
    """
    raw = document.get(ROLE_MODELS_KEY) or {}
    if not isinstance(raw, dict):
        raise LocalLayerError(f"{path}: раздел '{ROLE_MODELS_KEY}:' — не "
                              f"отображение «роль: модель»")
    mapped = {}
    for role, model_id in raw.items():
        if not isinstance(model_id, str) or not model_id:
            raise LocalLayerError(
                f"{path}: {ROLE_MODELS_KEY}.{role} = {model_id!r} — не "
                f"идентификатор модели")
        mapped[role] = model_id
    return mapped


def _role_providers(document: dict, path) -> dict:
    """Карта «роль -> провайдер» раздела `role_providers:` (SPEC
    01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 5); раздела нет — пустая.

    Раздел кладёт в слой ЭФЕМЕРНОГО КЛОНА сам прогон канарейки
    (`canary._clone_local_layer_text`), а не Оператор: `roles.yaml`
    приходит из целевого sha и защищён, а локальный слой уже
    переадресован в клон. Имя провайдера здесь НЕ сверяется с реестром:
    незарегистрированное имя останавливает шаг своим именованным отказом
    (`providers.for_role`) и красит строку `doctor` — дублировать эту
    сверку в разборе слоя значило бы завести второй текст на одну причину.
    """
    raw = document.get(ROLE_PROVIDERS_KEY) or {}
    if not isinstance(raw, dict):
        raise LocalLayerError(f"{path}: раздел '{ROLE_PROVIDERS_KEY}:' — не "
                              f"отображение «роль: провайдер»")
    mapped = {}
    for role, name in raw.items():
        if not isinstance(name, str) or not name:
            raise LocalLayerError(
                f"{path}: {ROLE_PROVIDERS_KEY}.{role} = {name!r} — не имя "
                f"провайдера")
        mapped[role] = name
    return mapped


def load_canary_sets(path=None) -> dict:
    """Наборы ролей канарейки из локального слоя (SPEC
    01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 2): «имя набора -> {роль ->
    `CanarySetRole`}». Раздела нет — пустое отображение, не отказ: пульт
    без наборов — штатное состояние (набор по умолчанию наборов не
    требует).

    Читается отдельным входом, а не полем `LocalLayer`: набор нужен ровно
    двум читателям (прогон `canary --set` и строка `doctor`), а слой
    читает каждый шаг любой роли — платить за разбор наборов на каждом
    шаге незачем. Форма записи — вложенные блочные отображения; потоковых
    отображений (`{provider: codex}`) единственный разбор пульта
    (`orchestrator/yamlmini.py`) не знает вовсе.
    """
    path = path or config.MODELS_LOCAL
    document = _document(path, LocalLayerError, LocalLayerMissingError)
    raw = document.get(CANARY_SETS_KEY) or {}
    if not isinstance(raw, dict):
        raise LocalLayerError(
            f"{path}: раздел '{CANARY_SETS_KEY}:' — не отображение «имя "
            f"набора: роль: {PROVIDER_KEY}/{MODEL_KEY}»")
    sets = {}
    for name, raw_set in raw.items():
        where = f"{path}: {CANARY_SETS_KEY}.{name}"
        if not isinstance(raw_set, dict) or not raw_set:
            raise LocalLayerError(
                f"{where}: набор — не отображение «роль: "
                f"{PROVIDER_KEY}/{MODEL_KEY}» либо пуст")
        sets[name] = {role: _canary_set_role(role, raw_entry,
                                             f"{where}.{role}")
                      for role, raw_entry in raw_set.items()}
    return sets


def _canary_set_role(role: str, raw, where: str) -> CanarySetRole:
    if not isinstance(raw, dict):
        raise LocalLayerError(f"{where}: запись роли — не отображение "
                              f"«{PROVIDER_KEY}/{MODEL_KEY}»")
    values = {}
    for key in (PROVIDER_KEY, MODEL_KEY):
        value = raw.get(key)
        if not isinstance(value, str) or not value:
            raise LocalLayerError(
                f"{where}: {key} не задан — обязательны обе половины "
                f"записи ({PROVIDER_KEY} и {MODEL_KEY}): роль с моделью без "
                f"провайдера и есть то расхождение, за которым следит "
                f"doctor")
        values[key] = value
    return CanarySetRole(role, values[PROVIDER_KEY], values[MODEL_KEY])


def layers_or_none() -> tuple:
    """(каталог, локальный слой) ОДНИМ чтением — для вызывающих, которые
    зовут `resolve_role` в цикле по ролям (`doctor.check_models_local`,
    `doctor.check_role_providers`, `stack._model_checks`).

    Нечитаемый слой отдаётся `None`, а не исключением: `resolve_role`
    прочитает его сам и отдаст ИМЕННОЙ отказ по каждой роли — тот же
    текст и тот же класс, что и без предчтения, поэтому вызывающему не
    нужна отдельная ветка на «слой сломан» (REVIEW итерации 1, R1-F3: до
    этого `doctor` перечитывал оба файла по разу на роль в трёх разных
    циклах, а докстринг `resolve_role` обещал обратное).
    """
    def _or_none(load):
        try:
            return load()
        except ModelsError:
            return None
    return _or_none(load_catalog), _or_none(load_local)


def resolve_role(role: str, catalog: Catalog = None,
                 local: LocalLayer = None) -> Resolution:
    """Цепочка «роль -> ярус -> модель -> провайдер» с действующим тарифом
    (требование 8).

    Отказ на каждом звене — свой класс `ResolutionError`: `run`/`auto`
    печатают его текст Оператору вместо трейсбека, а `doctor` — красной
    строкой. `catalog`/`local` передаются, когда вызывающий код уже
    прочитал слои (`layers_or_none` выше): иначе каждая роль перечитывала
    бы оба файла. Одиночный вызов (шаг роли — `runner`) слои не
    передаёт: читать их заранее там негде и незачем.

    Действующий тариф — переопределение локального слоя, иначе
    прейскурант каталога (`_effective_tariff`); источник называется явно и
    уходит наружу полем `tariff_source`. Потребитель тарифа —
    `orchestrator/spend.py`: по нему считается стоимость шага.

    Роль с записью `role_models:` (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG,
    требование 2) идёт на модели записи мимо яруса — `_resolve_role_model`.
    Ярус при этом всё равно читается первым: роль, которой нет в карте
    исполнителей, остаётся прежним отказом, запись слоя её не описывает.
    """
    from . import roles
    try:
        tier = roles.model_tier(role)
    except roles.RolesError as exc:
        raise RoleTierError(str(exc)) from exc
    local = local or load_local()
    if role in local.role_models:
        return _resolve_role_model(role, tier, catalog, local)
    model_id = local.tiers.get(tier)
    if model_id is None:
        raise TierNotMappedError(
            f"ярус {tier} роли {role} не назван в '{TIERS_KEY}:' "
            f"{config.MODELS_LOCAL} (заданы: "
            f"{', '.join(sorted(local.tiers)) or '—'})")
    model = catalog_model(model_id, catalog)
    if model.status == STATUS_EXPERIMENTAL and model_id not in local.allow_experimental:
        raise ExperimentalNotAllowedError(
            f"модель {model_id} (ярус {tier} роли {role}) имеет статус "
            f"{STATUS_EXPERIMENTAL} и не разрешена явно — добавь "
            f"«{ALLOW_EXPERIMENTAL_KEY}: {{{model_id}: true}}» в "
            f"{config.MODELS_LOCAL}")
    effective = _effective_tariff(model, local)
    return Resolution(role, tier, model.id, model.provider, model.cli,
                      model.min_cli_version, model.status, model.list_price,
                      effective.tariff, effective.tariff_source,
                      effective.calibrated_at, effective.source)


def _resolve_role_model(role: str, tier: str, catalog: Catalog,
                        local: LocalLayer) -> Resolution:
    """Разрешение роли по записи `role_models:` — те же звенья
    fail-closed, что у яруса (модель в каталоге, разрешение
    `experimental`), но отказы называют и роль, и модель записи.

    Провайдер — `role_providers:` этой роли, иначе провайдер модели в
    каталоге: запись переводит роль на модель чужого провайдера, и
    провайдер обязан следовать за ней, если слой не назвал его явно.
    """
    model_id = local.role_models[role]
    try:
        model = catalog_model(model_id, catalog)
    except ModelNotInCatalogError as exc:
        raise RoleModelNotInCatalogError(
            f"роль {role}: модель {model_id} записи '{ROLE_MODELS_KEY}:' "
            f"{config.MODELS_LOCAL} — {exc}") from None
    if model.status == STATUS_EXPERIMENTAL and model_id not in local.allow_experimental:
        raise RoleModelExperimentalError(
            f"роль {role}: модель {model_id} записи '{ROLE_MODELS_KEY}:' "
            f"имеет статус {STATUS_EXPERIMENTAL} и не разрешена явно — "
            f"добавь «{ALLOW_EXPERIMENTAL_KEY}: {{{model_id}: true}}» в "
            f"{config.MODELS_LOCAL}")
    provider = local.role_providers.get(role) or model.provider
    effective = _effective_tariff(model, local)
    return Resolution(role, tier, model.id, provider, model.cli,
                      model.min_cli_version, model.status, model.list_price,
                      effective.tariff, effective.tariff_source,
                      effective.calibrated_at, effective.source)


def _effective_tariff(model: CatalogModel, local: LocalLayer) -> EffectiveTariff:
    """Действующий тариф записи каталога: переопределение локального слоя,
    иначе прейскурант. Дата — `calibrated_at` переопределения либо
    `price_date` каталога (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 1):
    именно она отсекает в сверке шаги, записанные до этой цены."""
    override = local.overrides.get(model.id)
    if override is not None:
        return EffectiveTariff(model.id, override.tariff,
                               TARIFF_SOURCE_OVERRIDE, override.calibrated_at,
                               override.source)
    return EffectiveTariff(model.id, model.list_price, TARIFF_SOURCE_CATALOG,
                           model.price_date, str(config.MODELS))


def resolve_model(model_id: str, catalog: Catalog = None,
                  local: LocalLayer = None) -> EffectiveTariff:
    """Действующий тариф модели по её идентификатору — без роли и без
    яруса (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требования 1-2).

    Нужен там, где модель известна сама по себе, а цепочка роли ничего не
    говорит: строка журнала «agent cost KNOWN» прошлого шага несёт модель
    ТОГО шага, и она не обязана совпадать с сегодняшней моделью роли —
    ровно на этом несовпадении и строился инцидент 13.09-20.09 (учёт по
    цене модели, на которой роль уже не ходит).

    Отказы — те же именованные классы, что и у `resolve_role`: модели нет
    в каталоге (`ModelNotInCatalogError`), слои не читаются
    (`CatalogError`/`LocalLayerError`). Статус `experimental` здесь НЕ
    сверяется: разрешение запуска — предмет цепочки роли, а у прошедшего
    шага вопрос «можно ли его запускать» уже не стоит, цена ему нужна в
    любом случае.
    """
    model = catalog_model(model_id, catalog)
    local = local if local is not None else load_local()
    return _effective_tariff(model, local)


# Шаблон локального слоя (требование 7): все ярусы на `claude-opus-5`,
# раздел переопределений пуст, наборы ролей канарейки — закомментированным
# образцом (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 10). Тот же текст
# лежит в `docs/reference/models-local.example.yaml` (требование 13) —
# сверяет тест, а не глаз Оператора.
LOCAL_TEMPLATE = """\
# Локальный слой моделей пульта (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,
# требование 6) — ВНЕ git: выбор конкретного пульта, а не общее знание.
# Кладут `init` и `doctor --fix`, если файла нет; существующий файл ни
# одна из команд не перезаписывает. Читатель — orchestrator/models.py.
#
# tiers — ярус роли (`model_tier` в roles.yaml) -> идентификатор модели
# из каталога models.yaml. Ярус без модели — отказ шага до старта агента.
tiers:
  strong: claude-opus-5
  standard: claude-opus-5
  cheap: claude-opus-5

# overrides — собственный тариф поверх прейскуранта каталога (прокси,
# скидка, свой счёт). Необязателен; без него действует прейскурант.
# Обязательны все четыре вида токенов плюс calibrated_at и source: тариф
# без даты калибровки и основания не отличим от опечатки.
#
# overrides:
#   claude-opus-5:
#     input: 5.0
#     output: 25.0
#     cache_write: 6.25
#     cache_read: 0.50
#     calibrated_at: 2026-09-20
#     source: сверено с фактом CLI 20.09, коэффициент 1.009
#
# Те же четыре цены можно сложить под ключ list_price_usd_per_mtok (как
# в каталоге) или tariff_usd_per_mtok — разбор принимает все три формы.

# allow_experimental — явное разрешение модели со статусом
# `experimental` из каталога. Без записи такая модель не запускается.
#
# allow_experimental:
#   gpt-5.4-mini: true

# canary_sets — именованные наборы ролей канарейки: «имя набора -> роль ->
# (provider, model)». Действует ТОЛЬКО внутри эфемерного клона прогона
# `canary --k <N> --set <имя>`: ни одна роль пульта набором не переведена,
# roles.yaml не трогается. Обе половины записи обязательны. Без --set
# прогон идёт набором по умолчанию (`default`) — всё как у пульта.
# Прогон на наборе, отличном от набора по умолчанию, зелёной канарейкой
# для сдвига пина не считается (docs/operator-session.md).
#
# canary_sets:
#   codex-strong:
#     developer:
#       provider: codex
#       model: gpt-5.6-terra
#     reviewer:
#       provider: codex
#       model: gpt-5.6-terra
#
# Раздел role_providers («роль -> провайдер», переопределение поля
# `provider:` карты исполнителей) кладёт в слой КЛОНА сам прогон, собирая
# его из выбранного набора — руками его писать не нужно.
"""


def local_template_text() -> str:
    """Текст шаблона локального слоя — одна точка для `init`,
    `doctor --fix` и сверки с `docs/reference/models-local.example.yaml`."""
    return LOCAL_TEMPLATE


def ensure_local_template(path=None) -> bool:
    """Кладёт шаблон локального слоя, если файла нет (требование 7).

    `True` — файл создан этим вызовом; `False` — файл уже был и НЕ
    тронут: ни `init`, ни `doctor --fix` не вправе затереть выбор
    Оператора (AC-9). Проверяется существование пути, а не содержимое:
    файл, отредактированный Оператором до неузнаваемости, — всё равно
    его файл.
    """
    path = path or config.MODELS_LOCAL
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(local_template_text(), encoding="utf-8")
    return True


def _price_text(tariff: Tariff) -> str:
    """Четыре цены одной ячейкой: `5/25/6.25/0.5` в порядке
    `PRICE_KINDS` — шапка таблицы называет порядок словами, поэтому
    повторять имена видов в каждой строке незачем."""
    return "/".join(_number_text(value) for value in tariff)


def _number_text(value: float) -> str:
    return f"{value:g}"


def _role_resolutions(catalog: Catalog, local: LocalLayer) -> tuple:
    """([(роль, `Resolution` либо текст отказа)], причина неполноты либо
    `None`) по ролям-агентам `roles.yaml` — столбец «роли» и итоговые
    строки `models` (SPEC 01M3SA3ANYZ7036AAGXZG753E3, требования 1, 6).

    Модель роли — только то, что отдаёт `resolve_role`: до этой задачи
    столбец строился своей копией правила по `tiers:` и не видел
    `role_models:` — таблица 30.09 приписала `claude-opus-5-5` роли,
    шаги которых шли на codex.

    Отказ разрешения одной роли не роняет команду и не гасит прочие
    роли: текст отказа уходит в итоговую строку роли. Нечитаемая карта
    исполнителей — пустой список. В обоих случаях причина неполноты
    печатается НАД таблицей (REVIEW итерации 1, R1-F5): прочерк в столбце
    ролей иначе читался бы как «ни одна роль сюда не ведёт».
    """
    from . import roles
    try:
        entries = roles.load()
    except roles.RolesError as exc:
        return [], f"карта исполнителей не прочитана: {exc}"
    resolutions, refused = [], []
    for role, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("executor") != "agent":
            continue
        try:
            resolutions.append((role, resolve_role(role, catalog, local)))
        except ModelsError as exc:
            resolutions.append((role, str(exc)))
            refused.append(role)
    if refused:
        return resolutions, (f"разрешение не прошло у ролей "
                             f"{', '.join(refused)} — причина в итоговых "
                             f"строках под таблицей")
    return resolutions, None


def _role_source(role: str, resolved: Resolution, local: LocalLayer) -> str:
    """Ключ источника модели роли: `role_models` либо ярус. Это подпись
    к уже разрешённой модели, а не выбор её — модель и провайдер берутся
    только из `Resolution`."""
    return ROLE_MODELS_KEY if role in local.role_models else resolved.tier


def cmd_models() -> None:
    """Команда `models` (требование 12) — ТОЛЬКО чтение: ни файлов, ни
    состояния, ни журнала. Печатает по строке на модель каталога:
    провайдер, модель, статус, минимум CLI, прейскурант, действующий
    тариф с источником и роли, которые фактически идут на эту модель, с
    источником (ярус или запись `role_models:`); под таблицей — строка
    «роль → модель → провайдер (источник)» на каждую роль-агента (SPEC
    01M3SA3ANYZ7036AAGXZG753E3).

    Каталог не разобран — отказ с причиной (sys.exit), а не пустая
    таблица. Локальный слой не прочитан — таблица печатается без
    столбцов тарифа и ролей и без итоговых строк: каталог сам по себе
    Оператору виден и без выбора пульта, а причина названа строкой над
    таблицей. Роль не разрешается — тем же приёмом: своя строка-причина
    над таблицей, иначе прочерк в столбце ролей читался бы как «сюда не
    указывает ни одна роль» (REVIEW итерации 1, R1-F5); текст отказа —
    в итоговой строке роли.
    """
    try:
        catalog = load_catalog()
    except ModelsError as exc:
        sys.exit(f"models: {exc}")
    try:
        local = load_local()
        local_note = None
    except ModelsError as exc:
        local, local_note = None, str(exc)
    if local_note is not None:
        print(f"локальный слой не прочитан: {local_note} — "
              f"действующий тариф и ярусы не показаны ({LOCAL_FIX_HINT})")

    resolutions, roles_note = ([], None)
    if local is not None:
        resolutions, roles_note = _role_resolutions(catalog, local)
    if roles_note is not None:
        print(f"роли показаны не полностью: {roles_note} — "
              f"прочерк в столбце ролей не значит «ролей нет»")
    # {модель: {источник: [роли]}} — только по разрешению роли: роль,
    # переведённая записью `role_models:`, у модели своего яруса не
    # появляется, потому что ярус здесь в обход `resolve_role` не читается.
    roles_of_model = {}
    for role, resolved in resolutions:
        if isinstance(resolved, Resolution):
            roles_of_model.setdefault(resolved.model, {}).setdefault(
                _role_source(role, resolved, local), []).append(role)

    header = ("провайдер", "модель", "статус", "мин. CLI",
              "прейскурант", "действующий тариф", "источник тарифа",
              "роли")
    rows = []
    for model_id in sorted(catalog.models):
        model = catalog.models[model_id]
        tariff_text = tariff_source = "—"
        if local is not None:
            override = local.overrides.get(model_id)
            tariff = override.tariff if override else model.list_price
            tariff_text = _price_text(tariff)
            # Источником названа не только СТОРОНА (каталог против
            # локального слоя), но и основание с датой: тариф, который
            # Оператор откалибровал по журналу, и тариф, переписанный с
            # прейскуранта прокси, — разные основания доверия, а по
            # одному слову «переопределение» их не различить.
            tariff_source = (
                f"{TARIFF_SOURCE_OVERRIDE}: {override.source} "
                f"({override.calibrated_at})" if override
                else f"{TARIFF_SOURCE_CATALOG} ({model.price_date})")
        # Модель без единой роли печатает «—»: ярус, который ведёт сюда,
        # но ролей не несёт, пустым хвостом «cheap: » только мешал бы.
        by_source = roles_of_model.get(model_id, {})
        used = "; ".join(
            f"{source}: {', '.join(sorted(by_source[source]))}"
            for source in sorted(by_source)) or "—"
        rows.append((model.provider, model_id, model.status,
                     ".".join(str(part) for part in model.min_cli_version),
                     _price_text(model.list_price), tariff_text,
                     tariff_source, used))

    widths = [max(len(str(cell)) for cell in column)
              for column in zip(header, *rows)]
    print(f"цены — $ за миллион токенов, порядок: {'/'.join(PRICE_KINDS)}")
    print("  ".join(cell.ljust(width) for cell, width in zip(header, widths)))
    for row in rows:
        print("  ".join(str(cell).ljust(width)
                        for cell, width in zip(row, widths)))
    if resolutions:
        # Порядок звеньев — как у строки `role-providers` `doctor`: роль,
        # затем модель, затем провайдер; Оператор сверяет две команды
        # глазом и не должен переставлять звенья в уме.
        print("роль → модель → провайдер (источник):")
    for role, resolved in resolutions:
        if not isinstance(resolved, Resolution):
            print(f"  {role} → не разрешено: {resolved}")
            continue
        source = _role_source(role, resolved, local)
        source_text = (ROLE_MODELS_KEY if source == ROLE_MODELS_KEY
                       else f"ярус {source}")
        print(f"  {role} → {resolved.model} → {resolved.provider} "
              f"({source_text})")


# --- Наборы моделей задач и допуск пар (SPEC 01M3YCHP14179R32SFJVKQB32G) ---
#
# Файл решений Оператора `model_sets.yaml` (корень, в git, защищённый
# путь): `sets:` — именованные наборы «роль -> модель», `pairs:` —
# допущенные пары «роль -> модель -> date/basis/state», `canary_templates:`
# — класс шаблона канарейки. Допуск пары выдаёт `admit` по числам ADR-0019
# п.5 из `canary_runs`; допуск набора (`set_admitted`) — вход части 2
# деления (`new --set`), правило вины (`autogate_refusal_blame`) — и
# части 3.

SETS_KEY = "sets"
PAIRS_KEY = "pairs"
CANARY_TEMPLATES_KEY = "canary_templates"
MODEL_SETS_SECTIONS = (SETS_KEY, PAIRS_KEY, CANARY_TEMPLATES_KEY)

PAIR_DATE_KEY = "date"
PAIR_BASIS_KEY = "basis"
PAIR_STATE_KEY = "state"
PAIR_ADMITTED = "допущена"
PAIR_SUSPENDED = "приостановлена"

TEMPLATE_FAST = "быстрый"
TEMPLATE_MEDIUM = "средний"
TEMPLATE_HARD = "трудный"
TEMPLATE_CLASSES = (TEMPLATE_FAST, TEMPLATE_MEDIUM, TEMPLATE_HARD)

#: Числа допуска пары (ADR-0019 п.5, дополнение 30.09.2026).
ADMIT_MIN_CLEAN_RUNS = 3
ADMIT_MIN_TEMPLATES = 2
#: Роль с дополнительным условием «прогон с правильным исходом неясности ТЗ».
ADMIT_TZ_AMBIGUITY_ROLE = "analyst"
#: Условие «без повтора developer» не проверяется: колонки повторов в
#: `canary_runs` нет (SPEC, «Не входит»), и сводка говорит это прямо, а не
#: молча опускает условие.
DEVELOPER_RETRIES_LINE = "повторы developer: нет данных"

#: Исходы правила вины отказа автогейта (требование 6) — дословно SPEC.
BLAME_ROLE = "роль"
BLAME_PULT = "пульт/пул"
BLAME_UNKNOWN = "не установлена"

#: Префикс строки отказа автогейта (`fsm_autogate._autogate_conditions`).
AUTOGATE_REFUSAL_PREFIX = "автогейт: "

#: Причины по вине роли — начала текстов `fsm_autogate` после префикса:
#: критерии `manual`/`skip` в планке (test_author), красный полный набор и
#: непройденный критерий `ci` (developer). Роль — виновная роль причины:
#: её пару набора приостанавливает отказ автогейта (SPEC
#: 01M3YCHVVEK14SK8GT4R0H7M2C, требование 4).
_ROLE_BLAME_ROLES = {
    "критерии manual": "test_author",
    "критерии skip": "test_author",
    "полный набор tests/ красный": "developer",
    "критерий ci не пройден": "developer",
}
_ROLE_BLAME_STARTS = tuple(_ROLE_BLAME_ROLES)

#: Причины по вине пульта/пула: ошибка источника планки
#: (`fsm_autogate._plank_sources`), пустой каталог приёмочных тестов,
#: незаведённый worktree, таймаут прогона, отсутствие `tests/` в worktree и
#: прогон, не начатый на занятой машине (`acceptance._full_suite_detail`),
#: исчерпанный бюджет. Тексты — литералы,
#: а не импорт производителей: `acceptance` тянет `stack`, а тот — этот
#: модуль; совпадение с производителями сверяет `tests/test_model_sets.py`.
_PULT_BLAME_STARTS = (
    "перечень долгоживущих файлов не прочитан",
    "долгоживущий файл планки не прочитан",
    "каталог приёмочных тестов пуст",
    "полный набор tests/ не проверен — worktree задачи не заведён",
    "прогон полного набора tests/ превысил",
    "tests/ нет в worktree",
    "прогон не начат",
    "бюджет задачи исчерпан",
)

#: Разделители сводки прогона канарейки (`canary._SUMMARY_SOURCE_SEP`,
#: `canary._plan_summary`): «роль → модель, …; источник: …». Литералы по
#: той же причине: `canary` импортирует этот модуль.
_SUMMARY_SOURCE_SEP = "; источник: "
_SUMMARY_PAIR_SEP = ", "
_SUMMARY_ARROW = " → "

#: Шапка файла, которую `admit` кладёт, если в файле её нет.
MODEL_SETS_HEADER = """\
# Наборы моделей задач и допуск пар «роль — модель» (SPEC
# 01M3YCHP14179R32SFJVKQB32G; ADR-0019 п.5). Решения Оператора: файл
# защищён от ролей, правится `doc-commit`; запись пары пишет команда
# `artel.py admit` — она пересобирает файл, сохраняя только эту шапку.
#
# sets:              <имя набора>: <роль>: <id модели каталога>
# pairs:             <роль>: <id модели>: date / basis / state
#                    (допущена | приостановлена)
# canary_templates:  <title прогона канарейки>: быстрый | средний | трудный
"""

ADMIT_USAGE = ('admit [--revoke] <роль> <модель> --basis "<основание: '
               'прогоны канарейки или документ замера>"')


class ModelSetsError(ModelsError):
    """`model_sets.yaml` не прочитан, не разобран или не по схеме."""


def model_sets_path():
    """Путь файла наборов в корне пульта — от `config.ROOT` в момент
    вызова (песочница подменяет корень)."""
    return config.ROOT / config.MODEL_SETS_REL


def load_model_sets(path=None) -> dict:
    """`model_sets.yaml` разобранным: три раздела всегда отображениями
    (пустой раздел — `{}`), прочие ключи верхнего уровня — как есть."""
    path = path or model_sets_path()
    document = _document(path, ModelSetsError)
    for key in MODEL_SETS_SECTIONS:
        value = document.get(key)
        if value is None:
            document[key] = {}
        elif not isinstance(value, dict):
            raise ModelSetsError(f"{path}: раздел '{key}:' — не отображение")
    return document


def summary_models(summary) -> dict:
    """«роль -> модель» из сводки `models_summary` строки `canary_runs`.
    Сводка без разделителя источника (строки до SPEC
    01M3PYMQ6N4SCAJ9WWTTKH6XNG) разбирается целиком; часть без стрелки
    (карта исполнителей не прочитана) пары не даёт."""
    if not summary:
        return {}
    named = str(summary).split(_SUMMARY_SOURCE_SEP, 1)[0]
    result = {}
    for part in named.split(_SUMMARY_PAIR_SEP):
        role, sep, model = part.partition(_SUMMARY_ARROW)
        if sep and role.strip() and model.strip():
            result[role.strip()] = model.strip()
    return result


def autogate_refusal_blame(text) -> str | None:
    """Правило вины отказа автогейта (требование 6): `BLAME_ROLE`,
    `BLAME_PULT` либо `BLAME_UNKNOWN`; `None` — отказа не было (пусто).

    Строка с префиксом автогейта сверяется по началу причины: сперва
    перечень роли, затем пульта/пула, вне обоих — «не установлена».
    Строка без префикса — не текст `fsm_autogate`; её сверяет
    классификатор отказа попытки роли (`failure_classification`) по
    сигнатурам всех провайдеров. На строках с префиксом классификатор не
    зовётся: его сигнатуры — подстроки («403»), и sha в скобках причины
    засчитал бы пульту причину, которой нет ни в одном перечне.
    """
    if text is None or not str(text).strip():
        return None
    reason = " ".join(str(text).split())
    if reason.startswith(AUTOGATE_REFUSAL_PREFIX):
        reason = reason[len(AUTOGATE_REFUSAL_PREFIX):]
        if reason.startswith(_ROLE_BLAME_STARTS):
            return BLAME_ROLE
        if reason.startswith(_PULT_BLAME_STARTS):
            return BLAME_PULT
        return BLAME_UNKNOWN
    from . import failure_classification, providers
    for name in providers.PROVIDERS:
        if failure_classification.classify_attempt_failure(
                reason, providers.get(name)) is not None:
            return BLAME_PULT
    return BLAME_UNKNOWN


def expected_escalation_met(row) -> bool:
    """Ожидаемая эскалация случилась верно: маркер задан, эскалация была,
    маркер совпал."""
    return (bool(row["expected_escalation"])
            and row["actual_escalation"] == 1
            and row["marker_mismatch"] == 0)


def unclean_reason(row) -> str | None:
    """Почему строка `canary_runs` не чистый прогон (требование 5);
    `None` — чистый. Пустой счётчик — не ноль: чистоту без данных не
    засчитываем."""
    if row["verdict"] != "green":
        return f"вердикт {row['verdict'] or '—'}"
    if row["review_iterations"] != 0:
        return f"итераций ревью {row['review_iterations']}"
    if row["escalations"] != 0 and not expected_escalation_met(row):
        return f"эскалаций {row['escalations']}, ожидаемой с верным исходом нет"
    # «Без эскалаций, кроме ожидаемой» (решение Оператора 02.10.2026, SPEC
    # 01M3YCHVVEK14SK8GT4R0H7M2C, требование 8): выполненная ожидаемая
    # покрывает ровно одну эскалацию, не любое их число.
    if row["escalations"] is not None and row["escalations"] > 1:
        return (f"эскалаций {row['escalations']}, ожидаемая эскалация "
                f"покрывает только одну")
    blame = autogate_refusal_blame(row["autogate_refusal"])
    if blame not in (None, BLAME_PULT):
        return f"отказ автогейта, вина: {blame}"
    return None


def clean_run(row) -> bool:
    return unclean_reason(row) is None


def _canary_rows(conn) -> list:
    """Все строки `canary_runs` по порядку записи; SQL — только в
    `store.py` (инвариант `test_no_sql_outside_store`)."""
    from . import store
    return store.all_canary_runs(conn)


def _template_class(document: dict, title) -> str | None:
    value = document[CANARY_TEMPLATES_KEY].get(title)
    return value if value in TEMPLATE_CLASSES else None


def pair_admission(conn, role: str, model: str,
                   document: dict) -> tuple[list, list]:
    """(строки сводки, перечень недостающего) допуска пары по
    `canary_runs` против чисел ADR-0019 п.5 (требование 3). Пустой
    перечень — чисел достаточно.

    Прогон пары — строка, сводка которой ведёт роль этой моделью. Прогон
    с правильным исходом неясности ТЗ (analyst) по SPEC — любой прогон
    пары, чистота для него отдельно не требуется.
    """
    runs = [row for row in _canary_rows(conn)
            if summary_models(row["models_summary"]).get(role) == model]
    clean = [row for row in runs if clean_run(row)]
    titles = sorted({row["title"] for row in clean})
    medium = [row for row in clean
              if _template_class(document, row["title"]) == TEMPLATE_MEDIUM]
    unclassified = [title for title in titles
                    if _template_class(document, title) is None]

    lines = [f"прогоны пары {role} → {model} в canary_runs: {len(runs)}"]
    for row in runs:
        cls = _template_class(document, row["title"]) or "класс не записан"
        reason = unclean_reason(row)
        verdict = "чистый" if reason is None else f"не чистый — {reason}"
        lines.append(f"  {row['run_stamp']} {row['title']} [{cls}]: {verdict}")
    lines.append(f"чистых прогонов: {len(clean)} (нужно не меньше "
                 f"{ADMIT_MIN_CLEAN_RUNS})")
    lines.append(f"шаблонов среди чистых: {len(titles)} (нужно не меньше "
                 f"{ADMIT_MIN_TEMPLATES})")
    lines.append(f"чистых на шаблоне класса «{TEMPLATE_MEDIUM}»: "
                 f"{len(medium)} (нужно не меньше 1)")

    missing = []
    if len(clean) < ADMIT_MIN_CLEAN_RUNS:
        missing.append(f"чистых прогонов {len(clean)} из "
                       f"{ADMIT_MIN_CLEAN_RUNS}")
    if len(titles) < ADMIT_MIN_TEMPLATES:
        missing.append(f"шаблонов среди чистых прогонов {len(titles)} из "
                       f"{ADMIT_MIN_TEMPLATES}")
    if not medium:
        text = f"нет чистого прогона на шаблоне класса «{TEMPLATE_MEDIUM}»"
        if unclassified:
            text += (f" (шаблоны без записи класса в "
                     f"'{CANARY_TEMPLATES_KEY}:' не засчитаны: "
                     f"{', '.join(unclassified)})")
        missing.append(text)
    if role == ADMIT_TZ_AMBIGUITY_ROLE:
        ambiguity = [row for row in runs if expected_escalation_met(row)]
        lines.append(f"прогонов с правильным исходом неясности ТЗ: "
                     f"{len(ambiguity)} (нужно не меньше 1)")
        if not ambiguity:
            missing.append("нет прогона пары с правильным исходом неясности "
                           "ТЗ (expected_escalation задан, "
                           "actual_escalation = 1, marker_mismatch = 0)")
    lines.append(DEVELOPER_RETRIES_LINE)
    return lines, missing


def _combat_model(role: str) -> str | None:
    """Модель роли разрешением пульта без набора; `None` — не разрешилась
    (тогда пара набора считается не-боевой и требует допуска)."""
    try:
        return resolve_role(role).model
    except ModelsError:
        return None


def set_admitted(conn, set_name: str) -> tuple[bool, str]:
    """(допущен ли набор `set_name` из `sets:`, пояснение) — требование 4.

    Допущен, если (а) каждая его пара, чья модель отличается от боевой
    модели роли, записана в `pairs:` с `state: допущена` и не
    приостановлена пультом (`pair_suspension_refusal`, SPEC
    01M3YCHVVEK14SK8GT4R0H7M2C, требование 5), и (б) в
    `canary_runs` есть строка `verdict = green` на шаблоне класса
    `трудный`, сводка которой совпадает с набором по всем его ролям, а
    каждая роль сводки вне набора шла на своей боевой модели.
    Нечитаемый файл и неизвестный набор — «не допущен» с причиной.
    """
    try:
        document = load_model_sets()
    except ModelsError as exc:
        return False, str(exc)
    members = document[SETS_KEY].get(set_name)
    if not isinstance(members, dict) or not members:
        return False, f"набора {set_name} нет в '{SETS_KEY}:'"
    for role, model in members.items():
        if model == _combat_model(role):
            continue
        refusal = (_pair_refusal(document, role, model)
                   or pair_suspension_refusal(conn, role, model))
        if refusal is not None:
            return False, refusal
    for row in _canary_rows(conn):
        if row["verdict"] != "green":
            continue
        if _template_class(document, row["title"]) != TEMPLATE_HARD:
            continue
        summary = summary_models(row["models_summary"])
        if (all(summary.get(role) == model
                for role, model in members.items())
                and all(model == _combat_model(role)
                        for role, model in summary.items()
                        if role not in members)):
            return True, (f"пары допущены; зелёный прогон набором "
                          f"{row['run_stamp']} на шаблоне {row['title']}")
    return False, (f"нет зелёного прогона набором целиком на шаблоне класса "
                   f"«{TEMPLATE_HARD}» (роли вне набора — на боевых моделях)")


def _pair_refusal(document: dict, role: str, model: str) -> str | None:
    """Почему пара «роль → модель» не допущена записью `pairs:`; `None` —
    `state: допущена`. Один текст на допуск набора (`set_admitted`) и на
    сверку пары набора задачи на старте шага (`resolve_task_role`)."""
    role_pairs = document[PAIRS_KEY].get(role)
    entry = role_pairs.get(model) if isinstance(role_pairs, dict) else None
    state = entry.get(PAIR_STATE_KEY) if isinstance(entry, dict) else None
    if state == PAIR_ADMITTED:
        return None
    return (f"пара {role} → {model} не допущена "
            f"(state: {state or 'нет записи'})")


# --- Набор моделей задачи (SPEC 01M3YCHS4F08VTV6XX10VF92H3) ---
#
# Набор задачи — имя набора и его состав «роль -> модель», записанные в
# строку задачи при `new --set`/`set-models` (колонки `model_set`/
# `model_set_members`). Разрешение модели шага с учётом задачи —
# `resolve_task_role`: роль из записанного состава идёт на модели набора
# теми же звеньями fail-closed, что `role_models:`; роль без записи — на
# боевой модели (`resolve_role`).

#: Подпись источника модели шага из набора задачи (запись старта шага).
SOURCE_TASK_SET = "набор задачи"

#: Модель шага по задаче: разрешение, подпись источника («набор задачи
#: <имя>», `role_models` либо «ярус <ярус>»), шла ли модель из набора, и
#: текст отката на боевую модель, если пара набора снята с допуска.
TaskModel = namedtuple("TaskModel", "resolution source from_set withdrawn")


class TaskSetError(ModelsError):
    """Набор задачи не допущен к `new --set`/`set-models` либо записанный
    состав в строке задачи не читается."""


class SetModelNotInCatalogError(ModelNotInCatalogError):
    """Модель набора задачи не найдена в каталоге."""


class SetModelExperimentalError(ExperimentalNotAllowedError):
    """Модель набора задачи со статусом `experimental` не разрешена
    локальным слоем."""


def _task_field(task, key):
    """Поле строки задачи либо `None`: строки старше колонки и словари
    тестов поля не несут."""
    if task is None:
        return None
    try:
        return task[key]
    except (KeyError, IndexError):
        return None


def task_set_name(task) -> str | None:
    """Имя набора задачи; `None` — задача без набора."""
    return _task_field(task, "model_set") or None


def task_set_members(task) -> dict:
    """Записанный состав набора задачи «роль -> модель»; `{}` — без набора.

    Нечитаемый состав — `TaskSetError`, а не пустой набор: пустой значил
    бы молчаливый шаг на боевых моделях у задачи, которую Оператор завёл
    на наборе."""
    raw = _task_field(task, "model_set_members")
    if not raw:
        return {}
    try:
        members = json.loads(raw)
    except ValueError as exc:
        raise TaskSetError(f"состав набора {task_set_name(task)} в строке "
                           f"задачи не читается: {exc}") from None
    if not isinstance(members, dict) or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in members.items()):
        raise TaskSetError(f"состав набора {task_set_name(task)} в строке "
                           f"задачи — не отображение «роль -> модель»")
    return members


def task_set_hint(task) -> str:
    """Хвост подсказки `approve` на гейте задачи с набором (требование 8):
    Оператор решает гейт, зная, на каких моделях шла задача. Пусто — без
    набора, подсказка байт-в-байт прежняя."""
    name = task_set_name(task)
    return f"  [{SOURCE_TASK_SET}: {name}]" if name else ""


#: Состояния закрытой задачи: её набор моделей больше ничего не запускает.
_CLOSED_STATES = ("done", "killed")


def live_task_set_providers() -> set:
    """Провайдеры моделей из наборов незакрытых задач — добавка к
    востребованным CLI манифеста стека (`stack.model_providers`): задача
    на наборе вправе перевести роль на модель провайдера, которого не
    требует ни один ярус (требование 4).

    БД нет — пустое множество, без её создания: манифест читают и вне
    пульта (CI `scripts/stack_ci.py`). Нечитаемая БД, состав или модель
    вне каталога — пропуск, а не исключение: о модели набора, которую
    шаг не запустит, говорит именованный отказ самого шага."""
    import sqlite3

    from . import store
    if not config.DB.exists():
        return set()
    try:
        rows = store.all_tasks(store.db())
    except sqlite3.Error:
        return set()
    found = set()
    for row in rows:
        if row["state"] in _CLOSED_STATES:
            continue
        try:
            members = task_set_members(row)
        except ModelsError:
            continue
        for model_id in members.values():
            try:
                found.add(catalog_model(model_id).provider)
            except ModelsError:
                continue
    return found


def members_text(members: dict) -> str:
    """Состав набора одной строкой журнала: «роль → модель, …»."""
    return _SUMMARY_PAIR_SEP.join(f"{role}{_SUMMARY_ARROW}{model}"
                                  for role, model in members.items())


def admitted_set_members(conn, set_name: str) -> dict:
    """Состав набора `set_name` из `model_sets.yaml`, если набор допущен
    проверкой части 1 (`set_admitted`); иначе `TaskSetError` с текстом,
    называющим набор и причину (пару и её состояние либо трудный класс).
    Вход `new --set` и `set-models` — одна проверка на обе команды."""
    admitted, reason = set_admitted(conn, set_name)
    if not admitted:
        raise TaskSetError(f"набор {set_name} не допущен: {reason}")
    return dict(load_model_sets()[SETS_KEY][set_name])


def _combat_task_model(role: str, catalog: Catalog, local: LocalLayer,
                       withdrawn: str | None = None) -> TaskModel:
    """Боевая модель роли (`resolve_role`) с подписью источника. Локальный
    слой для подписи читается после разрешения и без отказа: подпись не
    вправе остановить шаг, который цепочка роли уже разрешила."""
    resolved = resolve_role(role, catalog, local)
    if local is None:
        try:
            local = load_local()
        except ModelsError:
            local = None
    source = (ROLE_MODELS_KEY
              if local is not None and role in local.role_models
              else f"ярус {resolved.tier}")
    return TaskModel(resolved, source, False, withdrawn)


def _set_pair_withdrawn(role: str, model_id: str, catalog: Catalog,
                        local: LocalLayer) -> str | None:
    """Почему пара набора задачи больше не допущена к старту шага
    (требование 7); `None` — допущена либо модель совпадает с боевой (её
    пара допуска не требует — то же правило, что у `set_admitted`).
    Нечитаемый `model_sets.yaml` — тоже «не допущена»: подтвердить допуск
    нечем, а молчаливого продолжения на снятой паре быть не должно."""
    try:
        if model_id == resolve_role(role, catalog, local).model:
            return None
    except ModelsError:
        pass
    try:
        document = load_model_sets()
    except ModelsError as exc:
        return f"допуск пары {role} → {model_id} не подтверждён: {exc}"
    refusal = _pair_refusal(document, role, model_id)
    if refusal is not None or not config.DB.exists():
        return refusal
    # Приостановка пультом перекрывает `state: допущена` файла (SPEC
    # 01M3YCHVVEK14SK8GT4R0H7M2C, требование 5): шага роли на
    # приостановленной паре после приостановки нет.
    from . import store
    return pair_suspension_refusal(store.db(), role, model_id)


def resolve_task_role(role: str, task, catalog: Catalog = None,
                      local: LocalLayer = None) -> TaskModel:
    """Модель шага роли с учётом задачи (требования 2, 4, 7).

    Задача без набора и роль без записи в составе набора — боевая модель
    (`resolve_role`), поведение байт-в-байт прежнее. Роль из записанного
    состава идёт на модели набора; провайдер и CLI — модели в каталоге
    (набор переводит роль на модель чужого провайдера — провайдер следует
    за моделью). Звенья fail-closed те же, что у `role_models:`: модели
    нет в каталоге, `experimental` без разрешения локального слоя — отказ
    с ролью, моделью и набором.

    Пара роли, снятая с допуска в `model_sets.yaml` к старту шага, —
    боевая модель роли и непустой `withdrawn`: запись журнала о ней пишет
    вызывающий (`runner`), здесь только факт. Сверяется запись `pairs:`,
    а не `sets:`: правка состава набора в файле задачу в работе не
    двигает (требование 1), а снятие допуска пары — двигает.
    """
    members = task_set_members(task)
    if role not in members:
        return _combat_task_model(role, catalog, local)
    name = task_set_name(task)
    model_id = members[role]
    withdrawn = _set_pair_withdrawn(role, model_id, catalog, local)
    if withdrawn is not None:
        combat = _combat_task_model(role, catalog, local)
        return combat._replace(withdrawn=(
            f"набор задачи {name}: {withdrawn} — шаг роли {role} идёт на "
            f"боевой модели {combat.resolution.model} вместо {model_id}"))
    from . import roles
    try:
        tier = roles.model_tier(role)
    except roles.RolesError as exc:
        raise RoleTierError(str(exc)) from exc
    local = local or load_local()
    try:
        model = catalog_model(model_id, catalog)
    except ModelNotInCatalogError as exc:
        raise SetModelNotInCatalogError(
            f"роль {role}: модель {model_id} набора задачи {name} — "
            f"{exc}") from None
    if model.status == STATUS_EXPERIMENTAL and model_id not in local.allow_experimental:
        raise SetModelExperimentalError(
            f"роль {role}: модель {model_id} набора задачи {name} имеет "
            f"статус {STATUS_EXPERIMENTAL} и не разрешена явно — добавь "
            f"«{ALLOW_EXPERIMENTAL_KEY}: {{{model_id}: true}}» в "
            f"{config.MODELS_LOCAL}")
    effective = _effective_tariff(model, local)
    resolved = Resolution(role, tier, model.id, model.provider, model.cli,
                          model.min_cli_version, model.status,
                          model.list_price, effective.tariff,
                          effective.tariff_source, effective.calibrated_at,
                          effective.source)
    return TaskModel(resolved, f"{SOURCE_TASK_SET} {name}", True, None)


# --- Пробный период и приостановка пары набора (SPEC
# 01M3YCHVVEK14SK8GT4R0H7M2C; ADR-0019 п.5, дополнение 30.09.2026) ---
#
# Счётчик пробного периода и приостановки — в БД пульта, не в
# `model_sets.yaml`: файл несёт решения Оператора, а эти факты — следствия
# работы пульта. Приостановка пультом перекрывает `state: допущена` файла
# (`set_admitted`, `_set_pair_withdrawn`) до `pair-resume`.

#: Число пробных задач набора — ADR-0019 п.5.
SET_TRIAL_TASKS = 3
SET_TRIAL_PHRASE = "пробная задача набора"

#: Вердикты ревью в `pair_verdicts`.
VERDICT_RETURN = "return"
VERDICT_APPROVED = "approved"
#: Виновная роль возврата ревью: возвращена работа developer.
REVIEW_RETURN_ROLE = "developer"

PAIR_SUSPENDED_ACTION = "пара набора приостановлена"
PAIR_RESUMED_ACTION = "пара набора снята с приостановки"
PAIR_SUSPENSION_ALERT_SOURCE = "pair_suspension"
PAIR_RESUME_USAGE = 'pair-resume <роль> <модель> "<решение>"'

#: Поле модели записи «agent run started» (`runner._prepare_step`).
_STEP_MODEL_RE = re.compile(r"\bmodel=([^,\s]+)")
_STEP_STARTED_ACTION = "agent run started"


def _is_canary(task) -> bool:
    return bool(_task_field(task, "is_canary"))


def set_trial_reason(conn, task) -> str | None:
    """Причина ручной приёмки пробной задачи набора (требования 1-2);
    `None` — задача не пробная: без набора, канареечная либо настоящих
    задач в `done` с тем же записанным составом уже три и больше.

    Счёт — из БД на момент решения, по совпадению записанного состава
    (`model_set_members`), не по имени: набор под тем же именем с другим
    составом — другой набор. Нечитаемый состав — `TaskSetError`
    (fail-closed у вызывающего: автогейт не пройдёт)."""
    from . import store
    name = task_set_name(task)
    if not name or _is_canary(task):
        return None
    members = task_set_members(task)
    done = 0
    for row in store.all_tasks(conn):
        if row["state"] != "done" or _is_canary(row) or row["id"] == task["id"]:
            continue
        try:
            if task_set_members(row) == members:
                done += 1
        except ModelsError:
            continue
    if done >= SET_TRIAL_TASKS:
        return None
    return (f"{SET_TRIAL_PHRASE} {name}, {done + 1} из {SET_TRIAL_TASKS} — "
            f"приёмка ручная, пока в done меньше {SET_TRIAL_TASKS} настоящих "
            f"задач этого состава (ADR-0019 п.5)")


def pair_suspension_refusal(conn, role: str, model: str) -> str | None:
    """Текст отказа по действующей приостановке пары пультом; `None` —
    пара не приостановлена пультом."""
    from . import store
    row = store.active_pair_suspension(conn, role, model)
    if row is None:
        return None
    return (f"пара {role} → {model} приостановлена пультом (набор "
            f"{row['set_name']}, задача {row['task_id']}: {row['reason']}) — "
            f"снятие: artel.py pair-resume {role} {model} \"<решение>\"")


def _last_step_model(conn, task_id: str, role: str) -> str | None:
    """Модель последнего шага роли в задаче по записи «agent run started»;
    `None` — шага роли не было."""
    from . import store
    for row in reversed(store.task_steps(conn, task_id)):
        if row["actor"] == role and row["action"] == _STEP_STARTED_ACTION:
            match = _STEP_MODEL_RE.search(row["detail"] or "")
            return match.group(1) if match else None
    return None


def _set_pair(task, role: str) -> str | None:
    """Модель пары набора настоящей задачи по роли; `None` — задача без
    набора, канареечная, роль вне состава или на боевой модели (такая
    пара допуска не требует и не приостанавливается)."""
    if not task_set_name(task) or _is_canary(task):
        return None
    try:
        model = task_set_members(task).get(role)
    except ModelsError:
        return None
    if model is None or model == _combat_model(role):
        return None
    return model


def _suspend_pair(conn, task, role: str, model: str, reason: str) -> None:
    """Приостановка пары пультом (требование 5): строка БД, запись журнала
    задачи-причины и алерт Оператору. Уже приостановленная пара второй
    строки не получает."""
    from . import alerts, store
    if store.active_pair_suspension(conn, role, model) is not None:
        return
    task_id, name = task["id"], task_set_name(task)
    store.insert_pair_suspension(conn, role, model, name, task_id, reason)
    detail = (f"пара {role} → {model} набора {name} приостановлена пультом "
              f"по задаче {task_id}: {reason}; до снятия шаги роли {role} "
              f"идут на боевой модели, new --set с этой парой отказывает; "
              f"снятие — artel.py pair-resume {role} {model} \"<решение>\"")
    store.journal(conn, task_id, "fsm", PAIR_SUSPENDED_ACTION, detail)
    alerts.raise_alert(conn, task_id, "incident",
                       PAIR_SUSPENSION_ALERT_SOURCE, detail)
    print(f"[{task_id}] ВНИМАНИЕ: {detail}")


def _consecutive_returns(conn, role: str, model: str, task_id: str,
                         verdict_id: int) -> str | None:
    """Причина приостановки по возвратам ревью подряд (требование 3);
    `None` — возврат одиночный. «Подряд» — по потоку вердиктов пары
    (ANSWER-1, п.1): непосредственно предыдущий вердикт пары — тоже
    возврат, в этой задаче или в соседней; одобрение между ними цепочку
    рвёт. Засчитываются только вердикты после последнего снятия
    приостановки пары."""
    from . import store
    mark = store.last_pair_resume_mark(conn, role, model)
    earlier = [row for row in store.pair_verdicts_after(conn, role, model, mark)
               if row["id"] < verdict_id]
    if not earlier or earlier[-1]["verdict"] != VERDICT_RETURN:
        return None
    previous = earlier[-1]["task_id"]
    if previous == task_id:
        return f"второй возврат ревью подряд в задаче {task_id}"
    return (f"возврат ревью в задаче {task_id} подряд за возвратом ревью "
            f"предыдущей задачи пары {previous}")


def record_review_verdict(conn, task_id: str, verdict: str) -> None:
    """Вердикт ревью настоящей задачи — паре набора по роли developer, если
    последний шаг developer задачи шёл на этой паре; возврат ревью подряд
    приостанавливает пару (требование 3). Зовётся из `store.set_state` на
    переходах `review -> in_dev`/`review -> acceptance`."""
    from . import store
    task = store.get_task(conn, task_id)
    role = REVIEW_RETURN_ROLE
    model = _set_pair(task, role)
    if model is None or _last_step_model(conn, task_id, role) != model:
        return
    verdict_id = store.insert_pair_verdict(conn, role, model, task_id, verdict)
    if verdict != VERDICT_RETURN:
        return
    reason = _consecutive_returns(conn, role, model, task_id, verdict_id)
    if reason is not None:
        _suspend_pair(conn, task, role, model, reason)


def _refusal_role(reason: str) -> str | None:
    """Виновная роль причины отказа автогейта по перечню правила вины."""
    text = " ".join(str(reason).split())
    if text.startswith(AUTOGATE_REFUSAL_PREFIX):
        text = text[len(AUTOGATE_REFUSAL_PREFIX):]
    for start, role in _ROLE_BLAME_ROLES.items():
        if text.startswith(start):
            return role
    return None


def suspend_on_autogate_refusal(conn, task, reason: str) -> None:
    """Отказ автогейта приёмки по вине роли в настоящей задаче с набором
    приостанавливает пару набора виновной роли (требование 4), если
    последний шаг этой роли в задаче не шёл на другой модели (ANSWER-1,
    п.2): шаг, откаченный на боевую модель, вину на пару не кладёт. Вина `пульт/пул` и `не установлена` (в том числе пробный
    период) пару не трогают."""
    if autogate_refusal_blame(reason) != BLAME_ROLE:
        return
    role = _refusal_role(reason)
    model = _set_pair(task, role) if role is not None else None
    if model is None:
        return
    # Записи шага роли нет — отката не наблюдалось, роль шла по составу
    # набора; вину снимает только последний шаг роли на другой модели.
    last = _last_step_model(conn, task["id"], role)
    if last is not None and last != model:
        return
    _suspend_pair(conn, task, role, model,
                  f"отказ автогейта приёмки по вине роли {role}: {reason}")


def cmd_pair_resume(argv: list) -> None:
    """`pair-resume <роль> <модель> "<решение>"` — снятие приостановки пары
    пультом (требование 6). Пара без действующей приостановки — отказ до
    любой записи в БД. Ручную `state: приостановлена` в `model_sets.yaml`
    команда не трогает: её ведёт Оператор (`admit`/`doc-commit`)."""
    from . import store
    if len(argv) != 3 or not " ".join(argv[2].split()):
        sys.exit(f"pair-resume: нужны роль, модель и текст решения\n"
                 f"{PAIR_RESUME_USAGE}")
    role, model = argv[0], argv[1]
    decision = " ".join(argv[2].split())
    conn = store.db()
    row = store.active_pair_suspension(conn, role, model)
    if row is None:
        sys.exit(f"pair-resume: пара {role} → {model} не приостановлена "
                 f"пультом — снимать нечего (запись state: "
                 f"{PAIR_SUSPENDED} в {config.MODEL_SETS_REL} ведёт "
                 f"Оператор через admit/doc-commit)")
    store.resume_pair_suspension(conn, row["id"], decision)
    detail = (f"пара {role} → {model} набора {row['set_name']} снята с "
              f"приостановки пульта; решение Оператора: {decision}")
    store.journal(conn, row["task_id"], "operator", PAIR_RESUMED_ACTION, detail)
    print(detail)

def _scalar_yaml(value, where: str) -> str:
    """Скаляр так, чтобы `yamlmini.scalar` вернул его дословно (число,
    `#`, ведущая `[` — в кавычки); невыразимый — отказ."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value)
    if text and not text.startswith("[") and yamlmini.scalar(text) == text:
        return text
    for quote in ('"', "'"):
        if quote not in text:
            quoted = f"{quote}{text}{quote}"
            if yamlmini.scalar(quoted) == text:
                return quoted
    raise ModelSetsError(f"{where}: значение {text!r} не записывается в "
                         f"подмножестве YAML пульта")


def _render_block(block: dict, indent: int, where: str) -> list:
    pad = " " * indent
    lines = []
    for key, value in block.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines += _render_block(value, indent + 2, f"{where}.{key}")
            continue
        rendered = _scalar_yaml(value, f"{where}.{key}")
        lines.append(f"{pad}{key}: {rendered}" if rendered else f"{pad}{key}:")
    return lines


def _with_sections(document: dict) -> dict:
    """Документ с тремя разделами по порядку (пустой — `{}`) и прочими
    ключами верхнего уровня за ними — форма записи и сравнения."""
    result = {key: document.get(key) or {} for key in MODEL_SETS_SECTIONS}
    result.update({key: value for key, value in document.items()
                   if key not in result})
    return result


def _leading_comments(text: str) -> str:
    """Шапка файла — строки комментариев (и пустые) до первого ключа."""
    head = []
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            break
        head.append(line)
    while head and not head[-1].strip():
        head.pop()
    return "\n".join(head) + "\n" if head else ""


def render_model_sets(document: dict, header: str = MODEL_SETS_HEADER) -> str:
    """Текст `model_sets.yaml`: шапка, три раздела по порядку, прочие
    ключи верхнего уровня. Результат сверяется обратным разбором: текст,
    который `yamlmini` прочёл бы в другие записи (ключ с двоеточием,
    невыразимое значение), не пишется — `ModelSetsError`."""
    ordered = _with_sections(document)
    body = "\n".join(_render_block(ordered, 0, config.MODEL_SETS_REL))
    text = (header.rstrip("\n") + "\n\n" if header else "") + body + "\n"
    try:
        parsed = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        raise ModelSetsError(f"{config.MODEL_SETS_REL}: пересобранный текст "
                             f"не разбирается: {exc}") from exc
    if _with_sections(parsed) != ordered:
        raise ModelSetsError(f"{config.MODEL_SETS_REL}: пересобранный текст "
                             f"разбирается в другие записи (ключ или значение "
                             f"вне подмножества YAML пульта)")
    return text


def _parse_admit_args(argv: list):
    import argparse

    class _Parser(argparse.ArgumentParser):
        # Отказ разбора — именованный текст с образцом команды, а не код 2
        # и справка argparse в stderr.
        def error(self, message):
            sys.exit(f"admit: {message}\n{ADMIT_USAGE}")

    parser = _Parser(prog="admit", add_help=False)
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument("--basis")
    parser.add_argument("role")
    parser.add_argument("model")
    return parser.parse_args(argv)


def cmd_admit(argv: list) -> None:
    """`admit <роль> <модель> --basis <текст>` — допуск пары по числам
    ADR-0019 п.5; `admit --revoke …` — снятие (требование 3).

    Выдача печатает сводку прогонов пары; недобор — отказ с перечнем
    недостающего до любой записи: файл и HEAD не трогаются, флага вопреки
    недобору нет. Снятие чисел не сверяет. Запись — изолированный коммит
    механизмом `doc-commit` (`notes.doc_commit_content`: окно тишины,
    удержание, гейт полного набора на пути конфигурации).
    """
    from datetime import date

    from . import notes, roles, store
    args = _parse_admit_args(argv)
    basis = " ".join((args.basis or "").split())
    if not basis:
        sys.exit(f"admit: --basis обязателен — основание решения входит в "
                 f"запись пары\n{ADMIT_USAGE}")
    try:
        roles.model_tier(args.role)
    except roles.RolesError as exc:
        sys.exit(f"admit: роль {args.role}: {exc}")
    try:
        catalog_model(args.model)
        document = load_model_sets()
    except ModelsError as exc:
        sys.exit(f"admit: {exc}")

    if args.revoke:
        state, action = PAIR_SUSPENDED, "снятие допуска"
    else:
        lines, missing = pair_admission(store.db(), args.role, args.model,
                                        document)
        print("\n".join(lines))
        if missing:
            sys.exit("admit: допуск пары не выдан — недостаёт:\n"
                     + "\n".join(f"  - {item}" for item in missing)
                     + f"\n{config.MODEL_SETS_REL} не изменён")
        state, action = PAIR_ADMITTED, "допуск"

    pairs = document[PAIRS_KEY]
    if not isinstance(pairs.get(args.role), dict):
        pairs[args.role] = {}
    pairs[args.role][args.model] = {PAIR_DATE_KEY: date.today().isoformat(),
                                    PAIR_BASIS_KEY: basis,
                                    PAIR_STATE_KEY: state}
    try:
        current = model_sets_path().read_text(encoding="utf-8")
        text = render_model_sets(
            document, _leading_comments(current) or MODEL_SETS_HEADER)
    except (OSError, UnicodeDecodeError, ModelsError) as exc:
        sys.exit(f"admit: {exc}")
    print(f"{action} пары {args.role} → {args.model}: state: {state}")
    notes.doc_commit_content(
        config.MODEL_SETS_REL, text,
        f"{action} пары {args.role} → {args.model}: {basis}")
