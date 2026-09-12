"""AC-1 (tasks/01M29284PTCJXGERV5262E9XMM/SPEC.md): после вызова
`catalog.spawn_subtask` у созданной подзадачи в БД `parent_task_id`
равен id родителя.

Красен до реализации: колонка `parent_task_id` ещё не добавлена в схему
(`orchestrator/schema.py::migrate` не несёт `add_column(conn, "tasks",
"parent_task_id", "TEXT")`), а `catalog.spawn_subtask` не зовёт
`store.update_task(conn, task_id, parent_task_id=parent_id)` — обращение
к `row["parent_task_id"]` ниже упадёт `IndexError` (колонки нет в БД).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

PARENT_ID = "AC1PARENTTASK"
PARENT_TITLE = "Родитель приёмочного теста AC-1"
TZ_BODY = "Зоны: orchestrator/foo.py\nПорядок: первая\n\nТекст ТЗ подзадачи."


class SpawnSubtaskParentTaskIdTest(RealGitSandbox):

    def test_ac1_spawn_subtask_fills_parent_task_id(self):
        """Подзадача, заведённая `spawn_subtask(parent_id, ...)`, обязана
        нести в строке БД `parent_task_id`, равный `parent_id` родителя.

        Ловит мутацию: `spawn_subtask` заводит строку подзадачи общим
        `_new_task_row`, но не зовёт следом `store.update_task(conn,
        task_id, parent_task_id=parent_id)` (колонка останется NULL),
        либо зовёт его со значением `sub_id`/`parent_title` вместо
        `parent_id` — `assertEqual` ниже поймает оба случая порчи.
        """
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача AC-1", TZ_BODY)

        row = store.get_task(store.db(), sub_id)

        self.assertEqual(row["parent_task_id"], PARENT_ID)


if __name__ == "__main__":
    unittest.main()
