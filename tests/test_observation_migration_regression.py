"""Регрессии миграции позиций наблюдения на старых и живых БД."""

import sqlite3
import unittest

from orchestrator import schema, store


class ObservationMigrationTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        schema.create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_complete_observation_does_not_start_a_write(self):
        """Ловит мутацию: безусловный UPDATE на каждом открытии БД берёт write lock."""
        store.register_observation(self.conn, "artel", "codex", "chat", "session", [])
        statements = []
        self.conn.set_trace_callback(statements.append)

        schema.migrate(self.conn)

        self.assertFalse(any(sql.lstrip().upper().startswith("UPDATE OBSERVATIONS")
                             for sql in statements), statements)

    def test_missing_steps_table_does_not_break_migration(self):
        """Ловит мутацию: заполнение позиции запрашивает MAX(id) отсутствующей steps."""
        self.conn.execute("DROP TABLE steps")
        self.conn.execute(
            "INSERT INTO observations(id, target, client, chat, session_id, state, created_at) "
            "VALUES ('old', 'artel', 'codex', 'chat', 'session', 'active', 'now')")
        self.conn.commit()

        schema.migrate(self.conn)

        row = self.conn.execute(
            "SELECT notified_step_id FROM observations WHERE id='old'").fetchone()
        self.assertIsNone(row[0])


if __name__ == "__main__":
    unittest.main()
