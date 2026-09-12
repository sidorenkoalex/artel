"""Пакет orchestrator/doctor -- lease с мёртвым pid, мьютекс merge, рекон осиротевшего шага.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import socket
import time

from orchestrator import doctor


# --- рекон осиротевшего шага (SPEC 01M1G..., требование 4, AC-7/AC-8) ---

# Терминальные события, закрывающие «agent run started» тем же приёмом,
# что уже пишет `orchestrator/runner.py` (`store.journal(..., "agent run
# ...")`): любое из них ПОСЛЕ старта — шаг довели до конца, не сирота.
_STEP_TERMINAL_ACTIONS = {
    "agent run finished", "agent run FAILED", "agent run TIMEOUT",
    "agent run SKIPPED",
}
# Маркер терминального события САМОГО РЕКОНА (см. `_reconcile_orphaned_
# step` ниже) — засчитывается как та же терминальная пара: повторный
# проход по журналу больше не видит уже реконенный старт сиротой
# (идемпотентность, AC-8).
_ORPHAN_ACTION_MARKER = "шаг оборван"


def _orphaned_start_step(steps):
    """Последнее «agent run started» без терминальной пары ГДЕ УГОДНО
    дальше в журнале — не только сравнением с последней записью (реконом
    может быть пропущено другое событие между стартом и обрывом, см.
    докстринг AC-7 приёмочного теста). `steps` — журнал ОДНОЙ задачи по
    порядку записи; `None` — сирот нет."""
    pending = None
    for s in steps:
        action = s["action"] or ""
        if action == "agent run started":
            pending = s
        elif action in doctor._STEP_TERMINAL_ACTIONS or doctor._ORPHAN_ACTION_MARKER in action:
            pending = None
    return pending


def _reconcile_orphaned_step(conn, task_id: str, dead_session_id: str,
                             steps: list) -> None:
    """Дописывает «шаг оборван смертью сессии `<id>`» для «agent run
    started» без терминальной пары, если он есть (SPEC 01M1G..., AC-7).

    `steps` — снимок журнала, снятый ДО этого вызова (в `check_leases`,
    до печати FAIL-строки): реконенное событие не должно само стать
    «последним событием задачи» в FAIL-строке этого же прогона (иначе
    Оператор не увидел бы, что реально происходило до рекона)."""
    orphan = doctor._orphaned_start_step(steps)
    if orphan is None:
        return
    action = f"шаг оборван смертью сессии {dead_session_id}"
    detail = (f"шаг id={orphan['id']} ({orphan['actor']}), старт "
             f"{orphan['ts']}: {orphan['detail'] or '—'}")
    doctor.store.journal(conn, task_id, "doctor", action, detail)


def _last_start_step(steps):
    """Последняя запись «agent run started» в журнале задачи, ЗАКРЫТА она
    терминальной парой или нет — в отличие от `_orphaned_start_step`,
    которая ищет только НЕзакрытую (для идемпотентного рекона, AC-7/AC-8).
    Используется в FAIL-строке `check_leases` (AC-10, REVIEW.md
    итерации 1, R1-F1): держатель lease мог умереть МЕЖДУ шагами, когда
    последний запуск агента уже штатно завершился терминальным событием —
    Оператору всё равно нужен номер и время старта ПОСЛЕДНЕГО шага
    задачи, не только оборванного. `None` — агент по этой задаче ещё ни
    разу не запускался (в журнале нет ни одной записи «agent run
    started»)."""
    last = None
    for s in steps:
        if (s["action"] or "") == "agent run started":
            last = s
    return last


def _lease_fail_detail(conn, row, steps: list) -> str:
    """FAIL-строка `check_leases` по мёртвому lease (SPEC 01M1G...,
    требование 5, AC-10): держатель/pid/host (существующий текст,
    прежде байт-в-байт совпадавший с сообщением алерта) + роль держателя,
    номер и время старта последнего шага задачи (не только оборванного —
    R1-F1) и последнее журнальное событие задачи — Оператору не нужно
    отдельно звать `log`, чтобы понять, что произошло.

    Подсказка «следующий approve/auto перехватит сам» (SPEC
    01M290PS4ZXK1RCZ3PXQSXK0Y9, требование 4/AC-7) — только здесь, в
    `base` этой функции (Check-текст для Оператора), НЕ в `message`
    `check_leases` ниже: тот разбирается regex'ом авто-ack (SPEC T054,
    AC-1) и обязан оставаться байт-в-байт прежним."""
    base = (f"{row['task_id']}: lease сессии {row['session_id']} "
           f"мёртв (pid {row['pid']} на {row['hostname']}) — следующий "
           f"approve/auto перехватит lease сам, release не требуется")
    t = doctor.store.get_task(conn, row["task_id"])
    role = doctor.config.STATE_ROLE.get(t["state"], t["state"])
    parts = [base, f"роль {role}"]
    last_start = doctor._last_start_step(steps)
    if last_start is not None:
        parts.append(f"шаг {last_start['id']} (старт {last_start['ts']})")
    if steps:
        last = steps[-1]
        parts.append(f"последнее событие: {last['action']} ({last['ts']})")
    return ", ".join(parts)


def check_leases(conn) -> list[doctor.Check]:
    """Требование 11 (T044)/5 (01M1G...): lease с мёртвым pid НА ЭТОМ host
    — incident-алерт, по аналогии с `check_orphans`. Чужой host не
    проверяется — pid без доступа к его процессной таблице нельзя ни
    подтвердить, ни опровергнуть.

    Анти-race (AC-9): «мёртв» на первом снимке — не окончательный вердикт,
    пока не подтверждён вторым снимком после `LEASE_DEAD_RECHECK_SEC` —
    ловит гонку между pid'ами двух соседних шагов ОДНОЙ сессии (шаг A уже
    завершился, шаг B ещё не стартовал).

    Каждый подтверждённо мёртвый lease заодно реконит осиротевший шаг
    задачи (AC-7/AC-8) — `doctor.check_leases` уже владеет и мёртвым pid,
    и строкой `leases` в одном месте (SPEC, «Материалы»).

    Авто-ack (SPEC T054, требование 1) зовётся на каждом прогоне, не
    только когда найден свежий мёртвый lease — иначе алерт прошлого
    прогона не закроется в прогоне, где условие уже снято, но новых
    находок нет.
    """
    host = socket.gethostname()
    rows = doctor.store.all_leases(conn)
    candidates = [row for row in rows
                 if row["hostname"] == host and not doctor.liveness._pid_alive(row["pid"])]
    dead = []
    for row in candidates:
        time.sleep(doctor.LEASE_DEAD_RECHECK_SEC)
        if not doctor.liveness._pid_alive(row["pid"]):
            dead.append(row)

    if not dead:
        results = [doctor.Check("leases", "ok", "нет lease с мёртвым pid на этом host")]
    else:
        results = []
        for row in dead:
            steps = doctor.store.task_steps(conn, row["task_id"])
            doctor._reconcile_orphaned_step(conn, row["task_id"], row["session_id"], steps)
            # Сообщение алерта — прежний формат байт-в-байт (не FAIL-строка
            # `Check` ниже): `_LEASE_ALERT_RE`/`_lease_alert_live` разбирают
            # именно его для авто-ack, менять его означало бы сломать AC-1
            # SPEC T054.
            message = (f"{row['task_id']}: lease сессии {row['session_id']} "
                      f"мёртв (pid {row['pid']} на {row['hostname']})")
            doctor.alerts.raise_alert(conn, doctor.store.task_target(conn, row["task_id"]),
                              "incident", "doctor.leases", message)
            results.append(doctor.Check("leases", "fail",
                                 doctor._lease_fail_detail(conn, row, steps)))

    rows_by_task = {row["task_id"]: row for row in rows}
    doctor._auto_ack_gone(conn, "doctor.leases",
                  lambda msg: doctor._lease_alert_live(msg, rows_by_task))
    return results


def check_merge_lock(conn) -> list[doctor.Check]:
    """SPEC T053, требование 4: мёртвый держатель мьютекса merge (протухший
    heartbeat/неживой pid) не блокирует merge навечно — `merge_lock.acquire`
    сам перешагивает такой замок при следующем взятии; эта проверка лишь
    делает факт видимым Оператору, тем же приёмом, что `check_leases`
    (требование 11 T044, на которую и ссылается требование 4). Чужой host
    не проверяется — та же причина, что у `check_leases`.

    Авто-ack (SPEC T054, требование 2) — как у `check_leases`: зовётся на
    каждом прогоне перед `return`, не только когда найден свежий мёртвый
    держатель.
    """
    row = doctor.store.merge_lock_row(conn)
    if row is None:
        result = [doctor.Check("merge-lock", "ok", "мьютекс merge свободен")]
    elif row["hostname"] != socket.gethostname():
        result = [doctor.Check("merge-lock", "ok",
                        f"мьютекс merge держит {row['task_id']} на чужом "
                        f"host {row['hostname']} — pid не проверяется")]
    elif doctor.liveness._pid_alive(row["pid"]):
        result = [doctor.Check("merge-lock", "ok",
                        f"мьютекс merge держит {row['task_id']} (сессия "
                        f"{row['session_id']}), pid жив")]
    else:
        message = (f"{row['task_id']}: мьютекс merge сессии {row['session_id']} "
                  f"мёртв (pid {row['pid']} на {row['hostname']})")
        doctor.alerts.raise_alert(conn, doctor.store.task_target(conn, row["task_id"]),
                           "incident", "doctor.merge_lock", message)
        result = [doctor.Check("merge-lock", "fail", message)]

    doctor._auto_ack_gone(conn, "doctor.merge_lock",
                  lambda msg: doctor._merge_lock_alert_live(msg, row))
    return result


