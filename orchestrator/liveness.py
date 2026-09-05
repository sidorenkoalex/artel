"""Возраст heartbeat и адресуемость pid — общие для lease/merge_lock/doctor.

Дедупликация находок CR-2026-08-28-3/4 (docs/audits/code-revision-2026-08-28.md,
tasks/T057/SPEC.md): `_age_seconds` была байт-в-байт продублирована в
`lease.py`/`merge_lock.py`, `_pid_alive` — в `doctor.py`/`merge_lock.py`.
Единственные определения — здесь; `lease.py`/`merge_lock.py`/`doctor.py`
импортируют модуль и зовут `liveness._age_seconds`/`liveness._pid_alive`.

Лист графа импортов (только stdlib) — ни один из трёх модулей выше не
становится зависим от чужого слоя ради общего хелпера.

`terminate_process_group` (SPEC 01M1PNBSHR2PMFECMP7C204MF1, требование 2)
— тот же общий приём для ЧЕТЫРЁХ путей (`runner` на таймауте,
`cleanup.cmd_kill`, `pause.cmd_pause_now`, `release.cmd_release`,
`doctor` под `--fix`), по образцу `pause._terminate_pid` для одиночного
pid, но по группе целиком (`os.killpg`) — потомок, заведённый ролью
через `pytest`/`unittest`, не пересиживает ни один из этих путей.
"""
import os
import signal
import subprocess
import time
from datetime import datetime, timezone

# Грейс между SIGTERM и эскалацией до SIGKILL для группы процессов —
# тот же порядок величины, что `pause.TERMINATE_GRACE_SEC`/
# `TERMINATE_POLL_SEC` уже используют для одиночного pid (T074).
GROUP_TERMINATE_GRACE_SEC = 3.0
GROUP_TERMINATE_POLL_SEC = 0.05


def _age_seconds(heartbeat_ts: str) -> float:
    ts = datetime.strptime(heartbeat_ts, "%Y-%m-%d %H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds()


def _pid_alive(pid: int) -> bool:
    """`os.kill(pid, 0)` не шлёт сигнал, только проверяет адресуемость:
    `ProcessLookupError` — процесса нет, `PermissionError` — есть, но чужой
    (всё равно жив)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _group_member_count(pgid: int) -> int:
    """Число процессов, прямо сейчас числящихся в группе `pgid` (`ps -g`
    — переносимо между BSD/macOS и Linux `ps`, в отличие от `/proc`,
    которого на macOS нет). 0 — группа пуста/уже не существует, либо
    `ps` не ответил (тихая деградация, тот же приём, что и у остальных
    git/OS-примитивов пульта)."""
    try:
        res = subprocess.run(["ps", "-o", "pid=", "-g", str(pgid)],
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return 0
    if res.returncode != 0:
        return 0
    return len([line for line in res.stdout.splitlines() if line.strip()])


def terminate_process_group(
        pgid: int, grace_sec: float = GROUP_TERMINATE_GRACE_SEC,
        poll_sec: float = GROUP_TERMINATE_POLL_SEC) -> int:
    """SIGTERM всей группе `pgid`; членам, не завершившимся за `grace_sec`,
    — SIGKILL (SPEC 01M1PNBSHR2PMFECMP7C204MF1, требование 2). Возвращает
    число процессов группы НА МОМЕНТ сигнала (AC-7: «число снятых
    процессов группы») — считать точнее поздно, они уже мертвы либо в
    процессе завершения.

    Никогда не бьёт СОБСТВЕННУЮ группу вызывающего процесса — `pgid`,
    случайно совпавший с ней, был бы самоубийством пульта/doctor
    посреди работы, а не снятием чужого зависшего шага.

    `ProcessLookupError`/`PermissionError` на `killpg` — группа уже
    пуста либо часть её членов недоступна вызывающему; оба — тихая
    деградация (не крах), тем же приёмом, что `pause._terminate_pid`
    уже применяет к одиночному pid.
    """
    if pgid == os.getpgid(0):
        return 0
    count = _group_member_count(pgid)
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return count
    deadline = time.monotonic() + grace_sec
    while time.monotonic() < deadline and _group_member_count(pgid) > 0:
        time.sleep(poll_sec)
    if _group_member_count(pgid) > 0:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    return count


def group_kill_detail(pgid: int, count: int) -> str:
    """Текст журнала группового снятия (SPEC 01M1PNBSHR2PMFECMP7C204MF1,
    AC-7) — общая формулировка для всех четырёх путей требования 2."""
    return f"группа процессов (pgid={pgid}) снята: {count} процесс(ов)"
