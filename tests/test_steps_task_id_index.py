"""Юнит-тесты индекса `steps(task_id)` (SPEC 01M3GKJFN90ATK2KECNDZXPPP6,
требования 1-2; находка ревизии CR-2026-09-26-2).

Предмет — схема, а не читатели: индекс обязан быть И в базовой `SCHEMA`
(свежая БД `init`), И в `migrate` (живая БД пульта, заведённая до этой
задачи), и план запроса журнала одной задачи обязан идти по нему без
сортировки во временном B-дереве — тем самым составной `steps(task_id,
id)` не нужен (требование 2: `id` — алиас rowid, который SQLite сам
дописывает хвостовым ключом каждой записи индекса).

Имя индекса тесты не фиксируют: «индекс по `steps(task_id)`» узнаётся по
составу колонок (`PRAGMA index_info`), ровно `(task_id,)`.
"""
import re
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import schema, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

#: Имя индекса из строки плана «… USING INDEX <имя> (task_id=?)».
PLAN_INDEX_RE = re.compile(r"USING (?:COVERING )?INDEX (\S+)")

#: Строка плана «сортировка во временном B-дереве».
TEMP_B_TREE = "USE TEMP B-TREE FOR ORDER BY"


def _steps_index_map(conn) -> dict:
    """{имя индекса `steps`: кортеж его колонок} — сравнимый снимок НАБОРА
    индексов таблицы."""
    names = sorted(row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
        ("steps",)))
    return {name: tuple(row[2] for row in sorted(
        conn.execute(f"PRAGMA index_info({name})"), key=lambda r: r[0]))
        for name in names}


def _task_id_indexes(conn) -> list:
    """Индексы `steps`, чей ключ — РОВНО `(task_id,)`."""
    return [name for name, columns in _steps_index_map(conn).items()
            if columns == ("task_id",)]


class StepsTaskIdIndexTest(TmpRootTest):
    """Пути `config` уведены в песочницу не ради файлов БД, а ради
    `migrate`: она засевает счётчики задач по наблюдаемому миру
    (`store.seed_task_counters` -> `coldstart`) и иначе сканировала бы
    реальный пульт."""

    def _db(self, name: str, drop_indexes: bool = False):
        conn = sqlite3.connect(self.root / name)
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        schema.create_schema(conn)
        if drop_indexes:
            for index in _steps_index_map(conn):
                conn.execute(f"DROP INDEX {index}")
            conn.commit()
        return conn

    def test_migrate_adds_the_index_and_a_second_run_changes_nothing(self):
        """БД без единого индекса `steps` (состояние живой БД пульта до
        этой задачи) догоняется миграцией, и повторный `migrate` набор
        индексов не меняет.

        Ловит мутацию: запись миграции написана без `IF NOT EXISTS` —
        `migrate` идёт на КАЖДОМ `store.db()`, и второй вызов на живой БД
        падал бы `sqlite3.OperationalError: index … already exists`."""
        conn = self._db("pre-index.db", drop_indexes=True)
        self.assertEqual({}, _steps_index_map(conn),
                         "исходная БД сценария обязана быть без индексов")

        schema.migrate(conn)
        after_first = _task_id_indexes(conn)
        self.assertEqual(1, len(after_first),
                         f"индексов по steps(task_id) не один: "
                         f"{_steps_index_map(conn)}")

        schema.migrate(conn)
        self.assertEqual(after_first, _task_id_indexes(conn))

    def test_fresh_db_carries_the_same_steps_indexes_as_a_migrated_one(self):
        """Свежесозданная БД несёт индекс сама, `migrate` на ней набор
        индексов `steps` не меняет, и набор совпадает с набором БД,
        догнанной миграцией.

        Ловит мутацию: индекс заведён только записью миграции и забыт в
        базовой `SCHEMA` — свежая БД уходила бы в работу без индекса, а
        `migrate` на ней реально шла бы по ветке создания (тот же класс,
        что сторожит tests/test_store_schema_migration_parity.py)."""
        fresh = self._db("fresh.db")
        self.assertEqual(1, len(_task_id_indexes(fresh)),
                         f"свежая БД без индекса: {_steps_index_map(fresh)}")

        before = _steps_index_map(fresh)
        schema.migrate(fresh)
        self.assertEqual(before, _steps_index_map(fresh))

        migrated = self._db("migrated.db", drop_indexes=True)
        schema.migrate(migrated)
        self.assertEqual(_steps_index_map(fresh), _steps_index_map(migrated))

    def test_migrate_of_a_db_without_the_steps_table_does_not_fail(self):
        """БД прошлой версии, где есть `tasks` и ещё нет `steps`: `migrate`
        проходит целиком (прежние колонки догнаны), индекс не заводится —
        заводить его не на чем, `steps` создаёт только `create_schema`.

        Ловит мутацию: запись индекса в `migrate` выполняется без проверки
        наличия таблицы — `migrate` на такой БД падает
        `sqlite3.OperationalError: no such table: main.steps`, унося с собой
        ВСЕ последующие записи миграции и любое открытие этой БД."""
        conn = sqlite3.connect(self.root / "no-steps.db")
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        conn.executescript("CREATE TABLE tasks (id TEXT PRIMARY KEY, state TEXT);")
        conn.commit()

        schema.migrate(conn)

        self.assertEqual({}, _steps_index_map(conn),
                         "индекс заведён на БД без таблицы steps")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        self.assertIn("escalated_from", columns,
                      "migrate не дошла до конца: прежние колонки не догнаны")
        self.assertIn("parent_task_id", columns)

    def test_journal_query_plan_searches_the_index_without_sorting(self):
        """План `SELECT * FROM steps WHERE task_id=? ORDER BY id`: поиск по
        индексу с ключом `(task_id,)`, без `SCAN steps` и без сортировки во
        временном B-дереве.

        Ловит мутацию: индекс заведён по соседней колонке того же журнала
        (`steps(ts)` — опечатка в одной строке DDL): план вернулся бы к
        `SCAN steps`, то есть к тому самому чтению, из-за которого профиль
        `status` и вырос."""
        conn = self._db("plan.db", drop_indexes=True)
        schema.migrate(conn)
        for number in range(40):
            store.journal(conn, f"T{number % 4:03d}", "fsm", "state -> review",
                          "запись плана запроса")

        plan = [str(row[-1]) for row in conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM steps WHERE task_id=? "
            "ORDER BY id", ("T000",)).fetchall()]

        searched = [PLAN_INDEX_RE.search(line) for line in plan
                    if "SEARCH" in line and "steps" in line]
        index_names = {match.group(1) for match in searched if match}
        self.assertTrue(index_names, f"план не ищет по индексу: {plan}")
        self.assertTrue(
            index_names <= set(_task_id_indexes(conn)),
            f"план ищет по индексу с другим ключом: {index_names} при "
            f"{_steps_index_map(conn)}")
        self.assertEqual(
            [], [line for line in plan
                 if line.startswith("SCAN") and "steps" in line],
            f"план содержит SCAN таблицы steps: {plan}")
        self.assertEqual([], [line for line in plan if TEMP_B_TREE in line],
                         f"план сортирует во временном B-дереве: {plan}")


if __name__ == "__main__":
    unittest.main()
