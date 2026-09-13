"""Юнит-тесты `doctor.check_artifact_branch_sync` (SPEC
01M1TQ0X14Y5B3C87WC0Q31PK2, требование 3, AC-6).
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from orchestrator import artifact_branch, doctor, gitcmd, store
from tests.sandbox import AutoOriginSandbox

EXTERNAL_TARGET = "extproj"


class ArtifactBranchSyncSandbox(AutoOriginSandbox):

    def new_task(self, task_id: str, state: str = "in_dev",
                target: str = "artel") -> str:
        store.insert_task(store.db(), task_id, "Задача", state,
                          f"task/{task_id.lower()}-x", target, 25.0)
        return artifact_branch.branch_name(task_id)

    def commit(self, task_id: str, text: str) -> str:
        return artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": text},
            f"{task_id}: правка")

    def force_push(self, task_id: str) -> None:
        branch = artifact_branch.branch_name(task_id)
        self.git("push", "-q", "-f", "origin",
                 f"refs/heads/{branch}:refs/heads/{branch}")

    def origin_sha(self, branch: str) -> str:
        out = subprocess.run(
            ["git", "ls-remote", self.bare, f"refs/heads/{branch}"],
            capture_output=True, text=True, check=True).stdout
        return out.split()[0] if out.strip() else ""

    def push_external_commit(self, task_id: str) -> None:
        branch = artifact_branch.branch_name(task_id)
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", self.bare, scratch], check=True)
        subprocess.run(["git", "-C", scratch, "checkout", "-q", branch],
                       check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.email",
                        "operator@example.invalid"], check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.name",
                        "operator"], check=True)
        path = Path(scratch) / f"tasks/{task_id}/EXTERNAL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("внешний коммит\n", encoding="utf-8")
        subprocess.run(["git", "-C", scratch, "add", "-A"], check=True)
        subprocess.run(["git", "-C", scratch, "commit", "-q", "-m", "внешний"],
                       check=True)
        subprocess.run(["git", "-C", scratch, "push", "-q", "origin", branch],
                       check=True)

    def checks(self):
        return doctor.check_artifact_branch_sync(store.db())


class SyncOkTest(ArtifactBranchSyncSandbox):

    def test_ok_when_matching(self):
        task_id = "01SYNCOKMATCHING0001"
        self.new_task(task_id)
        self.commit(task_id, "спека\n")
        self.force_push(task_id)

        mine = [c for c in self.checks() if task_id in c.detail]
        self.assertTrue(mine)
        self.assertTrue(all(c.status == "ok" for c in mine))


class SyncOriginAheadTest(ArtifactBranchSyncSandbox):

    def test_warn_local_behind(self):
        task_id = "01SYNCLOCALBEHIND001"
        branch = self.new_task(task_id)
        self.commit(task_id, "спека v1\n")
        self.force_push(task_id)
        self.push_external_commit(task_id)

        local_sha = gitcmd.branch_head_sha(branch)
        origin_sha = self.origin_sha(branch)
        self.assertNotEqual(local_sha, origin_sha)

        warn = [c for c in self.checks() if c.status == "warn"
               and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn(local_sha, warn[0].detail)
        self.assertIn(origin_sha, warn[0].detail)
        self.assertIn("локальный отстаёт", warn[0].detail)


class SyncLocalAheadTest(ArtifactBranchSyncSandbox):

    def test_warn_origin_behind(self):
        task_id = "01SYNCORIGINBEHIND01"
        branch = self.new_task(task_id)
        self.commit(task_id, "спека v1\n")
        self.force_push(task_id)
        self.commit(task_id, "спека v2, не запушена\n")

        local_sha = gitcmd.branch_head_sha(branch)
        origin_sha = self.origin_sha(branch)
        self.assertNotEqual(local_sha, origin_sha)

        warn = [c for c in self.checks() if c.status == "warn"
               and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn("origin отстаёт", warn[0].detail)


class SyncDivergedTest(ArtifactBranchSyncSandbox):

    def test_warn_diverged(self):
        task_id = "01SYNCDIVERGEDTASK01"
        branch = self.new_task(task_id)
        self.commit(task_id, "спека v1\n")
        self.force_push(task_id)
        self.push_external_commit(task_id)
        self.commit(task_id, "локальная правка, не запушена\n")

        warn = [c for c in self.checks() if c.status == "warn"
               and task_id in c.detail]
        self.assertEqual(len(warn), 1, self.checks())
        self.assertIn("разошлись", warn[0].detail)


class SyncSkipWithoutOriginTest(ArtifactBranchSyncSandbox):

    def test_skip_without_origin(self):
        self.git("remote", "remove", "origin")
        task_id = "01SYNCSKIPNOORIGIN01"
        self.new_task(task_id)
        self.commit(task_id, "спека\n")

        checks = self.checks()
        self.assertTrue(checks)
        self.assertTrue(all(c.status == "skip" for c in checks))
        self.assertTrue(all(c.detail.strip() for c in checks))


class SyncExcludesTerminalAndForeignTargetTest(ArtifactBranchSyncSandbox):

    def test_excludes_done_and_external_target(self):
        done_id = "01SYNCEXCLUDEDONE001"
        self.new_task(done_id, state="done")
        self.commit(done_id, "спека\n")
        self.force_push(done_id)
        self.push_external_commit(done_id)

        external_id = "01SYNCEXCLUDEEXTERN1"
        self.new_task(external_id, target=EXTERNAL_TARGET)
        self.commit(external_id, "спека\n")
        self.force_push(external_id)
        self.push_external_commit(external_id)

        offending = [c for c in self.checks()
                    if c.status != "ok"
                    and (done_id in c.detail or external_id in c.detail)]
        self.assertEqual(offending, [])


if __name__ == "__main__":
    unittest.main()
