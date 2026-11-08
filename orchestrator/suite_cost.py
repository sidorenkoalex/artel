"""Цена набора тестов по отчёту junit CI `main` (ADR-0032 п. 6, SPEC
01M6Y44ZPXPQCNYDXQG6FMZPK5): сводка прогона, её запись и команда
`suite-cost`.

Сводка — число тестов (элементов `testcase`, не `testsuite@tests`: тот
считает подтесты), сумма их времени, `testsuite@time`, длительность
попытки задания, 20 самых медленных, доля каждого размера и прирост от
предыдущей сводки — ближайшего предка по первой родительской линии `main`
среди сводок с отчётом — со списком задач, смерженных между ними.
"""
import json
import re
import sys
from datetime import datetime, timezone

from . import ci, config, forge, gitcmd, store

BUCKETS = ("до 1 с", "1–10 с", "10–60 с", "60 с и дольше")
SLOWEST_COUNT = 20
OK, WARN, ALERT = "ok", "warn", "alert"
# Тема коммита мержа задачи в `main` (`fsm_merge_gate`): `<id>: merge task/…`.
_MERGE_SUBJECT = re.compile(r"^(\S+): merge task/")


def size_bucket(seconds: float) -> str:
    """Ориентир размера теста по его времени; левая граница — в старшем."""
    if seconds < 1:
        return BUCKETS[0]
    if seconds < 10:
        return BUCKETS[1]
    if seconds < 60:
        return BUCKETS[2]
    return BUCKETS[3]


def limit_level(seconds: float, limit: float) -> str:
    """Уровень длительности против предела: доля, равная порогу, — уже
    следующий уровень. Сравнение умножением, а не делением: ровно порог
    доли не теряется на округлении частного."""
    if seconds >= limit * config.SUITE_COST_ALERT_RATIO:
        return ALERT
    if seconds >= limit * config.SUITE_COST_WARN_RATIO:
        return WARN
    return OK


def summarize(times, suite_seconds, job_seconds, previous=None,
              tasks=()) -> dict:
    """Сводка прогона (требование 4); `times = None` — отчёта нет."""
    summary = {"tests": None, "total_seconds": None,
               "suite_seconds": suite_seconds, "job_seconds": job_seconds,
               "slowest": None, "buckets": None, "delta_tests": None,
               "delta_seconds": None, "tasks": list(tasks)}
    if times is None:
        return summary
    total = sum(times.values())
    ranked = sorted(times.items(), key=lambda kv: (-kv[1], kv[0]))
    counts = {b: 0 for b in BUCKETS}
    seconds = {b: 0.0 for b in BUCKETS}
    for value in times.values():
        counts[size_bucket(value)] += 1
        seconds[size_bucket(value)] += value
    summary.update(
        tests=len(times), total_seconds=total,
        slowest=[[node, value] for node, value in ranked[:SLOWEST_COUNT]],
        buckets={b: {"count": counts[b],
                     "share": seconds[b] / total if total else 0.0}
                 for b in BUCKETS})
    if previous is not None and previous.get("tests") is not None:
        summary["delta_tests"] = summary["tests"] - previous["tests"]
        summary["delta_seconds"] = total - previous["total_seconds"]
    return summary


def merged_tasks(prev_sha, sha) -> list:
    """Задачи проекта артели, смерженные в `main` на отрезке
    `prev_sha..sha` первой родительской линии, — от старых к новым; темы
    с id, которого в БД пульта нет, не входят. `prev_sha` пуст — `[]`."""
    if not prev_sha:
        return []
    res = gitcmd.in_repo(config.ROOT, "log", "--first-parent",
                         "--format=%s", f"{prev_sha}..{sha}")
    if res is None or res.returncode != 0:
        return []
    conn = store.db()
    found = []
    for subject in reversed(res.stdout.splitlines()):
        match = _MERGE_SUBJECT.match(subject)
        if not match:
            continue
        task_id = match.group(1)
        if (task_id not in found and store.task_exists(conn, task_id)
                and store.task_target(conn, task_id) == config.DEFAULT_TARGET):
            found.append(task_id)
    return found


def _full_sha(sha: str) -> str | None:
    res = gitcmd.in_repo(config.ROOT, "rev-parse", "--verify",
                         f"{sha}^{{commit}}")
    if res is None or res.returncode != 0:
        return None
    return res.stdout.strip() or None


def _previous(conn, target: str, sha: str):
    """Сводка-предшественник `sha` (требование 4): ближайший предок по
    первой родительской линии среди сводок проекта с отчётом; `None` —
    такой нет."""
    with_report = {}
    for row in store.suite_costs(conn, target):
        if json.loads(row["summary"]).get("tests") is not None:
            with_report[row["sha"]] = row
    if not with_report:
        return None
    res = gitcmd.in_repo(config.ROOT, "rev-list", "--first-parent", sha)
    if res is None or res.returncode != 0:
        return None
    for ancestor in res.stdout.split()[1:]:
        if ancestor in with_report:
            return with_report[ancestor]
    return None


def _seconds(value) -> str:
    return f"{value:.2f}"


def render(row) -> list:
    """Строки вывода сводки записи `row` таблицы `suite_costs`."""
    summary = json.loads(row["summary"])
    lines = [f"Сводка цены набора {row['target']}: коммит {row['sha']}, "
             f"записана {row['recorded_at']}"]
    job = summary.get("job_seconds")
    lines.append(f"  попытка задания «{ci.FULL_SUITE_JOB}»: "
                 + (f"{job:.0f} с" if job is not None else "нет данных"))
    if summary.get("tests") is None:
        lines.append(f"  отчёта junit нет: {row['reason']}")
    else:
        lines += [f"  тестов (testcase): {summary['tests']}",
                  f"  сумма времени тестов: "
                  f"{_seconds(summary['total_seconds'])} с",
                  f"  testsuite@time: {_seconds(summary['suite_seconds'])} с"]
        if summary.get("delta_tests") is None:
            lines.append("  прирост: предыдущей сводки с отчётом нет")
        else:
            lines.append(f"  прирост: {summary['delta_tests']:+d} тестов, "
                         f"{summary['delta_seconds']:+.2f} с")
        lines.append("  размеры:")
        for bucket, value in summary["buckets"].items():
            lines.append(f"    {bucket}: {value['count']} тестов, "
                         f"{value['share'] * 100:.1f} % суммы времени")
        lines.append(f"  самые медленные ({len(summary['slowest'])}):")
        for node, value in summary["slowest"]:
            lines.append(f"    {_seconds(value)} с  {node}")
    tasks = summary.get("tasks") or []
    lines.append("  задачи с предыдущей сводки: "
                 + (", ".join(tasks) if tasks else "нет"))
    return lines


def _record(sha_arg: str, how: str) -> None:
    target = config.DEFAULT_TARGET
    sha = _full_sha(sha_arg)
    if sha is None:
        sys.exit(f"suite-cost {how}: коммита {sha_arg} нет в репозитории "
                 f"пульта — сводка не записана (прирост и задачи считаются "
                 f"по линии main пульта; подтяни main)")
    conn = store.db()
    if any(row["sha"] == sha for row in store.suite_costs(conn, target)):
        print(f"suite-cost {how}: сводка коммита {sha} уже записана — не "
              f"меняется")
        return
    times, suite_seconds, job_seconds, reason = forge.ci_suite_report(
        target, sha)
    if job_seconds is None:
        sys.exit(f"suite-cost {how}: сводка коммита {sha} не записана — "
                 f"{reason}")
    previous = _previous(conn, target, sha)
    tasks = merged_tasks(previous["sha"], sha) if previous is not None else []
    summary = summarize(times, suite_seconds, job_seconds,
                        json.loads(previous["summary"]) if previous else None,
                        tasks)
    store.insert_suite_cost(conn, target, sha,
                            json.dumps(summary, ensure_ascii=False), reason)
    row = next(r for r in store.suite_costs(conn, target) if r["sha"] == sha)
    print("\n".join(render(row)))


def cmd_suite_cost(rest: list) -> None:
    """`suite-cost [--record <sha> | --record-latest]` (требование 6)."""
    usage = "синтаксис: suite-cost [--record <sha> | --record-latest]"
    if not rest:
        rows = store.suite_costs(store.db(), config.DEFAULT_TARGET)
        if not rows:
            print(f"Сводок цены набора проекта {config.DEFAULT_TARGET} нет — "
                  f"`artel.py suite-cost --record-latest` запишет первую")
            return
        print("\n".join(render(rows[0])))
        return
    if rest[0] == "--record" and len(rest) == 2 and not rest[1].startswith("-"):
        _record(rest[1], "--record")
        return
    if rest == ["--record-latest"]:
        sha, reason = forge.last_executed_commit(
            config.DEFAULT_TARGET, config.MAIN_BRANCH, ci.FULL_SUITE_JOB)
        if not sha:
            sys.exit(f"suite-cost --record-latest: сводка не записана — "
                     f"{reason}")
        _record(sha, "--record-latest")
        return
    sys.exit(f"suite-cost: аргументы {' '.join(rest)} не разобраны; {usage}")


def age_text(stamp: str, moment: datetime | None = None) -> str:
    """Возраст метки времени `store.now()` словами («5 ч 2 мин»)."""
    try:
        then = datetime.strptime(stamp[:19].replace("T", " "),
                                 "%Y-%m-%d %H:%M:%S").replace(
                                     tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return "неизвестен"
    minutes = max(0, int(((moment or datetime.now(timezone.utc)) - then)
                         .total_seconds() // 60))
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days} д {hours} ч"
    if hours:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"
