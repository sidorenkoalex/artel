"""Юнит-тесты R1-F1 (REVIEW.md 01M1TNN4TMWAQSQ9Y1PW37J5H0 итерация 1,
замечание 1, blocker) — `is_extraneous_task_root_file` (SPEC
01M1TNN4TMWAQSQ9Y1PW37J5H0, требования 1-3) до правки проверял
допустимость файла первого уровня `tasks/<id>/` только для путей РОВНО
из одного сегмента: файл внутри ЛЮБОЙ новой поддиректории (не
`acceptance_tests/`, не `__pycache__/`, без `.`-префикса) — например
`tasks/<id>/wip/_head_map.md` — проходил молча через все три точки
контроля (guard `--all`, `checkpoint.commit_step_artifacts`,
`fsm_merge_gate._guard_task_root_or_refuse`). Залоченная планка приёмки
(`tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/acceptance_tests/`) не заводит файл
глубже одного уровня ни в одном сценарии — этот пробел покрывает файл
здесь, во всех трёх точках, единым критерием `guard.
is_extraneous_task_root_file`.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import checkpoint, config, fsm_merge_gate, gitcmd, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import RealGitSandbox, TmpRootTest  # noqa: E402

TARGET = "extproj"
NESTED_STRAY = "wip/_head_map.md"


class IsExtraneousTaskRootFilePredicateTest(unittest.TestCase):
    """Критерий сам по себе: первый сегмент пути решает допустимость
    независимо от глубины остального пути."""

    def test_file_inside_a_new_subdirectory_is_stray(self):
        """Ловит мутацию R1-F1: критерий проверяет только `len(parts) ==
        1`, поэтому файл глубже одного уровня проходит молча."""
        self.assertTrue(guard.is_extraneous_task_root_file(NESTED_STRAY))
        self.assertTrue(
            guard.is_extraneous_task_root_file("tmp/notes.md"))
        self.assertTrue(
            guard.is_extraneous_task_root_file("tmp/screenshot.png"))

    def test_file_inside_acceptance_tests_subdirectory_stays_legal(self):
        """Единственная легальная поддиректория первого уровня —
        `acceptance_tests/` — не задета правилом R1-F1 (по собственным
        правилам 01M1SAA01YRRTWAVADT2F81RRQ)."""
        self.assertFalse(
            guard.is_extraneous_task_root_file("acceptance_tests/test_x.py"))

    def test_top_level_files_unaffected_by_the_fix(self):
        """Регресс-контроль: правка не трогает поведение файлов РОВНО
        одного уровня — уже покрытое залоченной планкой AC-1/AC-2."""
        self.assertFalse(guard.is_extraneous_task_root_file("PLAN.md"))
        self.assertTrue(guard.is_extraneous_task_root_file("_head_map.md"))
        self.assertFalse(guard.is_extraneous_task_root_file("screenshot.png"))


class GuardAllModeFlagsSubdirectoryFileTest(unittest.TestCase):
    """Guard `--all`: файл в новой поддиректории первого уровня —
    именованная причина «посторонний файл в каталоге задачи»."""

    TASK = "01FAKEGUARDNESTEDSTRAY1"

    def run_guard(self, argv: list) -> tuple:
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["scripts/guard.py", *argv]):
            with redirect_stdout(buf):
                rc = guard.main()
        return rc, buf.getvalue()

    def test_nested_stray_file_is_flagged_in_all_mode(self):
        """Ловит мутацию R1-F1: `tasks/<id>/wip/_head_map.md` рядом с
        валидным `PLAN.md` не получает именованную причину — код возврата
        остаётся 0 там, где ожидается 1."""
        import os
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            task_dir = tmp_root / "tasks" / self.TASK
            (task_dir / "wip").mkdir(parents=True)
            (task_dir / "PLAN.md").write_text(
                "---\ntask: x\ntype: plan\nstatus: draft\n---\n# x\n",
                encoding="utf-8")
            (task_dir / "wip" / "_head_map.md").write_text(
                "черновая копия карты\n", encoding="utf-8")
            orig_cwd = Path.cwd()
            os.chdir(tmp_root)
            try:
                rc, out = self.run_guard(["--all"])
            finally:
                os.chdir(orig_cwd)

        self.assertEqual(rc, 1, out)
        self.assertIn(guard.EXTRANEOUS_TASK_ROOT_FILE_REASON, out)
        self.assertIn(NESTED_STRAY, out)


class CheckpointDropsSubdirectoryFileTest(RealGitSandbox):
    """AC-4/AC-5/AC-6: `commit_step_artifacts` отбрасывает файл в новой
    поддиректории первого уровня тем же критерием, одна запись журнала."""

    def setUp(self):
        super().setUp()
        self.TASK = "01CHKNESTEDTASKROOTSTR"
        conn = store.db()
        store.insert_task(conn, self.TASK, "Задача внешнего target",
                          "in_dev", f"task/{self.TASK.lower()}-x", TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, text: str = "содержимое\n") -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def journal_rows(self) -> list:
        return store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()

    def test_nested_stray_file_dropped_allowed_file_kept_single_journal_entry(self):
        """Ловит мутацию R1-F1: `checkpoint.py` наследует дырявый критерий
        guard'а — `wip/_head_map.md` уезжает в артефактную ветку наравне
        с `PLAN.md`, и `assertNotIn` ниже это поймает."""
        self.write("PLAN.md", "план")
        self.write(NESTED_STRAY, "черновая копия карты кодовой базы")

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertTrue(detail)
        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", files)
        self.assertNotIn(f"tasks/{self.TASK}/{NESTED_STRAY}", files)

        rows = self.journal_rows()
        stray_rows = [r for r in rows if NESTED_STRAY in (r["detail"] or "")]
        self.assertEqual(len(stray_rows), 1, [dict(r) for r in rows])


class MergeGateGuardRefusesSubdirectoryFileTest(TmpRootTest):
    """AC-7/AC-8: `_guard_task_root_or_refuse` отказывает на файле в новой
    поддиректории первого уровня снимка артефактной ветки — тем же
    критерием, ДО push."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.TASK = "01MERGEGATENESTEDSTRAY1"
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          f"task/{self.TASK.lower()}-x",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def test_nested_stray_file_in_snapshot_blocks_before_push(self):
        """Ловит мутацию R1-F1: критерий унаследованный из guard.py не
        видит файл глубже одного уровня — `_guard_task_root_or_refuse`
        молча возвращается там, где ожидается `SystemExit`."""
        scratch = self.root / "scratch"
        task_dir = scratch / "tasks" / self.TASK
        (task_dir / "wip").mkdir(parents=True)
        (task_dir / "PLAN.md").write_text("план\n", encoding="utf-8")
        (task_dir / "wip" / "_head_map.md").write_text(
            "черновая копия карты\n", encoding="utf-8")

        with self.assertRaises(SystemExit) as exit_:
            fsm_merge_gate._guard_task_root_or_refuse(
                store.db(), self.TASK, scratch)

        message = str(exit_.exception)
        self.assertIn(NESTED_STRAY, message)

        row = store.db().execute("SELECT state FROM tasks WHERE id=?",
                                 (self.TASK,)).fetchone()
        self.assertEqual(row["state"], "merge_gate")

        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=?",
            (self.TASK,)).fetchall()
        self.assertTrue(
            any(NESTED_STRAY in (r["detail"] or "") for r in rows),
            [dict(r) for r in rows])


if __name__ == "__main__":
    unittest.main()
