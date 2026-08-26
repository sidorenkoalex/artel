"""Стоимость шага: разбор чисел, событие потока, учёт в spent_usd."""
import json
import math

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


def step_tokens(usage) -> int | None:
    """Сумма счётчиков usage; None, если нет ни одного — токены необязательны."""
    if not isinstance(usage, dict):
        return None
    counts = [usage[k] for k in config.USAGE_TOKEN_KEYS
              if isinstance(usage.get(k), int) and not isinstance(usage[k], bool)]
    return sum(counts) if counts else None


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
    return {"usd": usd, "tokens": step_tokens(event.get("usage"))}


def stream_usage_tokens(raw_line: str) -> int | None:
    """Токены usage ЛЮБОГО события потока, не только финального `result`.

    `parse_cost_event` намеренно смотрит только `type: result` — это
    единственное событие, где CLI считает доллары. Здесь другая задача
    (tasks/T040): собрать хоть что-то, если финальное событие вообще не
    придёт (таймаут, обрыв stdout-пайпа). `type: assistant` несёт usage
    в `message.usage` — тем же набором счётчиков, что и результат,
    поэтому разбор счётчиков не дублируется, берётся готовый
    `step_tokens`. Курса токена в доллары нет нигде в кодовой базе —
    отсюда и функция отдаёт только токены, не сумму в $.
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
    return step_tokens(usage)


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
    return f", {cost_note(cost)}"


def charge_missing_result(conn, task_id: str, role: str, numbered: str,
                          cause: str, partial_tokens: int,
                          saw_usage_event: bool) -> str:
    """Учёт попытки без финального события потока (таймаут/обрыв пайпа).

    Вызывается вместо `charge_step`, когда `pump.cost is None` ИМЕННО
    из-за таймаута шага или обрыва stdout-пайпа (tasks/T040) — обычный
    «тихий» путь `charge_step` (cost=None без этих причин) не трогается.

    Восстановить точную сумму в долларах нечем: её считает сам CLI
    только в финальном событии, курс токена в доллары нигде в кодовой
    базе не задан (SPEC T040 — «не входит»: не изобретать прайс-лист).
    Поэтому `store.charge` здесь не зовётся ни в одной из веток —
    записывать в `spent_usd` непроверенную сумму хуже, чем честно
    показать пробел (SPEC T040, требование 1).

    `saw_usage_event=True` — до обрыва в потоке были usage-события
    (`stream_usage_tokens`): в журнал идёт частичная сумма ТОКЕНОВ с
    пометкой «частичная», алерт не заводится (AC-1/2 — «либо…либо»).
    `saw_usage_event=False` — восстановить нечего вовсе: в журнал идёт
    «стоимость шага неизвестна», и открывается алерт `alerts`
    (`kind=incident`, `source=spend.unknown_cost`) — требование 3.
    """
    if saw_usage_event:
        detail = (f"{numbered}: {cause}, финальное событие потока "
                  f"отсутствует — частичная сумма из промежуточных "
                  f"usage-событий: {partial_tokens} токенов (курс в "
                  f"доллары не задан) — spent_usd не изменён")
        store.journal(conn, task_id, role, "agent cost PARTIAL", detail)
        return f", частичная: {partial_tokens} токенов"

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
