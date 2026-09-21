"""Общая обвязка планки 01M31ZHSA6HMH40C2JTDPQJQNZ: чтение НОВОЙ части
интерфейса провайдера и две заглушки-провайдера.

Не тест: общий код нескольких файлов планки живёт только в модулях
`_*.py` рядом с тестами (skills/test-authoring.md).

Имён новых членов интерфейса SPEC не называет: требование 1 описывает
ПРЕДМЕТ («разбор строки вывода исполнителя в событие общего вида»),
требование 9 — переезд сигнатур провалов, а как эти члены будут названы,
решает разработчик. Поэтому планка читает состав интерфейса из самого
`orchestrator/providers/base.py`: всё, что объявлено там СВЕРХ шести
методов и их составных частей, пришедших задачей 01M2ZNTHSNFYSTF904P6SZTPYF
(список `PRE_TASK_MEMBERS` ниже), и есть новая часть контракта.

Заглушки строятся НАД `ClaudeProvider`, а не переписывают его:
- `StubFormatProvider` — «другой формат строки» (AC-8, AC-14): каждый
  новый член интерфейса, принимающий аргументы, получает их в СВОЁМ
  формате (префикс `STUB_PREFIX`) и снимает префикс перед тем, как
  отдать строку реализации Claude; строка формата Claude для заглушки —
  мусор, из которого не извлекается ничего. Члены без аргументов
  (таблица сигнатур, если разработчик объявит её так) отдаются с тем же
  префиксом у каждой строки-сигнатуры — имена самих КЛАССОВ провала
  общие (требование 9) и остаются нетронутыми.
- `CliPriceFreeProvider` — провайдер, чьи модели помечены в каталоге
  `cost_from_cli: false` (AC-9): разбор потока у него тот же, что у
  Claude, отличается только признак каталога.
"""
import inspect
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (config, failure_classification,  # noqa: E402
                          models, providers, roles)
from orchestrator.providers.base import RoleExecutorProvider  # noqa: E402
from orchestrator.providers.claude import ClaudeProvider  # noqa: E402

#: Состав интерфейса ДО этой задачи (SPEC 01M2ZNTHSNFYSTF904P6SZTPYF,
#: требование 1 + составные части предполёта): всё, что объявлено в
#: `base.py` сверх этого набора, — новая часть контракта.
PRE_TASK_MEMBERS = frozenset({
    "name", "command", "environment", "home_reference", "preflight",
    "cli_tool", "model_verdict", "check_cli_found", "check_cli_version",
    "check_token", "check_home_reference", "installed_cli_version",
    "live_smoke_command",
})

#: Префикс «чужого формата» заглушки — им помечена и строка потока, и
#: текст провалившейся попытки.
STUB_PREFIX = "СТЕНД| "

STUB_FORMAT_PROVIDER_NAME = "stub-format"
CLI_PRICE_FREE_PROVIDER_NAME = "stub-no-cli-price"

#: Имена классов провала — общие (требование 9), у заглушки те же.
FAILURE_CLASS_NAMES = frozenset(failure_classification.CLASS_LABELS)


def new_members() -> list:
    """Имена членов, объявленных `RoleExecutorProvider` сверх
    `PRE_TASK_MEMBERS`, в порядке объявления."""
    return [name for name in vars(RoleExecutorProvider)
            if not name.startswith("_") and name not in PRE_TASK_MEMBERS]


def _positional(fn) -> list:
    """Позиционные параметры метода без `self` (метод читается у класса,
    поэтому `self` отсекается явно)."""
    params = [p for p in inspect.signature(fn).parameters.values()
              if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    return params[1:] if params and params[0].name == "self" else params


def new_callables() -> list:
    """(имя, число позиционных параметров) новых членов-функций базы."""
    out = []
    for name in new_members():
        value = vars(RoleExecutorProvider)[name]
        if inspect.isfunction(value):
            out.append((name, len(_positional(value))))
    return out


def parse_results(provider, line: str) -> list:
    """Всё, что новые одноаргументные члены провайдера отдают на строке
    потока.

    Планка не выбирает «тот самый» метод разбора по имени: требование 1
    называет предмет, а не имя, и разбор законно может быть разложен на
    несколько членов. Ассерты ищут названные критерием значения в
    ОБЪЕДИНЕНИИ отданного — это ровно то, что критерий и утверждает
    («событие различает пять предметов»), без фантазии об именах.
    """
    results = []
    for name, arity in new_callables():
        if arity != 1:
            continue
        results.append(getattr(provider, name)(line))
    return results


def claude() -> ClaudeProvider:
    """Провайдер `claude` из реестра — тот же экземпляр, что получает шаг."""
    return providers.get(providers.DEFAULT_PROVIDER)


# --- заглушка «другой формат строки» ---------------------------------

def _stripped(value):
    """Аргумент заглушки в формате Claude: без префикса — не её формат,
    и разбирать в нём нечего."""
    if isinstance(value, str):
        return value[len(STUB_PREFIX):] if value.startswith(STUB_PREFIX) else ""
    return value


def _prefixed(value):
    """Та же структура, где каждая строка, кроме имён классов провала,
    несёт префикс заглушки."""
    if isinstance(value, str):
        return value if value in FAILURE_CLASS_NAMES else STUB_PREFIX + value
    if hasattr(value, "_fields"):
        return type(value)(*[_prefixed(item) for item in value])
    if isinstance(value, dict):
        return {_prefixed(key): _prefixed(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return type(value)(_prefixed(item) for item in value)
    return value


def _translating_method(name: str, arity: int):
    origin = getattr(ClaudeProvider, name)
    if arity:
        def method(self, *args, **kwargs):
            return origin(self, *[_stripped(a) for a in args],
                          **{k: _stripped(v) for k, v in kwargs.items()})
    else:
        def method(self, *args, **kwargs):
            return _prefixed(origin(self, *args, **kwargs))
    method.__name__ = name
    return method


def stub_format_provider_class():
    """Класс заглушки «другой формат строки», собранный по НОВОЙ части
    интерфейса. Новых членов ещё нет — класс совпадает с `ClaudeProvider`
    по поведению, и тесты AC-8/AC-14 честно краснеют: разбор и сигнатуры
    у пульта, а не у провайдера."""
    attrs = {"name": STUB_FORMAT_PROVIDER_NAME}
    for name, arity in new_callables():
        attrs[name] = _translating_method(name, arity)
    for name in new_members():
        value = vars(RoleExecutorProvider)[name]
        if not inspect.isfunction(value) and not isinstance(value, property):
            attrs[name] = _prefixed(getattr(ClaudeProvider, name, value))
    return type("StubFormatProvider", (ClaudeProvider,), attrs)


def stub_line(line: str) -> str:
    """Та же строка потока в формате заглушки."""
    return STUB_PREFIX + line


class CliPriceFreeProvider(ClaudeProvider):
    """Провайдер, чьи модели помечены в каталоге `cost_from_cli: false`.

    Разбор потока — тот же, что у Claude: предмет AC-9 — признак
    каталога, а не формат строки, и смешивать два отличия в одной
    заглушке значило бы не знать, какое из них дало результат.
    """

    name = CLI_PRICE_FREE_PROVIDER_NAME


# --- каталог моделей планки -------------------------------------------

#: Модель провайдера без цены от CLI и её прейскурант. Цены нарочно не
#: совпадают ни с одной ценой репозитория: сумма по тарифу обязана
#: отличаться и от факта CLI образца, и от суммы по «родной» модели.
PRICE_FREE_MODEL = "stub-model-no-cli-price"
PRICE_FREE_PRICES = {"input": 4.0, "output": 20.0,
                     "cache_write": 5.0, "cache_read": 0.40}
PRICE_FREE_DATE = "2026-09-20"


def catalog_text(cost_from_cli: bool = False) -> str:
    """Каталог `models.yaml` планки: один раздел провайдера-заглушки с
    одной моделью. Форма — та же, что у настоящего каталога
    репозитория (`orchestrator/yamlmini.py` не знает блочных списков)."""
    lines = ["providers:", f"  {CLI_PRICE_FREE_PROVIDER_NAME}:",
             "    cli: claude", "    min_cli_version: 1.0.0",
             f"    {models.COST_FROM_CLI_KEY}: "
             f"{'true' if cost_from_cli else 'false'}",
             "    models:", f"      {PRICE_FREE_MODEL}:",
             "        min_cli_version: 1.0.0",
             f"        status: {models.STATUS_SUPPORTED}",
             f"        {models.LIST_PRICE_KEY}:"]
    lines += [f"          {kind}: {PRICE_FREE_PRICES[kind]}"
              for kind in models.PRICE_KINDS]
    lines.append(f"        {models.PRICE_DATE_KEY}: {PRICE_FREE_DATE}")
    return "\n".join(lines) + "\n"


def local_text(model_id: str) -> str:
    """Локальный слой: все три яруса — на одну модель планки."""
    lines = [f"{models.TIERS_KEY}:"]
    lines += [f"  {tier}: {model_id}" for tier in models.TIERS]
    return "\n".join(lines) + "\n"


def expected_tariff_usd(tokens_by_type: dict,
                        prices: dict = None) -> float:
    """Стоимость разбивки usage по четырём ценам тарифа: каждый вид —
    своей ценой, цены заданы за миллион токенов (`spend.tariff_cost_usd`
    считает это же — здесь независимая копия формулы, иначе тест сверял
    бы функцию с ней же)."""
    prices = prices or PRICE_FREE_PRICES
    return sum(count * prices[_sample_kind(key)] / 1_000_000
               for key, count in tokens_by_type.items())


def _sample_kind(key: str) -> str:
    import _sample
    return _sample.KIND_FOR_COUNTER.get(key, key)


# --- регистрация провайдера роли шага ---------------------------------

def register(testcase, provider, role: str) -> None:
    """Ставит `provider` провайдером роли `role` на время теста: запись в
    реестре (`providers.PROVIDERS`) плюс подмена карты исполнителей
    (`roles.provider`) — те же две точки, которыми провайдер роли
    задаётся в работе пульта."""
    registry = dict(providers.PROVIDERS)
    registry[provider.name] = provider
    patcher = mock.patch.object(providers, "PROVIDERS", registry)
    patcher.start()
    testcase.addCleanup(patcher.stop)

    origin = roles.provider

    def provider_of(name):
        return provider.name if name == role else origin(name)

    role_patcher = mock.patch.object(roles, "provider", provider_of)
    role_patcher.start()
    testcase.addCleanup(role_patcher.stop)


def use_catalog(testcase, text: str) -> Path:
    """Каталог моделей планки вместо каталога репозитория
    (`config.MODELS` — защищённый путь, планка его не трогает)."""
    path = testcase.root / "models-under-test.yaml"
    path.write_text(text, encoding="utf-8")
    patcher = mock.patch.object(config, "MODELS", path)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return path
