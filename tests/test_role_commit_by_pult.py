"""Юнит-тесты сверки незакоммиченного результата шага после отказа git на
коммите пульта — `checkpoint.pult_commit_failed_paths` (SPEC
01M3VFYP4RXBY0BG8D3A0B18HD, требование 3).

Свойства, не покрытые долгоживущими файлами задачи: сверка включается
только свежей записью отказа git, снимается последующим успешным коммитом
пульта и не считает посторонние пути вне зон задачи; «нечего коммитить»
отказом git не считается. Песочница — настоящий git
(`tests/sandbox.py::RealGitSandbox`), отказ git — настоящий хук
`pre-commit`.
"""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from orchestrator import checkpoint, config, fsm, store, workspace
from scripts import guard
from tests.sandbox import RealGitSandbox

TASK = "01M0000000000000000000RCBP"
BRANCH = "task/fixture-role-commit-by-pult"


class _Sandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Фикстура коммита пультом",
                          "in_dev", BRANCH, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(TASK, BRANCH)
        self.assertIsNone(error, error)
        self.wt = wt

    def write(self, rel: str, text: str = "x = 1\n") -> None:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def wt_git(self, *args: str) -> str:
        return self.git("-C", str(self.wt), *args)

    def reject_commits(self) -> Path:
        common = Path(self.git("rev-parse", "--git-common-dir").strip())
        if not common.is_absolute():
            common = self.root / common
        hook = common / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\necho 'hook says no' >&2\nexit 1\n",
                        encoding="utf-8")
        hook.chmod(0o755)
        self.addCleanup(hook.unlink, missing_ok=True)
        return hook

    def failed_records(self) -> list:
        return [r for r in store.task_steps(self.conn, TASK)
                if r["action"] == checkpoint.PULT_COMMIT_GIT_FAILED_ACTION]


class PultCommitFailedPathsTest(_Sandbox):

    def test_dirty_worktree_without_git_failure_is_not_reported(self):
        """Ловит мутацию: сверка не ждёт записи отказа git и считает
        незакоммиченным результатом любую грязь worktree — путь без отказа
        git попадёт в возврат, и `advance` откажет на ровном месте."""
        self.write("pkg/wip.py")
        self.assertEqual(checkpoint.pult_commit_failed_paths(self.conn, TASK),
                         [])

    def test_failure_reports_uncommitted_paths_except_task_dir(self):
        """Ловит мутацию: `tasks/<id>/` не исключён из сверки — PLAN.md
        роли, который пульт переносит в артефактную ветку, а не в кодовую,
        попадёт в перечень незакоммиченного кода."""
        hook = self.reject_commits()
        self.write("pkg/code.py")
        self.write(f"tasks/{TASK}/PLAN.md", "plan\n")
        checkpoint.commit_success_checkpoint(self.conn, TASK, "developer")
        self.assertTrue(self.failed_records())
        hook.unlink()
        self.assertEqual(checkpoint.pult_commit_failed_paths(self.conn, TASK),
                         ["pkg/code.py"])

    def test_later_pult_commit_clears_failure(self):
        """Ловит мутацию: успешный коммит пульта после отказа не снимает
        признак отказа — новая правка worktree следующего шага
        числилась бы незакоммиченным результатом прошлого."""
        hook = self.reject_commits()
        self.write("pkg/code.py")
        checkpoint.commit_success_checkpoint(self.conn, TASK, "developer")
        hook.unlink()
        detail = checkpoint.commit_success_checkpoint(self.conn, TASK,
                                                      "developer")
        self.assertTrue(detail, "пульт не закоммитил код после снятия хука")
        self.write("pkg/next_step.py")
        self.assertEqual(checkpoint.pult_commit_failed_paths(self.conn, TASK),
                         [])

    def test_stray_paths_outside_zones_do_not_count(self):
        """Ловит мутацию: зонный фильтр не применён к сверке — посторонний
        путь вне зон, который пульт сознательно не коммитит
        (`STRAY_WORKTREE_FILES_ACTION`), держал бы переход вечно, хотя код
        в зоне роль уже закоммитила сама."""
        store.update_task(self.conn, TASK, zones="pkg/")
        hook = self.reject_commits()
        self.write("pkg/code.py")
        self.write("stray/notes.txt")
        checkpoint.commit_success_checkpoint(self.conn, TASK, "developer")
        hook.unlink()
        self.wt_git("add", "pkg/code.py")
        self.wt_git("commit", "-q", "-m", "роль закоммитила сама")
        self.assertEqual(checkpoint.pult_commit_failed_paths(self.conn, TASK),
                         [])


class TestsWritingBlockedAfterGitFailureTest(_Sandbox):

    def test_tests_writing_advance_refuses_uncommitted_long_lived_file(self):
        """Ловит мутацию: выход из `tests_writing` не сверяет
        незакоммиченный результат шага (требование 4 → требование 3) —
        после отказа git у test_author `advance` отказывает по иной
        причине (трассируемость) либо уводит задачу в `in_dev`, и записи
        «результат шага не закоммичен» с путём долгоживущего файла нет."""
        store.update_task(self.conn, TASK, state="tests_writing")
        rel = f"{guard.long_lived_path_prefix(TASK)}case.py"
        self.write(rel, "def test_ac1_case():\n    pass\n")
        hook = self.reject_commits()
        checkpoint.commit_success_checkpoint(self.conn, TASK, "test_author")
        self.assertTrue(self.failed_records())
        hook.unlink()
        since = store.task_steps(self.conn, TASK)[-1]["id"]
        with redirect_stdout(io.StringIO()):
            try:
                fsm.cmd_advance(TASK)
            except SystemExit:
                pass
        self.assertEqual(store.get_task(self.conn, TASK)["state"],
                         "tests_writing")
        refusals = [r["detail"] for r in store.task_steps(self.conn, TASK)
                    if r["id"] > since and r["action"]
                    == "переход отклонён: результат шага не закоммичен"]
        self.assertTrue(refusals)
        self.assertIn(rel, refusals[0])


class NothingToCommitIsNotFailureTest(_Sandbox):

    def test_clean_worktree_writes_no_git_failure_record(self):
        """Ловит мутацию: «нечего коммитить» (`diff --cached --quiet` с
        кодом 0) журналируется как отказ git — запись
        `PULT_COMMIT_GIT_FAILED_ACTION` появится на чистом worktree."""
        self.assertEqual(
            checkpoint.commit_success_checkpoint(self.conn, TASK, "developer"),
            "")
        self.assertEqual(self.failed_records(), [])


if __name__ == "__main__":
    unittest.main()
