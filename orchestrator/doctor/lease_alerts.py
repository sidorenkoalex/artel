"""Пакет orchestrator/doctor -- разбор live-условия алертов мёртвого lease/merge_lock.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import re

from orchestrator import doctor


# --- lease с мёртвым pid (SPEC T044, требование 11) ----------------------

# Тот же приём разбора, что у `_branch_alert_live`/`_dir_alert_live`/
# `_worktree_alert_live` выше: сущность восстанавливается из `message`,
# который сами же `check_leases`/`check_merge_lock` и составляют.
_LEASE_ALERT_RE = re.compile(r"^(\S+): lease сессии (\S+) мёртв \(pid \d+ на \S+\)$")
_MERGE_LOCK_ALERT_RE = re.compile(
    r"^(\S+): мьютекс merge сессии (\S+) мёртв \(pid \d+ на \S+\)$")


def _lease_alert_live(message: str, rows_by_task: dict) -> bool:
    """SPEC T054, требование 1: условие живо, пока строка leases с тем же
    task_id/session_id ещё на месте и её (актуальный, не из сообщения) pid
    мёртв. Строки нет, session_id другой (lease перехвачен/переиздан) или
    pid ожил — условие снято."""
    match = doctor._LEASE_ALERT_RE.match(message)
    if match is None:
        return True
    task_id, session_id = match.group(1), match.group(2)
    row = rows_by_task.get(task_id)
    if row is None or row["session_id"] != session_id:
        return False
    return not doctor.liveness._pid_alive(row["pid"])


def _merge_lock_alert_live(message: str, row) -> bool:
    """SPEC T054, требование 2: условие живо, пока текущий держатель
    мьютекса — то же (task_id, session_id), что в сообщении, и его
    (актуальный) pid мёртв. Замок пуст, держатель сменился или pid ожил —
    условие снято."""
    match = doctor._MERGE_LOCK_ALERT_RE.match(message)
    if match is None:
        return True
    if row is None:
        return False
    task_id, session_id = match.group(1), match.group(2)
    if row["task_id"] != task_id or row["session_id"] != session_id:
        return False
    return not doctor.liveness._pid_alive(row["pid"])


