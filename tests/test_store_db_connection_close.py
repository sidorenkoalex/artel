"""Юнит-тесты закрытия соединений `store.db()` (tasks/T090/SPEC.md,
требование 1).

Приёмочный тест (tasks/T090/acceptance_tests/test_no_unclosed_connections.py)
ловит РЕЗУЛЬТАТ на всём `tests/` (0 `ResourceWarning`); здесь — сам
механизм в изоляции: соединение закрывается при потере последней ссылки
без явного `.close()`, повторное закрытие безопасно, а WAL/схема/
`row_factory` не меняются относительно прежнего поведения `db()`.
"""
import gc
import sqlite3
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class DbConnectionAutoCloseTest(TmpRootTest):

    def test_del_closes_the_connection(self):
        conn = store.db()
        conn.execute("SELECT 1")

        conn.__del__()  # то же самое `close()`, которое CPython зовёт
                        # сам при потере последней ссылки (обходим
                        # неопределённость момента GC, тестируем эффект)

        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_no_resourcewarning_when_connection_is_used_inline_and_discarded(self):
        store.create_schema(store.db())

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            store.db().execute("SELECT 1")
            gc.collect()

        resource_warnings = [
            w for w in caught if issubclass(w.category, ResourceWarning)]
        self.assertEqual(
            resource_warnings, [],
            f"инлайн-вызов `store.db()` оставил незакрытое соединение: "
            f"{[str(w.message) for w in resource_warnings]}")

    def test_explicit_close_then_gc_does_not_raise(self):
        conn = store.db()
        conn.close()

        del conn
        gc.collect()  # __del__ зовёт close() повторно — не должен упасть

    def test_row_factory_and_wal_unchanged(self):
        conn = store.db()
        try:
            self.assertIs(conn.row_factory, sqlite3.Row)
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")
        finally:
            conn.close()
