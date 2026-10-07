"""Relative full-suite duration signal, calibrated per target and worker count."""

import json
import statistics

from orchestrator import doctor


SOURCE = "suite.duration"


def _reference(conn, target: str) -> str | None:
    candidates = [row["ack_ts"] for row in doctor.store.alerts_older_than(
        conn, doctor._FAR_FUTURE_TS)
        if row["target"] == target and row["kind"] == "trigger"
        and row["source"] == SOURCE and row["ack_ts"] is not None]
    return max(candidates) if candidates else None


def _series(conn, target: str, rows: list, task_targets: dict) -> list[dict]:
    reference = _reference(conn, target)
    values = []
    for row in rows:
        if task_targets.get(row["task_id"]) != target:
            continue
        if reference is not None and row["ts"] <= reference:
            continue
        try:
            entry = json.loads(row["detail"])
        except (TypeError, ValueError):
            continue
        if entry.get("seconds_per_test") is not None:
            values.append(entry)
    if not values:
        return values
    workers = values[-1]["xdist_workers"]
    start = len(values) - 1
    while start and values[start - 1]["xdist_workers"] == workers:
        start -= 1
    return values[start:]


def check_suite_duration(conn) -> list[doctor.Check]:
    rows = doctor.store.steps_of_action(conn, doctor.acceptance.SUITE_DURATION_ACTION)
    task_targets = {task["id"]: task["target"]
                    for task in doctor.store.all_tasks(conn)}
    targets = sorted({task_targets[row["task_id"]] for row in rows
                      if row["task_id"] in task_targets})
    checks = []
    k = doctor.config.SUITE_DURATION_CALIBRATION_RUNS
    for target in targets:
        series = _series(conn, target, rows, task_targets)
        name = f"suite-duration:{target}"
        if len(series) <= k:
            checks.append(doctor.Check(name, "ok",
                                       f"калибровка: {len(series)}/{k} прогонов"))
            continue
        baseline = statistics.median(
            item["seconds_per_test"] for item in series[:k])
        last = series[-1]
        value = last["seconds_per_test"]
        if value <= baseline * (1 + doctor.config.SUITE_DURATION_RATIO):
            checks.append(doctor.Check(name, "ok", "время на тест в пределах нормы"))
            continue
        message = (f"время на тест {value:.4f} с выше медианы окна "
                   f"{baseline:.4f} с; {doctor.acceptance.suite_load_line(last)}")
        doctor.alerts.raise_alert(conn, target, "trigger", SOURCE, message)
        checks.append(doctor.Check(name, "warn", message))
    return checks
