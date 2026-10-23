"""Уточнения ANSWER-2 задачи 01M5M675F6K2TE7TTJN3AET4PP, не покрытые её
долгоживущими файлами: `git remote prune origin` не зовётся при отказе
`pin-update` по CI и по сбою `merge --ff-only` (п. 2); вид «бесхозные
каталоги .artel/worktrees» команды `prune` оставляет незарегистрированный
каталог с `.git` (п. 4) и убирает каталог с именем закрытой задачи (п. 5).

Песочницы — настоящий git главной копии с bare `origin`
(`SyncedOriginConnSandbox`) и главная копия плюс отдельный клон артели
(`RealGitSandbox`, `ARTEL_CLONE_IS_ROOT = False`); подменены только запуск
git (шпион), цвет CI и возраст прогона канарейки.
"""
import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import canary, ci, config, pin, prune, store  # noqa: E402
from tests.sandbox import RealGitSandbox, SyncedOriginConnSandbox  # noqa: E402


def _is_remote_prune(args) -> bool:
    words = [str(a) for a in args]
    return "remote" in words and "prune" in words


class PinRefusalSkipsPruneTest(SyncedOriginConnSandbox):

    def setUp(self):
        super().setUp()
        (self.root / "pin_target.txt").write_text("цель\n", encoding="utf-8")
        self.git("add", "pin_target.txt")
        self.git("commit", "-q", "-m", "целевой коммит main")
        self.target = self.git("rev-parse", "HEAD").strip()
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.old = self.git("rev-parse", "HEAD").strip()
        self.git("update-ref", "refs/remotes/origin/task/gone", self.old)

    def run_pin_update(self, ci_kind: str, fail_merge: bool):
        real_git = pin.gitcmd.git
        calls = []

        def spy(*args):
            calls.append(args)
            if fail_merge and args[:1] == ("merge",):
                return subprocess.CompletedProcess(list(args), 1, "",
                                                   "fatal: подменённый сбой")
            return real_git(*args)

        status = ci.MainLineStatus(ci_kind, self.target, [], [], "", "CI")
        with mock.patch.object(pin.gitcmd, "git", side_effect=spy), \
                mock.patch.object(ci, "main_line_status", return_value=status), \
                mock.patch.object(canary, "merges_since_last_green_run",
                                  return_value=0), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit):
            pin.cmd_pin_update(self.target)
        return calls

    def test_ci_and_merge_refusals_never_call_remote_prune(self):
        """Отказ по красному CI, по неподтверждённому CI и по сбою сдвига —
        `remote prune` не вызван, ссылка `origin/task/gone` на месте.

        Ловит мутацию: уборка поставлена до проверки CI или до `merge
        --ff-only` (либо в `finally`) — шпион видит вызов `remote prune`,
        ссылка исчезает при отказе.
        """
        for label, kind, fail_merge in (
                ("CI красный", ci.MAIN_RED, False),
                ("CI не подтверждён", ci.MAIN_UNKNOWN, False),
                ("сбой сдвига", ci.MAIN_GREEN, True)):
            with self.subTest(отказ=label):
                calls = self.run_pin_update(kind, fail_merge)
                self.assertEqual([a for a in calls if _is_remote_prune(a)], [])
                self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.old)
                self.assertTrue(self.git(
                    "for-each-ref", "refs/remotes/origin/task/gone").strip())


class OrphanWorktreeGitAndClosedNameTest(RealGitSandbox):

    ARTEL_CLONE_IS_ROOT = False

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        clone = config.PROJECTS / config.DEFAULT_TARGET / "repo"
        clone.parent.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", config.MAIN_BRANCH, str(clone))
        self.wt = Path(config.WORKTREES)

    def run_prune(self, execute: bool) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            prune.cmd_prune(execute=execute)
        return out.getvalue()

    def test_unregistered_dir_with_git_is_left_with_reason(self):
        """Незарегистрированный каталог с `.git` (файл и каталог) не
        удаляется ни планом, ни `--execute`; строка «оставлен — есть .git».

        Ловит мутацию: проверка `.git` убрана (каталог с `.git` удаляется
        как бесхозный без него) либо смотрит только `is_dir()` — каталог с
        файлом `.git` удаляется; либо строка «оставлен» не печатается.
        """
        names = ("with-git-dir", "with-git-file")
        (self.wt / names[0] / ".git").mkdir(parents=True)
        (self.wt / names[1]).mkdir(parents=True)
        (self.wt / names[1] / ".git").write_text("gitdir: /nowhere\n",
                                                 encoding="utf-8")
        for execute in (False, True):
            output = self.run_prune(execute)
            for name in names:
                self.assertIn(f"  каталог .artel/worktrees/{name}: оставлен — "
                              "есть .git", output.splitlines(), output)
                self.assertTrue(os.path.lexists(self.wt / name / ".git"), output)
            self.assertNotIn("нечего убирать", output)

    def test_closed_task_name_is_removed_open_kept(self):
        """Каталог с именем задачи `done`/`killed` удаляется, с именем
        незакрытой — остаётся.

        Ловит мутацию: защищены имена всех задач из БД, а не только
        незакрытых — каталоги закрытых задач переживают `--execute`.
        """
        dirs = {}
        for state in ("done", "killed", "in_dev"):
            task_id = f"01M5M675F6K2TE7TTJN3AET{state[:3].upper()}"
            store.insert_task(self.conn, task_id, "Задача", state,
                              f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                              25.0)
            (self.wt / task_id).mkdir(parents=True)
            (self.wt / task_id / "f.txt").write_text("x\n", encoding="utf-8")
            dirs[state] = task_id
        output = self.run_prune(execute=True)
        self.assertFalse(os.path.lexists(self.wt / dirs["done"]), output)
        self.assertFalse(os.path.lexists(self.wt / dirs["killed"]), output)
        self.assertTrue((self.wt / dirs["in_dev"] / "f.txt").is_file(), output)


if __name__ == "__main__":
    unittest.main()
