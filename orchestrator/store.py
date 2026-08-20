"""Состояние задач: БД, миграции схемы, журнал шагов, смена состояния."""
import sqlite3
import sys
from datetime import datetime, timezone

from . import config


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def db() -> sqlite3.Connection:
    config.DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(config.DB)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Догоняет схему БД, созданной прошлой версией (Фаза 0: без alembic)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)")}
    if not cols:
        return
    if "reviewed_iter" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN reviewed_iter INTEGER DEFAULT 0")
        conn.commit()
    if "escalated_from" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN escalated_from TEXT")
        conn.commit()
    if "budget_source" not in cols:
        # NULL в старых строках — «потолок никем не задан», то есть дефолт:
        # значение из SPEC применится к ним на общих основаниях.
        conn.execute("ALTER TABLE tasks ADD COLUMN budget_source TEXT")
        conn.commit()


def journal(conn, task_id: str, actor: str, action: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO steps (task_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
        (task_id, now(), actor, action, detail),
    )
    conn.commit()


def set_state(conn, task_id: str, state: str, actor: str, detail: str = "") -> None:
    conn.execute(
        "UPDATE tasks SET state=?, updated_at=? WHERE id=?", (state, now(), task_id)
    )
    journal(conn, task_id, actor, f"state -> {state}", detail)
    print(f"[{task_id}] -> {state}" + (f"  ({detail})" if detail else ""))


def get_task(conn, task_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        sys.exit(f"Задача {task_id} не найдена. `status` покажет существующие.")
    return row
