"""Юнит-тесты `orchestrator.fsm_advance._reviewer_verdict_baseline` (регрессия
№15, tasks/01M1SCQ6WZHMQVK1AHP9F392JZ/SPEC.md, требование 1, AC-1/AC-2):
вырожденные случаи (git не ответил, ни одного совпавшего коммита, ни одной
записи журнала) без поднятия настоящего git-репозитория — приёмочная планка
задачи (`tasks/01M1SCQ6WZHMQVK1AHP9F392JZ/acceptance_tests/
test_review_rework_gate.py`) уже покрывает АС-1..АС-7 целиком на НАСТОЯЩЕМ
git, здесь — дополнительно узкие срезы самой функции.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK_ID = "T001"
BRANCH = "artifact/t001"


def _git_log(lines: str, returncode: int = 0):
    """`gitcmd.git("log", "--format=%cI\\x1f%s", ...)` отвечающий `lines`
    ровно на подкоманду `log`; всё остальное здесь не зовётся."""
    def fake(*args):
        if args and args[0] == "log":
            return subprocess.CompletedProcess(list(args), returncode,
                                               lines, "")
        return subprocess.CompletedProcess(list(args), 0, "", "")
    return fake


class ReviewerVerdictBaselineTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()

    def test_uses_the_freshest_reviewer_step_autocommit(self):
        """Ловит мутацию: подбирается не самый свежий, а какой попало
        коммит с префиксом reviewer — в реальной истории только самый
        свежий соответствует вердикту ТЕКУЩЕЙ итерации."""
        lines = (
            "2026-08-03T10:00:00+00:00\x1fT001: артефакты шага developer "
            "(автокоммит оркестратора)\n"
            "2026-08-02T10:00:00+00:00\x1fT001: артефакты шага reviewer "
            "(автокоммит оркестратора)\n"
            "2026-08-01T10:00:00+00:00\x1fT001: артефакты шага reviewer "
            "(автокоммит оркестратора)\n"
        )
        with mock.patch.object(gitcmd, "git", _git_log(lines)):
            ts, source = fsm_advance._reviewer_verdict_baseline(
                self.conn, TASK_ID, BRANCH)

        self.assertEqual(ts.isoformat(), "2026-08-02T10:00:00+00:00")
        self.assertIn("reviewer", source)

    def test_developer_ledger_edit_commit_is_not_a_candidate(self):
        """Ловит мутацию: префикс сверяется настолько широко, что
        совпадает и с автокоммитом шага developer — правка леджера
        замечаний (T100) ошибочно сдвигала бы опорное время вперёд
        (AC-2, инцидент 05.09)."""
        lines = (
            "2026-08-03T10:00:00+00:00\x1fT001: артефакты шага developer "
            "(автокоммит оркестратора)\n"
            "2026-08-01T10:00:00+00:00\x1fT001: артефакты шага reviewer "
            "(автокоммит оркестратора)\n"
        )
        with mock.patch.object(gitcmd, "git", _git_log(lines)):
            ts, source = fsm_advance._reviewer_verdict_baseline(
                self.conn, TASK_ID, BRANCH)

        self.assertEqual(ts.isoformat(), "2026-08-01T10:00:00+00:00")

    def test_no_matching_commit_falls_back_to_the_journal_entry(self):
        """Ловит мутацию: fallback на журнал не реализован — REVIEW.md,
        правленный вручную в обход checkpoint.py (ни один коммит не несёт
        префикс reviewer), не даёт опорного времени вовсе."""
        lines = "2026-08-03T10:00:00+00:00\x1fT001: правка REVIEW.md вручную\n"
        store.journal(self.conn, TASK_ID, "reviewer", "agent run finished",
                      "REVIEW.md: changes_requested, итерация 1")
        with mock.patch.object(gitcmd, "git", _git_log(lines)):
            ts, source = fsm_advance._reviewer_verdict_baseline(
                self.conn, TASK_ID, BRANCH)

        self.assertIsNotNone(ts)
        self.assertIn("журнал", source)

    def test_git_not_answering_falls_back_to_the_journal_entry(self):
        """Ловит мутацию: неответ git (returncode != 0) не деградирует к
        journal-fallback, а сразу отдаёт `(None, None)` — легковесная
        песочница без настоящего git осталась бы вовсе без опорного
        времени, даже когда журнал его несёт."""
        store.journal(self.conn, TASK_ID, "reviewer", "agent run finished",
                      "REVIEW.md: changes_requested, итерация 1")
        with mock.patch.object(gitcmd, "git", _git_log("", returncode=1)):
            ts, source = fsm_advance._reviewer_verdict_baseline(
                self.conn, TASK_ID, BRANCH)

        self.assertIsNotNone(ts)
        self.assertIn("журнал", source)

    def test_neither_commit_nor_journal_entry_gives_none(self):
        """Ловит мутацию: отсутствие обоих сигналов тем не менее отдаёт
        какое-то время — гейту дальше сверять было бы не с чем не по
        имени, а фактически, ложно."""
        with mock.patch.object(gitcmd, "git", _git_log("", returncode=1)):
            ts, source = fsm_advance._reviewer_verdict_baseline(
                self.conn, TASK_ID, BRANCH)

        self.assertIsNone(ts)
        self.assertIsNone(source)

    def test_journal_entry_of_a_different_role_is_not_picked(self):
        """Ловит мутацию: fallback читает ЛЮБУЮ запись `agent run
        finished`, не отфильтрованную по роли `reviewer` — запись
        developer'а не имеет права участвовать в опорном времени
        ревьювера."""
        store.journal(self.conn, TASK_ID, "developer", "agent run finished",
                      "rc=0")
        with mock.patch.object(gitcmd, "git", _git_log("", returncode=1)):
            ts, source = fsm_advance._reviewer_verdict_baseline(
                self.conn, TASK_ID, BRANCH)

        self.assertIsNone(ts)
        self.assertIsNone(source)


if __name__ == "__main__":
    unittest.main()
