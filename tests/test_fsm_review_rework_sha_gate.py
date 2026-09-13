"""Юнит-тесты `orchestrator.fsm_advance._code_sha_at_review_escalation`/
`_review_escalation_sha_gate` (SPEC 01M1VBEDGMEXHVGWAH42FTDZ4X, требование
3): budget-эскалация из `review` с уже вынесенным approved-вердиктом не
пропускает возврат в `verifying` по устаревшему коду.

Приёмочные тесты (`tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/
test_ac8_ac9_ac14_ac15_review_verdict_sha.py`) кроют AC-8/AC-9/AC-14/AC-15
сквозным путём через `fsm.cmd_advance`/`auto.cmd_auto`; здесь — сами
примитивы в изоляции, без FSM/lease.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import budget, fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest, TmpRootTest  # noqa: E402

TASK_ID = "T001"


class CodeShaAtReviewEscalationTest(SchemaConnTmpRootTest):

    def _journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(self.conn, TASK_ID, actor, action, detail)

    def test_no_escalation_record_returns_none(self):
        sha = fsm_advance._code_sha_at_review_escalation(self.conn, TASK_ID)
        self.assertIsNone(sha)

    def test_escalation_record_after_the_reviewer_run_is_used(self):
        self._journal("reviewer", "agent run finished", "rc=0")
        self._journal("fsm", budget.REVIEW_ESCALATION_CODE_SHA_ACTION, "a" * 40)

        sha = fsm_advance._code_sha_at_review_escalation(self.conn, TASK_ID)

        self.assertEqual(sha, "a" * 40)

    def test_stale_escalation_record_before_a_newer_reviewer_run_is_ignored(self):
        """Запись эскалации СТАРШЕ последнего прогона reviewer — она
        относится к предыдущему циклу ревью, не к текущему вердикту."""
        self._journal("fsm", budget.REVIEW_ESCALATION_CODE_SHA_ACTION, "a" * 40)
        self._journal("reviewer", "agent run finished", "rc=0")

        sha = fsm_advance._code_sha_at_review_escalation(self.conn, TASK_ID)

        self.assertIsNone(sha)

    def test_only_the_latest_escalation_record_counts(self):
        self._journal("reviewer", "agent run finished", "rc=0")
        self._journal("fsm", budget.REVIEW_ESCALATION_CODE_SHA_ACTION, "a" * 40)
        self._journal("fsm", "state -> escalated", "бюджет исчерпан")
        self._journal("operator", "state -> review", "бюджет поднят, продолжаем")
        self._journal("fsm", budget.REVIEW_ESCALATION_CODE_SHA_ACTION, "b" * 40)

        sha = fsm_advance._code_sha_at_review_escalation(self.conn, TASK_ID)

        self.assertEqual(sha, "b" * 40)


class ReviewEscalationShaGateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.t = {"branch": "task/t001-x"}

    def _journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(self.conn, TASK_ID, actor, action, detail)

    def test_no_escalation_record_passes(self):
        with mock.patch.object(gitcmd, "branch_head_sha", lambda b: "z" * 40):
            refusal = fsm_advance._review_escalation_sha_gate(
                self.conn, TASK_ID, self.t)

        self.assertIsNone(refusal)

    def test_unchanged_sha_passes(self):
        self._journal("reviewer", "agent run finished", "rc=0")
        self._journal("fsm", budget.REVIEW_ESCALATION_CODE_SHA_ACTION, "a" * 40)

        with mock.patch.object(gitcmd, "branch_head_sha", lambda b: "a" * 40):
            refusal = fsm_advance._review_escalation_sha_gate(
                self.conn, TASK_ID, self.t)

        self.assertIsNone(refusal)

    def test_changed_sha_refuses(self):
        self._journal("reviewer", "agent run finished", "rc=0")
        self._journal("fsm", budget.REVIEW_ESCALATION_CODE_SHA_ACTION, "a" * 40)

        with mock.patch.object(gitcmd, "branch_head_sha", lambda b: "b" * 40):
            refusal = fsm_advance._review_escalation_sha_gate(
                self.conn, TASK_ID, self.t)

        self.assertIsNotNone(refusal)
        self.assertIn("код сменился", refusal.action)
        self.assertIn("a" * 40, refusal.detail)
        self.assertIn("b" * 40, refusal.detail)

    def test_git_not_answering_now_passes_fail_open(self):
        self._journal("reviewer", "agent run finished", "rc=0")
        self._journal("fsm", budget.REVIEW_ESCALATION_CODE_SHA_ACTION, "a" * 40)

        with mock.patch.object(gitcmd, "branch_head_sha", lambda b: ""):
            refusal = fsm_advance._review_escalation_sha_gate(
                self.conn, TASK_ID, self.t)

        self.assertIsNone(refusal)

    def test_stale_escalation_record_passes(self):
        """Эскалация относится к предыдущему циклу (новый прогон reviewer
        уже случился после неё) — гейт не держит текущий вердикт по ней."""
        self._journal("fsm", budget.REVIEW_ESCALATION_CODE_SHA_ACTION, "a" * 40)
        self._journal("reviewer", "agent run finished", "rc=0")

        with mock.patch.object(gitcmd, "branch_head_sha", lambda b: "b" * 40):
            refusal = fsm_advance._review_escalation_sha_gate(
                self.conn, TASK_ID, self.t)

        self.assertIsNone(refusal)


if __name__ == "__main__":
    unittest.main()
