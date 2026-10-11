"""AC-3 (tasks/T048/SPEC.md): ветка с именем создаваемой задачи уже
существует — именованный отказ, задача не создаётся (нет новой строки в
БД, нет каталога `tasks/<id>/`), номер счётчика не расходуется.
"""
import unittest

from orchestrator import catalog, store  # noqa: E402

from _sandbox import TmpGitTaskTest  # noqa: E402


class ExistingBranchRefusalTest(TmpGitTaskTest):

    def test_ac3_pre_existing_branch_name_refuses_without_side_effects(self):
        first_title = "Первая задача до конфликта веток"
        colliding_branch = f"task/t001-{catalog.slugify(first_title)}"
        self.git("branch", colliding_branch, "main")

        with self.assertRaises(SystemExit):
            self.cli_new(first_title)

        self.assertIsNone(
            store.db().execute(
                "SELECT 1 FROM tasks WHERE id='T001'").fetchone(),
            "отказ по конфликту ветки не должен создавать строку задачи")
        self.assertFalse(
            (self.root / "tasks" / "T001").exists(),
            "каталог задачи не должен появиться ни на диске main")

        second_title = "Вторая задача без конфликта веток"
        self.cli_new(second_title)

        rows = store.db().execute(
            "SELECT * FROM tasks ORDER BY id").fetchall()
        self.assertEqual(
            [r["id"] for r in rows], ["T001"],
            "номер счётчика не должен быть израсходован отказавшей попыткой")
        self.assertEqual(rows[0]["title"], second_title)


if __name__ == "__main__":
    unittest.main()
