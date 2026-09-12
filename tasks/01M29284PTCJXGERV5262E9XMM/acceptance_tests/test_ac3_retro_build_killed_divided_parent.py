"""AC-3 (tasks/01M29284PTCJXGERV5262E9XMM/SPEC.md): `retro.build_killed`
для родителя с подзадачами не содержит раздела о последней эскалации
(подстроку «Эскалации:» из `_escalations_block(full=True)`) и содержит
список подзадач с их id, названиями и состояниями на момент вызова.

Красен до реализации: колонка `parent_task_id` ещё не существует
(`orchestrator/schema.py::migrate`) — `store.update_task(conn, ...,
parent_task_id=...)` в `setUp` ниже откажет `ValueError: tasks: нет
колонок parent_task_id`; `retro.build_killed` (`orchestrator/retro.py`)
сегодня безусловно зовёт `_escalations_block(steps, full=True)` и не
знает о подзадачах вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, retro, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

PARENT_ID = "AC3PARENT"
SUB_DONE = "AC3SUBDONE"
SUB_INDEV = "AC3SUBINDEV"
ESCALATION_DETAIL = ("причина эскалации, которая не должна попасть в RETRO "
                    "поделённого родителя")


class RetroBuildKilledDividedParentTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, PARENT_ID, "Родитель AC-3", "killed",
                          "task/ac3parent-x", config.DEFAULT_TARGET, 25.0)
        store.insert_task(self.conn, SUB_DONE, "Подзадача уже смержена",
                          "done", "task/ac3subdone-x", config.DEFAULT_TARGET,
                          25.0)
        store.insert_task(self.conn, SUB_INDEV, "Подзадача в разработке",
                          "in_dev", "task/ac3subindev-x",
                          config.DEFAULT_TARGET, 25.0)
        store.update_task(self.conn, SUB_DONE, parent_task_id=PARENT_ID)
        store.update_task(self.conn, SUB_INDEV, parent_task_id=PARENT_ID)
        store.journal(self.conn, PARENT_ID, "fsm", "state -> escalated",
                      ESCALATION_DETAIL)
        store.journal(self.conn, PARENT_ID, "operator", "state -> killed",
                      "деление на подзадачи")

    def test_ac3_no_last_escalation_section_for_divided_parent(self):
        """RETRO поделённого родителя не цитирует последнюю эскалацию —
        ни заголовком «Эскалации:», ни её текстом.

        Ловит мутацию: `build_killed` для родителя с подзадачами
        по-прежнему зовёт `_escalations_block(steps, full=True)`
        (условие «есть подзадачи» не сработало), либо сработало, но
        секция не убрана из итогового списка строк документа.
        """
        text = retro.build_killed(self.conn, PARENT_ID)

        self.assertNotIn("Эскалации:", text)
        self.assertNotIn(ESCALATION_DETAIL, text)

    def test_ac3_lists_each_subtask_id_title_and_state(self):
        """RETRO поделённого родителя несёт список подзадач: id, название
        и состояние КАЖДОЙ на момент генерации.

        Ловит мутацию: список подзадач не строится вовсе, либо строится
        только по id без названия/состояния, либо теряет одну из двух
        подзадач (например, читает только первую найденную строку).
        """
        text = retro.build_killed(self.conn, PARENT_ID)

        for task_id, title, state in (
            (SUB_DONE, "Подзадача уже смержена", "done"),
            (SUB_INDEV, "Подзадача в разработке", "in_dev"),
        ):
            self.assertIn(task_id, text, text)
            self.assertIn(title, text, text)
            self.assertIn(state, text, text)


if __name__ == "__main__":
    unittest.main()
