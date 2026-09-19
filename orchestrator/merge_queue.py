"""Очередь FIFO ожидания мьютекса merge-окна (SPEC
01M291EPQ2VFGCHZTXXC81616V, часть 2 из 2 родительской задачи
01M28VZ8Q1QTP5PRDVJJQ9AQV0).

Часть 1 (01M291EJMA995AZ61MEMDZKWRY, смержена) сделала так, что мьютекс
merge-окна (`orchestrator/merge_lock.py`, SPEC T053) держится на весь цикл
`approve` `merge_gate`, включая ожидание CI. До этой задачи второй
`approve` на занятое окно завершался немедленным отказом
(`merge_lock.acquire` -> `sys.exit`) — Оператору приходилось вручную
повторять команду. Эта задача меняет это единственное место: занятый
мьютекс ведёт не в `sys.exit`, а в `wait_for_window` — регистрацию в
таблице `merge_queue` и опрос освобождения окна с интервалом
`config.MERGE_GATE_CI_WAIT_POLL_SEC` (требование 1), пока эта задача не
станет головой очереди И не возьмёт мьютекс сама (требование 2: только
голова очереди берёт освободившееся окно, остальные продолжают ждать) —
либо пока не истечёт потолок `config.MERGE_QUEUE_WAIT_CEILING_SEC`
(требование 3).

Признак мёртвого участника очереди — буквально тот же, что и у держателя
мьютекса (`merge_lock._holder_is_dead`, требование 5): протухший heartbeat
ИЛИ неживой pid на своём host. Пруна мёртвых записей вызывается на каждом
опросе, ДО определения головы очереди — мёртвая голова не имеет права
вечно занимать место и блокировать живых участников позади себя (AC-8).
"""
import os
import socket
import sys
import time
from datetime import datetime

from . import config, merge_lock, store


def _prune_dead_entries(conn) -> None:
    """Удаляет из `merge_queue` записи мёртвых участников (требование 5)."""
    for row in store.merge_queue_rows(conn):
        if merge_lock._holder_is_dead(row):
            store.delete_merge_queue_row(conn, row["rowid"])


def _head_task_id(conn) -> str | None:
    """`task_id` головы очереди — первая запись по времени входа (FIFO,
    требование 2); `None` — очередь пуста."""
    rows = store.merge_queue_rows(conn)
    return rows[0]["task_id"] if rows else None


def _current_holder_id(conn) -> str:
    """`task_id` текущего держателя мьютекса merge-окна — для текста входа
    в очередь (требование 1, AC-2). Занятый мьютекс — предпосылка вызова
    `wait_for_window`, так что держатель почти всегда есть; `"?"` — на
    случай, если он успел освободиться между отказом `merge_lock.acquire`
    и входом в очередь (безвредная деградация только текста сообщения)."""
    row = store.merge_lock_row(conn)
    return row["task_id"] if row is not None else "?"


def _current_holder_label(conn) -> str:
    """Держатель мьютекса merge-окна для журнала входа в очередь и
    суффикса `status` — «<task_id> (pid <pid>)» (SPEC
    01M2XFSE8G3MBRHHQR38H53J1M, требования 6-7): держатель — процесс, и
    по одному task_id Оператор не отличит два параллельных цикла одного
    пульта. Без держателя — прежний `"?"` (тот же довод, что у
    `_current_holder_id`)."""
    row = store.merge_lock_row(conn)
    if row is None:
        return "?"
    return f"{row['task_id']} (pid {row['pid']})"


def queue_wait_minutes(conn, task_id: str) -> int | None:
    """Минуты, прошедшие с момента входа `task_id` в очередь ожидания
    merge-окна (`catalog.cmd_status`, требование 1/AC-2, по образцу
    `zone_lock.wait_minutes`); `None` — задача сейчас не в очереди."""
    row = next((r for r in store.merge_queue_rows(conn)
               if r["task_id"] == task_id), None)
    if row is None:
        return None
    started = datetime.strptime(row["enqueued_ts"], "%Y-%m-%d %H:%M:%SZ")
    now = datetime.strptime(store.now(), "%Y-%m-%d %H:%M:%SZ")
    return max(0, int((now - started).total_seconds() // 60))


def wait_suffix(conn, t) -> str:
    """Добавка `status` вида «[ждёт merge-окна: занято <id> (pid <pid>),
    N мин]» (требование 1, AC-2; pid держателя — SPEC
    01M2XFSE8G3MBRHHQR38H53J1M, требование 7) — ДОБАВКОЙ в конец строки,
    по образцу `catalog._zone_wait_suffix`; пустая строка — задача сейчас
    не в очереди `merge_queue`."""
    minutes = queue_wait_minutes(conn, t["id"])
    if minutes is None:
        return ""
    holder = _current_holder_label(conn)
    return f"  [ждёт merge-окна: занято {holder}, {minutes} мин]"


def wait_for_window(conn, task_id: str, sid: str) -> None:
    """Встаёт в очередь `merge_queue` и опрашивает освобождение мьютекса
    merge-окна с интервалом `config.MERGE_GATE_CI_WAIT_POLL_SEC`, пока эта
    задача не станет головой очереди И не возьмёт мьютекс сама (требования
    1-2) — либо пока не истечёт потолок `config.MERGE_QUEUE_WAIT_CEILING_
    SEC` (требование 3): тогда `sys.exit` именованным сообщением, задача
    остаётся на `merge_gate` (переход состояния не выполняется — этот
    модуль `store.set_state` не зовёт вовсе).

    Вызывать ТОЛЬКО когда прямой `merge_lock.acquire` уже отказал —
    функция сама этого не проверяет, ей просто больше неоткуда взяться в
    `fsm_merge_gate._cmd_approve_merge_gate_cycle`. Возврат — мьютекс уже
    взят ЭТИМ процессом (требование 1: «получая окно после освобождения
    без нового ручного вызова»), вызывающий код продолжает как если бы
    `merge_lock.acquire` сразу вернул успех.

    Своя запись очереди адресуется процессом — (sid, pid), не одним sid
    (SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требование 5): два цикла `approve`
    одной рабочей копии пульта несут один session_id и стоят в очереди
    двумя записями, продлевая и снимая каждый только свою; журнал входа
    называет держателя с pid (требование 6).
    """
    pid, hostname = os.getpid(), socket.gethostname()
    ts = store.now()
    store.enqueue_merge_wait(conn, task_id, sid, pid, hostname, ts)
    holder = _current_holder_label(conn)
    store.journal(
        conn, task_id, "orchestrator",
        f"ждёт merge-окна: держит {holder}",
        f"вход в очередь merge_queue, опрос каждые "
        f"{config.MERGE_GATE_CI_WAIT_POLL_SEC} сек, потолок "
        f"{config.MERGE_QUEUE_WAIT_CEILING_SEC} сек")
    deadline = time.monotonic() + config.MERGE_QUEUE_WAIT_CEILING_SEC
    try:
        while True:
            store.touch_merge_queue_heartbeat(conn, sid, pid, store.now())
            _prune_dead_entries(conn)
            if _head_task_id(conn) == task_id:
                refusal = merge_lock.acquire(conn, task_id, sid)
                if refusal is None:
                    return
            if time.monotonic() >= deadline:
                sys.exit(
                    f"[{task_id}] merge отклонён: потолок ожидания очереди "
                    f"merge-окна истёк ({config.MERGE_QUEUE_WAIT_CEILING_SEC} "
                    f"сек)\n  задача осталась на гейте merge; повтори: "
                    f"artel.py approve {task_id}")
            time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)
    finally:
        store.dequeue_merge_wait(conn, sid, pid)
