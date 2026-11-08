"""Пакет orchestrator/doctor -- цена набора тестов против пределов CI и
локального прогона (ADR-0032 п. 6, SPEC 01M6Y44ZPXPQCNYDXQG6FMZPK5,
требование 7).

Две строки `suite-cost:<проект>`: «CI:» — длительность попытки задания
полного набора последней сводки (`suite-cost --record…`) против
`config.SUITE_COST_CI_LIMIT_SEC`; «локальный прогон:» — длительность
последней записи «прогон: время» задач проекта против предела профиля.
Цена набора — сигнал, не провал окружения: статусы только `ok`, `warn`,
`skip`; уровень «тревога» заводит алерт `suite.cost`.
"""
import json

from orchestrator import doctor

SOURCE = "suite.cost"
_LEVEL_TEXT = {"ok": "в норме", "warn": "предупреждение", "alert": "тревога"}


def _alert_message(target: str) -> str:
    # Без чисел и sha: дедуп `raise_alert` держит один открытый алерт на
    # проект, пока Оператор его не подтвердит.
    return (f"цена набора тестов проекта {target} у предела (CI или "
            f"локальный прогон) — строки `suite-cost:{target}` в `doctor`")


def _leveled(conn, target: str, name: str, prefix: str, seconds: float,
             limit, tail: str) -> doctor.Check:
    level = doctor.suite_cost_core.limit_level(seconds, limit)
    detail = (f"{prefix} {seconds:.0f} с из предела {limit} с "
              f"({seconds / limit * 100:.1f} %), {tail} — "
              f"{_LEVEL_TEXT[level]}")
    if level == doctor.suite_cost_core.ALERT:
        doctor.alerts.raise_alert(conn, target, "trigger", SOURCE,
                                  _alert_message(target))
    status = "ok" if level == doctor.suite_cost_core.OK else "warn"
    return doctor.Check(name, status, detail)


def _ci_line(conn, target: str, name: str) -> doctor.Check:
    rows = doctor.store.suite_costs(conn, target)
    if not rows:
        return doctor.Check(name, "skip",
                            "CI: сводок цены набора нет — `artel.py "
                            "suite-cost --record-latest` запишет")
    row = rows[0]
    job = json.loads(row["summary"]).get("job_seconds")
    if not isinstance(job, (int, float)):
        return doctor.Check(name, "skip", f"CI: у сводки {row['sha'][:12]} "
                                          f"нет длительности попытки")
    tail = (f"сводка {row['sha'][:12]}, возраст "
            f"{doctor.suite_cost_core.age_text(row['recorded_at'])}")
    if row["reason"]:
        tail += f", отчёта junit нет: {row['reason']}"
    return _leveled(conn, target, name, "CI: попытка задания",
                    float(job), doctor.config.SUITE_COST_CI_LIMIT_SEC, tail)


def _local_line(conn, target: str, name: str, rows: list) -> doctor.Check:
    if not rows:
        return doctor.Check(name, "skip",
                            "локальный прогон: записей «прогон: время» задач "
                            "проекта нет")
    row = max(rows, key=lambda r: (r["ts"] or "", r["id"]))
    try:
        seconds = json.loads(row["detail"]).get("duration_seconds")
    except (TypeError, ValueError, AttributeError):
        seconds = None
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        return doctor.Check(name, "skip",
                            f"локальный прогон: в записи задачи "
                            f"{row['task_id']} нет duration_seconds")
    try:
        limit, source = doctor.project_profile.full_suite_limit(target)
    except doctor.targets.TargetsError as exc:
        return doctor.Check(name, "skip", f"локальный прогон: предел не "
                                          f"определён — {exc}")
    tail = (f"источник предела: {source}, задача {row['task_id']}, возраст "
            f"{doctor.suite_cost_core.age_text(row['ts'])}")
    return _leveled(conn, target, name, "локальный прогон:", float(seconds),
                    limit, tail)


def check_suite_cost(conn) -> list[doctor.Check]:
    steps = doctor.store.steps_of_action(
        conn, doctor.acceptance.SUITE_DURATION_ACTION)
    task_targets = {task["id"]: task["target"]
                    for task in doctor.store.all_tasks(conn)}
    local = {}
    for row in steps:
        if row["task_id"] in task_targets:
            local.setdefault(task_targets[row["task_id"]], []).append(row)
    projects = sorted(set(local) | set(doctor.store.suite_cost_targets(conn)))
    checks = []
    for target in projects:
        name = f"suite-cost:{target}"
        checks.append(_ci_line(conn, target, name))
        checks.append(_local_line(conn, target, name, local.get(target, [])))
    return checks
