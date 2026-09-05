"""Юнит-тест регресса R1-F2 (REVIEW.md 01M1NKTF173WV5CPDZ1C3WW69K итерации 1,
blocker): каждая колонка `tasks`, которую `store.migrate()` добавляет через
`add_column`, обязана уже жить в базовой `store.SCHEMA` — иначе `add_column`
на свежей БД реально идёт по ветке `ALTER TABLE`, и сверка «есть/нет колонки»
(`table_columns`) не атомарна с самим `ALTER TABLE`: параллельные вызовы
`store.db()` (штатно происходящие, например, в `catalog.cmd_new`) гонятся за
одной и той же колонкой — все, кроме первого, падают необработанным
`sqlite3.OperationalError: duplicate column name`.

Символптом был найден косвенно (`tests.test_multitarget.TaskNumberingTest.
test_two_callers_at_once_do_not_get_the_same_number` падал из-за именно этой
гонки на колонке `materialized_artifact_sha`) — этот тест ловит КЛАСС
дефекта напрямую, на уровне схемы, а не через побочный эффект в
несвязанном тесте: любая будущая колонка, добавленная так же неполно,
проваливает его сразу, до того как гонка успеет проявиться где-то ещё.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import store  # noqa: E402


class MigrateIsANoopOnAFreshSchemaTest(unittest.TestCase):

    def test_every_migrated_tasks_column_already_lives_in_create_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            import sqlite3
            conn = sqlite3.connect(Path(tmp) / "state.db")
            conn.row_factory = sqlite3.Row
            store.create_schema(conn)

            before = store.table_columns(conn, "tasks")
            store.migrate(conn)
            after = store.table_columns(conn, "tasks")

            self.assertEqual(
                after, before,
                "`migrate()` добавила колонку(и) свежей БД: "
                f"{after - before} — они отсутствуют в `store.SCHEMA` "
                "(CREATE TABLE tasks) и живут только в цепочке "
                "`add_column`, что и вызывает TOCTOU-гонку `ALTER TABLE` "
                "при параллельных `store.db()`.")
            conn.close()


if __name__ == "__main__":
    unittest.main()
