"""AC-6 (tasks/T052/SPEC.md): ни в одном из сценариев провала merge
(содержательный конфликт, конфликт в защищённых путях, инфраструктурный
отказ, красный CI) задача не переходит в состояние `done`.

Четыре сценария — четыре теста: первые два требуют настоящего git
(содержательный/защищённый конфликт, `_sandbox.MergeGateRealGitTest`,
тот же довод, что AC-3/AC-4), последние два — лёгкая песочница
`tests.test_invariants.FsmTest` с подменённым git/CI (инфраструктурный
отказ и красный CI не нуждаются в настоящем репозитории).
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from _sandbox import MergeGateRealGitTest  # noqa: E402
from orchestrator import fsm, gitcmd  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

RED_CI = json.dumps({"total_count": 1, "check_runs": [
    {"name": "python", "status": "completed", "conclusion": "failure"}]})


class ContentConflictNeverReachesDoneTest(MergeGateRealGitTest):

    def test_ac6_content_conflict_never_reaches_done(self):
        self.make_conflicting_branch(
            "shared.txt", "правка ветки задачи\n", "правка main\n")

        self.approve()

        self.assertNotEqual(self.state(), "done")


class ProtectedPathConflictNeverReachesDoneTest(MergeGateRealGitTest):

    def test_ac6_protected_path_conflict_never_reaches_done(self):
        self.make_conflicting_branch(
            "gates.yaml", "task: true\n", "main: true\n")

        self.approve()

        self.assertNotEqual(self.state(), "done")


class InfrastructureFailureNeverReachesDoneTest(FsmTest):
    """Инфраструктурный отказ (push не отвечает) — не содержательный
    конфликт: та же git-подкоманда, что `MergeFailureStillReportsTest`
    в `tasks/T036/acceptance_tests/test_merge_gitcmd.py`, но предмет
    здесь — именно запрет `done`, а не текст журнала."""

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

    def test_ac6_git_infrastructure_failure_never_reaches_done(self):
        def failing(cmd, *args, **kwargs):
            self.git_spy(cmd, *args, **kwargs)
            rc = 1 if list(cmd)[:2] == ["git", "push"] else 0
            return subprocess.CompletedProcess(
                list(cmd), rc, "", "сеть недоступна" if rc else "")

        with mock.patch.object(gitcmd.subprocess, "run", failing):
            with self.assertRaises(SystemExit):
                self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotEqual(self.state(), "done")


class RedCiNeverReachesDoneTest(FsmTest):

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

    def test_ac6_red_ci_never_reaches_done(self):
        self.set_ci(RED_CI)

        with self.assertRaises(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotEqual(self.state(), "done")


if __name__ == "__main__":
    unittest.main()
