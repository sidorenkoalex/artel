"""Стоимость шага: разбор чисел, событие потока, учёт в spent_usd."""
import json
import math
import re
from pathlib import Path

from . import alerts, config, models, store


def json_number(value) -> float | None:
    """Число из JSON или None. bool — не число: `True` не стоит доллар."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def cli_number(raw: str) -> float | None:
    """Число из аргумента CLI; запятая как разделитель тоже считается."""
    try:
        value = float(raw.replace(",", ".").strip())
    except (AttributeError, ValueError):
        return None
    # float() принимает 'nan' и 'inf' — потолком ни то, ни другое не работает.
    return value if math.isfinite(value) else None


def usage_tokens_by_type(usage) -> dict | None:
    """Разбивка usage-события по видам (`config.USAGE_TOKEN_KEYS`); `None`
    — нет ни одного известного счётчика. Только счётчики, реально
    присутствующие в событии (не дополняется нулями за отсутствующие) —
    вызывающий код (`partial_cost_usd`) сам решает, что делать с
    видом, которого в конкретном событии не было (SPEC
    01M1PP0VYRT55WN8GGVG66X89Y, требование 2)."""
    if not isinstance(usage, dict):
        return None
    counts = {k: usage[k] for k in config.USAGE_TOKEN_KEYS
              if isinstance(usage.get(k), int) and not isinstance(usage[k], bool)}
    return counts or None


def step_tokens(usage) -> int | None:
    """Сумма счётчиков usage; None, если нет ни одного — токены необязательны."""
    by_type = usage_tokens_by_type(usage)
    return sum(by_type.values()) if by_type is not None else None


def parse_cost_event(raw_line: str) -> dict | None:
    """Стоимость запуска из финального события потока, иначе None.

    Поток `--output-format stream-json` заканчивается событием
    `type: result` с итоговой стоимостью запуска и usage. В файл лога оно
    не попадает (`render_agent_line` гасит служебные события), поэтому
    стоимость снимается прямо с потока перекачкой.

    Всё, что не разобралось — чужой формат, поле не число, отрицательная
    цена, — это None: по SPEC неизвлечённая стоимость не проваливает шаг.
    """
    if not raw_line.lstrip().startswith("{"):
        return None
    try:
        event = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict) or event.get("type") != "result":
        return None
    usd = json_number(event.get("total_cost_usd"))
    if usd is None or usd < 0:
        return None
    tokens_by_type = usage_tokens_by_type(event.get("usage"))
    tokens = sum(tokens_by_type.values()) if tokens_by_type is not None else None
    return {"usd": usd, "tokens": tokens, "tokens_by_type": tokens_by_type}


def stream_usage_by_type(raw_line: str) -> dict | None:
    """Разбивка usage ЛЮБОГО события потока, не только финального `result`.

    `parse_cost_event` намеренно смотрит только `type: result` — это
    единственное событие, где CLI считает доллары. Здесь другая задача
    (tasks/T040, уточнённая 01M1PP0VYRT55WN8GGVG66X89Y требованием 2):
    собрать хоть что-то по ВИДАМ токена, если финальное событие вообще не
    придёт (таймаут, обрыв stdout-пайпа) — раньше (`stream_usage_tokens`)
    счётчики сразу суммировались в одно число, и эта сумма тарифицировалась
    средней ставкой входа/выхода, что и завышало частичную стоимость шага,
    состоящего в основном из дешёвых чтений кэша (SPEC «Контекст»).
    `type: assistant` несёт usage в `message.usage` — тем же набором
    счётчиков, что и результат, поэтому разбор не дублируется, берётся
    готовый `usage_tokens_by_type`.
    """
    if not raw_line.lstrip().startswith("{"):
        return None
    try:
        event = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None
    kind = event.get("type")
    if kind == "result":
        usage = event.get("usage")
    elif kind == "assistant":
        message = event.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
    else:
        return None
    return usage_tokens_by_type(usage)


def partial_tokens_from_log(path: Path) -> tuple[dict, bool]:
    """(разбивка по видам, видели_ли_usage) из УЖЕ ЗАПИСАННОГО на диск лога
    шага.

    Тот же разбор, что `OutputPump.catch_cost` делает по ходу потока
    (T040): каждая строка — через `stream_usage_by_type`, найденные
    счётчики складываются по видам (не одной суммой — SPEC
    01M1PP0VYRT55WN8GGVG66X89Y, требование 2). Здесь — постфактум по
    файлу, а не по живому потоку (SPEC T074, требование 4): `pause --now`
    живёт в ДРУГОМ процессе, чем прерванный шаг, — памяти его
    `OutputPump` уже нет, есть только то, что успело лечь в лог-файл на
    диск.

    Лог не прочитан (отсутствует прогон, ФС не ответила) — `({}, False)`,
    та же деградация без данных, что у отсутствия usage-событий в потоке.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}, False
    totals: dict = {}
    saw = False
    for line in text.splitlines():
        found = stream_usage_by_type(line)
        if found is not None:
            saw = True
            for key, count in found.items():
                totals[key] = totals.get(key, 0) + count
    return totals, saw


def cost_note(cost: dict | None) -> str:
    """Стоимость шага для журнала и консоли; пустая строка — не извлеклась."""
    if cost is None:
        return ""
    note = f"стоимость ${cost['usd']:.4f}"
    return f"{note}, токенов {cost['tokens']}" if cost["tokens"] is not None else note


def charge_step(conn, task_id: str, role: str, cost: dict | None,
                numbered: str) -> str:
    """Прибавляет стоимость попытки к `spent_usd`; возвращает её для журнала.

    Стоимость не извлеклась — шаг не проваливаем (так решил SPEC): warning в
    журнал, `spent_usd` не трогаем, дальше всё как раньше. Цена сбоя формата
    события — потерянная метрика, а не остановленный конвейер.
    """
    if cost is None:
        store.journal(conn, task_id, role, "agent cost UNKNOWN",
                      f"{numbered}: в выводе нет события со стоимостью — "
                      f"spent_usd не изменён")
        return ""
    store.charge(conn, task_id, cost["usd"])
    tokens_by_type = cost.get("tokens_by_type")
    if tokens_by_type:
        # Источник данных калибровки (SPEC 01M1PP0VYRT55WN8GGVG66X89Y,
        # требования 4/6, AC-6/AC-8): завершённый шаг с известной
        # фактической ценой (`cost["usd"]`, из `total_cost_usd` потока) и
        # разбивкой usage — `report.token_rate_divergence` читает эту
        # запись, чтобы сравнить расчётную цену с фактической. Отдельное
        # действие журнала, не замена существующего `cost_note` в «agent
        # run finished» — требование 6 (дополняет, не заменяет).
        #
        # Сверка тарифа с фактом считается ДО записи строки и попадает в
        # неё же (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 3, AC-4):
        # свежий шаг обязан входить в собственный коэффициент, а править
        # уже вставленную строку журнала нечем — `store` эта задача
        # держит на чтении.
        #
        # Модель шага читается из `numbered` (`model=`, пишет
        # `runner._numbered_with_model`), а не разрешается по роли
        # заново: строка обязана считаться по той модели, которую сама
        # называет, иначе запись и её последующий разбор разошлись бы.
        model_id = journal_model(numbered)
        effective = model_tariff(model_id)
        record_tariff(conn, effective)
        divergence_note = _divergence_note(conn, role, effective, cost["usd"],
                                           tokens_by_type)
        detail = (f"{numbered}: {cost_note(cost)}, источник=факт CLI, "
                 f"разбивка по видам: "
                 f"{_tokens_by_type_text(tokens_by_type)} | "
                 f"actual_usd={cost['usd']!r}"
                 f"{_tariff_note(effective)}{divergence_note}")
        store.journal(conn, task_id, role, KNOWN_COST_JOURNAL_ACTION, detail)
    return f", {cost_note(cost)}"


def _tariff_note(effective) -> str:
    """Хвост строки KNOWN/PARTIAL: дата действующего тарифа модели шага
    (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 7, AC-9). Пустая строка
    — тариф не разрешился.

    Дата стоит в строке САМА, а не только внутри коэффициента сверки:
    коэффициента может не быть вовсе (первый шаг модели, сверять не с
    чем), а вопрос «по какой цене посчитан этот шаг» читатель журнала
    задаёт всегда — RETRO и отчёт считают по тарифу, действовавшему на
    момент шага.
    """
    if effective is None:
        return ""
    return f" | тариф модели с {effective.calibrated_at}"


def _divergence_note(conn, role: str, effective, actual_usd: float,
                     tokens_by_type: dict) -> str:
    """Хвост строки KNOWN: расчёт по тарифу модели и коэффициент его
    расхождения с фактом CLI (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH,
    требования 3-4). Пустая строка — сверять нечем.

    В сверку идут прежние строки KNOWN этой ПАРЫ (роль, модель) с даты
    действующего тарифа модели (`known_cost_pairs`) ПЛЮС пара текущего
    шага: коэффициент в строке отвечает на вопрос «как тариф расходится
    с фактом на этот момент», включая сам записываемый шаг.

    Тариф не разрешился — тихий пропуск: учёт шага важнее сверки и не
    имеет права упасть вместе с ней (тот же урок, что R1-F1 у
    `charge_missing_result` ниже; SPEC 01M300A14KRHCFB0DQXVCBJEKF,
    требование 9).
    """
    if effective is None:
        return ""
    calculated = tariff_cost_usd(effective.tariff, tokens_by_type)
    pairs = known_cost_pairs(conn, role, effective.model).get(
        (role, effective.model), [])
    pairs.append((calculated, actual_usd))
    divergence = check_rate_divergence(conn, effective.model, pairs)
    if divergence is None:
        return ""
    return (f" | расчёт по тарифу=${calculated:.4f}, "
            f"коэффициент пары с {divergence.since}={divergence:.2f}")


# Счётчик usage (`config.USAGE_TOKEN_KEYS`) -> вид цены тарифа модели
# (`models.PRICE_KINDS`), которым он тарифицируется (SPEC
# 01M300A14KRHCFB0DQXVCBJEKF, требование 1). Отображение записано
# поимённо, а не порядком двух кортежей: имена счётчиков потока CLI и
# имена видов цены каталога живут в разных файлах и по разным поводам —
# сдвиг любого из них на одну позицию тарифицировал бы 2 млн чтений кэша
# по цене выхода и не покраснел бы ни на одном сравнении форм.
_PRICE_KIND_FOR_USAGE_KEY = {
    "input_tokens": "input",
    "output_tokens": "output",
    "cache_creation_input_tokens": "cache_write",
    "cache_read_input_tokens": "cache_read",
}

#: Цены тарифа заданы за МИЛЛИОН токенов (`models.PRICE_KINDS`,
#: `list_price_usd_per_mtok`), а разбивка usage — в штуках.
TOKENS_PER_PRICE_UNIT = 1_000_000

#: `model=` строки журнала «agent cost KNOWN/PARTIAL» (пишет
#: `runner._numbered_with_model`). Значение — либо идентификатор модели,
#: либо метка «дефолт CLI» с пробелом: до конца поля читается один токен
#: без пробелов и запятых, а идентификатор ли это — решает каталог.
#:
#: Хвостовое двоеточие поля НЕ входит в значение: `model=` стоит последним
#: в `numbered`, а `charge_step` приписывает к нему `": "` — без этого
#: отсечения моделью считалось бы `claude-opus-5:`, которой в каталоге
#: нет. Двоеточие отсекается только перед пробелом/запятой/концом строки:
#: идентификатор модели у другого провайдера сам может нести двоеточия
#: (arn Bedrock), и рубить по первому из них нельзя.
_MODEL_FIELD_RE = re.compile(r"model=([^\s,]+?):?(?=[\s,]|$)")


def journal_model(detail: str) -> str | None:
    """Идентификатор модели из поля `model=` строки журнала; `None` —
    поля нет (строка старого формата до 19.09) либо его значение — не
    один токен (метка «дефолт CLI»).

    Сверку значения с каталогом функция НЕ делает: «это вообще похоже на
    поле» и «такая модель у пульта есть» — разные вопросы, и второй
    отвечает `model_tariff` ниже, отдавая `None` на неизвестной модели.
    """
    match = _MODEL_FIELD_RE.search(detail or "")
    return match.group(1) if match else None


def role_tariff(role: str) -> models.EffectiveTariff | None:
    """Действующий тариф модели РОЛИ (цепочка «роль -> ярус -> модель»);
    `None` — цепочка не разрешилась.

    Деградация вместо исключения — требование 9 SPEC
    01M300A14KRHCFB0DQXVCBJEKF: учёт шага важнее цены и не имеет права
    упасть вместе с ней. Роль без яруса (`verifier`, `executor: none`),
    нечитаемый локальный слой, модель вне каталога — всё это здесь
    «тарифа нет», ровно как раньше «курса роли нет»; называет причину
    поимённо `doctor` (строки `models-catalog`/`models-local`), а не
    стоимость шага.
    """
    try:
        resolved = models.resolve_role(role)
    except models.ModelsError:
        return None
    return models.EffectiveTariff(resolved.model, resolved.tariff,
                                  resolved.tariff_source,
                                  resolved.calibrated_at, resolved.source)


def model_tariff(model_id: str, catalog=None, local=None):
    """Действующий тариф МОДЕЛИ по идентификатору; `None` — модели нет в
    каталоге или слои не читаются (та же деградация, что `role_tariff`).

    `catalog`/`local` передаются вызывающим, который разрешает тариф в
    цикле по строкам журнала (`known_cost_pairs`): без них каждая строка
    перечитывала бы оба файла слоёв.
    """
    if not model_id:
        return None
    try:
        return models.resolve_model(model_id, catalog, local)
    except models.ModelsError:
        return None


def tariff_cost_usd(tariff, tokens_by_type: dict) -> float:
    """Стоимость разбивки usage по четырём ценам тарифа: каждый вид
    токенов — своей ценой (SPEC 01M1PP0VYRT55WN8GGVG66X89Y, требование 2),
    не средней ставкой на общую сумму токенов: чтения кэша почти всегда —
    большинство объёма шага и стоят на порядок дешевле входа, усреднение
    завышало частичную стоимость таймаута в ~20 раз (инцидент 04.09)."""
    return sum(tokens_by_type.get(usage_key, 0) * getattr(tariff, kind)
               / TOKENS_PER_PRICE_UNIT
               for usage_key, kind in _PRICE_KIND_FOR_USAGE_KEY.items())


def record_tariff(conn, effective) -> bool:
    """История тарифов: строка в `model_tariffs`, если действующий тариф
    модели отличается от последней её записи (SPEC
    01M300A14KRHCFB0DQXVCBJEKF, требование 6). `True` — строка добавлена.

    Зовётся в точке учёта шага — единственной, где есть и соединение с
    БД, и уже разрешённый тариф. Команды записи в таблицу нет: руками
    история не правится, её пишет только пульт, разрешая тариф.
    """
    if effective is None:
        return False
    return store.record_model_tariff(conn, effective.model,
                                     tuple(effective.tariff),
                                     effective.calibrated_at,
                                     effective.source)


def _tokens_by_type_text(tokens_by_type: dict) -> str:
    """Разбивка по видам как строка журнала — общий формат для «agent
    cost KNOWN» (`charge_step`) и «agent cost PARTIAL»
    (`charge_missing_result`), читаемый обратно `report.
    token_rate_divergence`."""
    return ", ".join(f"{key}={tokens_by_type.get(key, 0)}"
                     for key in config.USAGE_TOKEN_KEYS)


def partial_cost_usd(role: str, tokens_by_type: dict) -> float | None:
    """Стоимость разбивки usage по действующему тарифу МОДЕЛИ роли, или
    `None` — тариф не разрешился (SPEC 01M300A14KRHCFB0DQXVCBJEKF,
    требования 1-2, AC-2).

    Принимает роль, а не модель: вызывающие (`charge_missing_result`,
    `runner._cost_partial_expected`) знают роль ШАГА, а модель у неё —
    результат разрешения цепочки, а не их знание. Две роли одного яруса
    считают одну и ту же разбивку одинаково, смена модели яруса меняет
    сумму — ровно то, чего не умел курс по роли.

    Неполный прейскурант больше не даёт здесь `ValueError`: набор из
    четырёх цен обязателен на разборе каталога и локального слоя
    (`models._prices`, `IncompletePriceError`) — отказ стал строже и
    переехал раньше по течению, к чтению файла, а сюда неполный тариф
    попасть уже не может.
    """
    effective = role_tariff(role)
    if effective is None:
        return None
    return tariff_cost_usd(effective.tariff, tokens_by_type)


# --- сверка тарифа модели с фактом CLI (01M2ZNJX2N5SPZCAQE6EHD4EWH, 3-7;
#     пара «роль, модель» — 01M300A14KRHCFB0DQXVCBJEKF, требование 2)
#
# Формат строки «agent cost KNOWN» пишет `charge_step` выше — разбор
# ниже его обратная операция. Оба живут в одном модуле с того момента,
# как точек чтения стало две (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH,
# требование 6): сверка при записи шага (`_divergence_note`) и отчёт
# (`report.token_rate_divergence`, зовёт эти же функции). До этого
# разбор стоял в `report.py` рядом с единственным читателем.
KNOWN_COST_JOURNAL_ACTION = "agent cost KNOWN"

_ACTUAL_USD_RE = re.compile(r"actual_usd=([0-9eE.+-]+)")
_TOKEN_FIELD_RE = {key: re.compile(rf"(?<![a-z_]){re.escape(key)}=(\d+)")
                   for key in config.USAGE_TOKEN_KEYS}


def known_cost_breakdown(detail: str) -> tuple:
    """(фактическая_цена, разбивка_по_видам) из детали «agent cost
    KNOWN», либо `(None, None)` — запись не несёт того, что нужно
    (старый формат, повреждённая строка)."""
    usd_match = _ACTUAL_USD_RE.search(detail or "")
    if usd_match is None:
        return None, None
    try:
        actual_usd = float(usd_match.group(1))
    except ValueError:
        return None, None
    tokens_by_type = {}
    for key, pattern in _TOKEN_FIELD_RE.items():
        m = pattern.search(detail)
        if m is not None:
            tokens_by_type[key] = int(m.group(1))
    return actual_usd, tokens_by_type


def rate_calibrated_at(role: str) -> str | None:
    """Дата действующего тарифа модели роли, с которой идёт сверка:
    `calibrated_at` переопределения локального слоя, иначе `price_date`
    каталога (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 1, AC-3);
    `None` — тариф не разрешился."""
    effective = role_tariff(role)
    return effective.calibrated_at if effective is not None else None


def _within_tariff_period(since: str | None, ts) -> bool:
    """Записан ли шаг не раньше даты действующего тарифа его модели.

    `store.now()` пишет `YYYY-MM-DD HH:MM:SSZ`, дата тарифа —
    `YYYY-MM-DD`: сравнение префикса лексикографически и есть сравнение
    дат, разбирать их нечем. Строки старше даты — шаги, посчитанные по
    ДРУГОЙ цене той же модели (SPEC 01M300A14KRHCFB0DQXVCBJEKF,
    требование 2), в коэффициент пары не входят. Тариф без даты либо
    строка без `ts` — тоже мимо: отнести такой шаг к периоду тарифа
    нечем, а молча смешать две цены — ровно тот дефект, который линия и
    закрывает.
    """
    if not since or not ts:
        return False
    return str(ts)[:len(since)] >= since


def known_cost_pairs(conn, role: str | None = None,
                     model_id: str | None = None) -> dict:
    """{(роль, модель): [(расчёт по тарифу, факт CLI), …]} по строкам
    журнала `KNOWN_COST_JOURNAL_ACTION`; `role`/`model_id` — сузить
    чтение до одной пары (путь записи шага).

    Ключ — ПАРА (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 2, AC-4):
    модель берётся из поля `model=` самой строки, а не из сегодняшней
    цепочки роли — шаг, прошедший на прежней модели, обязан считаться по
    её цене, а не по цене нынешней. Строка входит в пару, только если
    записана не раньше даты действующего тарифа ЭТОЙ модели.

    Журнал читается существующими функциями `store` (`all_tasks` +
    `task_steps`), тем же приёмом, что `report._all_steps`: функции «весь
    журнал одним запросом» в `store` нет. Слои моделей читаются ОДИН раз
    на вызов (`models.layers_or_none`), а тариф каждой встреченной модели
    — один раз и кладётся в `tariffs`: иначе длинный журнал упёрся бы в
    файловый ввод-вывод на каждой строке.

    Строка, которую нечем сверить, пропускается молча: старый формат без
    `actual_usd`, строка без опознаваемой модели (требование 3, AC-5),
    модель вне каталога, нечитаемые слои. Сверка не обязана падать из-за
    неполноты конфигурации — назвать её поимённо дело `doctor`.
    """
    catalog, local = models.layers_or_none()
    tariffs: dict = {}
    pairs: dict = {}
    for task in store.all_tasks(conn):
        for row in store.task_steps(conn, task["id"]):
            if row["action"] != KNOWN_COST_JOURNAL_ACTION:
                continue
            actor = row["actor"]
            if role is not None and actor != role:
                continue
            step_model = journal_model(row["detail"])
            if step_model is None or (model_id is not None
                                      and step_model != model_id):
                continue
            if step_model not in tariffs:
                tariffs[step_model] = model_tariff(step_model, catalog, local)
            effective = tariffs[step_model]
            if effective is None:
                continue
            if not _within_tariff_period(effective.calibrated_at, row["ts"]):
                continue
            actual_usd, tokens_by_type = known_cost_breakdown(row["detail"])
            if actual_usd is None or not tokens_by_type:
                continue
            pairs.setdefault((actor, step_model), []).append(
                (tariff_cost_usd(effective.tariff, tokens_by_type), actual_usd))
    return pairs


class RateDivergence(float):
    """Коэффициент расхождения тарифа модели с фактом CLI — число,
    которое помнит, по какой выборке оно посчитано: `steps` (сколько
    шагов в неё вошло) и `since` (дата тарифа, с которой идёт сверка).

    Именно число, а не словарь или кортеж: возврат
    `report.token_rate_divergence` — `{модель: коэффициент}` — читается
    как число (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 4, AC-6).
    Дату и число шагов обязаны назвать строка журнала (SPEC
    01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 3) и строка отчёта
    (требование 7), поэтому они едут рядом с коэффициентом — считать их
    второй раз у каждого читателя значило бы развести две математики.
    """

    __slots__ = ("steps", "since")

    def __new__(cls, coefficient: float, steps: int, since: str):
        value = super().__new__(cls, coefficient)
        value.steps = steps
        value.since = since
        return value


def check_rate_divergence(conn, model_id: str,
                          pairs: list) -> RateDivergence | None:
    """Коэффициент расхождения тарифа МОДЕЛИ с фактом CLI по парам
    «расчёт, факт» — и алерт, если он выше порога. `None` — сверять
    нечего либо тариф модели не разрешился.

    ЕДИНСТВЕННОЕ место, где живёт математика «сумма расчёта против суммы
    фактов» (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 6, AC-8): её
    зовут обе точки — запись шага (`_divergence_note`) и отчёт
    (`report.token_rate_divergence`). Суммарное расхождение по шагам, не
    среднее по шагам: несколько маленьких шагов не должны топить один
    крупный расходящийся.

    Адресат алерта — модель, а не роль (SPEC
    01M300A14KRHCFB0DQXVCBJEKF, требование 1): разошлась ЦЕНА, а она у
    модели одна на все роли яруса, и три роли на одной модели обязаны
    дать один устойчивый сигнал, а не три копии. Сам алерт прежний —
    `kind=warning`, `target=None` (расхождение считается поперёк всех
    задач и target'ов) через `alerts.raise_token_rate_divergence_alert`,
    не `alerts.raise_alert`: сообщение несёт растущие суммы, дедуп по
    точному тексту не сработал бы на повторных шагах (REVIEW.md
    01M1PP0VYRT55WN8GGVG66X89Y итерации 1, R1-F2) — дедуп идёт по
    префиксу сообщения, поэтому текст начинается с идентификатора модели.

    Возврат — `RateDivergence`: сам коэффициент числом (форма возврата
    `report.token_rate_divergence` этим и сохранена), а дата и число
    вошедших шагов — его атрибутами, потому что строка журнала и строка
    отчёта обязаны их назвать (требования 3, 7).
    """
    effective = model_tariff(model_id)
    if effective is None or not pairs:
        return None
    since = effective.calibrated_at
    actual_sum = sum(actual for _, actual in pairs)
    if actual_sum == 0:
        return None
    calculated_sum = sum(calculated for calculated, _ in pairs)
    coefficient = abs(calculated_sum - actual_sum) / actual_sum
    if coefficient > config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD:
        alerts.raise_token_rate_divergence_alert(
            conn, model_id,
            f"{model_id}: коэффициент расхождения тарифа модели "
            f"{coefficient:.2f} выше порога "
            f"{config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD} — расчётная "
            f"цена ${calculated_sum:.4f} против фактической "
            f"${actual_sum:.4f} по {len(pairs)} шагам с {since}")
    return RateDivergence(coefficient, len(pairs), since)


def charge_missing_result(conn, task_id: str, role: str, numbered: str,
                          cause: str, partial_tokens: dict,
                          saw_usage_event: bool) -> str:
    """Учёт попытки без финального события потока (таймаут/обрыв пайпа).

    Вызывается вместо `charge_step`, когда `pump.cost is None` ИМЕННО
    из-за таймаута шага или обрыва stdout-пайпа (tasks/T040) — обычный
    «тихий» путь `charge_step` (cost=None без этих причин) не трогается.

    `partial_tokens` — разбивка усечённого usage по видам
    (`config.USAGE_TOKEN_KEYS`), не просуммированное число (SPEC
    01M1PP0VYRT55WN8GGVG66X89Y, требование 2): восстановить точную сумму
    в долларах, которую посчитал бы сам CLI в финальном событии, всё
    равно нечем, но раздельные счётчики позволяют тарифицировать каждый
    вид его собственной ценой, а не средней ставкой входа/выхода на всю
    сумму (`partial_cost_usd`, требование 2/4, AC-2/AC-3). Действующий
    тариф модели роли (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 1)
    переводит разбивку в доллары там, где цепочка роли разрешается;
    исходное решение T040 «курса нигде нет» осталось только для ролей,
    чей тариф не разрешился.

    `saw_usage_event=True` — до обрыва в потоке были usage-события:
    тариф модели разрешился — частичная сумма по нему прибавляется к
    `spent_usd` (требование 2, AC-2), алерт не заводится. Тариф НЕ
    разрешился — прибавить нечего, вместо этого заводится алерт
    `kind=threshold` и в `spent_estimate_usd` идёт именованная верхняя
    оценка `config.STEP_COST_ESTIMATE_USD` (требование 3, AC-3) — каждый
    повтор отказа прибавляет оценку заново, недоучёт не должен копиться
    молча только потому, что алерт уже открыт.
    `saw_usage_event=False` — восстановить нечего вовсе, ни точно, ни
    по тарифу, ни оценкой: в журнал идёт «стоимость шага неизвестна», и
    открывается алерт `alerts` (`kind=incident`,
    `source=spend.unknown_cost`) — требование 4, поведение T040 без
    изменений.

    Неразрешимый тариф здесь именно деградирует, а не обрушивает
    вызывающего (REVIEW.md 01M1NWCM3TDY0YABEKE8DYQA1C итерации 1, R1-F1;
    SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 9): этот путь зовётся
    ровно в момент обработки таймаута шага/`pause --now`, до коммита
    чекпоинта и записи журнала «agent run TIMEOUT» — необработанное
    исключение здесь потеряло бы и то, и другое.
    """
    if not saw_usage_event:
        detail = (f"{numbered}: {cause}, финальное событие потока "
                 f"отсутствует, промежуточных usage-событий тоже нет — "
                 f"стоимость шага неизвестна, spent_usd не изменён")
        store.journal(conn, task_id, role, "agent cost LOST", detail)
        target = store.task_target(conn, task_id)
        alerts.raise_alert(conn, target, "incident", "spend.unknown_cost",
                           f"{task_id}/{role}: {numbered}, {cause} — "
                           f"финальное событие потока отсутствует, "
                           f"стоимость шага не восстановлена")
        return ""

    total_tokens = sum(partial_tokens.values())
    effective = role_tariff(role)
    rate_reason = f"тариф модели роли {role!r} не разрешён"
    if effective is not None:
        record_tariff(conn, effective)
        usd = tariff_cost_usd(effective.tariff, partial_tokens)
        # `источник=расчёт по тарифу` (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH,
        # требование 2): читатель журнала обязан отличать эту сумму от
        # факта CLI строки KNOWN — недоучёт шага PARTIAL (SPEC
        # «Контекст») начинался с того, что обе выглядели одинаково.
        detail = (f"{numbered}: {cause}, финальное событие потока "
                 f"отсутствует — частичная стоимость по тарифу модели "
                 f"{effective.model}: ${usd:.4f}, источник=расчёт по тарифу, "
                 f"{total_tokens} токенов, "
                 f"разбивка по видам: {_tokens_by_type_text(partial_tokens)}"
                 f"{_tariff_note(effective)}")
        store.journal(conn, task_id, role, "agent cost PARTIAL", detail)
        store.charge(conn, task_id, usd)
        return (f", частичная стоимость по тарифу: ${usd:.4f}, "
                f"{total_tokens} токенов")

    estimate = config.STEP_COST_ESTIMATE_USD
    detail = (f"{numbered}: {cause}, финальное событие потока "
             f"отсутствует, {rate_reason} — верхняя "
             f"оценка стоимости шага: ${estimate:.4f}, {total_tokens} "
             f"токенов")
    store.journal(conn, task_id, role, "agent cost ESTIMATED", detail)
    store.charge_estimate(conn, task_id, estimate)
    target = store.task_target(conn, task_id)
    alerts.raise_alert(conn, target, "threshold", "spend.step_cost_unknown_rate",
                       f"{task_id}/{role}: {numbered}, {cause} — стоимость "
                       f"шага не учтена ({rate_reason}), "
                       f"{total_tokens} токенов")
    return f", верхняя оценка стоимости шага: ${estimate:.4f}"
