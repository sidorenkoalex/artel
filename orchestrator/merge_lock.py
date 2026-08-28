"""Мьютекс merge-окна: один держатель на весь пульт (SPEC T053).

Lease задачи (`lease.py`, T044) не защищает от гонки за main между двумя
РАЗНЫМИ задачами: обе могут одновременно исполнять merge-окно, каждая
удерживая lease только своей собственной задачи. Этот мьютекс — второй,
отдельный замок с единственной строкой на весь пульт (не per-task, в
отличие от `leases`): держит его СЕССИЯ, вне зависимости от того, чью
задачу она мержит (требование 2). Взятие атомарно тем же приёмом, что
`lease.acquire` — `BEGIN IMMEDIATE` до чтения строки закрывает то же окно
между чтением и записью, которое без него позволяло бы двум сессиям
одновременно решить, что мьютекс свободен, и обеим уйти мержить main
(ревью T044, итерация 1, замечание 1 — тот же класс дефекта).

В отличие от lease, который сессия держит через СЕРИЮ вызовов `auto`
(её `release()` снимает только то, что взяла с нуля САМА), этот мьютекс
живёт РОВНО одну операцию — merge-окно одного вызова `approve` из
`merge_gate` (SPEC требование 1) — поэтому `release()` снимает его
безусловно по завершении окна (успех, отказ, `sys.exit` — try/finally
в `fsm._cmd_approve`, требование 3), без понятия «взят с нуля».
"""
import os
import socket
from datetime import datetime, timezone

from . import config, store


def _age_seconds(heartbeat_ts: str) -> float:
    ts = datetime.strptime(heartbeat_ts, "%Y-%m-%d %H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds()


def _pid_alive(pid: int) -> bool:
    """`os.kill(pid, 0)` не шлёт сигнал, только проверяет адресуемость —
    тот же приём, что `doctor._pid_alive` (SPEC T044, требование 11)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _holder_is_dead(row) -> bool:
    """Требование 4: протухший heartbeat ИЛИ неживой pid — два независимых
    признака мёртвого держателя, любой из них перешагивается при взятии
    (в отличие от `lease.acquire`, T044, которая смотрит только heartbeat
    — там держатель обычно жив весь МЕЖДУ-командный интервал `auto`, а не
    один синхронный вызов, и pid-проверку делает только `doctor`). Чужой
    host — судить о pid нечем, решает только heartbeat (тот же приём, что
    `doctor.check_leases`/`check_merge_lock`)."""
    if _age_seconds(row["heartbeat_ts"]) > config.LEASE_STALE_AFTER_SEC:
        return True
    return row["hostname"] == socket.gethostname() and not _pid_alive(row["pid"])


def acquire(conn, task_id: str, session_id: str) -> str | None:
    """None — мьютекс взят (свободен, свой либо перехвачен мёртвый
    держатель) и можно исполнять merge-окно; иначе — именованный отказ
    с session_id держателя и задачей, которую он держит (требование 2),
    ничего не меняется.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = store.merge_lock_row(conn)
        pid, hostname = os.getpid(), socket.gethostname()
        if row is None or row["session_id"] == session_id:
            store.set_merge_lock(conn, task_id, session_id, pid, hostname,
                                 store.now())
            return None
        if not _holder_is_dead(row):
            age = _age_seconds(row["heartbeat_ts"])
            return (f"[{task_id}] merge-окно занято сессией "
                   f"{row['session_id']} (задача {row['task_id']}), "
                   f"heartbeat {int(age)} сек назад — дождись освобождения "
                   f"и повтори approve")
        detail = (f"держатель мьютекса merge мёртв (сессия "
                 f"{row['session_id']} на {row['hostname']}, pid "
                 f"{row['pid']}, задача {row['task_id']}, heartbeat "
                 f"{int(_age_seconds(row['heartbeat_ts']))} сек назад) — "
                 f"перехвачен сессией {session_id}")
        store.set_merge_lock(conn, task_id, session_id, pid, hostname,
                             store.now())
        store.journal(conn, task_id, "merge-lock",
                     "мьютекс merge перехвачен", detail)
        return None
    finally:
        if conn.in_transaction:
            conn.rollback()


def release(conn, session_id: str) -> None:
    """Снимает мьютекс merge-окна, если он принадлежит этой сессии —
    вызывать из `finally` по завершении окна, независимо от исхода (SPEC
    T053, требование 3)."""
    store.release_merge_lock(conn, session_id)
