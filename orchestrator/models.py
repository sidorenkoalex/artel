"""Три слоя данных о моделях: каталог `models.yaml`, локальный слой
`.artel/models.yaml` и разрешение цепочки «роль -> ярус -> модель ->
провайдер» (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD, требования 1, 3, 6, 8;
docs/research/providers-codex-plan.md §3).

До этой задачи модель роли была строкой `model:` в `roles.yaml`, а
вердикт её совместимости с CLI — таблицей в `orchestrator/stack.py`. Цен
моделей в системе не было вовсе: курс токенов задавался по РОЛИ
(`config.TOKEN_RATES`). Теперь модель шага — результат разрешения
цепочки, а провайдер, минимум версии CLI, прейскурант и статус модели
живут в каталоге.

Слои и их назначение:

- `config.MODELS` (`models.yaml` в корне, в git, защищённый путь) — что
  пульт вообще умеет запускать: провайдер, минимум версии CLI,
  прейскурант, статус. Общее знание всех клонов.
- `config.MODELS_LOCAL` (`.artel/models.yaml`, ВНЕ git) — выбор
  конкретного пульта: ярус -> модель, при необходимости собственный тариф
  поверх прейскуранта и явное разрешение модели со статусом
  `experimental`. Шаблон кладут `init` и `doctor --fix`.
- `roles.yaml` (`model_tier` у роли) — ярус роли, читает
  `orchestrator/roles.py`.

Каждое звено fail-closed (принцип 5 плана провайдеров): ярус без модели,
модель вне каталога, `experimental` без явного разрешения — именованный
отказ ДО старта агента, а не молчаливый дефолт CLI.

Действующий тариф эта задача только ОТДАЁТ (`Resolution.tariff`): его
потребитель — часть 2 линии, `config.TOKEN_RATES` и `orchestrator/
spend.py` этой задачей не меняются.
"""
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


Tariff = namedtuple("Tariff", " ".join(PRICE_KINDS))

CatalogModel = namedtuple(
    "CatalogModel",
    "id provider cli min_cli_version status list_price price_date "
    "cost_from_cli")

ProviderSection = namedtuple(
    "ProviderSection", "name cli min_cli_version cost_from_cli models")

Catalog = namedtuple("Catalog", "providers models")

Override = namedtuple("Override", "model tariff calibrated_at source")

LocalLayer = namedtuple("LocalLayer", "tiers overrides allow_experimental")

Resolution = namedtuple(
    "Resolution",
    "role tier model provider cli min_cli_version status list_price "
    "tariff tariff_source calibrated_at source")


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


def _prices(raw, where: str, error_missing, error_incomplete) -> Tariff:
    """Четыре цены записи (`list_price_usd_per_mtok` каталога либо
    `tariff_usd_per_mtok` переопределения) — с тремя именованными
    отказами требования 3: прейскуранта нет вовсе, задан не весь набор,
    ноль как цена. Три разных отказа, а не один общий: Оператор чинит
    каждый из них по-своему."""
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
            raise ZeroPriceError(
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
                     IncompletePriceError)
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
                           LocalLayerError)
    flat = {kind: raw.get(kind) for kind in PRICE_KINDS}
    if any(value is not None for value in flat.values()):
        # Хотя бы один вид токенов записью модели — форма выбрана
        # плоская, и неполнота набора здесь уже ошибка, а не «другая
        # форма»: `_prices` назовёт недостающие виды поимённо.
        return _prices(flat, where, LocalLayerError, LocalLayerError)
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
    document = _document(path, LocalLayerError, LocalLayerMissingError)
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
    return LocalLayer(tiers, overrides, allowed)


def resolve_role(role: str, catalog: Catalog = None,
                 local: LocalLayer = None) -> Resolution:
    """Цепочка «роль -> ярус -> модель -> провайдер» с действующим тарифом
    (требование 8).

    Отказ на каждом звене — свой класс `ResolutionError`: `run`/`auto`
    печатают его текст Оператору вместо трейсбека, а `doctor` — красной
    строкой. `catalog`/`local` передаются, когда вызывающий код уже
    прочитал слои (`doctor`, команда `models`, строки `check_stack()` по
    ролям): иначе каждая роль перечитывала бы оба файла.

    Действующий тариф — переопределение локального слоя, иначе
    прейскурант каталога; источник называется явно и уходит наружу
    полем `tariff_source` (потребитель тарифа — часть 2 линии).
    """
    from . import roles
    try:
        tier = roles.model_tier(role)
    except roles.RolesError as exc:
        raise RoleTierError(str(exc)) from exc
    local = local or load_local()
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
    override = local.overrides.get(model_id)
    if override is not None:
        tariff, source_kind = override.tariff, TARIFF_SOURCE_OVERRIDE
        calibrated_at, source = override.calibrated_at, override.source
    else:
        tariff, source_kind = model.list_price, TARIFF_SOURCE_CATALOG
        calibrated_at, source = model.price_date, str(config.MODELS)
    return Resolution(role, tier, model.id, model.provider, model.cli,
                      model.min_cli_version, model.status, model.list_price,
                      tariff, source_kind, calibrated_at, source)


# Шаблон локального слоя (требование 7): все ярусы на `claude-opus-5`,
# раздел переопределений пуст. Тот же текст лежит в
# `docs/reference/models-local.example.yaml` (требование 13) — сверяет
# тест, а не глаз Оператора.
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


def _roles_by_tier() -> dict:
    """{ярус: [роли]} по `roles.yaml` — столбец «роли по ярусам»
    (требование 12). Нечитаемая карта исполнителей не роняет команду:
    столбец просто пуст, остальная таблица Оператору всё равно нужна."""
    from . import roles
    grouped = {}
    try:
        entries = roles.load()
    except roles.RolesError:
        return grouped
    for role, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("executor") != "agent":
            continue
        try:
            grouped.setdefault(roles.model_tier(role), []).append(role)
        except roles.RolesError:
            continue
    return grouped


def cmd_models() -> None:
    """Команда `models` (требование 12) — ТОЛЬКО чтение: ни файлов, ни
    состояния, ни журнала. Печатает по строке на модель каталога:
    провайдер, модель, статус, минимум CLI, прейскурант, действующий
    тариф с источником и роли, чьи ярусы на неё указывают.

    Каталог не разобран — отказ с причиной (sys.exit), а не пустая
    таблица. Локальный слой не прочитан — таблица печатается без
    столбцов тарифа и ролей: каталог сам по себе Оператору виден и без
    выбора пульта, а причина названа строкой над таблицей.
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

    by_tier = _roles_by_tier() if local is not None else {}
    tier_of_model = {}
    for tier, model_id in (local.tiers.items() if local else ()):
        tier_of_model.setdefault(model_id, []).append(tier)

    header = ("провайдер", "модель", "статус", "мин. CLI",
              "прейскурант", "действующий тариф", "источник тарифа",
              "роли по ярусам")
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
        # Ярус, на который не указывает ни одна роль, в столбец не
        # попадает: «cheap: » пустым хвостом только мешал бы читать
        # таблицу, а сам факт «ярус ведёт сюда, но ролей нет» виден по
        # отсутствию строки — модель без единой роли печатает «—».
        used = "; ".join(
            f"{tier}: {', '.join(sorted(by_tier[tier]))}"
            for tier in sorted(tier_of_model.get(model_id, []))
            if by_tier.get(tier)) or "—"
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
