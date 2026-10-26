"""Юнит-тесты эпиков и модели доски вне долгоживущих файлов задачи
01M5TBBDFS6DWQY6MS263T1KPY: миграция эпиков на БД со старой схемой
`steps` и порядок задач эпика при цикле зависимостей."""
import sqlite3

from orchestrator import board, config, schema


def test_epics_migration_on_steps_without_target_and_session(tmp_root):
    """БД, чей `steps` ещё без колонок `target`/`session_id`: `migrate` догоняет их и пишет одну запись о миграции эпиков без исключения.

    Ловит мутацию: миграция эпиков стоит в начале `migrate`, до догона
    колонок `steps` — запись журнала падает `table steps has no column
    named target`, а с ней любое открытие такой БД.
    """
    conn = sqlite3.connect(tmp_root.root / "old.db")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, state TEXT,"
        " branch TEXT, budget_usd REAL, spent_usd REAL DEFAULT 0);"
        "CREATE TABLE steps (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " task_id TEXT, ts TEXT, actor TEXT, action TEXT, detail TEXT);")
    conn.commit()

    schema.migrate(conn)

    assert "epic_id" in schema.table_columns(conn, "tasks")
    rows = conn.execute("SELECT task_id, action FROM steps").fetchall()
    assert [tuple(r) for r in rows] == [
        (config.EPICS_MIGRATION_JOURNAL_TASK_ID, schema.EPICS_MIGRATED_ACTION)]
    conn.close()


def test_epic_order_keeps_tasks_of_a_dependency_cycle():
    """Цикл `merge_after` внутри эпика (A↔B) не теряет задач: свободная C — первой, затем остаток цикла по id.

    Ловит мутацию: порядок строится только обходом Кана без хвоста —
    задачи цикла выпадают из `nodes` модели и из видов `status`/`epic show`.
    """
    edges = [{"from": "A", "to": "B", "kind": board.EDGE_MERGE_AFTER},
             {"from": "B", "to": "A", "kind": board.EDGE_MERGE_AFTER},
             {"from": "P", "to": "C", "kind": board.EDGE_PARENT}]

    assert board._ordered(["A", "B", "C"], edges) == ["C", "A", "B"]
