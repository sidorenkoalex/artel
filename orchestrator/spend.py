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


def partial_tokens_from_log(path: Path) -> tuple[int, bool]:
    """(токены, видели_ли_usage) из УЖЕ ЗАПИСАННОГО на диск лога шага.

    Тот же разбор, что `OutputPump.catch_cost` делает по ходу потока
    (T040): каждая строка — через `stream_usage_tokens`, найденные счётчики
    суммируются. Здесь — постфактум по файлу, а не по живому потоку
    (SPEC T074, требование 4): `pause --now` живёт в ДРУГОМ процессе, чем
    прерванный шаг, — памяти его `OutputPump` уже нет, есть только то, что
    успело лечь в лог-файл на диск.

    Лог не прочитан (отсутствует прогон, ФС не ответила) — `(0, False)`,
    та же деградация без данных, что у отсутствия usage-событий в потоке.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0, False
    tokens = 0
    saw = False
    for line in text.splitlines():
        found = stream_usage_tokens(line)
        if found is not None:
            saw = True
            tokens += found
    return tokens, saw


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


def partial_cost_usd(role: str, partial_tokens: int) -> float | None:
    """Частичная стоимость `partial_tokens` токенов по курсу роли, или
    `None` — курс для роли не задан (`config.TOKEN_RATES`).

    `partial_tokens` — уже просуммированное число без разбивки на
    входные/выходные (`step_tokens`/`stream_usage_tokens`): курс несёт
    раздельную цену входного и выходного токена, но точной разбивки для
    частичного потока нет — эффективная ставка берётся средним цены
    входного и выходного токена роли (SPEC требование 2 не фиксирует
    точную формулу пересчёта, только то, что сумма должна быть
    ненулевой при известном курсе).
    """
    rate = config.TOKEN_RATES.get(role)
    if rate is None:
        return None
    effective = (rate["input_usd_per_token"] + rate["output_usd_per_token"]) / 2
    return partial_tokens * effective


def charge_missing_result(conn, task_id: str, role: str, numbered: str,
                          cause: str, partial_tokens: int,
                          saw_usage_event: bool) -> str:
    """Учёт попытки без финального события потока (таймаут/обрыв пайпа).

    Вызывается вместо `charge_step`, когда `pump.cost is None` ИМЕННО
    из-за таймаута шага или обрыва stdout-пайпа (tasks/T040) — обычный
    «тихий» путь `charge_step` (cost=None без этих причин) не трогается.

    Восстановить точную сумму в долларах, которую посчитал бы сам CLI в
    финальном событии, всё равно нечем — есть только сумма токенов
    промежуточных usage-событий. Курс роли (`config.TOKEN_RATES`, SPEC
    01M1NWCM3TDY0YABEKE8DYQA1C, требование 1) переводит эту сумму в
    доллары там, где он задан; исходное решение T040 «курса нигде нет»
    осталось только для ролей БЕЗ записи в таблице.

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

    usd = partial_cost_usd(role, partial_tokens)
    if usd is not None:
        detail = (f"{numbered}: {cause}, финальное событие потока "
                 f"отсутствует — частичная стоимость по курсу роли "
                 f"{role!r}: ${usd:.4f}, {partial_tokens} токенов")
        store.journal(conn, task_id, role, "agent cost PARTIAL", detail)
        store.charge(conn, task_id, usd)
        return f", частичная стоимость по курсу: ${usd:.4f}, {partial_tokens} токенов"

    estimate = config.STEP_COST_ESTIMATE_USD
    detail = (f"{numbered}: {cause}, финальное событие потока "
             f"отсутствует, курс роли {role!r} не задан — верхняя "
             f"оценка стоимости шага: ${estimate:.4f}, {partial_tokens} "
             f"токенов")
    store.journal(conn, task_id, role, "agent cost ESTIMATED", detail)
    store.charge_estimate(conn, task_id, estimate)
    target = store.task_target(conn, task_id)
    alerts.raise_alert(conn, target, "threshold", "spend.step_cost_unknown_rate",
                       f"{task_id}/{role}: {numbered}, {cause} — стоимость "
                       f"шага не учтена (курс роли не задан), "
                       f"{partial_tokens} токенов")
    return f", верхняя оценка стоимости шага: ${estimate:.4f}"
