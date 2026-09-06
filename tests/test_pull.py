"""Юнит-тесты `orchestrator/pull.py::evaluate` (роадмап §3, фаза R, R3):
каждый из четырёх исходов подтяжки — `Fresh`/`Pulled`/`Conflict`/
`Refused` — лёгкой песочницей с поддельным git (тот же приём, что
`tests/test_fsm_map_conflict_autoresolve.py`), но зовёт `pull.evaluate`
напрямую, минуя `fsm._pull_main_or_escalate` — предмет проверки ровно
вычисление исхода, не диспетчеризация FSM вокруг него (та — в
`tests/test_branch_freshness_gate.py`/`tests/test_fsm_map_conflict_
autoresolve.py` и в приёмочных тестах задачи).

`origin_main_source`/`origin_main_sha`/`read_branch_text_or_refuse` —
узлы `fsm.py`, `evaluate()` принимает их параметрами (не импортом
`fsm`, см. докстринг `pull.py`) — здесь это простые фейки, без
затрагивания `orchestrator.fsm` вовсе.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance, config, gitcmd, pull, store  # noqa: E402
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show)

MAP_REL = "docs/codebase-map.md"

SPEC_WITH_AC_MARKUP = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка (фикстура tests/test_pull.py)

## Критерии приёмки

AC-1. Фикстура.
"""


class PullEvaluateTest(TmpRootTest):

    TASK = "01PULLEVALUATEUNITTEST"
    BRANCH = f"task/{TASK.lower()}-x"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "Юнит-тест pull.evaluate",
                          "in_dev", self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        # `gitcmd.in_repo` — каждый тест патчит своей заглушкой (дефолт
        # «чисто, всё ок» — `self._default_in_repo`, ниже переопределяется
        # точечно там, где нужен конфликт/инцидент).
        self.wt_path = self.root / "wt"
        from orchestrator import workspace
        ensure_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        ensure_patcher.start()
        self.addCleanup(ensure_patcher.stop)

        self.origin_main_source = mock.Mock(
            return_value=("origin", config.MAIN_BRANCH))
        self.origin_main_sha = mock.Mock(return_value="deadbeefcafefeed")
        self.read_branch_text_or_refuse = mock.Mock(return_value=None)

    # ------------------------------------------------------------ утилиты

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            ("git", "-C", str(repo), *args), 0, "", "")

    def _default_in_repo(self, repo, *args) -> subprocess.CompletedProcess:
        return self._ok(repo, *args)

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def evaluate(self, state: str = "in_dev"):
        conn = store.db()
        t = self.task_row()
        return pull.evaluate(
            conn, self.TASK, t, state,
            origin_main_source=self.origin_main_source,
            origin_main_sha=self.origin_main_sha,
            read_branch_text_or_refuse=self.read_branch_text_or_refuse)

    def write_acceptance_plank(self) -> None:
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(
            SPEC_WITH_AC_MARKUP.format(task=self.TASK), encoding="utf-8")
        tests_dir = tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_stub.py").write_text(
            "import unittest\n\n\nclass StubTest(unittest.TestCase):\n\n"
            "    def test_stub(self):\n        pass\n", encoding="utf-8")

    def write_spec_requiring_ac_without_plank(self) -> None:
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(
            SPEC_WITH_AC_MARKUP.format(task=self.TASK), encoding="utf-8")

    def conflict_in_repo(self, conflict_files: list):
        def side_effect(repo, *args) -> subprocess.CompletedProcess:
            if args[:1] == ("merge",) and "--abort" in args:
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, "",
                    "CONFLICT (content): boom")
            if args[:2] == ("diff", "--name-only"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0,
                    "\n".join(conflict_files) + "\n", "")
            return self._ok(repo, *args)
        return side_effect

    # --------------------------------------------------------------- Fresh

    def test_fresh_when_origin_sha_missing(self):
        """`origin_main_sha` выродилась (git fetch/rev-parse не ответили) —
        `evaluate` обязан вернуть `Fresh()` немедленно, не вызывая
        `commits_behind`/merge вовсе."""
        self.origin_main_sha.return_value = None
        with mock.patch.object(gitcmd, "commits_behind") as behind:
            outcome = self.evaluate()
        self.assertEqual(outcome, pull.Fresh())
        behind.assert_not_called()

    def test_fresh_when_branch_not_behind(self):
        with mock.patch.object(gitcmd, "commits_behind", return_value=0):
            outcome = self.evaluate()
        self.assertEqual(outcome, pull.Fresh())

    # -------------------------------------------------------------- Pulled

    def test_pulled_on_clean_merge_and_green_acceptance(self):
        self.write_acceptance_plank()
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._default_in_repo), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            outcome = self.evaluate()
        self.assertIsInstance(outcome, pull.Pulled)
        self.assertEqual(outcome.sha, "deadbeefcafefeed")
        self.assertEqual(self.task_row()["state"], "in_dev")

    def test_pulled_when_plank_missing_but_skip_tests_legitimate(self):
        """Планка не найдена, но SPEC без AC-разметки — легитимный
        вырожденный случай (AC-5 SPEC 01M1R9YEK08XEQWBFX0929WFVJ):
        `Pulled`, не `Refused`."""
        self.read_branch_text_or_refuse.return_value = (
            "---\ntask: x\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 1\n---\n\n# SPEC\n")
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._default_in_repo):
            outcome = self.evaluate()
        self.assertIsInstance(outcome, pull.Pulled)

    # ------------------------------------------------------------ Conflict

    def test_conflict_on_two_file_unresolved_merge_conflict(self):
        with mock.patch.object(gitcmd, "commits_behind", return_value=4), \
             mock.patch.object(
                 gitcmd, "in_repo",
                 side_effect=self.conflict_in_repo([MAP_REL, "shared.txt"])):
            outcome = self.evaluate(state="in_dev")
        self.assertIsInstance(outcome, pull.Conflict)
        self.assertEqual(outcome.files, [MAP_REL, "shared.txt"])
        self.assertIn("конфликт подтяжки", outcome.note)
        self.assertEqual(self.task_row()["state"], "escalated")

    def test_conflict_when_worktree_not_available(self):
        from orchestrator import workspace
        with mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(workspace, "ensure",
                               return_value=(self.wt_path, "worktree add упал")):
            outcome = self.evaluate()
        self.assertIsInstance(outcome, pull.Conflict)
        self.assertIn("worktree", outcome.note)
        self.assertEqual(self.task_row()["state"], "escalated")

    def test_conflict_on_red_acceptance_after_clean_merge(self):
        self.write_acceptance_plank()
        with mock.patch.object(gitcmd, "commits_behind", return_value=5), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._default_in_repo), \
             mock.patch.object(acceptance, "run",
                               return_value=(False, "МАРКЕР-КРАСНЫЙ")):
            outcome = self.evaluate()
        self.assertIsInstance(outcome, pull.Conflict)
        self.assertIn("МАРКЕР-КРАСНЫЙ", outcome.note)
        self.assertEqual(self.task_row()["state"], "escalated")

    # ------------------------------------------------------------- Refused

    def test_refused_when_plank_missing_and_ac_required(self):
        self.write_spec_requiring_ac_without_plank()
        self.read_branch_text_or_refuse.return_value = (
            SPEC_WITH_AC_MARKUP.format(task=self.TASK))
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._default_in_repo):
            outcome = self.evaluate()
        self.assertIsInstance(outcome, pull.Refused)
        self.assertIsNotNone(outcome.reason)
        self.assertIn("планка не найдена в источнике", outcome.reason)
        self.assertEqual(self.task_row()["state"], "in_dev",
                         "Refused не имеет права менять состояние задачи")

    def test_refused_none_when_branch_text_read_already_refused(self):
        """`read_branch_text_or_refuse` уже журналировала/напечатала свой
        именованный отказ (вернула `None`) — `evaluate` не добавляет
        второй, несёт `Refused(None)` как сигнал «уже сделано»."""
        self.read_branch_text_or_refuse.return_value = None
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._default_in_repo):
            outcome = self.evaluate()
        self.assertEqual(outcome, pull.Refused(None))


if __name__ == "__main__":
    unittest.main()
