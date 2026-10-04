"""Юнит-тесты прогона планки после подтяжки main с долгоживущей группой
(SPEC 01M3XVW94Z8E8R71XN7QWYMSP4, требования 1-3, 5; AC-1…AC-4).

Песочница — приём `tests/test_pull.py::PullEvaluateTest`: `pull.evaluate`
напрямую, дисковые `gitcmd.show`/`gitcmd.ls_tree_files`
(`tests/sandbox.py`) — перечень читается из «дерева лока» на диске
`config.TASKS`, поддельный `gitcmd.in_repo` (merge «проходит»),
`workspace.ensure` — временный каталог `wt`. Прогон pytest'ом планки и
долгоживущего файла — настоящий (`acceptance.run`): ложная эскалация, от
которой лечит задача, — именно исход настоящего pytest «collected 0 items».
"""
import hashlib
import subprocess
import unittest
from unittest import mock

from orchestrator import acceptance, config, gitcmd, pull, store, workspace
from scripts import guard
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,
                           disk_backed_show)

SPEC_FIXTURE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: фикстура tests/test_pull_long_lived_plank.py

## Критерии приёмки

AC-1. Фикстура.
"""

ONE_OFF_GREEN = '''import unittest


class OneOffTest(unittest.TestCase):

    def test_one_off(self):
        self.assertTrue(True)
'''

LONG_LIVED = '''import unittest


class LongLivedTest(unittest.TestCase):

    def test_long_lived(self):
        self.assertTrue({green})
'''


class PullLongLivedPlankTest(TmpRootTest):

    TASK = "01PULLLONGLIVEDPLANKUNIT"
    BRANCH = f"task/{TASK.lower()}-x"
    LOCKED = "2222222222222222222222222222222222222222"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "Планка после подтяжки",
                          "in_dev", self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(store.db(), self.TASK, tests_locked_sha=self.LOCKED)
        self.wt_path = self.root / "wt"
        (self.wt_path / "tests").mkdir(parents=True)
        tdir = config.TASKS / self.TASK
        self.plank = tdir / "acceptance_tests"
        self.plank.mkdir(parents=True)
        (tdir / "SPEC.md").write_text(SPEC_FIXTURE.format(task=self.TASK),
                                      encoding="utf-8")
        self.own = f"tests/test_{self.TASK.lower()}_alpha.py"
        self.manifest_rel = (f"tasks/{self.TASK}/acceptance_tests/"
                             f"{guard.LONG_LIVED_MANIFEST_NAME}")

        for patcher in (
                mock.patch.object(gitcmd, "show", disk_backed_show),
                mock.patch.object(gitcmd, "ls_tree_files",
                                  disk_backed_ls_tree_files),
                mock.patch.object(workspace, "ensure",
                                  lambda task_id, branch: (self.wt_path, None)),
                mock.patch.object(gitcmd, "commits_behind", return_value=3),
                mock.patch.object(gitcmd, "in_repo", side_effect=self._ok)):
            patcher.start()
            self.addCleanup(patcher.stop)
        real_run = acceptance.run
        self.run_spy = mock.Mock(side_effect=lambda *a, **k: real_run(*a, **k))
        run_patcher = mock.patch.object(acceptance, "run", self.run_spy)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

    # ------------------------------------------------------------ утилиты

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            ("git", "-C", str(repo), *args), 0, "", "")

    def evaluate(self):
        conn = store.db()
        return pull.evaluate(
            conn, self.TASK, store.get_task(conn, self.TASK), "in_dev",
            origin_main_source=mock.Mock(
                return_value=("origin", config.MAIN_BRANCH)),
            origin_main_sha=mock.Mock(return_value="deadbeefcafefeed"),
            read_branch_text_or_refuse=mock.Mock(return_value=None))

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def journal_text(self) -> str:
        return "\n".join(f"{r['action']} {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), self.TASK))

    def long_lived_only_plank(self, green: bool) -> None:
        data = LONG_LIVED.format(green=green).encode("utf-8")
        (self.wt_path / self.own).write_bytes(data)
        (self.plank / guard.LONG_LIVED_MANIFEST_NAME).write_text(
            f"{hashlib.sha256(data).hexdigest()}  {self.own}\n",
            encoding="utf-8")

    def extra_passed(self) -> list:
        return list(self.run_spy.call_args.kwargs.get("extra", ()))

    # ---------------------------------------------------------------- AC-1

    def test_long_lived_only_plank_green_pulls(self):
        """Планка — один перечень, долгоживущий файл зелёный: исход
        `Pulled`, задача в `in_dev`, долгоживущий файл передан в прогон.

        Ловит мутацию: прогон после подтяжки снова берёт только каталог
        acceptance_tests/ — pytest «collected 0 items» (код 5), исход
        `Conflict`, задача в `escalated`."""
        self.long_lived_only_plank(green=True)
        outcome = self.evaluate()
        self.assertIsInstance(outcome, pull.Pulled, self.journal_text())
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.extra_passed(), [self.own])

    # ---------------------------------------------------------------- AC-2

    def test_long_lived_red_escalates(self):
        """Тот же случай с красным долгоживущим файлом: исход `Conflict`,
        задача в `escalated`, деталь называет упавший файл.

        Ловит мутацию: долгоживущая группа передана, но её исход не
        учитывается — задача остаётся в `in_dev`, исход `Pulled`."""
        self.long_lived_only_plank(green=False)
        outcome = self.evaluate()
        self.assertIsInstance(outcome, pull.Conflict)
        self.assertEqual(self.state(), "escalated")
        self.assertIn(self.own, outcome.note)

    # ---------------------------------------------------------------- AC-3

    def test_manifest_read_failure_refuses_by_name(self):
        """git не ответил на дерево лока по пути перечня: исход `Refused`
        с текстом о перечне, прогона нет, задача не эскалирована —
        даже при зелёной разовой группе в планке.

        Ловит мутацию: сбой перечня молча сводится к пустой группе —
        прогон одной разовой группы зелёный, исход `Pulled`."""
        self.long_lived_only_plank(green=True)
        (self.plank / "test_one_off.py").write_text(ONE_OFF_GREEN,
                                                    encoding="utf-8")
        manifest_rel = self.manifest_rel

        def ls_tree(branch, rel, repo=None):
            # `repo` — клон проекта задачи (ADR-0021 п.1, этап 2).
            if rel == manifest_rel:
                return None
            return disk_backed_ls_tree_files(branch, rel, repo=repo)

        with mock.patch.object(gitcmd, "ls_tree_files", ls_tree):
            outcome = self.evaluate()
        self.assertIsInstance(outcome, pull.Refused)
        self.assertIn("перечень долгоживущих файлов", outcome.reason)
        self.assertIn(self.LOCKED, outcome.reason)
        self.run_spy.assert_not_called()
        self.assertEqual(self.state(), "in_dev")
        self.assertIn("перечень долгоживущих файлов не прочитан",
                      self.journal_text())

    # ---------------------------------------------------------------- AC-4

    def test_task_without_manifest_runs_plank_only(self):
        """Задача без перечня (лок без перечня в дереве; лока нет вовсе):
        один прогон без долгоживущих файлов, исход `Pulled`, `in_dev`.

        Ловит мутацию: отсутствие перечня трактуется как сбой его чтения
        (`Refused`) либо в прогон уходит чужая группа файлов `tests/`
        (`extra` не пуст)."""
        (self.plank / "test_one_off.py").write_text(ONE_OFF_GREEN,
                                                    encoding="utf-8")
        for label, locked in (("лок без перечня", self.LOCKED),
                              ("без лока", None)):
            with self.subTest(вид=label):
                store.update_task(store.db(), self.TASK,
                                  tests_locked_sha=locked)
                self.run_spy.reset_mock()
                outcome = self.evaluate()
                self.assertIsInstance(outcome, pull.Pulled)
                self.assertEqual(self.state(), "in_dev")
                self.assertEqual(self.run_spy.call_count, 1)
                self.assertEqual(self.extra_passed(), [])


if __name__ == "__main__":
    unittest.main()
