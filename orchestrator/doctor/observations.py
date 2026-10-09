"""Diagnostics for observation process ownership and obsolete Codex hooks."""

import os
from pathlib import Path

from orchestrator import config, watch

_UNATTENDED_STATES = ("dead", "stale")


def check_observations(conn):
    from orchestrator import doctor
    rows = conn.execute("SELECT * FROM observations WHERE state='active'").fetchall()
    if not rows:
        return doctor.Check("observations", "ok", "активных наблюдений нет")
    states = {row["id"]: watch.observation_process_state(row) for row in rows}
    detail = ", ".join(f"{observation_id}: {state}"
                       for observation_id, state in states.items())
    # Мёртвый PID и протухшая связь — дозора нет, хотя наблюдение активно:
    # новые `run`/`auto` получат отказ, события никто не выводит.
    if any(state in _UNATTENDED_STATES for state in states.values()):
        return doctor.Check("observations", "warn",
                            detail + "; перезапустите watch --observation <ID>")
    return doctor.Check("observations", "ok", detail)


def check_codex_background_hooks():
    from orchestrator import doctor
    locations = (config.ROOT / ".codex" / "hooks.json",
                 Path(os.path.expanduser("~")) / ".codex" / "hooks.json")
    found = []
    for path in locations:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if "guard-artel-bg" in content:
            found.append(str(path))
    if found:
        return doctor.Check("codex-background-hook", "warn",
                            "guard-artel-bg найден: " + ", ".join(found) +
                            "; используйте hook-migrate")
    return doctor.Check("codex-background-hook", "ok", "guard-artel-bg не найден")
