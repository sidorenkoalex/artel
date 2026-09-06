"""Пакет orchestrator/doctor -- сторож зависших прогонов тестов и ожидания зон.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from pathlib import Path
import os
import re
import socket

from orchestrator import doctor


# --- сторож зависших прогонов тестов --------------------------------------
# (SPEC 01M1PNBSHR2PMFECMP7C204MF1, требование 3, AC-8..AC-12/AC-15)

# `python -m unittest`/`pytest` в командной строке процесса (AC-8) — та
# же пара инструментов, что оставила шесть висящих прогонов инцидента
# 04.09 (SPEC «Контекст»).
_HUNG_TEST_CMD_RE = re.compile(r"\bpytest\b|-m\s+unittest\b")
# `ps -o etime=`: `[[дни-]часы:]минуты:секунды` (macOS/BSD и Linux —
# общий формат).
_ETIME_RE = re.compile(r"^(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+)$")


def _etime_to_seconds(etime: str) -> float | None:
    match = doctor._ETIME_RE.match(etime.strip())
    if match is None:
        return None
    days, hours, minutes, seconds = match.groups()
    total = int(minutes) * 60 + int(seconds)
    if hours:
        total += int(hours) * 3600
    if days:
        total += int(days) * 86400
    return float(total)


def _running_processes() -> list[tuple[int, float, str]]:
    """(pid, возраст в секундах, командная строка) всех процессов машины;
    пустой список — `ps` не ответил (тихая деградация, тот же приём, что
    и у остальных OS-примитивов доктора). `-ww` — без обрезки длинной
    командной строки (BSD `ps`, macOS)."""
    try:
        res = doctor.subprocess.run(["ps", "-axww", "-o", "pid=,etime=,command="],
                             capture_output=True, text=True, timeout=10)
    except (OSError, doctor.subprocess.TimeoutExpired):
        return []
    if res.returncode != 0:
        return []
    rows = []
    for line in res.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        pid_s, etime_s, command = parts
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        age = doctor._etime_to_seconds(etime_s)
        if age is None:
            continue
        rows.append((pid, age, command))
    return rows


def _process_cwd(pid: int) -> str | None:
    """cwd процесса `pid` по `lsof` (`ps` его не несёт вовсе) — `None`,
    если `lsof` не ответил или процесс уже исчез."""
    try:
        res = doctor.subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, doctor.subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    for line in res.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def _hung_test_run_task_id(cwd: str) -> str | None:
    """id задачи по cwd процесса — первый сегмент относительно
    `config.WORKTREES` (тот же критерий легитимности, что и
    `_is_legit_task_worktree`); `.resolve()` на обеих сторонах — cwd,
    отданный `lsof`, разрешает симлинки ОС (`/var` -> `/private/var` на
    macOS), путь `config.WORKTREES` из песочницы теста иначе не совпал
    бы с ним побайтово."""
    try:
        rel = Path(cwd).resolve().relative_to(doctor.config.WORKTREES.resolve())
    except (ValueError, OSError):
        return None
    return rel.parts[0] if rel.parts else None


def _hung_test_run_task_lease_alive(conn, task_id: str) -> bool:
    """AC-9: «нет живого lease» — тот же критерий «мёртв», что и
    `check_leases`'s кандидаты (свой host и pid не адресуем); лизы нет
    вовсе, чужой host или pid жив — консервативно считается живым (не
    трогать чужое, если есть хоть малейшее сомнение)."""
    row = doctor.store.lease_row(conn, task_id)
    if row is None:
        return False
    if row["hostname"] != socket.gethostname():
        return True
    return doctor.liveness._pid_alive(row["pid"])


def _find_hung_test_runs(conn) -> list[dict]:
    """Кандидаты сторожа (AC-8/AC-9): `python -m unittest`/`pytest` с cwd
    внутри `.artel/worktrees/<id>`, старше `config.HUNG_TEST_RUN_AGE_SEC`,
    чья задача не держит живой lease."""
    found = []
    for pid, age, command in doctor._running_processes():
        if age < doctor.config.HUNG_TEST_RUN_AGE_SEC:
            continue
        if not doctor._HUNG_TEST_CMD_RE.search(command):
            continue
        cwd = doctor._process_cwd(pid)
        if cwd is None:
            continue
        task_id = doctor._hung_test_run_task_id(cwd)
        if task_id is None:
            continue
        if doctor._hung_test_run_task_lease_alive(conn, task_id):
            continue
        found.append({"pid": pid, "age": age, "cwd": cwd, "task_id": task_id})
    return found


_HUNG_TEST_ALERT_RE = re.compile(
    r"^зависший прогон тестов: pid (\d+), worktree .+, возраст \d+ сек$")


def _hung_test_run_alert_live(message: str) -> bool:
    match = doctor._HUNG_TEST_ALERT_RE.match(message)
    if match is None:
        return True
    return doctor.liveness._pid_alive(int(match.group(1)))


def check_hung_test_runs(conn) -> list[doctor.Check]:
    """AC-8..AC-10: только поиск и алерт — снятие живёт отдельно, под
    `doctor --fix` (`_fix_hung_test_runs`, AC-11/AC-12): тот же водораздел
    «наблюдение/действие», что `check_leases`/`_fix_dead_lease_groups`
    уже применяют к мёртвому lease (ANSWER-1, вариант B)."""
    candidates = doctor._find_hung_test_runs(conn)
    if not candidates:
        results = [doctor.Check("hung-test-runs", "ok",
                         "зависших прогонов тестов не найдено")]
    else:
        results = []
        for c in candidates:
            message = (f"зависший прогон тестов: pid {c['pid']}, worktree "
                      f"{c['cwd']}, возраст {int(c['age'])} сек")
            doctor.alerts.raise_alert(conn, doctor.store.task_target(conn, c["task_id"]),
                               "incident", "doctor.hung_test_runs", message)
            results.append(doctor.Check("hung-test-runs", "fail", message))
    doctor._auto_ack_gone(conn, "doctor.hung_test_runs", doctor._hung_test_run_alert_live)
    return results


def _fix_hung_test_runs(conn) -> None:
    """`doctor --fix` (AC-11): снимает найденные `check_hung_test_runs`
    прогоны ГРУППОЙ (лидер + реальные потомки — аналог pytest-xdist
    воркера) и пишет перечень снятых pid в алерт (не только в журнал
    задачи — «в журнал алертов», AC-11). Обычный прогон (без `--fix`,
    AC-12) сюда не заходит вовсе."""
    candidates = doctor._find_hung_test_runs(conn)
    if not candidates:
        return
    fixed = []
    for c in candidates:
        try:
            pgid = os.getpgid(c["pid"])
        except ProcessLookupError:
            continue
        count = doctor.liveness.terminate_process_group(pgid)
        fixed.append(f"{c['task_id']}: pid {c['pid']} "
                    f"({count} процесс(ов) группы)")
    if not fixed:
        return
    doctor.alerts.raise_alert(conn, None, "incident", "doctor.hung_test_runs.fix",
                       f"зависшие прогоны тестов сняты (doctor --fix): "
                       f"{'; '.join(fixed)}")
    print(f"  зависшие прогоны тестов сняты: {'; '.join(fixed)}")


def _fix_dead_lease_groups(conn) -> None:
    """`doctor --fix` (SPEC 01M1PNBSHR2PMFECMP7C204MF1, AC-6, ANSWER-1
    вариант B): остаточная группа процессов МЁРТВОГО lease — снимается
    ТОЛЬКО здесь, под флагом; `check_leases` остаётся наблюдательным
    (несёт только алерт, как и раньше, не предмет этой задачи)."""
    host = socket.gethostname()
    for row in doctor.store.all_leases(conn):
        if row["hostname"] != host or doctor.liveness._pid_alive(row["pid"]):
            continue
        if not row["pgid"]:
            continue
        count = doctor.liveness.terminate_process_group(row["pgid"])
        doctor.store.journal(conn, row["task_id"], "doctor",
                      "doctor --fix: группа процессов мёртвого lease снята",
                      doctor.liveness.group_kill_detail(row["pgid"], count))
        print(f"  [FIX] {row['task_id']}: "
              f"{doctor.liveness.group_kill_detail(row['pgid'], count)}")
def check_zone_waits(conn) -> list[doctor.Check]:
    """SPEC 01M1P9QAG65GVF69YJEV0V18D9, требование 4: задача, чей первый
    шаг developer заблокирован занятостью зоны, — видимая проверка
    doctor, по образцу `check_leases`/`check_orphans`, не только строка в
    журнале САМОЙ заблокированной задачи. Вычисление занятости берётся у
    `zone_lock.blocking_conflict` целиком — та же проверка, что не
    пускает `run`/`auto` дальше, не отдельная копия.

    Не incident-алерт (в отличие от `check_leases`): занятость зоны —
    штатное ожидание, не операционный сбой, снимается сама после мержа/
    kill занявшей задачи (AC-6) или явной командой Оператора (AC-7).

    Позиция в очереди (`zone_lock.queue_position`, R1-F3, REVIEW.md
    итерация 1) — в детали, только когда конкурентов по ЭТОЙ зоне больше
    одного.
    """
    blocked = []
    for row in doctor.store.all_tasks(conn):
        if row["state"] != "in_dev":
            continue
        conflict = doctor.zone_lock.blocking_conflict(conn, row["id"], row)
        if conflict is None:
            continue
        path, occupier_id, occupier_state = conflict
        position, total = doctor.zone_lock.queue_position(conn, row["id"], path)
        queue = f", очередь {position}/{total}" if total > 1 else ""
        blocked.append(doctor.Check(
            "zone-waits", "warn",
            f"{row['id']} ждёт зоны {path} — занята {occupier_id} "
            f"({occupier_state}){queue}"))
    if not blocked:
        return [doctor.Check("zone-waits", "ok", "нет задач, ожидающих зоны")]
    return blocked


