"""Юнит-тесты 01M29284PTCJXGERV5262E9XMM — углы, не закрытые приёмочными
тестами `tasks/01M29284PTCJXGERV5262E9XMM/acceptance_tests/` (те держат
сценарий «родитель + 2 подзадачи»; здесь — единственная подзадача и
изоляция стоимости родителя от подзадач в RETRO).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import canary, catalog, config, retro, schema, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class SchemaHasParentTaskIdColumnTest(unittest.TestCase):

    def test_fresh_schema_carries_the_column(self):
        """Ловит мутацию класса R1-F2 (tests/test_store_schema_migration_
        parity.py): колонка добавлена только через `add_column` в
        `migrate()`, но не в базовом `CREATE TABLE tasks` — тогда
        параллельные `store.db()` на свежей БД гонятся за `ALTER TABLE`."""
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        schema.create_schema(conn)

        self.assertIn("parent_task_id", schema.table_columns(conn, "tasks"))


class DivisionSuffixSingleSubtaskTest(TmpRootTest):
    """Один родитель с ОДНОЙ подзадачей — «часть 1/1», не «1/2», как в
    приёмочном сценарии с двумя подзадачами."""

    PARENT = "T950PARENT"
    SUB = "T950SUB"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        conn = store.db()
        store.insert_task(conn, self.PARENT, "Родитель одной подзадачи",
                          "killed", "task/t950parent-x",
                          config.DEFAULT_TARGET, 25.0)
        store.insert_task(conn, self.SUB, "Единственная подзадача",
                          "in_dev", "task/t950sub-x", config.DEFAULT_TARGET,
                          25.0)
        store.update_task(conn, self.SUB, parent_task_id=self.PARENT)

    def test_single_subtask_shows_one_of_one(self):
        """Ловит мутацию: `M` в «часть N/M» считается не по числу
        подзадач ЭТОГО родителя, а хардкодится/берётся из другого
        источника (например, общего числа задач в БД) — тогда
        единственная подзадача показала бы «часть 1/2» вместо «1/1»."""
        out = capture(catalog.cmd_status)

        sub_line = next(ln for ln in out.splitlines()
                        if ln.split()[0] == self.SUB)
        self.assertIn(f"[часть 1/1 родителя {self.PARENT}]", sub_line, out)


class RetroDividedParentCostIsolationTest(TmpRootTest):
    """RETRO поделённого родителя несёт стоимость РОДИТЕЛЯ, не суммирует
    в неё расход подзадач (SPEC, требование 3: «стоимость родителя ДО
    деления»)."""

    PARENT = "T951PARENT"
    SUB = "T951SUB"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.PARENT, "Родитель со стоимостью",
                          "killed", "task/t951parent-x",
                          config.DEFAULT_TARGET, 25.0)
        store.update_task(self.conn, self.PARENT, spent_usd=3.5)
        store.insert_task(self.conn, self.SUB, "Дорогая подзадача",
                          "in_dev", "task/t951sub-x", config.DEFAULT_TARGET,
                          25.0)
        store.update_task(self.conn, self.SUB, parent_task_id=self.PARENT,
                          spent_usd=99.0)

    def test_cost_block_shows_only_the_parents_own_spend(self):
        """Ловит мутацию: `_cost_block` в ветке «поделена» суммирует
        `spent_usd` подзадач в стоимость родителя (или подставляет
        стоимость подзадачи вместо родителя) — тогда $3.50 подменится
        суммой с $99.00 или самим $99.00."""
        text = retro.build_killed(self.conn, self.PARENT)

        self.assertIn("Стоимость итого: $3.50", text)
        self.assertNotIn("99.00", text)

    def test_divided_outcome_line_replaces_killed_reason(self):
        """Ловит мутацию: обе ветки (`killed — причина: ...` и «поделена»)
        печатаются одновременно, либо старая ветка остаётся первой."""
        text = retro.build_killed(self.conn, self.PARENT)

        self.assertIn("Итог: поделена на подзадачи", text)
        self.assertNotIn("killed — причина", text)


class HasSubtasksTest(TmpRootTest):

    TASK = "T952LONE"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача без подзадач",
                          "killed", "task/t952lone-x", config.DEFAULT_TARGET,
                          25.0)

    def test_task_without_subtasks_is_not_flagged_as_divided(self):
        """Ловит мутацию: `_has_subtasks` возвращает `True` безусловно
        (или проверяет наличие ЛЮБЫХ строк в `tasks`, а не строк с
        `parent_task_id == TASK`) — тогда одиночная задача без
        подзадач ложно считалась бы «поделённым родителем»."""
        self.assertFalse(canary._has_subtasks(self.conn, self.TASK))


if __name__ == "__main__":
    unittest.main()
