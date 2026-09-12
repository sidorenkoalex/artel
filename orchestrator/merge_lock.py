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
import sys

from . import config, liveness, store


def _holder_is_dead(row) -> bool:
    """Требование 4: протухший heartbeat ИЛИ неживой pid — два независимых
    признака мёртвого держателя, любой из них перешагивается при взятии
    (в отличие от `lease.acquire`, T044, которая смотрит только heartbeat
    — там держатель обычно жив весь МЕЖДУ-командный интервал `auto`, а не
    один синхронный вызов, и pid-проверку делает только `doctor`). Чужой
    host — судить о pid нечем, решает только heartbeat (тот же приём, что
    `doctor.check_leases`/`check_merge_lock`)."""
    if liveness._age_seconds(row["heartbeat_ts"]) > config.LEASE_STALE_AFTER_SEC:
        return True
    return (row["hostname"] == socket.gethostname()
           and not liveness._pid_alive(row["pid"]))


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
            age = liveness._age_seconds(row["heartbeat_ts"])
            return (f"[{task_id}] merge-окно занято сессией "
                   f"{row['session_id']} (задача {row['task_id']}), "
                   f"heartbeat {int(age)} сек назад — дождись освобождения "
                   f"и повтори approve")
        detail = (f"держатель мьютекса merge мёртв (сессия "
                 f"{row['session_id']} на {row['hostname']}, pid "
                 f"{row['pid']}, задача {row['task_id']}, heartbeat "
                 f"{int(liveness._age_seconds(row['heartbeat_ts']))} сек "
                 f"назад) — перехвачен сессией {session_id}")
        store.set_merge_lock(conn, task_id, session_id, pid, hostname,
                             store.now())
        store.journal(conn, task_id, "merge-lock",
                     "мьютекс merge перехвачен", detail)
        return None
    finally:
        if conn.in_transaction:
            conn.rollback()


def touch_heartbeat(conn) -> None:
    """Продлевает `heartbeat_ts` ТЕКУЩЕГО держателя мьютекса, если строка
    есть (SPEC 01M291EJMA995AZ61MEMDZKWRY, требование 3) — вызывать на
    каждой итерации опроса CI внутри `_wait_for_branch_ci_green`, чтобы
    долгое ожидание CI не роняло heartbeat ниже `LEASE_STALE_AFTER_SEC`
    и не подставляло живого держателя под перехват `_holder_is_dead`.

    Не принимает `session_id`: таблица несёт не более одной строки на
    весь пульт (требование 2), поэтому текущий держатель однозначен без
    сверки. Строки нет (мьютекс не взят либо вызвано вне окна) —
    молча ничего не делает.

    Чтение+запись обёрнуты `BEGIN IMMEDIATE`, тем же приёмом, что
    `acquire()` (см. модульный докстринг, ревью T044) — без этого
    конкурентный `acquire()` другой сессии мог бы атомарно перехватить
    протухший мьютекс МЕЖДУ чтением строки здесь и отложенной записью,
    и эта запись «воскресила» бы уже вытесненного держателя (R1-F1,
    REVIEW.md 01M291EJMA995AZ61MEMDZKWRY, итерация 1)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = store.merge_lock_row(conn)
        if row is None:
            return
        store.set_merge_lock(conn, row["task_id"], row["session_id"],
                             row["pid"], row["hostname"], store.now())
    finally:
        if conn.in_transaction:
            conn.rollback()


def release(conn, session_id: str) -> None:
    """Снимает мьютекс merge-окна, если он принадлежит этой сессии —
    вызывать из `finally` по завершении окна, независимо от исхода (SPEC
    T053, требование 3)."""
    store.release_merge_lock(conn, session_id)


def run_window(conn, task_id: str, session_id: str, body):
    """Единая точка окна merge-мьютекса (SPEC T053, требования 1-3):
    `acquire` -> отказ (`sys.exit`) -> `body()` -> `release` безусловно в
    `finally`, независимо от исхода тела (без понятия `fresh` — см.
    модульный докстринг).

    Перенесена дословно из `fsm._cmd_approve` (ветка `merge_gate`, SPEC
    T057, требование 1 rev. AC-3): `sid` там уже разрешён общей точкой
    `lease.run_locked` снаружи merge-окна, здесь он приходит готовым
    параметром, не переразрешается.
    """
    refusal = acquire(conn, task_id, session_id)
    if refusal is not None:
        sys.exit(refusal)
    try:
        return body()
    finally:
        release(conn, session_id)
