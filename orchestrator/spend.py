"""Стоимость шага: разбор чисел, событие потока, учёт в spent_usd."""
import json
import math
import re
from pathlib import Path

from . import alerts, config, store


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
        # Сверка курса с фактом считается ДО записи строки и попадает в
        # неё же (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 3, AC-4):
        # свежий шаг обязан входить в собственный коэффициент, а править
        # уже вставленную строку журнала нечем — `store` эта задача
        # держит на чтении.
        detail = (f"{numbered}: {cost_note(cost)}, источник=факт CLI, "
                 f"разбивка по видам: "
                 f"{_tokens_by_type_text(tokens_by_type)} | "
                 f"actual_usd={cost['usd']!r}"
                 f"{_divergence_note(conn, role, cost['usd'], tokens_by_type)}")
        store.journal(conn, task_id, role, KNOWN_COST_JOURNAL_ACTION, detail)
    return f", {cost_note(cost)}"


def _divergence_note(conn, role: str, actual_usd: float,
                     tokens_by_type: dict) -> str:
    """Хвост строки KNOWN: расчёт по курсу роли и коэффициент её
    расхождения с фактом CLI (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH,
    требования 3-4). Пустая строка — сверять нечем.

    В сверку идут прежние строки KNOWN этой роли с даты `calibrated_at`
    её курса (`known_cost_pairs`) ПЛЮС пара текущего шага: коэффициент в
    строке отвечает на вопрос «как курс роли расходится с фактом на этот
    момент», включая сам записываемый шаг.

    Курс роли не задан (`partial_cost_usd` вернула `None`) или неполон
    (`ValueError`, требование 3 SPEC 01M1PP0VYRT55WN8GGVG66X89Y) — тихий
    пропуск: учёт шага важнее сверки и не имеет права упасть вместе с
    ней (тот же урок, что R1-F1 у `charge_missing_result` ниже).
    """
    try:
        calculated = partial_cost_usd(role, tokens_by_type)
    except ValueError:
        return ""
    if calculated is None:
        return ""
    pairs = known_cost_pairs(conn, role).get(role, [])
    pairs.append((calculated, actual_usd))
    divergence = check_rate_divergence(conn, role, pairs)
    if divergence is None:
        return ""
    return (f" | расчёт по курсу=${calculated:.4f}, "
            f"коэффициент роли с {divergence['since']}="
            f"{divergence['coefficient']:.2f}")


# Счётчик usage (`config.USAGE_TOKEN_KEYS`) -> поле цены `TOKEN_RATES[role]`,
# которое его тарифицирует (SPEC 01M1PP0VYRT55WN8GGVG66X89Y, требование 1).
_RATE_FIELD_FOR_USAGE_KEY = {
    "input_tokens": "input_usd_per_token",
    "output_tokens": "output_usd_per_token",
    "cache_creation_input_tokens": "cache_creation_usd_per_token",
    "cache_read_input_tokens": "cache_read_usd_per_token",
}


def _tokens_by_type_text(tokens_by_type: dict) -> str:
    """Разбивка по видам как строка журнала — общий формат для «agent
    cost KNOWN» (`charge_step`) и «agent cost PARTIAL»
    (`charge_missing_result`), читаемый обратно `report.
    token_rate_divergence`."""
    return ", ".join(f"{key}={tokens_by_type.get(key, 0)}"
                     for key in config.USAGE_TOKEN_KEYS)


def partial_cost_usd(role: str, tokens_by_type: dict) -> float | None:
    """Частичная стоимость разбивки usage по курсу роли, или `None` — курс
    для роли не задан вовсе (`config.TOKEN_RATES`).

    Сумма произведений «количество токенов вида × цена этого вида по
    курсу роли» (SPEC 01M1PP0VYRT55WN8GGVG66X89Y, требование 2) — не
    средняя ставка на общую сумму токенов, как раньше: чтения кэша почти
    всегда — большинство объёма шага и стоят на порядок дешевле входа
    (`config.TOKEN_RATES`, докстрока калибровки), усреднение с ценой
    входа/выхода завышало частичную стоимость таймаута в ~20 раз
    (SPEC «Контекст», инцидент 04.09).

    Курс роли ЕСТЬ в таблице, но не несёт одной из четырёх цен
    (`config.USAGE_TOKEN_KEYS`) — `ValueError`, явный именованный отказ,
    а не тихий ноль/пропуск этого вида токена (требование 3, AC-5):
    неполный курс — ошибка конфигурации, её нельзя молча замять,
    занизив частичную стоимость.
    """
    rate = config.TOKEN_RATES.get(role)
    if rate is None:
        return None
    total = 0.0
    for key in config.USAGE_TOKEN_KEYS:
        rate_field = _RATE_FIELD_FOR_USAGE_KEY[key]
        if rate_field not in rate:
            raise ValueError(
                f"config.TOKEN_RATES[{role!r}] не несёт цены {rate_field!r} "
                f"(счётчик {key!r}) — курс роли неполон, частичная "
                f"стоимость не считается по неполному курсу молча")
        total += tokens_by_type.get(key, 0) * rate[rate_field]
    return total


# --- сверка курса роли с фактом CLI (01M2ZNJX2N5SPZCAQE6EHD4EWH, 3-7)
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
    """Дата калибровки курса роли (`config.TOKEN_RATES`), с которой идёт
    сверка; `None` — курса роли нет либо он не несёт даты."""
    rate = config.TOKEN_RATES.get(role)
    return rate.get("calibrated_at") if rate else None


def _within_rate_period(role: str, ts) -> bool:
    """Записан ли шаг не раньше даты калибровки курса роли.

    `store.now()` пишет `YYYY-MM-DD HH:MM:SSZ`, `calibrated_at` —
    `YYYY-MM-DD`: сравнение префикса лексикографически и есть сравнение
    дат, разбирать их нечем. Строки старше даты — шаги ДРУГОЙ модели
    (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 3), в сверку не входят.
    Курс без даты либо строка без `ts` — тоже мимо: отнести такой шаг к
    периоду курса нечем, а молча смешать две модели — ровно тот дефект,
    который задача и закрывает.
    """
    since = rate_calibrated_at(role)
    if since is None or not ts:
        return False
    return str(ts)[:len(since)] >= since


def known_cost_pairs(conn, role: str | None = None) -> dict:
    """{роль: [(расчёт по курсу, факт CLI), …]} по строкам журнала
    `KNOWN_COST_JOURNAL_ACTION` не старше даты калибровки курса роли;
    `role` — сузить чтение до одной роли (путь записи шага).

    Журнал читается существующими функциями `store` (`all_tasks` +
    `task_steps`), тем же приёмом, что `report._all_steps`: функции «весь
    журнал одним запросом» в `store` нет, а заводить её эта задача не
    вправе (SPEC «Не входит» — `store.py` только чтение).

    Строка, которую нечем сверить, пропускается молча: старый формат без
    `actual_usd`, роль без курса (`partial_cost_usd` — `None`), неполный
    курс (`ValueError`). Калибровка не обязана падать из-за неполноты
    конфигурации — это дело `partial_cost_usd` в её собственной точке
    вызова.
    """
    pairs: dict = {}
    for task in store.all_tasks(conn):
        for row in store.task_steps(conn, task["id"]):
            if row["action"] != KNOWN_COST_JOURNAL_ACTION:
                continue
            actor = row["actor"]
            if role is not None and actor != role:
                continue
            if not _within_rate_period(actor, row["ts"]):
                continue
            actual_usd, tokens_by_type = known_cost_breakdown(row["detail"])
            if actual_usd is None or not tokens_by_type:
                continue
            try:
                calculated_usd = partial_cost_usd(actor, tokens_by_type)
            except ValueError:
                continue
            if calculated_usd is None:
                continue
            pairs.setdefault(actor, []).append((calculated_usd, actual_usd))
    return pairs


def check_rate_divergence(conn, role: str, pairs: list) -> dict | None:
    """Коэффициент расхождения курса роли с фактом CLI по парам «расчёт,
    факт» — и алерт, если он выше порога. `None` — сверять нечего.

    ЕДИНСТВЕННОЕ место, где живёт математика «сумма расчёта против суммы
    фактов» (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 6, AC-8): её
    зовут обе точки — запись шага (`_divergence_note`) и отчёт
    (`report.token_rate_divergence`). Суммарное расхождение по шагам, не
    среднее по шагам: несколько маленьких шагов не должны топить один
    крупный расходящийся.

    Алерт — `kind=warning`, `target=None` (расхождение считается по роли
    поперёк всех задач и target'ов) через
    `alerts.raise_token_rate_divergence_alert`, не `alerts.raise_alert`:
    сообщение несёт растущие суммы, дедуп по точному тексту не сработал
    бы на повторных шагах (REVIEW.md 01M1PP0VYRT55WN8GGVG66X89Y итерации
    1, R1-F2). Заведение алерта живёт здесь, а не у вызывающих, по той же
    причине, что и сам расчёт: две копии условия разошлись бы.

    Возврат несёт дату и число вошедших шагов рядом с коэффициентом —
    строка журнала и строка отчёта обязаны их назвать (требования 3, 7),
    а считать их второй раз значило бы завести вторую математику.
    """
    since = rate_calibrated_at(role)
    if since is None or not pairs:
        return None
    actual_sum = sum(actual for _, actual in pairs)
    if actual_sum == 0:
        return None
    calculated_sum = sum(calculated for calculated, _ in pairs)
    coefficient = abs(calculated_sum - actual_sum) / actual_sum
    if coefficient > config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD:
        alerts.raise_token_rate_divergence_alert(
            conn, role,
            f"{role}: коэффициент расхождения курса токенов "
            f"{coefficient:.2f} выше порога "
            f"{config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD} — расчётная "
            f"цена ${calculated_sum:.4f} против фактической "
            f"${actual_sum:.4f} по {len(pairs)} шагам с {since}")
    return {"coefficient": coefficient, "steps": len(pairs), "since": since}


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
    сумму (`partial_cost_usd`, требование 2/4, AC-2/AC-3). Курс роли
    (`config.TOKEN_RATES`, SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, требование 1)
    переводит разбивку в доллары там, где он задан; исходное решение
    T040 «курса нигде нет» осталось только для ролей БЕЗ записи в
    таблице.

    `saw_usage_event=True` — до обрыва в потоке были usage-события:
    курс роли известен (`partial_cost_usd` не `None`) — частичная сумма
    по курсу прибавляется к `spent_usd` (требование 2, AC-2), алерт не
    заводится. Курс роли НЕ известен — прибавить нечего, вместо этого
    заводится алерт `kind=threshold` и в `spent_estimate_usd` идёт
    именованная верхняя оценка `config.STEP_COST_ESTIMATE_USD`
    (требование 3, AC-3) — каждый повтор отказа прибавляет оценку
    заново, недоучёт не должен копиться молча только потому, что алерт
    уже открыт.
    `saw_usage_event=False` — восстановить нечего вовсе, ни точно, ни
    по курсу, ни оценкой: в журнал идёт «стоимость шага неизвестна», и
    открывается алерт `alerts` (`kind=incident`,
    `source=spend.unknown_cost`) — требование 4, поведение T040 без
    изменений.

    Курс роли ЕСТЬ в таблице, но не несёт одной из четырёх цен —
    `partial_cost_usd` бросает `ValueError` (требование 3, AC-5); здесь
    это ловится и деградирует на ту же ветку «курс роли не задан» ниже
    (верхняя оценка + `threshold`-алерт), а не обрушивает вызывающего
    (REVIEW.md итерации 1, R1-F1): этот путь зовётся ровно в момент
    обработки таймаута шага/`pause --now`, до коммита чекпоинта и записи
    журнала «agent run TIMEOUT» — необработанное исключение здесь
    потеряло бы и то, и другое.
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
    try:
        usd = partial_cost_usd(role, partial_tokens)
    except ValueError as exc:
        usd = None
        rate_reason = f"курс роли {role!r} неполон ({exc})"
    else:
        rate_reason = f"курс роли {role!r} не задан"
    if usd is not None:
        # `источник=расчёт по тарифу` (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH,
        # требование 2): читатель журнала обязан отличать эту сумму от
        # факта CLI строки KNOWN — недоучёт шага PARTIAL (SPEC
        # «Контекст») начинался с того, что обе выглядели одинаково.
        detail = (f"{numbered}: {cause}, финальное событие потока "
                 f"отсутствует — частичная стоимость по курсу роли "
                 f"{role!r}: ${usd:.4f}, источник=расчёт по тарифу, "
                 f"{total_tokens} токенов, "
                 f"разбивка по видам: {_tokens_by_type_text(partial_tokens)}")
        store.journal(conn, task_id, role, "agent cost PARTIAL", detail)
        store.charge(conn, task_id, usd)
        return f", частичная стоимость по курсу: ${usd:.4f}, {total_tokens} токенов"

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
