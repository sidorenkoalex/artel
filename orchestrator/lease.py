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
import sys

from . import config, liveness, store
from .session import resolve_session_id  # noqa: F401 — единая функция identity (SPEC 01M1G..., требование 1): lease.resolve_session_id остаётся тем же объектом, что и session.resolve_session_id.


def acquire(conn, task_id: str, session_id: str, *,
           same_host_ok: bool = False,
           force: bool = False) -> tuple[str | None, bool]:
    """(отказ, взят_с_нуля). `отказ` — None, если можно продолжать.

    Требования 3-5: свободен или свой session_id -> взять/продлить; чужой
    свежий (heartbeat моложе `config.LEASE_STALE_AFTER_SEC`) -> именованный
    отказ, ничего не меняется; чужой протухший -> перехват (сессия/pid/
    hostname/heartbeat переписываются на вызывающую сторону) с отдельной
    записью в журнале задачи. `взят_с_нуля` — True, только если до этого
    вызова строки не было вовсе (см. модульный докстринг про `release`).

    SPEC 01M290PS4ZXK1RCZ3PXQSXK0Y9, требование 1/AC-1: чужой lease СВОЕГО
    hostname с проверяемо мёртвым pid держателя (`liveness._pid_alive` ->
    `False`) перехватывается так же, НЕЗАВИСИМО от возраста heartbeat —
    живость на своём host проверяема мгновенно, ждать порога незачем.
    Живость не проверяется вовсе для ДРУГОГО hostname (AC-4, pid чужой
    машины не адресуем локально) и не меняет исход, если pid на своём
    host ещё жив (AC-3, отказ «подожди её» как раньше).

    Гонка двух перехватчиков одного мёртвого держателя (AC-6): проигравший
    читает строку уже ПОСЛЕ коммита победителя и видит его (живой, свежий)
    lease — сама по себе эта строка неотличима от «сессия просто честно
    работает» (её pid и правда жив, это pid вызывающего процесса). Отличие
    в том, что читал этот же вызывающий МГНОВЕНИЕМ РАНЬШЕ, ДО захвата
    блокировки транзакции (`pre_row` ниже, обычное чтение без
    `BEGIN IMMEDIATE`, поэтому конкурентно с остальными): если тогда
    строка уже была мёртвым держателем на этом host, а после входа в
    транзакцию оказалась чужой ЖИВОЙ сессией — значит, интервал между
    этими двумя чтениями и есть та самая гонка, и кто-то другой в нём уже
    перехватил тот же мёртвый lease. Тогда вместо общего «подожди её» —
    именованный отказ «lease уже перехвачен сессией …» (требование 3),
    без повторной записи и второй записи журнала. Вызывающий, чьё
    `pre_row`-чтение само застало уже перехваченный (живой) lease, честно
    получает обычный «подожди её» — он не участвовал в перехвате, а
    застал его результат (see acceptance-тест AC-6: «хотя бы один из
    проигравших», не «каждый»).

    `same_host_ok` (SPEC 01M1VBEDGMEXHVGWAH42FTDZ4X, требование 1) —
    keyword-only, дефолт `False` сохраняет поведение ВСЕХ существующих
    вызывателей `run_locked` дословно (SPEC «Не входит»: исключение из
    отказа по живому lease распространяется только на `budget`, который
    один во всём пакете передаёт `True`). При `True` живой чужой lease
    ТОГО ЖЕ hostname не отказывает и НЕ перехватывается (строка чужой
    сессии остаётся как есть — это не взятие lease, а разрешение
    работать параллельно с ним): `(None, False)`. Живой чужой lease
    ДРУГОГО hostname отказывает всегда, независимо от `same_host_ok`
    (SPEC AC-4, инцидент 02.09.2026 — «другой Оператор физически» не
    исключение).

    Ветка «своя сессия» (SPEC 01M2B6JWGS9HMR9XZJBASXVNSY, требование 1)
    — тем же приёмом, что и ветка «чужая сессия» ниже: держатель СВОЕЙ
    сессии под ДРУГИМ pid'ом, который ещё жив (`liveness._pid_alive`) —
    не продление, а либо `same_host_ok=True` (`(None, False)` без
    мутации строки, AC-2 — та же семантика «разрешить параллельно», что
    и для чужой сессии выше), либо именованный отказ «ведёт процесс …
    этой же сессии» (AC-1), либо `force=True` перешагивает отказ и
    перезаписывает строку (AC-5, тот же приоритет `force`, что и ниже).
    Держатель своей сессии под ТЕМ ЖЕ pid'ом (тот же процесс, продление,
    AC-4) и держатель своей сессии с МЁРТВЫМ pid'ом (перехват, AC-3) —
    поведение не меняется вовсе: ровно то, что и было до этой задачи.

    `force=True` (SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P, AC-10; используется
    ТОЛЬКО `kill`) перешагивает именованный отказ «сессия свежая» — kill
    switch обязан прерывать работу немедленно, включая свежий lease
    живого отвязанного цикла, а не ждать её (SPEC требование 6), приоритетнее
    `same_host_ok` (эти два флага у разных вызывателей не пересекаются).
    Все прочие вызыватели передают `force` по умолчанию `False` —
    поведение отказа для них не меняется вовсе.

    Чтение строки (`store.lease_row`) и её запись (`insert_lease`/
    `update_lease`) выполняются внутри одной транзакции `BEGIN IMMEDIATE`:
    она берёт RESERVED-блокировку до чтения, поэтому вторая параллельная
    сессия, тоже вызвавшая `acquire()` на ту же задачу, не может ни
    прочитать, ни записать, пока первая не закоммитит (или не откатит)
    — без этого окно между чтением строки и её записью позволяло двум
    сессиям одновременно решить, что lease свободен или протух, и обеим
    уйти писать (ревью T044, итерация 1, Замечание 1).
    """
    pid, hostname = os.getpid(), socket.gethostname()
    # Обычное чтение ДО блокировки транзакции (намеренно вне
    # `BEGIN IMMEDIATE` ниже) — снимок «что я видел перед тем, как
    # решить, перехватывать ли мёртвого держателя» для отличения AC-6
    # от честного «сессия только что легитимно продлила свой lease»
    # (см. докстринг выше, абзац про гонку).
    pre_row = store.lease_row(conn, task_id)
    pre_dead_on_own_host = (pre_row is not None
                            and pre_row["hostname"] == hostname
                            and not liveness._pid_alive(pre_row["pid"]))
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = store.lease_row(conn, task_id)
        if row is None:
            store.insert_lease(conn, task_id, session_id, pid, hostname, store.now())
            # AC-4 (SPEC 01M1G...): захват СВОБОДНОГО lease — тоже событие
            # журнала, не только перехват протухшего чужого ниже.
            store.journal(conn, task_id, "lease", "lease взят",
                         f"взят сессией {session_id}", session_id=session_id)
            return None, True
        if row["session_id"] == session_id:
            if row["pid"] == pid:
                store.update_lease(conn, task_id, session_id, pid, hostname, store.now())
                return None, False
            if not force and liveness._pid_alive(row["pid"]):
                if same_host_ok:
                    return None, False
                return _own_session_live_holder_refusal(conn, task_id, row["pid"]), False
            store.update_lease(conn, task_id, session_id, pid, hostname, store.now())
            return None, False
        age = liveness._age_seconds(row["heartbeat_ts"])
        dead_on_own_host = (row["hostname"] == hostname
                            and not liveness._pid_alive(row["pid"]))
        if not force and age <= config.LEASE_STALE_AFTER_SEC:
            if same_host_ok and row["hostname"] == hostname:
                return None, False
            # SPEC 01M290PS4ZXK1RCZ3PXQSXK0Y9, требование 1/AC-1: держатель
            # на ЭТОМ host с мёртвым pid — перехват немедленно, не дожидаясь
            # протухания heartbeat (`same_host_ok` выше уже забрал случай
            # разрешённой параллельной работы — он приоритетнее; сюда
            # попадает только явный отказ либо перехват мёртвого держателя).
            if not dead_on_own_host:
                # AC-6: `pre_row` (снятый ДО этой блокировки) уже видел
                # мёртвого держателя на этом host, а сейчас (внутри
                # блокировки) держатель — другая, живая сессия — значит,
                # кто-то перехватил тот же мёртвый lease в промежутке
                # между этими двумя чтениями. Именованный отказ отличает
                # это от честного «сессия сама продлила свежий lease».
                if pre_dead_on_own_host and row["session_id"] != pre_row["session_id"]:
                    refusal = (f"[{task_id}] lease уже перехвачен сессией "
                              f"{row['session_id']} — перехват мёртвого "
                              f"держателя {pre_row['session_id']} уже "
                              f"выполнен, повторный перехват не нужен")
                    return refusal, False
                refusal = (f"[{task_id}] задачу ведёт сессия {row['session_id']} "
                          f"с host {row['hostname']}, heartbeat {int(age)} сек "
                          f"назад — подожди её или разберись, что с ней")
                return refusal, False
        # AC-5: причина перехвата — «pid мёртв», если прежний держатель на
        # ЭТОМ host и его pid проверяемо мёртв (тот же приём различения
        # «свой/чужой host», которым уже пользуется `doctor.check_leases`);
        # иначе (чужой host — pid непроверяем, либо pid ещё жив) причина
        # остаётся прежней «heartbeat протух» — триггер перехвата (возраст
        # heartbeat выше) не меняется, меняется только текст причины.
        if force and age <= config.LEASE_STALE_AFTER_SEC:
            cause = "kill switch (принудительно, сессия ещё свежая)"
        elif dead_on_own_host:
            cause = f"pid держателя мёртв (pid {row['pid']})"
        else:
            cause = (f"heartbeat протух ({int(age)} сек > порог "
                     f"{config.LEASE_STALE_AFTER_SEC})")
        detail = (f"lease перехвачен: {cause} у сессии {row['session_id']} "
                 f"({row['hostname']}) — перехвачен сессией {session_id}")
        store.update_lease(conn, task_id, session_id, pid, hostname, store.now())
        store.journal(conn, task_id, "lease", "lease перехвачен", detail,
                     session_id=session_id)
        return None, False
    finally:
        if conn.in_transaction:
            conn.rollback()


def _own_session_live_holder_refusal(conn, task_id: str, holder_pid: int) -> str:
    """Текст отказа AC-1 (SPEC 01M2B6JWGS9HMR9XZJBASXVNSY, требование 1):
    своя сессия уже держит lease под другим, живым pid'ом. Роль/шаг
    держателя — той же информацией, что уже подмешивает
    `warn_foreign_live` (`runner.step_role`, отложенный импорт во
    избежание цикла на уровне модуля), необязательной добавкой к
    отказу — «действие держателя, если известно» (SPEC)."""
    from . import runner
    t = store.get_task(conn, task_id)
    role = runner.step_role(t)
    action = f" ({role}, шаг {t['state']})" if role is not None else ""
    return (f"[{task_id}] задачу прямо сейчас ведёт процесс {holder_pid} "
           f"этой же сессии{action} — дождись завершения шага либо "
           f"artel.py stop {task_id}")


def release(conn, task_id: str, session_id: str) -> None:
    """Освобождает lease, взятый С НУЛЯ этой сессией (см. модульный докстринг)."""
    store.release_lease(conn, task_id, session_id)


def release_any(conn, task_id: str, actor: str, action: str) -> str | None:
    """Снимает lease задачи независимо от текущего держателя и журналирует
    СНИМАЮЩУЮ (вызывающую) identity, а не identity прежнего держателя
    (SPEC 01M1G..., требование 3, AC-6: снятие «любым путём»).

    В отличие от `release()` выше (отпускает только «своё», взятое с нуля
    этим же вызовом) и `run_locked` (который её и зовёт) — нужна путям,
    для которых lease не является «своим» настолько строго: `kill`
    (`orchestrator/cleanup.py`) и успешное закрытие задачи (`done`,
    `orchestrator/fsm_merge_gate.py`) обязаны снять ЛЮБОЙ lease задачи,
    даже удерживаемый чужой или уже продлённой (не «с нуля» этим же
    вызовом) сессией.

    `store.journal` зовётся БЕЗ явного `session_id` — дефолтный резолв
    внутри неё (`session.resolve_session_id`) и есть identity ВЫЗЫВАЮЩЕЙ
    стороны, единый источник требования 1. Возвращает detail-строку,
    только если что-то реально снято: строка могла уже сменить держателя
    между чтением и удалением (перехват другой сессией) — тот же приём
    защиты от гонки, что уже применяет `release.cmd_release`; в этом
    случае ни журнал, ни печать не имеют права заявлять успех устаревшим
    чтением.
    """
    row = store.lease_row(conn, task_id)
    if row is None:
        return None
    removed = store.release_lease(conn, task_id, row["session_id"])
    if not removed:
        return None
    detail = (f"session_id={row['session_id']}, pid={row['pid']}, "
             f"hostname={row['hostname']}")
    store.journal(conn, task_id, actor, action, detail)
    return detail


def foreign_live_lease(conn, task_id: str, session_id: str):
    """Строка `leases`, если она принадлежит ДРУГОЙ сессии и «жива» (SPEC
    01M1NEEYSP0QWPMXHG0BK591M7, требование 1): heartbeat не старше
    `config.LEASE_STALE_AFTER_SEC` И pid адресуем — иначе `None` (lease
    нет, lease свой, либо чужой мёртв/протух).

    Адресуемость pid проверяется, только если держатель на ЭТОМ host —
    тот же приём различения «свой/чужой host», которым уже пользуются
    `acquire` выше, `catalog._lease_holder_suffix` и
    `pause.cmd_pause_now` (REVIEW.md, замечание R1-F1): pid чужого host
    нельзя ни подтвердить мёртвым, ни опровергнуть локальной таблицей
    процессов, поэтому он молча считается «жив», раз heartbeat свежий —
    иначе межхостовый живой lease (ровно инцидент 02.09.2026 из
    «Контекст» SPEC) молчал бы, а pid чужого host, случайно совпавший с
    PID-ом реального локального процесса, ложно считался бы проверенным.
    """
    row = store.lease_row(conn, task_id)
    if row is None or row["session_id"] == session_id:
        return None
    age = liveness._age_seconds(row["heartbeat_ts"])
    if age > config.LEASE_STALE_AFTER_SEC:
        return None
    if row["hostname"] == socket.gethostname() and not liveness._pid_alive(row["pid"]):
        return None
    return row


def warn_foreign_live(conn, task_id: str, session_id: str) -> None:
    """Предупреждение о чужом живом lease перед выполнением `pause`/
    `release` (SPEC 01M1NEEYSP0QWPMXHG0BK591M7, требования 1, 3):
    печатает держателя, числовой возраст heartbeat и роль/шаг задачи,
    если роль известна (`runner.step_role`), ДО тела вызывающей команды,
    дублирует тем же событием журнала — с `session_id` ДЕРЖАТЕЛЯ
    (требование 3 явно называет его, не текущую сессию). Не блокирует и
    не запрашивает подтверждения — вызывающая команда выполняется дальше
    как обычно (требование 1).

    Отложенный импорт `runner` (не на уровне модуля): `orchestrator/
    runner.py` на уровне модуля импортирует `lease` — обратный импорт на
    уровне модуля был бы циклом (тот же приём, что `pause.cmd_pause_now`
    уже применяет к `runner` по той же причине).
    """
    row = foreign_live_lease(conn, task_id, session_id)
    if row is None:
        return
    age = int(liveness._age_seconds(row["heartbeat_ts"]))
    from . import runner
    t = store.get_task(conn, task_id)
    role = runner.step_role(t)
    role_part = f", role={role}, step={t['state']}" if role is not None else ""
    detail = (f"session_id={row['session_id']}, pid={row['pid']}, "
             f"hostname={row['hostname']}, heartbeat {age} сек назад"
             f"{role_part}")
    print(f"[{task_id}] ВНИМАНИЕ: задачу прямо сейчас ведёт другая сессия "
         f"({detail}) — она может активно работать над задачей; "
         f"предупреждение не блокирует выполнение")
    store.journal(conn, task_id, "operator",
                 "чужой живой lease: предупреждение", detail,
                 session_id=row["session_id"])


def run_locked(conn, task_id: str, session_id: str | None, body,
               *, on_refusal: str = "exit", same_host_ok: bool = False,
               force: bool = False):
    """Общая точка обвязки мутирующих команд задачи (SPEC T057, требование
    2): `resolve_session_id` -> `acquire` -> отказ -> `body(sid)` ->
    `release`-если-`fresh` в `finally`. Прежде эта пятишаговая связка была
    дословно продублирована в восьми вызывателях (CR-2026-08-28-4).

    `body` принимает уже разрешённый `session_id` и исполняется, только
    если `acquire()` не отказал; возврат `run_locked` — то же, что вернул
    `body`, либо `None` при отказе с `on_refusal="print"`.

    `on_refusal` — канал отказа не унифицирован между прежними 8 копиями
    (SPEC требование 4) и остаётся параметром, а не константой:
    `"exit"` (умолчание, approve/reject/run/budget/kill/workspace) —
    `sys.exit(refusal)` тем же текстом, что и раньше, без захода в тело;
    `"print"` (advance/auto) — печатает отказ и возвращает `None`, не
    бросая исключение, — эти два вызывателя сами решают исход отказанного
    пути (`False`/пустой возврат), а не проваливаются наружу через
    `SystemExit`.

    `same_host_ok` — пробрасывается в `acquire()` без изменений (см. её
    докстринг); дефолт `False` сохраняет поведение всех вызывателей, кроме
    `budget.cmd_budget` (SPEC 01M1VBEDGMEXHVGWAH42FTDZ4X, требование 1).

    `force` — пробрасывается в `acquire()` без изменений (см. её докстринг);
    дефолт `False` сохраняет поведение всех вызывателей, кроме `kill`
    (SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P, требование 6).
    """
    sid = resolve_session_id(session_id)
    refusal, fresh = acquire(conn, task_id, sid, same_host_ok=same_host_ok,
                             force=force)
    if refusal is not None:
        if on_refusal == "exit":
            sys.exit(refusal)
        print(refusal)
        return None
    try:
        return body(sid)
    finally:
        if fresh:
            release(conn, task_id, sid)


def is_live(conn, task_id: str) -> bool:
    """Есть ли СЕЙЧАС живой (heartbeat не протухший) lease задачи —
    независимо от того, чья это сессия (SPEC 01M1VBEDGMEXHVGWAH42FTDZ4X,
    требование 1, AC-2/AC-10): `budget.cmd_budget` читает это ДО
    `run_locked`, чтобы отличить «меняю потолок во время активного шага
    роли (своего или чужого — auto держит lease весь цикл)» от обычного
    вызова без какой-либо активной работы над задачей. Никогда не
    мутирует строку — чистое чтение, тем же приёмом, что и
    `foreign_live_lease` (см. её докстринг про адресуемость pid: здесь
    она не нужна, вопрос не «доступен ли ДЕРЖАТЕЛЬ», а «идёт ли шаг
    прямо сейчас», а протухший heartbeat уже отвечает на него сам по
    себе)."""
    row = store.lease_row(conn, task_id)
    if row is None:
        return False
    return liveness._age_seconds(row["heartbeat_ts"]) <= config.LEASE_STALE_AFTER_SEC
