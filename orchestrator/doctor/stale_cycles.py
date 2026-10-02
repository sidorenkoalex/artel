"""Пакет orchestrator/doctor -- циклы `auto`/`run` на коде старше пина.

SPEC 01M3Y75GCRESC2KDS9VPRJK4PS: отвязанный цикл `auto`/`run` загрузил
модули пульта при старте процесса и после сдвига пина исполняет прежний
код до своего завершения. `stale_cycles` — один отбор на две точки
вывода: `pin.cmd_pin_update` после успешного `merge --ff-only`
(требование 1) и проверка `check_stale_cycles` с моментом пина из
последней записи журнала «pin обновлён» (требование 3). Обе только
называют циклы и готовые команды перезапуска — сигналов процессам не
шлют, решение за Оператором (требование 2).

Отбор живёт здесь, а не в `pin.py`: `pin.py` — плотницкий модуль без
прямых вызовов `subprocess` (инвариант 33), а `ps` нужен обоим потребителям.
Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import os
import socket
from datetime import datetime, timezone

from orchestrator import doctor

STALE_CYCLES_CHECK = "stale-cycles"
START_UNDETERMINED = "не удалось определить"
# Формат `ps -o lstart=` под `LC_ALL=C` — общий у BSD/macOS и procps.
_LSTART_FORMAT = "%a %b %d %H:%M:%S %Y"


def process_start_time(pid: int) -> datetime | None:
    """Время старта процесса из таблицы процессов ОС (требование 4), UTC,
    с точностью `ps` до секунды; `None` — определить не удалось (отказ
    запуска, ненулевой код, пустой или неразборчивый ответ).

    `ps` ищется по PATH, а без него — по стандартному пути: окружение
    шага роли может не нести `/bin` в PATH."""
    ps = doctor.shutil.which("ps") or "/bin/ps"
    try:
        res = doctor.subprocess.run([ps, "-o", "lstart=", "-p", str(pid)],
                                    capture_output=True, text=True, timeout=10,
                                    env={**os.environ, "LC_ALL": "C"})
    except (OSError, doctor.subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    text = " ".join((res.stdout or "").split())
    try:
        started = datetime.strptime(text, _LSTART_FORMAT)
    except ValueError:
        return None
    # `lstart` — местное время машины: наивное значение `astimezone`
    # трактует как местное.
    return started.astimezone(timezone.utc)


def _observation_args(conn, task_id: str, pid: int) -> tuple:
    """`(client, chat)` наблюдения ЭТОГО запуска — строка `observed_runs`
    и по задаче, и по pid (у задачи могли наблюдаться прежние запуски с
    другим pid); `(None, None)` — цикл не под наблюдением."""
    row = conn.execute(
        "SELECT o.client, o.chat FROM observed_runs r "
        "JOIN observations o ON o.id = r.observation_id "
        "WHERE r.task_id=? AND r.pid=? ORDER BY r.id DESC LIMIT 1",
        (task_id, pid)).fetchone()
    if row is None:
        return None, None
    return row["client"], row["chat"]


def stale_cycles(conn, pin_moment: datetime) -> list[dict]:
    """Живые циклы этой машины, чей процесс стартовал раньше `pin_moment`.

    Цикл с неопределимым временем старта входит в перечень (`started` —
    `None`): доказать, что он загрузил уже новый код, нечем."""
    host = socket.gethostname()
    cycles = []
    for lease in sorted(doctor.store.all_leases(conn), key=lambda r: r["task_id"]):
        if lease["hostname"] != host or not doctor.liveness._pid_alive(lease["pid"]):
            continue
        started = doctor.process_start_time(lease["pid"])
        if started is not None and started >= pin_moment:
            continue
        task = conn.execute("SELECT state FROM tasks WHERE id=?",
                            (lease["task_id"],)).fetchone()
        cycles.append({
            "task_id": lease["task_id"],
            "pid": lease["pid"],
            "started": started,
            "state": task["state"] if task is not None else "задачи нет в БД",
            "observation_args": doctor._observation_args(
                conn, lease["task_id"], lease["pid"]),
        })
    return cycles


def stale_cycle_lines(cycles: list[dict]) -> list[str]:
    """Строка на цикл: id, pid, время старта, состояние, команды
    перезапуска в порядке исполнения — сначала `stop`, затем `auto`."""
    lines = []
    for c in cycles:
        started = (c["started"].strftime("%Y-%m-%d %H:%M:%SZ")
                   if c["started"] is not None else START_UNDETERMINED)
        lines.append(
            f"{c['task_id']} pid {c['pid']}, старт процесса {started}, "
            f"состояние {c['state']}; перезапуск: artel.py stop "
            f"{c['task_id']}, затем "
            + doctor.cycle_hint.cycle_command("auto", c["task_id"],
                                              *c["observation_args"]))
    return lines


def check_stale_cycles(conn) -> "doctor.Check":
    row = conn.execute(
        "SELECT ts FROM steps WHERE task_id=? AND action=? "
        "ORDER BY id DESC LIMIT 1",
        (doctor.config.PIN_UPDATE_JOURNAL_TASK_ID, "pin обновлён")).fetchone()
    if row is None:
        return doctor.Check(STALE_CYCLES_CHECK, "ok",
                            "записи «pin обновлён» в журнале нет — "
                            "сверять старт циклов не с чем")
    pin_moment = datetime.strptime(row["ts"], "%Y-%m-%d %H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    cycles = doctor.stale_cycles(conn, pin_moment)
    if not cycles:
        return doctor.Check(STALE_CYCLES_CHECK, "ok",
                            f"живых циклов, стартовавших до пина {row['ts']}, "
                            "на этой машине нет")
    lines = doctor.stale_cycle_lines(cycles)
    return doctor.Check(
        STALE_CYCLES_CHECK, "warn",
        f"циклы на коде старше пина ({row['ts']}, {len(cycles)}) — "
        "перезапуск за Оператором:\n    " + "\n    ".join(lines))
