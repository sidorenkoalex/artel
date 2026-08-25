"""Приёмочные тесты T034: AC-9 — колонка `target` одинаковой схемы.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 6
(ревью T019): `orchestrator/store.py` определяет колонку `target`
дважды — в `SCHEMA` (свежая БД, без `DEFAULT`) и в `migrate()`
(`add_column(..., "target", "TEXT DEFAULT '<таргет догфуда>'")`).
Свежая и мигрированная база от этого получают РАЗНУЮ схему одной и
той же колонки — задача приводит их к одному виду.

Сверяется `PRAGMA table_info` колонки `target` (тип и DEFAULT) в
таблицах `tasks` и `steps` между БД, созданной `create_schema` (путь
`SCHEMA`), и БД, где `tasks`/`steps` заведены без колонки `target` и
догнаны `migrate()`.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import store  # noqa: E402

# Схема tasks/steps без колонки target — тот же минимальный набор, что
# и в LEGACY_SCHEMA у tests/test_multitarget.py (схема до мультитаргета).
LEGACY_SCHEMA = """
CREATE TABLE tasks (
  id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
  review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
  reviewed_iter INTEGER DEFAULT 0, escalated_from TEXT,
  budget_usd REAL, spent_usd REAL DEFAULT 0, budget_source TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, ts TEXT,
  actor TEXT, action TEXT, detail TEXT
);
"""


def target_column_info(conn: sqlite3.Connection, table: str) -> tuple:
    """(тип, DEFAULT) колонки `target` таблицы; None — колонки нет."""
    for row in conn.execute(f"PRAGMA table_info({table})"):
        if row["name"] == "target":
            return (row["type"], row["dflt_value"])
    return None


class Ac9TargetColumnSchemaMatchesTest(unittest.TestCase):
    """AC-9: свежая и мигрированная БД дают одинаковую схему `target`."""

    def fresh_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        store.create_schema(conn)
        return conn

    def migrated_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(LEGACY_SCHEMA)
        conn.commit()
        store.migrate(conn)
        return conn

    def test_ac9_tasks_target_column_schema_matches(self):
        fresh = target_column_info(self.fresh_db(), "tasks")
        migrated = target_column_info(self.migrated_db(), "tasks")

        self.assertIsNotNone(fresh, "колонка target отсутствует в свежей tasks")
        self.assertIsNotNone(migrated,
                             "колонка target отсутствует в мигрированной tasks")
        self.assertEqual(
            fresh, migrated,
            f"схема колонки target в tasks разошлась: свежая {fresh!r}, "
            f"мигрированная {migrated!r}")

    def test_ac9_steps_target_column_schema_matches(self):
        fresh = target_column_info(self.fresh_db(), "steps")
        migrated = target_column_info(self.migrated_db(), "steps")

        self.assertIsNotNone(fresh, "колонка target отсутствует в свежей steps")
        self.assertIsNotNone(migrated,
                             "колонка target отсутствует в мигрированной steps")
        self.assertEqual(
            fresh, migrated,
            f"схема колонки target в steps разошлась: свежая {fresh!r}, "
            f"мигрированная {migrated!r}")


if __name__ == "__main__":
    unittest.main()
