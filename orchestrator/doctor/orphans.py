"""Пакет orchestrator/doctor -- сироты: каталоги без строки БД, ветки done/killed, worktree.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from pathlib import Path

from orchestrator import doctor


# --- сироты (требование 8) ----------------------------------------------

def _is_legit_task_worktree(wt_path: str, known_ids: set) -> bool:
    """Легитимный per-task worktree (SPEC T045, AC-9): лежит ровно в
    `config.WORKTREES/<id>`, и `<id>` — известная задача. Иначе (чужое
    место, неизвестная задача) — сирота по построению."""
    p = Path(wt_path)
    return p.parent == doctor.config.WORKTREES and p.name in known_ids


def _orphan_worktrees(known_ids: set) -> list[str]:
    # Первая запись `workspace.registered_paths()` — основной checkout
    # (ROOT), не worktree ни одной задачи.
    paths = doctor.workspace.registered_paths()[1:]
    return [p for p in paths if not doctor._is_legit_task_worktree(p, known_ids)]


def check_orphans(conn) -> list[doctor.Check]:
    """Требование 8: три под-проверки; каждый найденный факт — incident-алерт."""
    results = []

    known_ids = {r["id"] for r in doctor.store.all_tasks(conn)}
    # Исторический tasks/ пульта сканируется БЕЗ ИЗМЕНЕНИЙ (требование 3
    # SPEC A7) вдобавок к артефактному каталогу КАЖДОГО объявленного
    # target, включая артель — она больше не исключается по имени
    # (A7, требование 2, AC-4): новые задачи артели ведут первичку в
    # `.artel/projects/artel/tasks/`, тем же путём, что и любой другой
    # target.
    scan = [(doctor.config.DEFAULT_TARGET, doctor.config.TASKS)]
    try:
        for name in doctor.targets.load():
            scan.append((name, doctor.config.PROJECTS / name / "tasks"))
    except doctor.targets.TargetsError:
        pass  # сломанный targets.yaml — забота другой проверки doctor'а
    orphan_dirs = [
        (target_name, entry)
        for target_name, tasks_dir in scan if tasks_dir.is_dir()
        for entry in sorted(tasks_dir.iterdir())
        if entry.is_dir() and entry.name not in known_ids
    ]
    if orphan_dirs:
        for target_name, entry in orphan_dirs:
            doctor.alerts.raise_alert(conn, target_name, "incident", "doctor.orphans.dir",
                              f"{entry} без строки БД")
        results.append(doctor.Check("orphans-dirs", "fail",
                            "; ".join(str(e) for _, e in orphan_dirs)))
    else:
        results.append(doctor.Check("orphans-dirs", "ok", "нет каталогов без строки БД"))
    doctor._auto_ack_gone(conn, "doctor.orphans.dir",
                  lambda msg: doctor._dir_alert_live(msg, known_ids))

    stale = [r for r in doctor.store.all_tasks(conn)
            if r["state"] in ("done", "killed") and r["branch"]
            and doctor.gitcmd.branch_exists(r["branch"])]
    if stale:
        for r in stale:
            doctor.alerts.raise_alert(conn, r["target"] or doctor.config.DEFAULT_TARGET,
                              "incident", "doctor.orphans.branch",
                              f"{r['id']} ({r['state']}): ветка {r['branch']} "
                              f"не убрана")
        results.append(doctor.Check("orphans-branches", "fail",
                            "; ".join(f"{r['id']}:{r['branch']}" for r in stale)))
    else:
        results.append(doctor.Check("orphans-branches", "ok", "нет веток done/killed задач"))
    doctor._auto_ack_gone(conn, "doctor.orphans.branch", doctor._branch_alert_live)

    orphan_worktrees = doctor._orphan_worktrees(known_ids)
    if orphan_worktrees:
        for path in orphan_worktrees:
            doctor.alerts.raise_alert(conn, doctor.config.DEFAULT_TARGET, "incident",
                              "doctor.orphans.worktree", f"worktree {path} без задачи")
        results.append(doctor.Check("orphans-worktrees", "fail",
                            "; ".join(orphan_worktrees)))
    else:
        results.append(doctor.Check("orphans-worktrees", "ok", "лишних worktree нет"))
    current_worktree_paths = set(orphan_worktrees)
    doctor._auto_ack_gone(conn, "doctor.orphans.worktree",
                  lambda msg: doctor._worktree_alert_live(msg, current_worktree_paths))

    return results


