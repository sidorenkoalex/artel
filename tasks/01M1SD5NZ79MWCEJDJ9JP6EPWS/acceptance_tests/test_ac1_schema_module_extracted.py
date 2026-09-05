"""Приёмочный тест AC-1 (tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/SPEC.md):
`orchestrator/schema.py` существует и реально несёт `SCHEMA` (DDL),
`migrate(conn)` и вспомогательные `add_column`/проверки версии
(`table_columns`), перенесённые из `store.py` — не просто одноимённые
обёртки, оставляющие настоящую реализацию в `store.py`.

Красен до реализации: модуля `orchestrator/schema.py` пока не
существует — рефакторинг R6 ещё не сделан, схема и `migrate` живут
только в `orchestrator/store.py`. Импорт `from orchestrator import
schema` падает `ModuleNotFoundError` до того, как код теста дойдёт до
самих проверок.

Внимание разработчику (не отдельный AC, справочно): в `tests/
test_multitarget.py` уже есть `SqlOnlyInStoreTest.test_no_sql_outside_store`
— грепает `orchestrator/*.py`, КРОМЕ `store.py`, на ключевые слова SQL
(`CREATE`/`ALTER`/`SELECT`/...) и падает, если найдёт хоть одну строку
(ADR-0003 3ж: «SQL только в store.py» — по тексту самого ADR это
«цель, не факт», не пункт `docs/invariants.md`, поэтому requirement 6
SPEC его не защищает буквально). После переноса `SCHEMA`/`migrate` в
`schema.py` эта проверка НЕИЗБЕЖНО покраснеет — `schema.py` по
определению AC-1 несёт `CREATE TABLE`/`ALTER TABLE`. Тест-автор
проверил стабом: правка `SqlOnlyInStoreTest` (добавить `schema.py` в
список исключений рядом со `store.py`) — единственный вменяемый выход,
и она в зоне (`tests/` объявлен зоной SPEC), но это правка ФАЙЛА ВНЕ
`tests/test_store*.py`/подмен `mock.patch.object(store, ...)`, то есть
вне списка, который AC-9 требует оставить без правки утверждений — на
неё это ограничение не распространяется.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

_REQUIRED_TABLES = (
    "tasks", "steps", "task_counters", "alerts", "alerts_archive",
    "leases", "merge_locks",
)


class SchemaModuleHoldsDdlAndMigrationHelpersTest(unittest.TestCase):

    def test_ac1_schema_module_defines_ddl_and_migration_helpers(self):
        """`orchestrator.schema` несёт непустую строку `SCHEMA` со всеми
        семью `CREATE TABLE IF NOT EXISTS` таблицами БД и вызываемые
        `migrate`/`add_column`/`table_columns`.

        Ловит мутацию: перенос только константы `SCHEMA` без функций
        `migrate`/`add_column`/`table_columns` (частичный перенос) —
        `hasattr`/`callable` ниже упадут на первой отсутствующей.
        """
        from orchestrator import schema

        self.assertIsInstance(schema.SCHEMA, str)
        for table in _REQUIRED_TABLES:
            self.assertIn(
                f"CREATE TABLE IF NOT EXISTS {table}", schema.SCHEMA,
                f"таблица {table!r} отсутствует в orchestrator.schema.SCHEMA")

        for name in ("migrate", "add_column", "table_columns"):
            self.assertTrue(hasattr(schema, name),
                            f"orchestrator.schema.{name} отсутствует")
            self.assertTrue(callable(getattr(schema, name)),
                            f"orchestrator.schema.{name} не вызываем")

    def test_ac1_migrate_and_add_column_are_defined_in_schema_module_itself(self):
        """`schema.migrate`/`schema.add_column` — функции, чей
        `__module__` реально `orchestrator.schema`, а не тонкие обёртки
        над старой реализацией, оставшейся в `orchestrator.store`.

        Ловит мутацию: `schema.py` заводит `migrate`/`add_column` как
        `def migrate(conn): return store.migrate(conn)` (делегирование
        вместо переноса) — по формулировке AC-1 логика обязана
        ПЕРЕЕХАТЬ, а не продолжать жить в `store.py` за тонкой ширмой;
        `__module__` обёртки всё ещё указывал бы на `orchestrator.schema`
        (сама обёртка объявлена там), поэтому дополнительно проверяем,
        что `store.py` источником правды для миграции больше не
        является — `orchestrator.store.migrate` (после AC-2) обязан
        быть ТЕМ ЖЕ объектом, что и `schema.migrate` (`is`, не просто
        эквивалентное поведение).
        """
        from orchestrator import schema, store

        self.assertEqual(schema.migrate.__module__, "orchestrator.schema")
        self.assertEqual(schema.add_column.__module__, "orchestrator.schema")
        self.assertIs(store.migrate, schema.migrate)


if __name__ == "__main__":
    unittest.main()
