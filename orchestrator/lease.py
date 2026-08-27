"""Advisory-lease задачи: замок параллельных сессий CLI (SPEC T044).

Мутирующие команды (`run`, `auto`, `advance`, `approve`, `reject`, `kill`,
`budget`) берут lease задачи перед своей работой над ней (требование 2).
Истина состояния остаётся в `tasks.state` (FSM, `orchestrator/fsm.py`) —
lease не второй конечный автомат, а только право сессии сейчас мутировать
задачу (требование 12).

`release()` отпускает lease, только если ОН БЫЛ ВЗЯТ С НУЛЯ этим же
вызовом `acquire()` (строки не было вовсе до него). Продление своего
предсуществующего lease и перехват чужого протухшего строку не создают —
они её застают уже существующей, поэтому сами её не отпускают: так одна
сессия удерживает lease непрерывно на протяжении серии своих вызовов
(требование 9) — ровно то, ради чего `auto.cmd_auto` берёт lease один раз
на весь цикл и передаёт свой `session_id` во внутренние `run`/`advance`:
они видят уже существующий lease своей же сессии, продлевают его и сами
не отпускают, а стоящий на пути одноразовый самостоятельный вызов
(не из-под `auto`) корректно снимает за собой то, что сам же и создал.
"""
import os
import socket
from datetime import datetime, timezone

from . import config, store


def resolve_session_id(session_id: str | None) -> str:
    """Identity вызывающей сессии.

    Источник по умолчанию SPEC не фиксирует (требование 9) — решение
    разработчика: `ARTEL_SESSION_ID` из окружения, если задан явно, иначе
    pid родительского процесса. Один терминал/шелл — один родительский pid
    на всё время жизни сессии, то есть последовательные вызовы CLI из
    одного терминала получают одну и ту же identity без всякой настройки;
    два разных терминала получают разные pid — то самое разделение,
    которого требует замок. Явный параметр (тестовый шов приёмочных
    тестов, tasks/T044/acceptance_tests) всегда сильнее обоих источников.
    """
    if session_id:
        return session_id
    return os.environ.get("ARTEL_SESSION_ID") or f"ppid-{os.getppid()}"


def _age_seconds(heartbeat_ts: str) -> float:
    ts = datetime.strptime(heartbeat_ts, "%Y-%m-%d %H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds()


def acquire(conn, task_id: str, session_id: str) -> tuple[str | None, bool]:
    """(отказ, взят_с_нуля). `отказ` — None, если можно продолжать.

    Требования 3-5: свободен или свой session_id -> взять/продлить; чужой
    свежий (heartbeat моложе `config.LEASE_STALE_AFTER_SEC`) -> именованный
    отказ, ничего не меняется; чужой протухший -> перехват (сессия/pid/
    hostname/heartbeat переписываются на вызывающую сторону) с отдельной
    записью в журнале задачи. `взят_с_нуля` — True, только если до этого
    вызова строки не было вовсе (см. модульный докстринг про `release`).

    Чтение строки (`store.lease_row`) и её запись (`insert_lease`/
    `update_lease`) выполняются внутри одной транзакции `BEGIN IMMEDIATE`:
    она берёт RESERVED-блокировку до чтения, поэтому вторая параллельная
    сессия, тоже вызвавшая `acquire()` на ту же задачу, не может ни
    прочитать, ни записать, пока первая не закоммитит (или не откатит)
    — без этого окно между чтением строки и её записью позволяло двум
    сессиям одновременно решить, что lease свободен или протух, и обеим
    уйти писать (ревью T044, итерация 1, Замечание 1).
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = store.lease_row(conn, task_id)
        pid, hostname = os.getpid(), socket.gethostname()
        if row is None:
            store.insert_lease(conn, task_id, session_id, pid, hostname, store.now())
            return None, True
        if row["session_id"] == session_id:
            store.update_lease(conn, task_id, session_id, pid, hostname, store.now())
            return None, False
        age = _age_seconds(row["heartbeat_ts"])
        if age <= config.LEASE_STALE_AFTER_SEC:
            refusal = (f"[{task_id}] задачу ведёт сессия {row['session_id']} "
                      f"с host {row['hostname']}, heartbeat {int(age)} сек "
                      f"назад — подожди её или разберись, что с ней")
            return refusal, False
        detail = (f"lease протух ({int(age)} сек > порог "
                 f"{config.LEASE_STALE_AFTER_SEC}) у сессии {row['session_id']} "
                 f"({row['hostname']}) — перехвачен сессией {session_id}")
        store.update_lease(conn, task_id, session_id, pid, hostname, store.now())
        store.journal(conn, task_id, "lease", "lease перехвачен", detail)
        return None, False
    finally:
        if conn.in_transaction:
            conn.rollback()


def release(conn, task_id: str, session_id: str) -> None:
    """Освобождает lease, взятый С НУЛЯ этой сессией (см. модульный докстринг)."""
    store.release_lease(conn, task_id, session_id)
