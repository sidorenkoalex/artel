"""Юнит-тесты классификации/журналирования push артефактной ветки
(orchestrator/artifact_branch.py, SPEC 01M1TQ0X14Y5B3C87WC0Q31PK2,
требования 1-2, AC-1..AC-5).
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artifact_branch, gitcmd, store
from tests.sandbox import AutoOriginSandbox, OriginRealGitSandbox


class ClassifyPushFailureTest(unittest.TestCase):
    """`_classify_push_failure` — чистая функция, реальный git не нужен."""

    def test_rejected_fetch_first_is_non_fast_forward(self):
        stderr = (" ! [rejected]        artifact/x -> artifact/x (fetch first)\n"
                  "error: failed to push some refs")
        self.assertEqual(artifact_branch._classify_push_failure(stderr),
                         artifact_branch.PUSH_REASON_NON_FAST_FORWARD)

    def test_literal_non_fast_forward_is_non_fast_forward(self):
        self.assertEqual(
            artifact_branch._classify_push_failure("non-fast-forward updates"),
            artifact_branch.PUSH_REASON_NON_FAST_FORWARD)

    def test_anything_else_is_network(self):
        self.assertEqual(
            artifact_branch._classify_push_failure(
                "ssh: Could not resolve hostname example.invalid"),
            artifact_branch.PUSH_REASON_NETWORK)


class PushJournalSandbox(OriginRealGitSandbox):
    """Пульт — настоящий git-репозиторий; `self.bare` — origin, подключается
    отдельным вызовом `add_origin` (нужны сценарии и с ним, и без него)."""

    TASK = "01UNITPUSHTASK00001"

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          f"task/{self.TASK.lower()}-x", "artel", 25.0)

    def commit(self, text: str) -> str:
        return artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/SPEC.md": text},
            f"{self.TASK}: правка")

    def failed_rows(self) -> list:
        rows = store.task_steps(store.db(), self.TASK)
        return [r for r in rows if r["action"] == "push артефактной ветки FAILED"]

    def push_rows(self) -> list:
        rows = store.task_steps(store.db(), self.TASK)
        return [r for r in rows if "push" in r["action"].lower()]


class PushWithoutOriginTest(PushJournalSandbox):

    def test_returns_false_and_journals_no_origin(self):
        self.commit("спека\n")

        ok = artifact_branch.push(self.TASK)

        self.assertFalse(ok)
        failed = self.failed_rows()
        self.assertEqual(len(failed), 1, failed)
        self.assertIn("нет origin", failed[0]["detail"])

    def test_never_calls_real_git_push(self):
        """Ловит мутацию: `push` пытается push без origin, а не отсекает
        отказ заранее по `gitcmd.has_no_remote`."""
        self.commit("спека\n")
        recorded = []
        real_git = gitcmd.git

        def spy(*args):
            recorded.append(args)
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=spy):
            artifact_branch.push(self.TASK)

        push_calls = [c for c in recorded if c and c[0] == "push"]
        self.assertEqual(push_calls, [])


class PushSuccessTest(AutoOriginSandbox, PushJournalSandbox):
    """Множественное наследование (не просто `PushJournalSandbox`): `setUp`
    этого сценария был байт-в-байт как `ArtifactBranchSyncSandbox.setUp`
    в `tests/test_doctor_artifact_branch_sync.py` (SPEC
    01M2DC6SQVSANMECXPDZJDP75D, R8) — `AutoOriginSandbox` несёт этот
    `setUp` один раз, кооперативный `super()` проводит инициализацию через
    `PushJournalSandbox` (заводит задачу) перед вызовом `add_origin()`."""

    def test_returns_true_and_journals_success(self):
        self.commit("спека\n")

        ok = artifact_branch.push(self.TASK)

        self.assertTrue(ok)
        pushed = self.push_rows()
        self.assertEqual(len(pushed), 1, pushed)
        self.assertIn("успех", pushed[0]["detail"])
        branch = artifact_branch.branch_name(self.TASK)
        self.assertEqual(gitcmd.remote_branch_sha(branch),
                         gitcmd.branch_head_sha(branch))


class PushNonFastForwardTest(PushJournalSandbox):
    """Настоящее расхождение: внешний коммит уходит в origin в обход
    пульта (тот же приём, что `_sandbox.PultOriginSandbox.push_external_
    commit` приёмочных тестов этой задачи), затем локальный push
    отклоняется non-fast-forward."""

    def setUp(self):
        super().setUp()
        self.add_origin()
        self.branch = artifact_branch.branch_name(self.TASK)
        self.commit("спека v1\n")
        artifact_branch.push(self.TASK)
        self.assertEqual(gitcmd.remote_branch_sha(self.branch),
                         gitcmd.branch_head_sha(self.branch),
                         "предусловие: первый push обязан синхронизировать origin")

        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        self.git("clone", "-q", self.bare, scratch)
        subprocess.run(["git", "-C", scratch, "checkout", "-q", self.branch],
                       check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.email",
                        "operator@example.invalid"], check=True)
        subprocess.run(["git", "-C", scratch, "config", "user.name",
                        "operator"], check=True)
        external = Path(scratch) / f"tasks/{self.TASK}/EXTERNAL.md"
        external.parent.mkdir(parents=True, exist_ok=True)
        external.write_text("внешний коммит\n", encoding="utf-8")
        subprocess.run(["git", "-C", scratch, "add", "-A"], check=True)
        subprocess.run(["git", "-C", scratch, "commit", "-q", "-m",
                        "внешний коммит Оператора"], check=True)
        subprocess.run(["git", "-C", scratch, "push", "-q", "origin",
                        self.branch], check=True)

        self.commit("спека v2, локальная — не запушена\n")

    def test_journals_both_sha_direction_and_the_merge_hint(self):
        local_sha = gitcmd.branch_head_sha(self.branch)
        origin_sha = gitcmd.remote_branch_sha(self.branch)
        self.assertNotEqual(local_sha, origin_sha)

        ok = artifact_branch.push(self.TASK)

        self.assertFalse(ok)
        failed = [r for r in self.failed_rows()
                 if "non-fast-forward" in r["detail"]]
        self.assertEqual(len(failed), 1, self.failed_rows())
        detail = failed[0]["detail"]
        self.assertIn(local_sha, detail)
        self.assertIn(origin_sha, detail)
        self.assertIn("merge-коммитом", detail)
        # origin не изменился отказанным push'ем.
        self.assertEqual(gitcmd.remote_branch_sha(self.branch), origin_sha)

    def test_never_passes_force(self):
        """Ловит мутацию: повтор/отказ non-fast-forward «чинится»
        добавлением `--force`/`-f`/`--force-with-lease`."""
        recorded = []
        real_git = gitcmd.git

        def spy(*args):
            recorded.append(args)
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=spy):
            artifact_branch.push(self.TASK)

        push_calls = [c for c in recorded if c and c[0] == "push"]
        self.assertTrue(push_calls)
        for call in push_calls:
            self.assertNotIn("--force", call)
            self.assertNotIn("-f", call)
            self.assertNotIn("--force-with-lease", call)


if __name__ == "__main__":
    unittest.main()
