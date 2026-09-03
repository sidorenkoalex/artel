"""Юнит-тесты авторазрешения конфликта подтяжки, где единственный
конфликтующий файл — `docs/codebase-map.md` (SPEC T067) —
`orchestrator/fsm.py::_conflicting_files`/`_auto_resolve_map_conflict`,
подключённые внутрь `_pull_main_or_escalate`.

Полный прогон РЕАЛЬНОГО git и РЕАЛЬНОГО `scripts/codebase_map.py` —
приёмочные тесты `tasks/T067/acceptance_tests/` (`_sandbox.py`); здесь —
ветвление решения через мок трёх точек (`gitcmd.commits_behind`,
`gitcmd.in_repo`, `subprocess.run` регенератора), тем же приёмом лёгкой
FSM-песочницы без реального git, что и `tests/test_branch_freshness_
gate.py` (T051).
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
from tests.sandbox import (SpyRun, capture, capture_new_task_id,  # noqa: E402
                           disk_backed_ls_tree_files, disk_backed_show,
                           fake_git)

REPO_ROOT = Path(__file__).resolve().parent.parent

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: авторазрешение конфликта карты

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class MapConflictAutoResolveTest(unittest.TestCase):

    MAP_REL = "docs/codebase-map.md"

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
        # A7 (generic-путь заведения, AC-5): `cmd_new` коммитит артефакты
        # плотницки (`artifact_branch.write_commit`) — та функция зовёт
        # `subprocess.run` НАПРЯМУЮ, минуя `gitcmd.git`/фейк выше; `root`
        # здесь не настоящий git-репозиторий — без этого патча `cmd_new`
        # падает `sys.exit` («git не ответил») ещё до сценария, который
        # тест проверяет (тот же приём, что `tests.sandbox.TmpRootTest.
        # setUp`/`tests.test_spec_budget`).
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)
        # `artifact_source.resolve` теперь ВСЕГДА возвращает `foreign=True`
        # — FSM читает SPEC/PLAN через `gitcmd.show`/`ls_tree_files`, не с
        # диска напрямую; эта песочница без настоящего git ведёт один
        # источник истины — диск `self.tdir` (тот же приём, что
        # `tests.test_invariants.FsmTest`).
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        self.wt_path = root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Авторазрешение конфликта карты")
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

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in self.journal_rows()]

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def advance_from_in_dev(self) -> str:
        self.write_plan_ready()
        self.set_state("in_dev")
        return self.capture(fsm.cmd_advance, self.TASK)

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(("git", "-C", str(repo), *args), 0, "", "")

    def _conflict_response(self, repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            ("git", "-C", str(repo), *args), 1, "",
            "CONFLICT (content): Merge conflict in docs/codebase-map.md")

    def make_in_repo_side_effect(self, conflict_files: list[str]):
        """Заглушка `gitcmd.in_repo`, записывающая все вызовы, отвечающая
        конфликтом на `merge` и списком `conflict_files` на `diff
        --name-only --diff-filter=U`."""
        calls: list = []

        def side_effect(repo, *args):
            calls.append(args)
            if args[:1] == ("merge",) and "--abort" in args:
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                return self._conflict_response(repo, *args)
            if args[:2] == ("diff", "--name-only"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0,
                    "\n".join(conflict_files) + ("\n" if conflict_files else ""),
                    "")
            if args[:1] in (("checkout",), ("add",), ("commit",)):
                return self._ok(repo, *args)
            # `fsm._dirty_refuses`/`store.record_fixation` (A7: self/артель
            # фиксируется тем же кодом, что и любой target, — эти вызовы
            # существовали и до A7, просто не были достижимы этой лёгкой
            # песочницей раньше, пока она падала на `cmd_new`) сверяют/
            # коммитят артефактный репо `config.PROJECTS/<target>/`
            # (`fixation.read`/`fix`) ПЕРЕД/НА каждом из трёх гейтов
            # (SPEC/REVIEW/PLAN) — «чисто, нечего коммитить» здесь, тест
            # не о фиксации.
            if args == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "f" * 40 + "\n", "")
            if args[:2] == ("status", "--porcelain"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:1] == ("init",):
                return self._ok(repo, *args)
            if args[:2] == ("diff", "--cached"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")  # нечего коммитить
            raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

        return calls, side_effect

    # ------------------------------------------- авторазрешение — успех

    def test_map_only_conflict_autoresolves_without_escalation(self):
        calls, side_effect = self.make_in_repo_side_effect([self.MAP_REL])
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run",
                               return_value=subprocess.CompletedProcess(
                                   ["python3", "scripts/codebase_map.py"],
                                   0, "", "")) as regen, \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(self.state(), "review",
                         "конфликт только по карте не имеет права "
                         "эскалировать — переход обязан состояться")
        self.assertNotIn("эскалац", out.lower())
        regen.assert_called_once()
        self.assertEqual(regen.call_args.kwargs.get("cwd"), self.wt_path,
                         "регенерация обязана идти на СЛИТОМ дереве "
                         "worktree задачи, не главной копии пульта")
        acc_run.assert_called_once_with(self.wt_path / "tasks" / self.TASK)

        commit_calls = [c for c in calls if c[:1] == ("commit",)]
        self.assertEqual(len(commit_calls), 1,
                         "merge обязан быть завершён явным commit")
        abort_calls = [c for c in calls if c[:1] == ("merge",) and "--abort" in c]
        self.assertEqual(abort_calls, [], "успешное авторазрешение не "
                         "откатывает merge")

    def test_map_only_conflict_journal_records_orchestrator_and_method(self):
        calls, side_effect = self.make_in_repo_side_effect([self.MAP_REL])
        with mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run",
                               return_value=subprocess.CompletedProcess(
                                   ["python3", "scripts/codebase_map.py"],
                                   0, "", "")), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.advance_from_in_dev()

        rows = self.journal_rows()
        matching = [r for r in rows
                   if (r["actor"] or "") == "orchestrator"
                   and self.MAP_REL in (r["detail"] or "")]
        self.assertTrue(matching, f"нет записи actor=orchestrator, "
                        f"называющей {self.MAP_REL}: "
                        f"{[(r['actor'], r['action'], r['detail']) for r in rows]}")
        text = " ".join(f"{r['action'] or ''} {r['detail'] or ''}"
                        for r in matching).lower()
        self.assertTrue(any(k in text for k in ("регенерац", "regen")),
                        f"запись обязана называть способ разрешения: {text!r}")

    # --------------------------------------- авторазрешение — провал регенерации

    def test_map_only_conflict_regen_failure_aborts_and_escalates(self):
        calls, side_effect = self.make_in_repo_side_effect([self.MAP_REL])
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run",
                               return_value=subprocess.CompletedProcess(
                                   ["python3", "scripts/codebase_map.py"],
                                   1, "", "boom")), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(self.state(), "escalated",
                         "провал регенерации при авторазрешении обязан "
                         "эскалировать, а не оставлять полусмерженное "
                         "состояние")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        abort_calls = [c for c in calls if c[:1] == ("merge",) and "--abort" in c]
        self.assertEqual(len(abort_calls), 1,
                         "провал авторазрешения обязан откатывать merge")
        commit_calls = [c for c in calls if c[:1] == ("commit",)]
        self.assertEqual(commit_calls, [],
                         "merge не завершается commit'ом при провале "
                         "регенерации")
        acc_run.assert_not_called()

    # ----------------------------------- конфликт карты + другого файла

    def test_map_plus_other_file_conflict_still_escalates(self):
        calls, side_effect = self.make_in_repo_side_effect(
            [self.MAP_REL, "shared.txt"])
        with mock.patch.object(gitcmd, "commits_behind", return_value=4), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run") as regen, \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(self.state(), "escalated",
                         "конфликт по нескольким файлам, включая карту, "
                         "обязан эскалировать")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        regen.assert_not_called()
        abort_calls = [c for c in calls if c[:1] == ("merge",) and "--abort" in c]
        self.assertEqual(len(abort_calls), 1)
        acc_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
