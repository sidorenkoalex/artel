"""Возраст heartbeat и адресуемость pid — общие для lease/merge_lock/doctor.

Дедупликация находок CR-2026-08-28-3/4 (docs/audits/code-revision-2026-08-28.md,
tasks/T057/SPEC.md): `_age_seconds` была байт-в-байт продублирована в
`lease.py`/`merge_lock.py`, `_pid_alive` — в `doctor.py`/`merge_lock.py`.
Единственные определения — здесь; `lease.py`/`merge_lock.py`/`doctor.py`
импортируют модуль и зовут `liveness._age_seconds`/`liveness._pid_alive`.

Лист графа импортов (только stdlib) — ни один из трёх модулей выше не
становится зависим от чужого слоя ради общего хелпера.
"""
import os
from datetime import datetime, timezone


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
