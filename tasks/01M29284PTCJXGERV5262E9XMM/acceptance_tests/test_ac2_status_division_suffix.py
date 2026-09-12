"""AC-2 (tasks/01M29284PTCJXGERV5262E9XMM/SPEC.md): `catalog.cmd_status`
несёт добавку «[поделена: <id1>, <id2>]» в строке родителя и «[часть
N/M родителя <id>]» в строках его подзадач, соответственно их порядку
по возрастанию id.

Красен до реализации: колонка `parent_task_id` ещё не существует
(`orchestrator/schema.py::migrate`) — `store.update_task(conn, ...,
parent_task_id=...)` в `setUp` ниже откажет `ValueError: tasks: нет
колонок parent_task_id`; `cmd_status` (`orchestrator/catalog.py::
cmd_status`) сегодня не читает эту колонку вовсе и не печатает добавки
требования 2.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

PARENT_ID = "AC2PARENT"
SUB_A = "AC2SUBA"
SUB_B = "AC2SUBB"


class StatusDivisionSuffixTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        conn = store.db()
        store.insert_task(conn, PARENT_ID, "Родитель AC-2", "killed",
                          "task/ac2parent-x", config.DEFAULT_TARGET, 25.0)
        store.insert_task(conn, SUB_A, "Подзадача A", "in_dev",
                          "task/ac2suba-x", config.DEFAULT_TARGET, 25.0)
        store.insert_task(conn, SUB_B, "Подзадача B", "spec_writing",
                          "task/ac2subb-x", config.DEFAULT_TARGET, 25.0)
        store.update_task(conn, SUB_A, parent_task_id=PARENT_ID)
        store.update_task(conn, SUB_B, parent_task_id=PARENT_ID)

    def _line_for(self, task_id: str, out: str) -> str:
        return next(ln for ln in out.splitlines()
                    if ln.split()[0] == task_id)

    def test_ac2_parent_row_lists_both_subtask_ids_in_ascending_order(self):
        """Строка родителя обязана нести «[поделена: AC2SUBA, AC2SUBB]»
        — обе подзадачи, в порядке возрастания id, добавкой в конец
        строки.

        Ловит мутацию: разработчик показывает только одну из двух
        подзадач (например, берёт первую найденную вместо ВСЕХ строк с
        `parent_task_id`), либо печатает их не по возрастанию id —
        `assertIn` с точным текстом добавки ниже поймает оба случая.
        """
        out = capture(catalog.cmd_status)
        line = self._line_for(PARENT_ID, out)

        self.assertIn(f"[поделена: {SUB_A}, {SUB_B}]", line, line)

    def test_ac2_subtask_rows_show_their_order_and_total_among_siblings(self):
        """Строки подзадач несут «[часть 1/2 родителя AC2PARENT]»/«[часть
        2/2 родителя AC2PARENT]» соответственно порядку по возрастанию id
        среди подзадач ТОГО ЖЕ родителя.

        Ловит мутацию: разработчик путает местами N для двух подзадач
        (например, сортирует по title, а не по id), либо пишет
        одинаковый N в обеих строках.
        """
        out = capture(catalog.cmd_status)
        line_a = self._line_for(SUB_A, out)
        line_b = self._line_for(SUB_B, out)

        self.assertIn(f"[часть 1/2 родителя {PARENT_ID}]", line_a, line_a)
        self.assertIn(f"[часть 2/2 родителя {PARENT_ID}]", line_b, line_b)

    def test_ac2_unrelated_task_row_is_unchanged(self):
        """Задача без связи `parent_task_id` (ни родитель, ни подзадача)
        не получает ни одну из двух добавок (требование 2, последнее
        предложение).

        Ловит мутацию: добавка «[поделена: ...]»/«[часть N/M ...]»
        протекает в строку задачи, вообще не участвующей в делении —
        например, из-за неверного фильтра запроса подзадач (`parent_
        task_id IS NOT NULL` вместо точного сравнения с id этой строки).
        """
        conn = store.db()
        store.insert_task(conn, "AC2LONE", "Задача без деления", "in_dev",
                          "task/ac2lone-x", config.DEFAULT_TARGET, 25.0)

        out = capture(catalog.cmd_status)
        line = self._line_for("AC2LONE", out)

        self.assertNotIn("поделена", line)
        self.assertNotIn("часть", line)


if __name__ == "__main__":
    unittest.main()
