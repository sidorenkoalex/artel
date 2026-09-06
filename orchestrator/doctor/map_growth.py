"""Пакет orchestrator/doctor -- наблюдатель роста карты кодовой базы.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import json
import statistics

from orchestrator import doctor


# --- наблюдатель роста карты кодовой базы (01M1RFVWV6WWTXRC5F40K61632,
#     требование 3) -------------------------------------------------------

MAP_SIZE_ACTION = "карта: размер"
MAP_GROWTH_SOURCE = "map.growth"

# Sentinel заведомо позже любого реального `ts`/`ack_ts` (формат
# store.now(), лексикографическое сравнение) — использован как cutoff
# `store.alerts_older_than`, чтобы получить ВСЕ алерты существующей
# функцией store, без новой SQL здесь (ADR-0003 3ж): store.py вне зон
# этой задачи, фильтрация target/kind/source/ack_ts — в Python.
_FAR_FUTURE_TS = "9999-12-31 23:59:59Z"


def _all_map_size_steps(conn) -> list:
    """Все записи журнала «карта: размер» по всем задачам, в порядке
    появления (`id` — единый автоинкремент таблицы `steps`, поэтому
    сортировка по нему хронологична и через границы задач). Собрано из
    `store.all_tasks`/`store.task_steps` — существующих функций store,
    без прямой SQL здесь (ADR-0003 3ж)."""
    steps = []
    for task in doctor.store.all_tasks(conn):
        steps.extend(doctor.store.task_steps(conn, task["id"]))
    steps.sort(key=lambda row: row["id"])
    return [row for row in steps if row["action"] == doctor.MAP_SIZE_ACTION]


def _map_growth_reference_point(conn, target: str) -> str | None:
    """Момент последнего подтверждённого алерта `map.growth` этого
    target — `ack` переносит точку отсчёта и тем самым перекалибровывает
    базу (AC-10); подтверждённых алертов нет — начало ряда (`None`)."""
    candidates = [
        row["ack_ts"] for row in doctor.store.alerts_older_than(conn, doctor._FAR_FUTURE_TS)
        if row["target"] == target and row["kind"] == "trigger"
        and row["source"] == doctor.MAP_GROWTH_SOURCE and row["ack_ts"] is not None
    ]
    return max(candidates) if candidates else None


def _map_growth_series(conn, target: str) -> list:
    """Ряд `detail` (разобранных JSON) записей «карта: размер» этого
    target ПОСЛЕ точки отсчёта, в порядке появления."""
    reference = doctor._map_growth_reference_point(conn, target)
    rows = [row for row in doctor._all_map_size_steps(conn) if row["target"] == target]
    if reference is not None:
        rows = [row for row in rows if row["ts"] > reference]
    return [json.loads(row["detail"]) for row in rows]


def _map_growth_message(compare_from: dict, last: dict) -> str:
    """Текст алерта: каталог верхнего уровня с наибольшим приростом байт
    между сравниваемыми записями и три самые крупные секции текущей
    карты (AC-13) — без времени/id, детерминирован по данным ряда."""
    last_dirs = last["bytes_by_dir"]
    base_dirs = compare_from["bytes_by_dir"]
    grown_dir = max(last_dirs, key=lambda d: last_dirs[d] - base_dirs.get(d, 0))
    top3 = last["top_sections"][:3]
    sections_txt = ", ".join(
        f"{entry['name']} ({entry['bytes']} байт)" for entry in top3)
    return (f"рост карты кодовой базы: сильнее всего вырос каталог "
           f"{grown_dir}; крупнейшие секции карты — {sections_txt}")


def _map_growth_check(conn, target: str) -> doctor.Check:
    name = f"map-growth:{target}"
    series = doctor._map_growth_series(conn, target)
    k = doctor.config.MAP_GROWTH_CALIBRATION_MERGES
    if len(series) <= k:
        # Ровно на k-й записи окно калибровки (`series[:k]`) совпадает со
        # всем рядом — сравнивать эту запись с базой, посчитанной с её
        # же участием, самоссылочно (R1-F2); молчим ещё один ход, оценка
        # стартует с (k+1)-й записи против уже зафиксированного окна.
        return doctor.Check(name, "ok", f"калибровка: {len(series)}/{k} измерений")

    window = series[:k]
    baseline = statistics.median(entry["bytes_total"] for entry in window)
    last = series[-1]
    prev = series[-2] if len(series) >= 2 else None

    creep = last["bytes_total"] > baseline * (1 + doctor.config.MAP_GROWTH_RATIO)
    jump = (prev is not None and last["bytes_total"] >
           prev["bytes_total"] * (1 + doctor.config.MAP_JUMP_RATIO))
    if not (creep or jump):
        return doctor.Check(name, "ok", "рост в пределах нормы")

    compare_from = prev if prev is not None else window[0]
    message = doctor._map_growth_message(compare_from, last)
    doctor.alerts.raise_alert(conn, target, "trigger", doctor.MAP_GROWTH_SOURCE, message)
    return doctor.Check(name, "warn", message)


def check_map_growth(conn) -> list[doctor.Check]:
    """Требование 3: по каждому target с хотя бы одной записью «карта:
    размер» — самокалибрующийся относительный порог роста карты
    кодовой базы (AC-8..AC-16). Абсолютный потолок брифа эта проверка не
    читает и не меняет (AC-15) — только относительные сигналы (медиана
    окна калибровки, прирост между соседними записями).
    """
    targets_with_series = sorted({
        row["target"] for row in doctor._all_map_size_steps(conn)
        if row["target"] is not None
    })
    return [doctor._map_growth_check(conn, target) for target in targets_with_series]


