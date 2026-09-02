"""Юнит-тесты сверки свежести ветки на входе в гейт (SPEC T051, требования
1, 3-7, 10) — orchestrator/fsm.py::_pull_main_or_escalate и её подключение
в обеих точках (`in_dev -> review` через `cmd_advance`, `acceptance ->
merge_gate` через `cmd_approve`).

Полный прогон РЕАЛЬНОГО git (merge, конфликт, `git merge --abort`, счёт
коммитов) — приёмочные тесты `tasks/T051/acceptance_tests/`
(`_sandbox.py::RealGitFreshnessTest`); здесь — ветвление самой логики
через мок трёх точек механизма (`gitcmd.commits_behind`, `gitcmd.in_repo`,
`orchestrator.acceptance.run`), тем же приёмом лёгкой FSM-песочницы без
реального git, что и `tests/test_advance_guard.py`.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, catalog, config, fsm, gitcmd,  # noqa: E402
                          store, workspace)
from tests.sandbox import capture, capture_new_task_id, fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сверка свежести

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class BranchFreshnessGateTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(REPO_ROOT / "templates", root / "templates")

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.wt_path = root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Сверка свежести")
        self.tdir = config.TASKS / self.TASK
        self.branch = self.task_row()["branch"]

    # ------------------------------------------------------------ утилиты

    capture = staticmethod(capture)

    def task_row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def advance_from_in_dev(self) -> str:
        self.write_plan_ready()
        self.set_state("in_dev")
        return self.capture(fsm.cmd_advance, self.TASK)

    def approve_from_acceptance(self) -> str:
        self.set_state("acceptance")
        return self.capture(fsm.cmd_approve, self.TASK)

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(("git", "-C", str(repo), *args), 0, "", "")

    def _conflict_then_abort_ok(self, repo, *args) -> subprocess.CompletedProcess:
        if args[:1] == ("merge",) and "--abort" in args:
            self.abort_calls.append((repo, args))
            return self._ok(repo, *args)
        if args[:1] == ("merge",):
            self.merge_calls.append((repo, args))
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 1, "",
                "CONFLICT (content): Merge conflict in shared.txt")
        if args[:2] == ("diff", "--name-only"):
            # Конфликт не сводится к «только карта» (SPEC T067,
            # требование 4) — список конфликтующих файлов называет
            # посторонний файл, авторазрешение не применимо, прежний
            # abort+escalate.
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "shared.txt\n", "")
        raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

    def _recording_ok(self, repo, *args) -> subprocess.CompletedProcess:
        self.merge_calls.append((repo, args))
        return self._ok(repo, *args)

    def setup_recording(self) -> None:
        self.merge_calls: list = []
        self.abort_calls: list = []

    # ----------------------------------------------------- ветка не отстала

    def test_advance_skips_pull_when_branch_not_behind(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=0), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "review",
                         "переход обязан пройти как и до T051 (требование 7)")
        self.assertEqual(self.merge_calls, [], "не отставшая ветка — merge не звонится")
        acc_run.assert_not_called()

    def test_approve_skips_pull_when_branch_not_behind(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=None), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            self.approve_from_acceptance()

        self.assertEqual(self.state(), "merge_gate",
                         "None (git не ответил) — тот же вырожденный случай, "
                         "что и 0 коммитов (требование 9)")
        self.assertEqual(self.merge_calls, [])
        acc_run.assert_not_called()

    # ------------------------------------------------- успешная подтяжка

    def test_advance_pulls_main_and_advances_when_acceptance_green(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "review",
                         "переход обязан состояться после успешной подтяжки")
        self.assertEqual(len(self.merge_calls), 1)
        repo, args = self.merge_calls[0]
        self.assertEqual(repo, self.wt_path, "merge — в worktree ЗАДАЧИ, "
                         "не в рабочей копии пульта (ADR-0006 п.2)")
        self.assertEqual(args[0], "merge")
        self.assertIn("--no-ff", args, "подтяжка не rebase (требование 3)")
        self.assertIn(config.MAIN_BRANCH, args)
        self.assertNotIn(self.branch, args,
                         "ветка задачи не упоминается в аргументах merge")
        acc_run.assert_called_once_with(self.wt_path / "tasks" / self.TASK)

    def test_approve_pulls_main_and_advances_when_acceptance_green(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.approve_from_acceptance()

        self.assertEqual(self.state(), "merge_gate")
        self.assertEqual(len(self.merge_calls), 1)
        acc_run.assert_called_once_with(self.wt_path / "tasks" / self.TASK)

    # --------------------------------------------------- конфликт подтяжки

    def test_advance_escalates_on_pull_conflict_and_aborts(self):
        self.setup_recording()
        self.write_plan_ready()
        self.set_state("in_dev")
        with mock.patch.object(gitcmd, "commits_behind", return_value=5), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._conflict_then_abort_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated",
                         "конфликт подтяжки обязан эскалировать (требование 5)")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(len(self.abort_calls), 1,
                         "конфликт обязан откатываться git merge --abort")
        acc_run.assert_not_called()

    def test_approve_escalates_on_pull_conflict_and_aborts(self):
        self.setup_recording()
        self.set_state("acceptance")
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._conflict_then_abort_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        self.assertEqual(len(self.abort_calls), 1)
        acc_run.assert_not_called()

    # --------------------------------------- красные приёмочные после пула

    def test_advance_escalates_on_red_acceptance_after_pull_keeps_merge(self):
        self.setup_recording()
        self.write_plan_ready()
        self.set_state("in_dev")
        with mock.patch.object(gitcmd, "commits_behind", return_value=4), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(False, "MARKER-RED")):
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated",
                         "красные приёмочные после подтяжки эскалируют "
                         "(требование 6)")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("MARKER-RED", combined)
        self.assertEqual(len(self.merge_calls), 1,
                         "слияние остаётся — откат не выполняется")
        self.assertEqual(self.abort_calls, [])

    def test_approve_escalates_on_red_acceptance_after_pull_keeps_merge(self):
        self.setup_recording()
        self.set_state("acceptance")
        with mock.patch.object(gitcmd, "commits_behind", return_value=7), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(False, "MARKER-RED")):
            out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("MARKER-RED", combined)
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(self.abort_calls, [])

    # ------------------------------------------------ worktree недоступен

    def test_advance_escalates_when_worktree_not_available(self):
        with mock.patch.object(gitcmd, "commits_behind", return_value=9), \
             mock.patch.object(workspace, "ensure",
                               return_value=(self.wt_path, "worktree add упал")):
            self.write_plan_ready()
            self.set_state("in_dev")
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("worktree", combined)


if __name__ == "__main__":
    unittest.main()
