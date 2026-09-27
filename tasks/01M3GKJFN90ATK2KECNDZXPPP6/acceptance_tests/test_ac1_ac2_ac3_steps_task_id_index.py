"""AC-1, AC-2, AC-3 — 01M3GKJFN90ATK2KECNDZXPPP6: индекс `steps(task_id)` в
миграции, в базовой схеме и в плане запроса журнала одной задачи.

Источник — раздел «Критерии приёмки»:

AC-1. После `schema.migrate` на БД, созданной без индекса, в
`sqlite_master` есть индекс по `steps(task_id)`; повторный `migrate` на
той же БД проходит без ошибки и второго индекса не заводит.

AC-2. Индекс по `steps(task_id)` есть и в свежесозданной БД
(`create_schema`), а `migrate` на ней набор индексов `steps` не меняет:
список индексов `steps` новой БД и мигрированной совпадает.

AC-3. `EXPLAIN QUERY PLAN` запроса журнала одной задачи
(`WHERE task_id=? ORDER BY id`) на БД с индексом называет поиск по
индексу `steps(task_id)` и не содержит ни `SCAN` таблицы `steps`, ни
сортировки во временном B-дереве (`USE TEMP B-TREE FOR ORDER BY`) — тем
самым составной индекс `steps(task_id, id)` не нужен.

Имя индекса критерии не фиксируют, поэтому планка ищет его по составу
колонок (`PRAGMA index_info`, `_util.task_id_index_names`): ключ ровно
`(task_id,)`. «БД, созданная без индекса» — схема пульта, с которой
индексы `steps` сняты `DROP INDEX`: живая БД Оператора именно такая
(`CREATE TABLE steps` до этой задачи ни одного индекса не заводил), и
собрать её так честнее, чем копировать в планку прежний текст DDL,
который разойдётся с составом колонок при следующей же миграции.

Красен до реализации: ни `SCHEMA`, ни `migrate` индекса `steps` не
заводят — `_util.task_id_index_names` возвращает пустой список в обеих
БД, а план запроса называет `SCAN steps`.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import schema, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

#: Имя индекса из строки плана `… USING INDEX <имя> (task_id=?)`.
PLAN_INDEX_RE = re.compile(r"USING (?:COVERING )?INDEX (\S+)")

#: Строка плана «сортировка во временном B-дереве» (AC-3).
TEMP_B_TREE = "USE TEMP B-TREE FOR ORDER BY"

JOURNAL_QUERY = "SELECT * FROM steps WHERE task_id=? ORDER BY id"


class StepsTaskIdIndexTest(TmpRootTest):
    """Две БД во временном каталоге пульта: свежая (`create_schema`) и
    догнанная миграцией со состояния «индексов `steps` нет вовсе».

    Пути `config` уведены в песочницу `TmpRootTest` не ради самих файлов
    БД, а ради `migrate`: она засевает счётчики задач по наблюдаемому миру
    (`store.seed_task_counters` -> `coldstart`), и без подмены путей
    сканировала бы РЕАЛЬНЫЙ пульт Оператора.
    """

    def fresh_db(self):
        """Свежесозданная БД пульта — то, что ставит `init`."""
        conn = _util.open_db(self.root / "fresh.db")
        self.addCleanup(conn.close)
        schema.create_schema(conn)
        return conn

    def pre_index_db(self):
        """БД, у которой нет ни одного индекса `steps` — состояние живой
        БД пульта до этой задачи."""
        conn = _util.open_db(self.root / "pre-index.db")
        self.addCleanup(conn.close)
        schema.create_schema(conn)
        for name in _util.steps_index_names(conn):
            conn.execute(f"DROP INDEX {name}")
        conn.commit()
        self.assertEqual([], _util.steps_index_names(conn),
                         "исходная БД сценария обязана быть без индексов steps")
        return conn

    def test_ac1_migrate_adds_the_task_id_index_and_stays_idempotent(self):
        """БД без единого индекса `steps` догоняется миграцией: после
        первого `migrate` в `sqlite_master` появляется индекс с ключом
        `(task_id,)`, после второго `migrate` на той же БД — ни ошибки, ни
        второго такого индекса.

        Ловит мутацию: индекс объявлен в миграции без `IF NOT EXISTS`
        (`CREATE INDEX idx_steps_task_id …`) — повторный `migrate` живой
        БД, который пульт делает на КАЖДОМ `store.db()`, падал бы
        `sqlite3.OperationalError: index … already exists`.
        """
        conn = self.pre_index_db()

        schema.migrate(conn)
        after_first = _util.task_id_index_names(conn)
        self.assertEqual(
            1, len(after_first),
            "после migrate в sqlite_master нет ровно одного индекса по "
            f"steps(task_id): индексы steps — {_util.steps_index_map(conn)}")

        schema.migrate(conn)
        self.assertEqual(
            after_first, _util.task_id_index_names(conn),
            "повторный migrate изменил набор индексов по steps(task_id)")

    def test_ac2_new_db_carries_the_same_steps_indexes_as_a_migrated_one(self):
        """Свежесозданная БД несёт индекс по `steps(task_id)` сама, без
        миграции; `migrate` на ней набор индексов `steps` не меняет, и
        этот набор совпадает с набором БД, догнанной миграцией.

        Ловит мутацию: индекс заведён ТОЛЬКО записью миграции и забыт в
        базовой `SCHEMA` — свежая БД пульта уходила бы в работу без
        индекса до первого `migrate`, а `migrate` на ней реально шла бы по
        ветке создания (тот же класс, что сторожит
        tests/test_store_schema_migration_parity.py).
        """
        fresh = self.fresh_db()
        self.assertEqual(
            1, len(_util.task_id_index_names(fresh)),
            "свежесозданная БД не несёт индекса по steps(task_id): индексы "
            f"steps — {_util.steps_index_map(fresh)}")

        before = _util.steps_index_map(fresh)
        schema.migrate(fresh)
        self.assertEqual(before, _util.steps_index_map(fresh),
                         "migrate изменила набор индексов steps свежей БД")

        migrated = self.pre_index_db()
        schema.migrate(migrated)
        self.assertEqual(
            _util.steps_index_map(fresh), _util.steps_index_map(migrated),
            "набор индексов steps новой БД и мигрированной разошёлся")

    def test_ac3_journal_query_plan_searches_the_index_without_sorting(self):
        """План запроса журнала одной задачи на БД с индексом: поиск по
        индексу с ключом `(task_id,)`, без `SCAN` таблицы `steps` и без
        сортировки во временном B-дереве — то есть составной
        `steps(task_id, id)` действительно не нужен.

        Ловит мутацию: индекс заведён по другой колонке (`steps(ts)` —
        соседняя колонка того же журнала, опечатка в одной строке DDL):
        план вернулся бы к `SCAN steps`, то есть к тому самому чтению,
        из-за которого профиль `status` и вырос.
        """
        conn = self.pre_index_db()
        schema.migrate(conn)
        for number in range(40):
            store.journal(conn, f"01M3GKPLAN{number % 4:016d}", "fsm",
                          "state -> review", "запись плана запроса")

        plan = [str(row[-1]) for row in
                conn.execute(f"EXPLAIN QUERY PLAN {JOURNAL_QUERY}",
                             ("01M3GKPLAN" + "0" * 16,)).fetchall()]

        searched = [PLAN_INDEX_RE.search(line) for line in plan
                    if "SEARCH" in line and _util.STEPS_TABLE in line]
        index_names = [match.group(1) for match in searched if match]
        self.assertTrue(
            index_names,
            f"план не называет поиска по индексу steps: {plan}")
        self.assertTrue(
            set(index_names) <= set(_util.task_id_index_names(conn)),
            "план ищет по индексу, чей ключ не (task_id,): "
            f"{index_names} при индексах {_util.steps_index_map(conn)}")

        self.assertEqual(
            [], [line for line in plan
                 if line.startswith("SCAN") and _util.STEPS_TABLE in line],
            f"план содержит SCAN таблицы steps: {plan}")
        self.assertEqual(
            [], [line for line in plan if TEMP_B_TREE in line],
            f"план сортирует во временном B-дереве: {plan}")


if __name__ == "__main__":
    unittest.main()
