"""Юнит-тесты `doctor.check_artifact_branch_ci` (SPEC
01M1TQ0X14Y5B3C87WC0Q31PK2, требование 4, AC-7).
"""
import json
import subprocess
import unittest
from unittest import mock

from orchestrator import artifact_branch, ci, doctor, gitcmd, store
from tests.sandbox import RealGitSandbox

JOB_NAME = "protected-paths"


def _fake_gh(branch: str, payload):
    def fake(*args, timeout=None):
        if (len(args) >= 2 and args[0] == "run" and args[1] == "list"
                and "--branch" in args):
            requested = args[args.index("--branch") + 1]
            body = payload if requested == branch else []
            return subprocess.CompletedProcess(list(args), 0,
                                               json.dumps(body), "")
        return subprocess.CompletedProcess(list(args), 1, "",
                                           "gh: неожиданная команда в тесте")
    return fake


def _gh_unavailable(*args, timeout=None):
    return subprocess.CompletedProcess(list(args), 1, "",
                                       "gh: command not found")


class ArtifactBranchCiSandbox(RealGitSandbox):

    def new_task(self, task_id: str, state: str = "in_dev",
                target: str = "artel") -> str:
        store.insert_task(store.db(), task_id, "Задача", state,
                          f"task/{task_id.lower()}-x", target, 25.0)
        return artifact_branch.branch_name(task_id)

    def commit(self, task_id: str, text: str) -> str:
        return artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": text},
            f"{task_id}: правка")

    def checks(self):
        return doctor.check_artifact_branch_ci(store.db())


class CiOkTest(ArtifactBranchCiSandbox):

    def setUp(self):
        super().setUp()
        self.TASK = "01CIOKAAAAAAAAAAAAA1"
        self.branch = self.new_task(self.TASK)
        self.commit(self.TASK, "спека\n")
        self.sha = gitcmd.branch_head_sha(self.branch)

    def test_ok_when_green(self):
        payload = [{"headBranch": self.branch, "status": "completed",
                   "conclusion": "success", "name": JOB_NAME}]
        with mock.patch.object(ci, "gh", _fake_gh(self.branch, payload)):
            checks = self.checks()

        mine = [c for c in checks if self.TASK in c.detail]
        self.assertTrue(mine, checks)
        self.assertTrue(all(c.status == "ok" for c in mine), checks)

    def test_warn_when_red_names_sha_and_job(self):
        payload = [{"headBranch": self.branch, "status": "completed",
                   "conclusion": "failure", "name": JOB_NAME}]
        with mock.patch.object(ci, "gh", _fake_gh(self.branch, payload)):
            checks = self.checks()

        warn = [c for c in checks if c.status == "warn" and self.TASK in c.detail]
        self.assertEqual(len(warn), 1, checks)
        self.assertIn(self.sha, warn[0].detail)
        self.assertIn(JOB_NAME, warn[0].detail)

    def test_skip_when_gh_unavailable(self):
        with mock.patch.object(ci, "gh", _gh_unavailable):
            checks = self.checks()

        mine = [c for c in checks if self.TASK in c.detail]
        self.assertTrue(mine, checks)
        self.assertTrue(all(c.status == "skip" for c in mine), checks)
        self.assertTrue(all(c.detail.strip() for c in mine), checks)

    def test_skip_when_no_runs_at_all(self):
        with mock.patch.object(ci, "gh", _fake_gh(self.branch, [])):
            checks = self.checks()

        mine = [c for c in checks if self.TASK in c.detail]
        self.assertTrue(mine, checks)
        self.assertTrue(all(c.status == "skip" for c in mine), checks)


class CiExcludesTerminalAndForeignTargetTest(ArtifactBranchCiSandbox):

    def test_excludes_killed_and_external_target(self):
        killed_id = "01CIEXCLUDEKILLED001"
        killed_branch = self.new_task(killed_id, state="killed")
        self.commit(killed_id, "спека\n")

        external_id = "01CIEXCLUDEEXTERNAL1"
        external_branch = self.new_task(external_id, target="extproj")
        self.commit(external_id, "спека\n")

        payload = [{"headBranch": killed_branch, "status": "completed",
                   "conclusion": "failure", "name": JOB_NAME}]

        def fake(*args, timeout=None):
            if (len(args) >= 2 and args[0] == "run" and args[1] == "list"
                    and "--branch" in args):
                requested = args[args.index("--branch") + 1]
                body = payload if requested in (killed_branch, external_branch) else []
                return subprocess.CompletedProcess(list(args), 0,
                                                   json.dumps(body), "")
            return subprocess.CompletedProcess(list(args), 1, "", "нет gh")

        with mock.patch.object(ci, "gh", fake):
            checks = self.checks()

        offending = [c for c in checks
                    if c.status != "ok"
                    and (killed_id in c.detail or external_id in c.detail)]
        self.assertEqual(offending, [])


if __name__ == "__main__":
    unittest.main()
