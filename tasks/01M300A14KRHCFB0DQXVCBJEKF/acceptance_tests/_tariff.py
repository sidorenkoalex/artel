"""Общая обвязка планки задачи 01M300A14KRHCFB0DQXVCBJEKF (тариф на
модель, история тарифов, сверка по паре роль-модель).

Не тест: общий код нескольких файлов планки живёт только в модулях
`_*.py` рядом с тестами (skills/test-authoring.md). Здесь — временный
каталог моделей с ДВУМЯ моделями разной цены, локальный слой, карта
исполнителей, где две роли сидят на одной модели, а третья на другой, и
помощники журнала/`doctor`.

Песочница переходов FSM здесь не нужна и не заводится: предмет задачи —
учёт стоимости шага, а не переход состояния, поэтому берётся готовая
`tests.sandbox.TaskSeededTmpRootTest` (временные пути `config` + БД +
одна заведённая задача), а не собственная копия чего-либо из
`tests/sandbox.py`.
"""
import inspect
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, models, spend, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

#: Две модели каталога планки. Цены нарочно разные по всем четырём видам
#: токенов: любое «посчитали по чужому тарифу» меняет сумму. Ни один из
#: двух наборов не совпадает с сегодняшней ставкой удаляемой таблицы
#: курса по роли ($5/$25/$6.25/$0.50 за миллион) — иначе расчёт «по
#: роли» случайно сходился бы с ожиданием «по модели».
MODEL_ALFA = "model-alfa"
MODEL_BETA = "model-beta"

PRICES = {
    MODEL_ALFA: {"input": 3.0, "output": 15.0,
                 "cache_write": 3.75, "cache_read": 0.30},
    MODEL_BETA: {"input": 7.0, "output": 35.0,
                 "cache_write": 8.75, "cache_read": 0.70},
}

#: Дата прейскуранта каталога — в прошлом относительно дня прогона: с неё
#: идёт сверка, и строки журнала, записанные «сейчас», обязаны быть не
#: старше её. Абсолютный литерал здесь стал бы бомбой замедленного
#: действия (в 2027-м «2026-09-20» окажется старше любого порога).
CATALOG_PRICE_DATE = (date.today() - timedelta(days=30)).isoformat()

#: Дата и основание собственного тарифа локального слоя — нарочно не
#: совпадают ни с датой прейскуранта, ни с сегодняшним днём.
OVERRIDE_CALIBRATED_AT = "2026-02-03"
OVERRIDE_SOURCE = "калибровка планки 01M300A14K"

#: Разбивка usage характерного шага: почти весь объём — чтения кэша.
TOKENS = {"input_tokens": 40_000,
          "output_tokens": 20_000,
          "cache_creation_input_tokens": 60_000,
          "cache_read_input_tokens": 2_000_000}

#: Ярусы локального слоя: `developer`/`reviewer` (ярус strong) приходят на
#: одну модель, `test_author` (ярус standard) — на другую.
LOCAL_TIERS = (("strong", MODEL_ALFA), ("standard", MODEL_BETA),
               ("cheap", MODEL_ALFA))

ROLE_ON_ALFA = "developer"
OTHER_ROLE_ON_ALFA = "reviewer"
ROLE_ON_BETA = "test_author"

ROLES_TEXT = """\
roles:
  analyst:
    executor: agent
    token_slot: artel-analyst
    skills: [conventions-core]
    model_tier: strong
  test_author:
    executor: agent
    token_slot: artel-test-author
    skills: [conventions-core]
    model_tier: standard
  developer:
    executor: agent
    token_slot: artel-developer
    skills: [conventions-core]
    model_tier: strong
  reviewer:
    executor: agent
    token_slot: artel-reviewer
    skills: [conventions-core]
    model_tier: strong
token_fallback: artel-token
"""


def catalog_text(price_date: str = None, prices: dict = None) -> str:
    """Каталог `models.yaml` планки: один провайдер, две модели."""
    price_date = price_date or CATALOG_PRICE_DATE
    prices = prices or PRICES
    lines = ["providers:", "  claude:", "    cli: claude",
             "    min_cli_version: 1.0.0", "    cost_from_cli: true",
             "    models:"]
    for model_id in (MODEL_ALFA, MODEL_BETA):
        lines += [f"      {model_id}:",
                  "        min_cli_version: 1.0.0",
                  f"        status: {models.STATUS_SUPPORTED}",
                  f"        {models.LIST_PRICE_KEY}:"]
        lines += [f"          {kind}: {prices[model_id][kind]}"
                  for kind in models.PRICE_KINDS]
        lines.append(f"        {models.PRICE_DATE_KEY}: {price_date}")
    return "\n".join(lines) + "\n"


def local_text(overrides: dict = None) -> str:
    """Локальный слой `.artel/models.yaml` планки: ярусы и, по желанию,
    собственный тариф поверх прейскуранта (`{модель: {вид: цена}}`)."""
    lines = [f"{models.TIERS_KEY}:"]
    lines += [f"  {tier}: {model_id}" for tier, model_id in LOCAL_TIERS]
    if overrides:
        lines.append(f"{models.OVERRIDES_KEY}:")
        for model_id, table in overrides.items():
            lines.append(f"  {model_id}:")
            lines += [f"    {kind}: {table[kind]}"
                      for kind in models.PRICE_KINDS]
            lines.append(f"    {models.CALIBRATED_AT_KEY}: "
                         f"{OVERRIDE_CALIBRATED_AT}")
            lines.append(f"    {models.SOURCE_KEY}: {OVERRIDE_SOURCE}")
    return "\n".join(lines) + "\n"


def scaled(model_id: str, factor: float) -> dict:
    """Четыре цены модели, умноженные на `factor` — «подмена тарифа»."""
    return {kind: price * factor
            for kind, price in PRICES[model_id].items()}


def expected_cost_usd(model_id: str, tokens: dict = None,
                      prices: dict = None) -> float:
    """Стоимость разбивки usage по четырём ценам тарифа модели: каждый
    счётчик `config.USAGE_TOKEN_KEYS` — своей ценой того же порядкового
    вида `models.PRICE_KINDS`, цены заданы за МИЛЛИОН токенов."""
    tokens = TOKENS if tokens is None else tokens
    table = prices if prices is not None else PRICES[model_id]
    return sum(tokens.get(usage_key, 0) * table[kind] / 1_000_000
               for usage_key, kind in zip(config.USAGE_TOKEN_KEYS,
                                          models.PRICE_KINDS))


def cost(actual_usd: float, tokens: dict = None) -> dict:
    """Стоимость шага в форме `spend.parse_cost_event`."""
    tokens = TOKENS if tokens is None else tokens
    return {"usd": actual_usd, "tokens": sum(tokens.values()),
            "tokens_by_type": dict(tokens)}


def attempt_label(attempt: int) -> str:
    return f"попытка {attempt}/3"


def numbered_for(attempt: int, model_id: str | None) -> str:
    """`numbered`, который `orchestrator/runner.py` отдаёт `spend.py`:
    с `model=<идентификатор>` там, где модель шага известна (с 19.09), и
    без довеска там, где строка записана старым форматом."""
    label = attempt_label(attempt)
    return label if model_id is None else f"{label}, model={model_id}"


def known_actuals(pairs: dict) -> list:
    """Все фактические цены из `spend.known_cost_pairs` — поперёк любых
    ключей: форму ключа («роль», «модель», пара) критерий не фиксирует, а
    вошла строка в сверку или нет, видно по её факту CLI."""
    return [item[-1] for items in pairs.values() for item in items]


def model_tariff_rows(conn, model_id: str) -> list:
    """Строки `model_tariffs`, относящиеся к модели — по значению любой
    колонки: имя колонки-модели критерий AC-7 не называет."""
    rows = conn.execute("SELECT * FROM model_tariffs").fetchall()
    return [row for row in rows
            if model_id in {str(value) for value in tuple(row)}]


def doctor_checks_mentioning(*needles: str) -> list:
    """Проверки `doctor`, подключённые к `doctor.all_checks` и называющие
    в своём исходнике хотя бы одну из подстрок.

    Имён новых проверок SPEC не фиксирует (требование 8 называет их
    по-русски: «тариф свеж», «тариф не старше смены модели у роли»),
    поэтому планка ищет их по тому, что критерий называет ДОСЛОВНО —
    константе потолка и действию журнала. Если исходник самой функции
    подстроку не несёт (проверка вынесла разбор в помощник рядом),
    берётся модуль целиком — по подмодулю `orchestrator/doctor/`
    попадание всё равно локально.
    """
    from orchestrator import doctor
    wired = inspect.getsource(doctor.all_checks)
    exact, by_module = [], []
    for name in sorted(dir(doctor)):
        if not name.startswith("check_") or name not in wired:
            continue
        fn = getattr(doctor, name, None)
        if not inspect.isfunction(fn):
            continue
        try:
            own = inspect.getsource(fn)
            module = inspect.getmodule(fn)
            whole = inspect.getsource(module) if module is not None else ""
        except (OSError, TypeError):
            continue
        if any(needle in own for needle in needles):
            exact.append(fn)
        elif any(needle in whole for needle in needles):
            by_module.append(fn)
    return exact or by_module


def run_doctor_checks(fns: list, conn) -> list:
    """Результаты проверок списком `doctor.Check` — проверка без
    параметров зовётся без аргументов, с параметром получает соединение
    (оба приёма живут в `doctor.all_checks` рядом).

    Одиночный `Check` узнаётся по полю `status`, а не по «это не список»:
    `Check` — namedtuple, то есть сам кортеж, и слепое разворачивание
    кортежа рассыпало бы его на три строки.
    """
    results = []
    for fn in fns:
        out = fn(conn) if inspect.signature(fn).parameters else fn()
        if hasattr(out, "status"):
            results.append(out)
        else:
            results.extend(out)
    return results


class TariffSandbox(TaskSeededTmpRootTest):
    """Временный пульт с каталогом моделей планки, локальным слоем и
    картой исполнителей: `self.conn` — БД с одной заведённой задачей
    `self.TASK`."""

    def setUp(self):
        super().setUp()
        self.catalog_path = self.root / "models-under-test.yaml"
        self.roles_path = self.root / "roles-under-test.yaml"
        self.patch_config("MODELS", self.catalog_path)
        self.patch_config("ROLES", self.roles_path)
        self.roles_path.write_text(ROLES_TEXT, encoding="utf-8")
        self.use_catalog()
        self.use_local()
        self.conn = store.db()

    def patch_config(self, attr: str, value) -> None:
        patcher = mock.patch.object(config, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def use_catalog(self, **kwargs) -> None:
        self.catalog_path.write_text(catalog_text(**kwargs), encoding="utf-8")

    def use_local(self, **kwargs) -> None:
        config.MODELS_LOCAL.write_text(local_text(**kwargs), encoding="utf-8")

    def charge_known(self, role: str, model_id: str | None,
                     actual_usd: float, attempt: int = 1,
                     tokens: dict = None) -> None:
        """Шаг с известной стоимостью — тем же вызовом и тем же
        `numbered`, каким его записывает `orchestrator/runner.py`."""
        spend.charge_step(self.conn, self.TASK, role,
                          cost(actual_usd, tokens),
                          numbered_for(attempt, model_id))

    def backdate(self, attempt: int, day: str) -> None:
        """Состаривает строку журнала конкретной попытки до даты `day`."""
        self.conn.execute(
            "UPDATE steps SET ts=? WHERE action=? AND detail LIKE ?",
            (f"{day} 12:00:00Z", spend.KNOWN_COST_JOURNAL_ACTION,
             f"%{attempt_label(attempt)}%"))
        self.conn.commit()

    def details(self, action: str) -> list:
        return [row["detail"] for row in store.task_steps(self.conn, self.TASK)
                if row["action"] == action]
