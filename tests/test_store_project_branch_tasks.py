"""`store.project_branch_tasks` — занятость имени ветки у задач проекта (SPEC 01M5WDB7F14SQ30QVWJY2XYBG2, требование 2): строка без `target` — задача артели, как у `store.project_tasks`."""
from orchestrator import config, idgen, store


def test_row_without_target_counts_as_artel(initialized_tmp_root):
    """Задача со строкой без `target` занимает имя ветки артели и не занимает имя ветки внешнего проекта.

    Ловит мутацию: фильтр проекта `target=?` без `COALESCE(target, 'artel')`
    — строка без `target` выпадает из занятости имён веток артели.
    """
    conn = store.db()
    task_id = idgen.new_task_id()
    store.insert_task(conn, task_id, "Задача", "done", "feature/legacy",
                      config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
    conn.execute("UPDATE tasks SET target=NULL WHERE id=?", (task_id,))
    conn.commit()
    rows = store.project_branch_tasks(conn, config.DEFAULT_TARGET,
                                      ["feature/legacy"])
    assert [r["id"] for r in rows] == [task_id]
    assert store.project_branch_tasks(conn, "qother", ["feature/legacy"]) == []
