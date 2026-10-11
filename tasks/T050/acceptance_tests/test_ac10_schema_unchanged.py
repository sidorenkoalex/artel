"""AC-10 (tasks/T050/SPEC.md): схема БД не изменена, миграции не
добавлены.

Снимок таблиц/колонок ниже — по схеме `orchestrator/store.py` ДО этой
задачи (SPEC требование 9, «Не входит» — «изменение схемы БД / добавление
миграций»): CAS-переходы не имеют права добавить колонку, таблицу или
новый `ALTER TABLE`/`CREATE TABLE` в `migrate()`. Сверка — по реальной БД,
поднятой `store.db()` (создание схемы + миграции), не по чтению текста
`store.py`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

EXPECTED_COLUMNS = {
    "tasks": {
        "id", "title", "state", "branch", "review_iters", "accept_rejects",
        "reviewed_iter", "escalated_from", "budget_usd", "spent_usd",
        "budget_source", "target", "fixed_sha", "tests_locked_sha",
        "created_at", "updated_at",
    },
    "steps": {"id", "task_id", "target", "ts", "actor", "action", "detail"},
    "task_counters": {"target", "next_number"},
    "alerts": {"id", "target", "kind", "source", "message", "ts", "ack_ts",
              "ack_by", "ack_resolution"},
    "leases": {"task_id", "session_id", "pid", "hostname", "heartbeat_ts"},
}


class SchemaUnchangedTest(TmpRootTest):

    def test_ac10_table_and_column_set_is_unchanged(self):
        conn = store.db()
        store.create_schema(conn)

        actual_tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "name NOT LIKE 'sqlite_%'").fetchall()}
        self.assertEqual(actual_tables, set(EXPECTED_COLUMNS),
                         "набор таблиц БД изменился")

        for table, columns in EXPECTED_COLUMNS.items():
            with self.subTest(таблица=table):
                self.assertEqual(store.table_columns(conn, table), columns,
                                 f"набор колонок {table} изменился")


if __name__ == "__main__":
    unittest.main()
