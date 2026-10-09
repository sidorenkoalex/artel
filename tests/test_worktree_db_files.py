"""Файлы БД пульта в дереве: граница «своя БД пульта», уборка без
перезаписи логов, совет гейта мержа (SPEC 01M4FYTB8QWJNHYCP35K8QC4E3,
требования 4 и 6) — свойства, которых не касаются долгоживущие файлы задачи.
"""

import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, config, fsm_merge_gate, repo_context,
                          store, workspace)
from tests.sandbox import TmpRootTest

TASK = "01M4FYTB8QWJNHYCP35K8QC4E3"


class OwnPultDbTest(TmpRootTest):

    def test_pult_root_db_is_not_a_stray_tree_db_file(self):
        """Корень пульта со своей действующей `state.db` — не дерево с
        лишней БД; та же копия файла в другом дереве — лишняя.

        Ловит мутацию: из `store.tree_db_files` убрано исключение «дерево —
        сам корень пульта» — полный прогон на корне пульта (песочницы
        `RealGitSandbox`, прогон заметок) отказывал бы «не проверен» из-за
        собственной БД пульта.
        """
        store.create_schema(store.db())
        self.assertTrue(config.DB.is_file())
        self.assertEqual(store.tree_db_files(config.ROOT), [])

        other = self.root / "other-tree"
        (other / ".artel").mkdir(parents=True)
        (other / ".artel" / "state.db").write_bytes(config.DB.read_bytes())
        self.assertEqual(store.tree_db_files(other), [".artel/state.db"])


class CleanKeepsExistingLogsTest(TmpRootTest):

    def test_clean_does_not_overwrite_log_with_same_name(self):
        """Файл каталога логов с тем же именем, что выбрала уборка, остаётся
        прежним; перенесённое ложится рядом под другим именем.

        Ловит мутацию: из `workspace.cmd_worktree_db_clean` убран подбор
        свободного имени — `shutil.move` поверх существующего файла
        затирает прежний лог.
        """
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, TASK, "Задача", "in_dev", "task/x",
                          config.DEFAULT_TARGET, 25.0)
        wt = workspace.path(TASK)
        (wt / ".artel").mkdir(parents=True)
        (wt / ".artel" / "state.db").write_bytes(b"stray")
        logs = Path(config.LOGS)
        logs.mkdir(parents=True, exist_ok=True)
        stamp = "2026-10-09 10:00:00Z"
        taken = logs / f"{TASK}-worktree-2026-10-09T100000Z-state.db"
        taken.write_bytes(b"earlier")

        with mock.patch.object(store, "now", return_value=stamp):
            workspace.cmd_worktree_db_clean(TASK)

        self.assertEqual(taken.read_bytes(), b"earlier")
        self.assertEqual(Path(f"{taken}.2").read_bytes(), b"stray")
        self.assertFalse((wt / ".artel" / "state.db").exists())


class MergeGateDbAdviceTest(TmpRootTest):

    def test_db_refusal_advice_names_cleaning_not_waiting(self):
        """Отказ гейта мержа из-за файла БД в дереве советует убрать файлы,
        а не ждать освобождения машины; занятый замок — прежний совет.

        Ловит мутацию: ветка «прогон не начат» в
        `fsm_merge_gate._full_suite_or_refuse` снова одна на оба случая —
        отказ из-за файла БД советует «повтори, когда машина освободится».
        """
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, TASK, "Задача", "merge_gate", "task/x",
                          config.DEFAULT_TARGET, 25.0)
        ctx = repo_context.RepoContext(path=self.root, remote="origin",
                                       base=config.MAIN_BRANCH,
                                       target=config.DEFAULT_TARGET)
        db_note = acceptance._db_in_tree_note(self.root, TASK,
                                              [".artel/state.db"])
        busy_note = f"{acceptance.FULL_SUITE_NOT_STARTED}: машина занята"
        messages = {}
        for name, note in (("db", db_note), ("busy", busy_note)):
            run = acceptance.FullSuiteRun(False,
                                          acceptance.FULL_SUITE_NOT_STARTED,
                                          "", None, note)
            with mock.patch.object(fsm_merge_gate, "_full_suite_command",
                                   return_value=(True, None)), \
                    mock.patch.object(fsm_merge_gate.acceptance, "full_suite",
                                      return_value=run), \
                    mock.patch.object(fsm_merge_gate,
                                      "_drop_scratch_worktree"), \
                    self.assertRaises(SystemExit) as raised:
                fsm_merge_gate._full_suite_or_refuse(
                    conn, TASK, ["tests/x.py"], self.root, ctx)
            messages[name] = str(raised.exception.code)

        self.assertIn(f"artel.py worktree-db-clean {TASK}", messages["db"])
        self.assertIn("убери файлы БД пульта", messages["db"])
        self.assertNotIn("машина освободится", messages["db"])
        self.assertIn("машина освободится", messages["busy"])


if __name__ == "__main__":
    unittest.main()
