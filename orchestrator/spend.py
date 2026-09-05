"""Стоимость шага: разбор чисел, событие потока, учёт в spent_usd."""
import json
import math
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
        detail = (f"{numbered}: {cost_note(cost)}, разбивка по видам: "
                 f"{_tokens_by_type_text(tokens_by_type)} | "
                 f"actual_usd={cost['usd']!r}")
        store.journal(conn, task_id, role, "agent cost KNOWN", detail)
    return f", {cost_note(cost)}"


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
        detail = (f"{numbered}: {cause}, финальное событие потока "
                 f"отсутствует — частичная стоимость по курсу роли "
                 f"{role!r}: ${usd:.4f}, {total_tokens} токенов, "
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
