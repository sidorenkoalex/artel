"""Тесты статуса CI ветки задачи (см. tasks/T017/SPEC.md, требование 6).

Здесь — разбор ответа `gh` и правило «зелёный / не зелёный»: какие
заключения проходят, какие нет и почему любое отсутствие ответа считается
запретом. Сам гейт merge (что при не-зелёном CI merge не выполняется)
кодирован инвариантом `test_invariants.MergeNeedsGreenCiTest`.

Ни git, ни `gh` не запускаются: обе команды подменены.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import ci, config  # noqa: E402

SHA = "0123456789abcdef0123456789abcdef01234567"


def run(name: str, status: str = "completed", conclusion: str = "success") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion}


class BranchStatusTest(unittest.TestCase):
    """Решение о зелёности: и по составу проверок, и по способности спросить."""

    def setUp(self):
        patcher = mock.patch.object(ci, "head_sha", lambda branch: (SHA, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def answer(self, stdout: str, returncode: int = 0) -> None:
        patcher = mock.patch.object(
            ci, "gh",
            lambda *a: subprocess.CompletedProcess(list(a), returncode,
                                                   stdout, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def status(self, runs: list) -> tuple[bool, str]:
        self.answer(json.dumps({"check_runs": runs}))
        return ci.branch_status("task/t001-x")

    def test_all_green_is_green(self):
        green, note = self.status([run("guard"), run("python")])

        self.assertTrue(green)
        self.assertIn(SHA[:8], note, "в журнале виден коммит, признанный годным")
        self.assertIn("2", note, "и число проверок")

    def test_skipped_and_neutral_are_green(self):
        """`protected-paths` на push пропускается — иначе зелёного не бывает."""
        for conclusion in ("skipped", "neutral"):
            with self.subTest(заключение=conclusion):
                green, _ = self.status(
                    [run("guard"), run("protected-paths", conclusion=conclusion)])

                self.assertTrue(green)

    def test_failed_conclusions_are_not_green(self):
        for conclusion in ("failure", "cancelled", "timed_out",
                           "action_required", "stale", None):
            with self.subTest(заключение=conclusion):
                green, note = self.status(
                    [run("guard"), run("python", conclusion=conclusion)])

                self.assertFalse(green)
                self.assertIn("python", note, "названа непрошедшая проверка")

    def test_unfinished_check_is_not_green(self):
        for status in ("queued", "in_progress", "waiting"):
            with self.subTest(состояние=status):
                green, note = self.status(
                    [run("guard", status=status, conclusion=None)])

                self.assertFalse(green)
                self.assertIn("ещё идёт", note)

    def test_no_checks_at_all_is_unknown_and_not_green(self):
        """Проверок нет — статус неизвестен; неизвестный не значит хороший."""
        green, note = self.status([])

        self.assertFalse(green)
        self.assertIn("неизвестен", note)

    def test_gh_that_does_not_answer_is_not_green(self):
        cases = {
            "gh не установлен или упал": ("", 1),
            "ответ не JSON": ("fatal: not a repository", 0),
            "в ответе нет check_runs": (json.dumps({"message": "Not Found"}), 0),
            "check_runs не список": (json.dumps({"check_runs": 42}), 0),
            "элемент списка не объект": (json.dumps({"check_runs": ["ok"]}), 0),
        }
        for name, (stdout, returncode) in cases.items():
            with self.subTest(случай=name):
                self.answer(stdout, returncode)

                green, note = ci.branch_status("task/t001-x")

                self.assertFalse(green)
                self.assertIn("неизвестен", note)

    def test_unknown_head_commit_is_not_green(self):
        """Нечего проверять — тоже отказ: sha ветки не определился."""
        with mock.patch.object(ci, "head_sha",
                               lambda branch: ("", "ветки нет")):
            green, note = ci.branch_status("task/t001-x")

        self.assertFalse(green)
        self.assertIn("неизвестен", note)
        self.assertIn("ветки нет", note)


class HeadShaTest(unittest.TestCase):
    """Sha головного коммита: спрашивается у git, пустой ответ — причина."""

    def test_sha_comes_from_git(self):
        with mock.patch.object(ci.gitcmd, "git", lambda *a:
                               subprocess.CompletedProcess(list(a), 0,
                                                           f"{SHA}\n", "")):
            self.assertEqual(ci.head_sha("task/t001-x"), (SHA, ""))

    def test_missing_branch_is_a_named_reason(self):
        with mock.patch.object(ci.gitcmd, "git", lambda *a:
                               subprocess.CompletedProcess(list(a), 128, "",
                                                           "fatal: no branch")):
            sha, why = ci.head_sha("task/t001-x")

        self.assertEqual(sha, "")
        self.assertIn("fatal: no branch", why)


class GhCallTest(unittest.TestCase):
    """Отсутствие `gh` — ненулевой код, а не исключение (как в gitcmd.git)."""

    def test_missing_cli_is_a_nonzero_result(self):
        with mock.patch.object(ci.subprocess, "run",
                               side_effect=FileNotFoundError("gh")):
            res = ci.gh("api", "repos")

        self.assertNotEqual(res.returncode, 0)
        self.assertIn("gh", res.stderr)

    def test_the_call_is_bounded_in_time(self):
        """Молчащая сеть не вешает гейт: у вызова есть предел ожидания."""
        with mock.patch.object(ci.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "{}", "")
            ci.gh("api", "repos")

        self.assertEqual(run_.call_args.kwargs.get("timeout"),
                         config.GH_TIMEOUT_SEC, "вызов `gh` без предела ожидания")

    def test_silent_gh_is_a_nonzero_result_and_so_not_green(self):
        """Истёкший предел — «статус неизвестен», то есть отказ merge."""
        with mock.patch.object(
                ci.subprocess, "run",
                side_effect=subprocess.TimeoutExpired(["gh"], 60)):
            res = ci.gh("api", "repos")

        self.assertNotEqual(res.returncode, 0)
        self.assertIn("молчал", res.stderr)
        with mock.patch.object(ci, "head_sha", lambda branch: (SHA, "")), \
                mock.patch.object(ci, "gh", lambda *a: res):
            green, note = ci.branch_status("task/t001-x")

        self.assertFalse(green)
        self.assertIn("неизвестен", note)


if __name__ == "__main__":
    unittest.main()
