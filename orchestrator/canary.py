"""Команда `canary`: синтетический прогон конвейера (tasks/T065/SPEC.md).

Канарейка — типовые синтетические ТЗ с неподвижным входом, заведённые
и проведённые через FSM без участия Оператора: сдвиг метрик прогона
относительно `baseline.json` читается как регрессия самого конвейера,
не кодовой базы (её решение здесь не пишется в историю git и не может
"подсмотреть" прошлый прогон).

Каждая заведённая задача ведётся штатным `auto.cmd_auto` (run+advance,
тем же циклом, каким Оператор гоняет продуктовые задачи) до места, где
`auto` останавливается сам, — ручного гейта или терминального состояния.
`spec_gate`/`acceptance` эта команда проходит САМА, отдельным кодовым
путём (не через `fsm.cmd_approve`), тем же переходом, каким прошёл бы их
`approve` Оператора: инвариант 18 («`auto` не проходит гейты»,
docs/invariants.md) этим не затронут — `auto` как модуль по-прежнему
не проходит ни одного гейта; путь существует только внутри этого модуля
и только для задач, которые сама же команда `canary` завела. `merge_gate`
canary не approve никогда — задача убивается штатным `cleanup.cmd_kill`
(main этим путём не трогается — kill не мержит).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts import guard

from . import (artifacts, auto, catalog, cleanup, config, fsm, gitcmd,
              runner, store, yamlmini)

CANARY_MARK_ACTOR = "canary"


def _canary_dir() -> Path:
    return config.ROOT / ".artel" / "canary"


def _baseline_path() -> Path:
    return _canary_dir() / "baseline.json"


def _spec_gate_next_state(conn, task_id: str, t) -> str:
    """Куда ведёт SPEC-гейт — та же ветка условий, что и у
    `fsm._cmd_approve` для `spec_gate` (AC-разметка SPEC), скопированная
    сюда намеренно (см. модульный докстринг: не через `cmd_approve`)."""
    branch = t["branch"]
    if gitcmd.on_foreign_branch(branch):
        spec_text, _reason = gitcmd.show(branch, f"tasks/{task_id}/SPEC.md")
        meta = (yamlmini.frontmatter(spec_text) or {}) if spec_text is not None else {}
    else:
        meta = artifacts.frontmatter(config.TASKS / task_id / "SPEC.md")
    return "tests_writing" if guard.requires_ac_markup(meta) else "in_dev"


def _pass_spec_gate(conn, task_id: str) -> None:
    t = store.get_task(conn, task_id)
    next_state = _spec_gate_next_state(conn, task_id, t)
    store.set_state(conn, task_id, next_state, CANARY_MARK_ACTOR,
                    expected_state="spec_gate",
                    detail="canary: гейт SPEC пройден автоматически "
                    "(эквивалент operator approve)")


def _pass_acceptance_gate(conn, task_id: str) -> None:
    t = store.get_task(conn, task_id)
    if fsm._pull_main_or_escalate(conn, task_id, t, "acceptance") == "escalated":
        return
    store.set_state(conn, task_id, "merge_gate", CANARY_MARK_ACTOR,
                    expected_state="acceptance",
                    detail="canary: приёмка пройдена автоматически "
                    "(эквивалент operator approve)")


def _kill_at_merge_gate(conn, task_id: str) -> None:
    store.journal(conn, task_id, CANARY_MARK_ACTOR,
                 "canary: merge_gate не approve — задача убивается",
                 "канареечная задача никогда не мержится в main "
                 "(tasks/T065/SPEC.md, требование 3)")
    cleanup.cmd_kill(task_id)


def _drive_task(conn, task_id: str) -> None:
    """Ведёт ОДНУ заведённую канарейкой задачу до её конца (`killed`) или
    до состояния, дальше которого canary не умеет вести (эскалация и
    т.п.) — не роняет прогон остальных задач набора ни в одном случае."""
    while True:
        auto.cmd_auto(task_id)
        t = store.get_task(conn, task_id)
        state = t["state"]
        if state == "spec_gate":
            _pass_spec_gate(conn, task_id)
            continue
        if state == "acceptance":
            _pass_acceptance_gate(conn, task_id)
            continue
        if state == "merge_gate":
            _kill_at_merge_gate(conn, task_id)
            return
        if runner.step_role(t) is not None:
            # `auto` остановился, не дойдя до гейта (лимит AUTO_MAX_STEPS
            # за один вызов) — задаче всё ещё есть кому работать, просто
            # продолжаем цикл новым вызовом `auto.cmd_auto`.
            continue
        # done/escalated/killed или любое другое состояние без агентской
        # роли и не входящее в три canary-гейта выше — canary дальше не
        # ведёт (в предусмотренных сценариях недостижимо, см. PLAN «Риски»).
        return


def _step_count(steps) -> int:
    """«Шаги» задачи — число переходов FSM в её журнале, не число
    прогонов агента: устойчиво к подмене `runner.cmd_run` (приёмочная
    песочница `tasks/T065/acceptance_tests/_sandbox.py::SmartAgent` не
    журналирует "agent run …", только реальный `cmd_run` это делает)."""
    return sum(1 for r in steps if r["action"].startswith("state -> "))


def _escalation_notes(steps) -> list:
    return [r["detail"] or "" for r in steps if r["action"] == "state -> escalated"]


def _task_metrics(conn, task_id: str) -> dict:
    t = store.get_task(conn, task_id)
    steps = store.task_steps(conn, task_id)
    return {
        "steps": _step_count(steps),
        "cost_usd": t["spent_usd"] or 0.0,
        "review_iterations": t["review_iters"],
        "escalations": _escalation_notes(steps),
        "outcome": t["state"],
    }


def _summary(tasks_metrics: dict) -> dict:
    return {
        "cost_usd": sum(m["cost_usd"] for m in tasks_metrics.values()),
        "steps": sum(m["steps"] for m in tasks_metrics.values()),
    }


def _write_report(stamp: str, tasks_metrics: dict, summary: dict) -> Path:
    _canary_dir().mkdir(parents=True, exist_ok=True)
    path = _canary_dir() / f"{stamp}.json"
    report = {"tasks": tasks_metrics, "summary": summary}
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                               sort_keys=True), encoding="utf-8")
    return path


def _read_baseline() -> dict | None:
    path = _baseline_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_baseline(summary: dict) -> None:
    _canary_dir().mkdir(parents=True, exist_ok=True)
    _baseline_path().write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")


def _deviation_exceeds(current: float, baseline: float, ratio: float) -> bool:
    """|отклонение| текущего значения от бейзлайна превышает `ratio`.

    `baseline == 0` — сравнивать нечего делением: любое ненулевое текущее
    значение считается полным (100%) отклонением, нулевое — нулевым.
    """
    if baseline == 0:
        return current != 0
    return abs(current - baseline) / baseline > ratio


def _baseline_warnings(summary: dict, baseline: dict) -> list:
    warnings = []
    for key, label in (("cost_usd", "стоимости"), ("steps", "шагам")):
        current = summary.get(key, 0)
        base = baseline.get(key, 0)
        if _deviation_exceeds(current, base, config.CANARY_DEVIATION_RATIO):
            warnings.append(
                f"ВНИМАНИЕ: отклонение по {label} от бейзлайна превышает "
                f"{config.CANARY_DEVIATION_RATIO:.0%}: сейчас {current}, "
                f"бейзлайн {base}")
    return warnings


def cmd_canary(tz_dir: str, *, rewrite_baseline: bool = False) -> None:
    directory = Path(tz_dir)
    if not directory.is_dir():
        sys.exit(f"canary: каталог не найден: {tz_dir}")
    files = sorted(p for p in directory.iterdir()
                   if p.is_file() and p.suffix == ".md")
    if not files:
        sys.exit(f"canary: в {tz_dir} нет файлов *.md")

    conn = store.db()
    task_ids = []
    for f in files:
        task_id = catalog.cmd_new(f.stem, tz_path=str(f), canary=True)
        task_ids.append(task_id)
        print(f"[canary] {task_id} заведена из {f.name}")

    for task_id in task_ids:
        _drive_task(conn, task_id)

    tasks_metrics = {task_id: _task_metrics(conn, task_id)
                     for task_id in task_ids}
    summary = _summary(tasks_metrics)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = _write_report(stamp, tasks_metrics, summary)

    print(f"\n[canary] отчёт прогона: {report_path}")
    for task_id, m in tasks_metrics.items():
        print(f"  {task_id}: шагов={m['steps']}  ${m['cost_usd']:.2f}  "
             f"ревью-итераций={m['review_iterations']}  "
             f"эскалаций={len(m['escalations'])}  исход={m['outcome']}")
    print(f"  итого: шагов={summary['steps']}  ${summary['cost_usd']:.2f}")

    baseline = _read_baseline()
    if baseline is None or rewrite_baseline:
        _write_baseline(summary)
        note = ("бейзлайн перезаписан (--rewrite-baseline)"
                if baseline is not None else "бейзлайн создан")
        print(f"[canary] {note}: {_baseline_path()}")
    else:
        warnings = _baseline_warnings(summary, baseline)
        if warnings:
            for w in warnings:
                print(f"[canary] {w}")
        else:
            print(f"[canary] отклонение от бейзлайна в пределах порога "
                 f"{config.CANARY_DEVIATION_RATIO:.0%}")
