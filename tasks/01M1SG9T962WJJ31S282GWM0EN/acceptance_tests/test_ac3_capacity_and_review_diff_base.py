"""AC-3 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): гейт ёмкости
(`_capacity_gate_refuses`) и полный diff ревью-пакета
(`review.review_package` при `iteration == 1`) используют базу из AC-1
вместо `config.MAIN_BRANCH` как первый аргумент своего `git diff`/
`git_diff_part`.

Красен до реализации: сегодняшний `_capacity_gate_refuses` зовёт
`_review_git_diff_part(config.MAIN_BRANCH, t["branch"], ...)` буквально,
а `review.review_package` при `iteration == 1` берёт `base =
config.MAIN_BRANCH` без обращения к `gitcmd.diff_base` вовсе — оба
теста ниже ловят фактические аргументы команды `git diff` и обнаружат
там `config.MAIN_BRANCH`, а не подставленный фейковый merge-base sha.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import config, fsm_advance, gitcmd, review, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

FAKE_BASE = "abc123abc123abc123abc123abc123abc123ab"


def _diff_call_reasons(calls) -> list:
    return [c for c in calls if c and c[0] == "diff"]


class CapacityGateUsesDiffBaseTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.branch = "task/t001-x"
        self.t = {"title": "Тест гейта ёмкости", "branch": self.branch}

    def test_ac3_capacity_gate_diffs_from_diff_base_not_config_main_branch(self):
        """Ловит мутацию: `config.MAIN_BRANCH` в вызове `_review_git_diff_
        part` не заменён на `gitcmd.diff_base(t["branch"])` — все
        команды `git diff` этого гейта несли бы диапазон
        `main...task/t001-x`, а не диапазон с фейковой базой."""
        calls = []

        def fake_git(*args):
            calls.append(args)
            if args and args[0] == "diff":
                return subprocess.CompletedProcess(
                    list(args), 0, "diff --git a b\n+маленький diff", "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "diff_base", return_value=FAKE_BASE), \
             mock.patch.object(gitcmd, "git", fake_git):
            fsm_advance._capacity_gate_refuses(
                self.conn, self.task_id, self.t, "in_dev")

        diff_calls = _diff_call_reasons(calls)
        self.assertTrue(diff_calls, "гейт обязан позвать git diff хотя бы раз")
        for c in diff_calls:
            self.assertIn(f"{FAKE_BASE}...{self.branch}", c,
                          f"diff обязан идти от diff_base, не от "
                          f"config.MAIN_BRANCH: {c}")
            self.assertNotIn(f"{config.MAIN_BRANCH}...{self.branch}", c)


class ReviewPackageFullDiffUsesDiffBaseTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.branch = "task/t001-x"

    def test_ac3_review_package_full_diff_uses_diff_base_not_config_main_branch(self):
        """Ловит мутацию: `review.review_package` при `iteration == 1`
        по-прежнему берёт `base = config.MAIN_BRANCH` буквально, минуя
        `gitcmd.diff_base` — обе команды `git diff` пакета (`--stat` и
        полный diff) несли бы диапазон `main...task/t001-x`, а не
        диапазон с фейковой базой."""
        calls = []

        def fake_git(*args):
            calls.append(args)
            if args and args[0] == "show":
                return subprocess.CompletedProcess(
                    list(args), 128, "",
                    f"fatal: path does not exist in '{args[1]}'")
            if args and args[0] == "ls-tree":
                return subprocess.CompletedProcess(list(args), 0, "", "")
            if args and args[0] == "diff":
                return subprocess.CompletedProcess(
                    list(args), 0, "diff --git a b\n+маленький diff", "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "diff_base", return_value=FAKE_BASE), \
             mock.patch.object(gitcmd, "git", fake_git):
            review.review_package(self.conn, self.task_id,
                                  "Тест ревью-пакета", self.branch)

        diff_calls = _diff_call_reasons(calls)
        self.assertTrue(diff_calls, "полный diff пакета обязан позвать "
                                    "git diff хотя бы раз")
        for c in diff_calls:
            self.assertIn(f"{FAKE_BASE}...{self.branch}", c,
                          f"diff пакета обязан идти от diff_base, не от "
                          f"config.MAIN_BRANCH: {c}")
            self.assertNotIn(f"{config.MAIN_BRANCH}...{self.branch}", c)


if __name__ == "__main__":
    unittest.main()
