"""Лимитер параллельных задач: MAX_PARALLEL_TASKS (SPEC T060).

Читает существующую lease-механику (`orchestrator/lease.py`, SPEC T044),
не заводит отдельный конечный автомат: «другая занятая задача» — строка
`store.all_leases` с чужим `task_id`, чей `heartbeat_ts` не старше
`config.LEASE_STALE_AFTER_SEC` (`liveness._age_seconds`) и чей `pid`
адресуем на своём host (`liveness._pid_alive`). Протухшие по heartbeat и
мёртвые по pid lease в счёт не идут; lease самой стартующей задачи не
считается против неё независимо от того, чей это `session_id`
(требование 2).

Чужой host: числа pid host-локальны, `liveness._pid_alive` (`os.kill`)
на ЧУЖОЙ pid ничего не значит на этой машине — тот же приём, что
`doctor.check_leases`/`check_merge_lock`/`merge_lock._holder_is_dead`:
`_pid_alive` зовётся только для строк со своим host, для чужого host pid
нельзя ни подтвердить, ни опровергнуть — считаем занятой (heartbeat
по-прежнему решает, он host-независим).
"""
import socket

from . import config, liveness, store


def busy_other_tasks(conn, task_id: str) -> list:
    """Живые lease чужих (не `task_id`) задач."""
    host = socket.gethostname()
    busy = []
    for row in store.all_leases(conn):
        if row["task_id"] == task_id:
            continue
        if liveness._age_seconds(row["heartbeat_ts"]) > config.LEASE_STALE_AFTER_SEC:
            continue
        if row["hostname"] == host and not liveness._pid_alive(row["pid"]):
            continue
        busy.append(row)
    return busy


def refusal(conn, task_id: str) -> str | None:
    """Именованный отказ, если занятых других задач >= потолка, иначе None."""
    busy = busy_other_tasks(conn, task_id)
    if len(busy) < config.MAX_PARALLEL_TASKS:
        return None
    names = "; ".join(f"{row['task_id']} (session {row['session_id']})"
                      for row in busy)
    return (f"[{task_id}] лимит параллельных задач достигнут: заняты "
            f"{names} — потолок MAX_PARALLEL_TASKS="
            f"{config.MAX_PARALLEL_TASKS}, агент не запускается")
