"""Приёмочный тест AC-2 (tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/SPEC.md):
`store.create_schema`/`store.migrate` остаются вызываемыми как раньше
(реэкспорт из `schema.py`), и существующая тестовая подмена
`mock.patch.object(store, "migrate", ...)` продолжает перехватывать
вызов миграции внутри `store.db()` — то есть `store.py` действительно
реэкспортирует объект из `schema.py`, а не зовёт `schema.migrate(conn)`
напрямую в обход имени `store.migrate`, которое как раз и подменяет
`mock.patch.object`.

Красен до реализации: `orchestrator/schema.py` ещё не существует —
`test_ac2_store_create_schema_and_migrate_are_schema_objects` падает
`ModuleNotFoundError` на `from orchestrator import schema` раньше самих
проверок реэкспорта. Два теста `MockPatchStoreMigrateInterceptsDbTest`
проходят уже сегодня «случайно» (сегодняшний `store.py` и есть
единственный источник `migrate`/`create_schema`, патчить больше нечего
в обход) — они остаются в файле планкой ПОВЕДЕНИЯ, которое обязано
пережить сам перенос в `schema.py`, а не только зафиксировать факт
переноса.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tests.sandbox import TmpRootTest  # noqa: E402


class StoreReexportsSchemaFunctionsTest(unittest.TestCase):

    def test_ac2_store_create_schema_and_migrate_are_schema_objects(self):
        """`store.create_schema`/`store.migrate` — ТЕ ЖЕ объекты
        (`is`), что и `schema.create_schema`/`schema.migrate`, не
        одноимённые копии с независимой реализацией.

        Ловит мутацию: `store.py` держит собственные функции
        `create_schema`/`migrate`, которые просто ВЫЗЫВАЮТ одноимённые
        функции `schema.py` (делегирование, а не реэкспорт) — тогда
        `store.migrate is schema.migrate` было бы `False`, хотя внешнее
        поведение выглядело бы неотличимо.
        """
        from orchestrator import schema, store

        self.assertIs(store.create_schema, schema.create_schema)
        self.assertIs(store.migrate, schema.migrate)


class MockPatchStoreMigrateInterceptsDbTest(TmpRootTest):

    def test_ac2_mock_patch_object_store_migrate_intercepts_db(self):
        """Существующий тестовый приём `mock.patch.object(store,
        "migrate", ...)` (SPEC, требование 1) продолжает перехватывать
        вызов миграции, который делает `store.db()` изнутри.

        Ловит мутацию: `store.db()` после переноса зовёт
        `schema.migrate(conn)` напрямую (полным путём через модуль
        `schema`), а не безымянно через собственное пространство имён
        `store.py` (`migrate(conn)`, которое и подменяет
        `mock.patch.object(store, "migrate", ...)`) — тогда подмена
        молча перестаёт перехватывать реальный вызов внутри `db()`, и
        `mock_migrate.assert_called_once_with(conn)` ниже упадёт.
        """
        from orchestrator import store

        with mock.patch.object(store, "migrate") as mock_migrate:
            conn = store.db()

        mock_migrate.assert_called_once_with(conn)

    def test_ac2_mock_patch_object_store_create_schema_intercepts_catalog_init(self):
        """Существующий тестовый приём `mock.patch.object(store,
        "create_schema", ...)` продолжает перехватывать вызов, который
        делает `catalog.cmd_init()` — реальный потребитель
        `store.create_schema` в кодовой базе.

        Ловит мутацию: `catalog.cmd_init` после переноса схемы начинает
        звать `schema.create_schema(conn)` напрямую вместо
        `store.create_schema(conn)` — тогда подмена атрибута
        `store.create_schema` перестаёт что-либо перехватывать в
        `cmd_init`, и `mock_create.assert_called_once_with(conn)` ниже
        упадёт.
        """
        from orchestrator import catalog, store

        with mock.patch.object(
                store, "create_schema",
                wraps=store.create_schema) as mock_create:
            catalog.cmd_init()

        mock_create.assert_called_once()
        (conn_arg,), _ = mock_create.call_args
        self.assertIsNotNone(conn_arg)


if __name__ == "__main__":
    unittest.main()
