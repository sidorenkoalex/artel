"""Команда `pause`/`resume`: штатная приостановка задачи (SPEC T070).

Пауза не заводит нового состояния FSM (требование 4, AC-6) — пометка
живёт колонкой `tasks.paused`, не файлом в рабочем каталоге задачи
(требование 4, AC-7): рабочих копий несколько, БД — единственный
источник правды, той же логикой, что уже несут lease
(`orchestrator/lease.py`) и merge-lock.

Пометку проверяет только `runner._cmd_run` перед стартом агентного шага
(требование 2) — `kill` (`orchestrator/cleanup.py`), `approve`/`reject`
и `advance` (`orchestrator/fsm.py`) её не читают вовсе (требования 6-8):
они не заходят в эту точку, поэтому исполняются на приостановленной
задаче как обычно без единой правки в их модулях.

`cmd_pause`/`cmd_resume` не берут lease задачи и не проходят лимитер
параллельных задач — по тому же доводу, что и `orchestrator/
release.py::cmd_release`: они не мутируют шаг задачи, только пометку.

`cmd_pause` (SPEC 01M1NEEYSP0QWPMXHG0BK591M7) печатает предупреждение
ДО выполнения, если задачу прямо сейчас ведёт ЧУЖАЯ живая сессия
(`lease.warn_foreign_live`) — предупреждение только информирует, само
выполнение `pause` не блокирует и подтверждения не запрашивает.

`cmd_pause_now` (SPEC T074) — жёсткий вариант поверх того же модуля:
ставит ту же пометку (требование 1), но, если задача сейчас держит
живой lease на этой же машине (роль агентная, `store.lease_row`
адресует живой pid), прерывает его процесс, чекпоинтит WIP worktree
(механика T041/T059, `orchestrator/checkpoint.py::commit_pause_now_checkpoint`)
и снимает lease тем же приёмом, что `orchestrator/release.py::cmd_release`.
Она тоже не берёт lease задачи и не проходит лимитер — по тому же
доводу: действует НАД чужим держателем, не мутирует шаг своей же
сессией.
"""
import os
import signal
import socket
import time
from pathlib import Path

from . import agent_log, checkpoint, lease, liveness, spend, store
from .session import resolve_session_id

# Опрос после SIGTERM перед эскалацией до SIGKILL (требование 1: «процесс
# агента корректно завершается» — короткая пауза на штатное завершение,
# не мгновенный SIGKILL без шанса на graceful shutdown).
TERMINATE_GRACE_SEC = 3.0
TERMINATE_POLL_SEC = 0.05

# Action журнальной записи, которой `runner._cmd_run` отказывает СТАРТУ шага
# из-за паузы (см. её единственное место записи в `orchestrator/runner.py`).
# Строка — общий узел между записью и разбором отказа в `orchestrator/
# auto.py`: цикл узнаёт, что именно ЭТОТ вызов `cmd_run` отказал по паузе, а
# не приписывает ей отказ по независимому текущему опросу `is_paused`
# (REVIEW.md T070, итерация 2, замечание 1 — опрос текущего состояния путал
# паузу с одновременным отказом по бюджету/лимиту параллельных задач).
REFUSAL_ACTION = "run отклонён: задача на паузе"


def is_paused(task_row) -> bool:
    """Пометка паузы задачи — из строки `tasks` БД, не из файла (AC-7)."""
    return bool(task_row["paused"])


def cmd_pause(task_id: str) -> None:
    """Ставит пометку паузы: следующий агентный шаг `run`/`auto` не
    начнётся (AC-1), уже идущий шаг не прерывается (AC-3).

    Задача, уже приостановленная, — не ошибка (требование 9, AC-12):
    понятное сообщение вместо повторной записи в БД и журнал — молчаливый
    no-op, а не вторая запись о том же факте.

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до `update_task`/журнала — иначе `pause <префикс>` печатала бы успех,
    физически не меняя ни одной строки (REVIEW T094 итерация 1, замечание
    1).

    Предупреждение о чужом живом lease (SPEC 01M1NEEYSP0QWPMXHG0BK591M7,
    требование 1) печатается ЗДЕСЬ же, до веток "уже на паузе"/пометки —
    факт, что задачу ведёт другая сессия, верен независимо от того,
    окажется ли сам `pause` no-op'ом.
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.warn_foreign_live(conn, task_id, resolve_session_id())
    t = store.get_task(conn, task_id)
    if is_paused(t):
        print(f"[{task_id}] уже на паузе — pause ничего не делает")
        return
    store.update_task(conn, task_id, paused=1)
    store.journal(conn, task_id, "operator", "pause",
                  "задача приостановлена: следующий агентный шаг не начнётся")
    print(f"[{task_id}] приостановлена: следующий run/auto не начнёт "
          f"агентный шаг, пока не выполнишь `artel.py resume {task_id}`")


def cmd_resume(task_id: str) -> None:
    """Снимает пометку паузы (AC-4); сама шаг не запускает и `advance` не
    зовёт (AC-5).

    Задача, не бывшая на паузе, — не ошибка (требование 9, AC-13):
    понятное сообщение, без записи в журнал (нечего снимать — не новый
    факт).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    тем же доводом, что у `cmd_pause` (REVIEW T094 итерация 1, замечание
    1).
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    t = store.get_task(conn, task_id)
    if not is_paused(t):
        print(f"[{task_id}] не была на паузе — resume ничего не делает")
        return
    store.update_task(conn, task_id, paused=0)
    store.journal(conn, task_id, "operator", "resume", "пауза снята")
    print(f"[{task_id}] пауза снята: run/auto снова начинают агентные шаги")


def _terminate_pid(pid: int) -> None:
    """`SIGTERM`, эскалация до `SIGKILL`, если процесс не завершился за
    `TERMINATE_GRACE_SEC` (требование 1: «процесс агента корректно
    завершается»). Не `waitpid` — адресованный процесс НЕ потомок этого
    (требование 2: «в другом процессе той же машины», см. `_sandbox.py`,
    «Допущения интерфейса»), только опрос адресуемости pid
    (`liveness._pid_alive`).
    """
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + TERMINATE_GRACE_SEC
    while time.monotonic() < deadline and liveness._pid_alive(pid):
        time.sleep(TERMINATE_POLL_SEC)
    if liveness._pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _account_partial_cost(conn, task_id: str, role: str) -> None:
    """Частичная стоимость прерванного шага (требование 4, AC-10) — из
    ДИСКОВОГО лога шага (`agent_log.last_agent_log`), не из памяти
    прерванного процесса (`pause --now` работает в другом процессе, её
    там никогда не было). Дальше — существующая механика T040
    (`spend.charge_missing_result`): частичная сумма токенов в журнал
    либо, при отсутствии usage-событий вовсе, алерт `spend.unknown_cost`.
    """
    log_path = agent_log.last_agent_log(task_id, role)
    if log_path == "—":
        tokens, saw_usage = 0, False
    else:
        tokens, saw_usage = spend.partial_tokens_from_log(Path(log_path))
    spend.charge_missing_result(conn, task_id, role, "pause --now",
                                "шаг прерван pause --now", tokens, saw_usage)


def cmd_pause_now(task_id: str) -> None:
    """Жёсткая пауза (SPEC T074): пометка паузы (требование 1, AC-2) +,
    если сейчас бежит агентный шаг задачи в другом процессе этой же
    машины, его прерывание — процесс завершён, WIP зачекпоинчен, lease
    снят, частичная стоимость учтена, журнал несёт всю
    последовательность (AC-1, AC-3..AC-6, AC-9..AC-11).

    Отложенный импорт `runner` (не на уровне модуля): `orchestrator/
    runner.py` на уровне модуля импортирует `pause` (нужен `_cmd_run` —
    проверка `pause.is_paused`), поэтому обратный импорт на уровне модуля
    был бы циклом; тот же приём, что `runner._cmd_run` уже применяет к
    `doctor`.

    Три пути деградации до обычного `pause` — без ошибки, с честным
    сообщением (требование 2, 6; AC-7, AC-15):
    - агентного шага сейчас нет вовсе (`runner.step_role` — `None`,
      состояние вне `config.STATE_ROLE`/`spec_writing`);
    - lease задачи не заведён (нечего адресовать);
    - lease заведён, но его процесс уже мёртв (`liveness._pid_alive`).

    Четвёртый путь — честный ОТКАЗ прерывания без деградации всей
    команды (требование 2, AC-8): lease адресует процесс на ДРУГОМ host —
    прерывание вне объёма `pause --now`. Пометка паузы всё равно
    ставится (требование 1 безусловно) — команда явно вызывает `cmd_pause`
    и в этой ветке тоже.

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до `lease_row`/чекпоинта/журнала — весь дальнейший код функции читает
    уже разрешённый `task_id` (REVIEW T094 итерация 1, замечание 1).
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    t = store.get_task(conn, task_id)

    from . import runner
    role = runner.step_role(t)
    if role is None:
        print(f"[{task_id}] агентный шаг сейчас не бежит — pause --now "
              f"деградирует до обычной pause")
        cmd_pause(task_id)
        return

    row = store.lease_row(conn, task_id)
    if row is None:
        print(f"[{task_id}] lease задачи не заведён — прерывать нечего, "
              f"pause --now деградирует до обычной pause")
        cmd_pause(task_id)
        return

    hostname = socket.gethostname()
    if row["hostname"] != hostname:
        detail = (f"lease держит {row['session_id']} на host "
                  f"{row['hostname']} (эта машина — {hostname}) — "
                  f"прерывание процессов на другом host вне объёма "
                  f"pause --now (SPEC T074, «Не входит»)")
        store.journal(conn, task_id, "operator",
                      "pause --now: host вне объёма", detail)
        print(f"[{task_id}] {detail}")
        cmd_pause(task_id)
        return

    if not liveness._pid_alive(row["pid"]):
        print(f"[{task_id}] lease-процесс (pid {row['pid']} на "
              f"{row['hostname']}) уже мёртв — pause --now деградирует "
              f"до обычной pause")
        cmd_pause(task_id)
        return

    detail = (f"role={role}, session_id={row['session_id']}, "
             f"pid={row['pid']}, host={row['hostname']}")
    store.journal(conn, task_id, "operator",
                  "pause --now: обнаружен бегущий шаг", detail)
    print(f"[{task_id}] бегущий шаг ({role}) найден по lease: {detail}")

    _terminate_pid(row["pid"])
    store.journal(conn, task_id, "operator",
                  "pause --now: процесс агента прерван",
                  f"pid {row['pid']} завершён сигналом ОС")
    print(f"[{task_id}] процесс pid {row['pid']} прерван")

    # Группа процессов записанного AC-2 агентного шага (SPEC
    # 01M1PNBSHR2PMFECMP7C204MF1, AC-5) — НЕ ТОЛЬКО pid держателя lease
    # выше: `_terminate_pid` снимает сам процесс лизы (обычно — процесс
    # пульта, ведущий шаг), но не его потомков в другой группе; group-kill
    # закрывает именно их (`pytest`/`unittest`, запущенные ролью).
    if row["pgid"]:
        count = liveness.terminate_process_group(row["pgid"])
        store.journal(conn, task_id, "operator",
                      "pause --now: группа процессов шага снята",
                      liveness.group_kill_detail(row["pgid"], count))
        print(f"[{task_id}] {liveness.group_kill_detail(row['pgid'], count)}")

    _account_partial_cost(conn, task_id, role)

    checkpoint_detail = checkpoint.commit_pause_now_checkpoint(conn, task_id, role)
    if checkpoint_detail:
        print(f"[{task_id}] {checkpoint_detail}")

    removed = store.release_lease(conn, task_id, row["session_id"])
    lease_detail = (f"session_id={row['session_id']}, pid={row['pid']}, "
                    f"host={row['hostname']}" if removed else
                    "lease уже сменил держателя — снимать было нечего")
    store.journal(conn, task_id, "operator", "pause --now: lease снят",
                  lease_detail)
    print(f"[{task_id}] lease {'снят' if removed else 'уже сменил держателя'}"
          f": {lease_detail}")

    cmd_pause(task_id)
