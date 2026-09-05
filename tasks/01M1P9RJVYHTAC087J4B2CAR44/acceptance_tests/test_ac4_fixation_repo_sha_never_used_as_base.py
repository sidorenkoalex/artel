"""AC-4 (tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md): фиксационный sha
артефактного/фиксационного репозитория target'а (значение поля `sha=`
записи «sha зафиксирован») НИ ПРИ КАКИХ УСЛОВИЯХ не используется как база
инкрементального diff — проверяется напрямую по аргументу, реально
ушедшему в команду `git diff <base>...<branch>` (`review.review_package`),
не по побочному эффекту (пустой/непустой diff, AC-2/AC-3).

Красен до реализации: `review.previous_verdict_sha` сегодня возвращает
именно значение поля `sha=` (первое совпадение `sha=([0-9a-f]{4,40})` в
`detail`), и `review_package` подставляет ЕГО как `base` каждого вызова
`git diff` — ровно то, что этот AC запрещает «ни при каких условиях».
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import gitcmd, review, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RecordingGit  # noqa: E402

TASK = "T001"
FIXATION_REPO_SHA = "1234567890abcdef1234567890abcdef12345678"  # `sha=`
CODE_BRANCH_SHA = "abcdef1234567890abcdef1234567890abcdef12"    # `код=`


class FixationRepoShaNeverUsedAsBaseTest(TmpRootTest):

    BRANCH = "task/t001-ac4"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.git = RecordingGit()
        patcher = self._patch_git()
        self.addCleanup(patcher.stop)

    def _patch_git(self):
        from unittest import mock
        patcher = mock.patch.object(gitcmd, "git", self.git)
        patcher.start()
        return patcher

    def fixate(self) -> None:
        detail = (f"target=sled, sha={FIXATION_REPO_SHA}, чисто=True, "
                  f"код={CODE_BRANCH_SHA}, артефакты={'e' * 40}")
        store.journal(self.conn, TASK, "fsm", "sha зафиксирован", detail)
        store.journal(self.conn, TASK, "fsm", "sha зафиксирован", detail)

    def test_ac4_diff_and_stat_calls_never_carry_the_fixation_repo_sha(self):
        """Итерация 2: `review_package` собирает и `--stat`, и полный diff —
        оба вызова обязаны нести `код=` базой, ни один — `sha=`.

        Ловит мутацию: `previous_verdict_sha` продолжает разбирать поле
        `sha=` — оба вызова `git diff` понесли бы FIXATION_REPO_SHA
        базой вместо CODE_BRANCH_SHA.
        """
        self.fixate()
        prev_sha = review.previous_verdict_sha(self.conn, TASK)

        review.review_package(self.conn, TASK, "AC-4", self.BRANCH,
                              iteration=2, prev_sha=prev_sha)

        bases = self.git.diff_bases()
        self.assertEqual(len(bases), 2, "ожидались вызовы --stat и полного diff")
        for base in bases:
            self.assertNotEqual(base, FIXATION_REPO_SHA,
                                "фиксационный sha артефактного репозитория "
                                "target'а использован базой diff")
            self.assertEqual(base, CODE_BRANCH_SHA)


if __name__ == "__main__":
    unittest.main()
