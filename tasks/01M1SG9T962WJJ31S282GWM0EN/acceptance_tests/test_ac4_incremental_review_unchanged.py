"""AC-4 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): инкрементальный diff
ревью-пакета (база — sha предыдущего вердикта, `iteration > 1` с
непустым `prev_sha`) этой задачей не меняется — `gitcmd.diff_base` не
участвует в этой ветке `review.review_package` вовсе.

Зелёный с рождения: сегодняшний `review.review_package` при `iteration
> 1` и непустом `prev_sha` уже берёт `base = prev_sha` и не зовёт
`config.MAIN_BRANCH`/`gitcmd.diff_base` — этот тест фиксирует
СУЩЕСТВУЮЩЕЕ поведение (требование 2 SPEC: «не меняется»), а не новый
код задачи; `boom` ниже должен молчать что до, что после реализации
AC-1..AC-3.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import config, gitcmd, review, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

PREV_SHA = "cafebabecafebabecafebabecafebabecafebabe"


class IncrementalReviewPackageDoesNotUseDiffBaseTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.branch = "task/t001-x"

    def test_ac4_incremental_diff_uses_prev_sha_and_never_calls_diff_base(self):
        """Ловит мутацию: разработчик заводит diff_base ЕДИНОЙ точкой правды
        и для инкрементального случая тоже (например, `base = gitcmd.
        diff_base(branch) if not incremental else prev_sha` подменяется
        на безусловный вызов `gitcmd.diff_base` до проверки `incremental`)
        — `boom` ниже поймает сам факт обращения к `diff_base`, а
        проверка диапазона диффа поймает подмену `prev_sha` на что-то
        иное, даже если `diff_base` не вызван, но его результат всё
        равно просочился в `base`."""
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

        def boom(*a, **k):
            raise AssertionError(
                "инкрементальный diff ревью-пакета не имеет права звать "
                "gitcmd.diff_base — требование 2 SPEC («не меняется»)")

        with mock.patch.object(gitcmd, "diff_base", boom), \
             mock.patch.object(gitcmd, "git", fake_git):
            review.review_package(self.conn, self.task_id,
                                  "Тест инкремента", self.branch,
                                  iteration=2, prev_sha=PREV_SHA)

        diff_calls = [c for c in calls if c and c[0] == "diff"]
        self.assertTrue(diff_calls)
        for c in diff_calls:
            self.assertIn(f"{PREV_SHA}...{self.branch}", c)
            self.assertNotIn(f"{config.MAIN_BRANCH}...{self.branch}", c)


if __name__ == "__main__":
    unittest.main()
