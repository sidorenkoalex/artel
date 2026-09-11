"""Приёмочный тест AC-6/AC-7 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-6: push ветки задачи (`github_adapter.ensure_draft_mr`,
`ensure_head_in_origin`) для target ≠ self идёт в origin клона контекста
target'а; для self — в origin `config.ROOT`, как и прежде.

AC-7: Draft-MR, снятие Draft и комментарий защищённых путей
(`github_adapter.ensure_draft_mr`, `undraft_mr`) для target ≠ self зовут
`gh --repo <url>` контекста target'а.

Push — настоящий git (единственный надёжный способ отличить «ушёл в
origin целевого» от «ушёл в origin пульта», раз оба принимают `git push
-u origin <branch>` с одним и тем же именем удалённого без ошибки).
`ci.gh` — замоканный (никакого настоящего `gh`/сети в песочнице), но
именно ЕГО аргументы несут проверяемый `--repo`.

Красен до реализации: `ensure_draft_mr`/`ensure_head_in_origin` сегодня
безусловно зовут `gitcmd.git(...)` (`config.ROOT`) и `ci.gh(...)` без
`--repo` — push уйдёт в `pult_origin` (или упадёт: ветки внешнего target
там нет), а не в `target_origin`.
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, github_adapter, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import EXTERNAL_TARGET, ExternalTargetGitSandbox  # noqa: E402

TASK = "01AC6AC7DRAFTMRTASK0001"


def _gh_spy():
    calls = []

    def fake_gh(*args, **kwargs):
        # Тот же приём сборки argv, что и настоящий `ci.gh(..., repo=...)`
        # (AC-2): здесь подменяется САМА `ci.gh`, значит её сборку
        # `--repo` симулирует спай, иначе `repo=` кваргой осталась бы
        # незамеченной вызывающим тестом.
        repo = kwargs.get("repo")
        recorded = args + (("--repo", repo) if repo else ())
        calls.append(recorded)
        if args[:2] == ("pr", "create"):
            return subprocess.CompletedProcess(
                args, 0, "https://example.invalid/extproj/pull/1\n", "")
        return subprocess.CompletedProcess(args, 0, "ok\n", "")
    return calls, fake_gh


class DraftMrExternalTargetTest(ExternalTargetGitSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{TASK}: код фичи")
        self.insert_external_task(TASK, self.branch, state="in_dev")

    def test_ac6_ensure_draft_mr_pushes_the_branch_to_the_target_origin(self):
        """Push ветки задачи внешнего target уходит в `target_origin`,
        а НЕ в `pult_origin`.

        Ловит мутацию: push по-прежнему идёт в `config.ROOT`/`origin`
        пульта — `origin_git("show-ref", ...)` целевого не нашёл бы
        ветку, а `pult_origin_git` нашёл бы её там, где её быть не
        должно.
        """
        conn = store.db()
        t = store.get_task(conn, TASK)
        calls, fake_gh = _gh_spy()

        with mock.patch.object(github_adapter.ci, "gh", fake_gh):
            github_adapter.ensure_draft_mr(conn, TASK, t)

        ref = self.origin_git("show-ref", "--verify", "--quiet",
                              f"refs/heads/{self.branch}")
        self.assertEqual(ref.returncode, 0,
                         f"{self.branch} не найдена в target_origin после "
                         f"ensure_draft_mr")
        pult_ref = self.pult_origin_git("show-ref", "--verify", "--quiet",
                                        f"refs/heads/{self.branch}")
        self.assertNotEqual(
            pult_ref.returncode, 0,
            f"{self.branch} внешнего target утекла в origin ПУЛЬТА")

    def test_ac7_pr_create_is_called_with_repo_flag_of_the_target(self):
        """`gh pr create` внешнего target несёт `--repo
        https://example.invalid/extproj` (targets.yaml[extproj].url).

        Ловит мутацию: `ci.gh` зовётся без контекста (как до задачи) —
        `--repo` не появится в аргументах вовсе.
        """
        conn = store.db()
        t = store.get_task(conn, TASK)
        calls, fake_gh = _gh_spy()

        with mock.patch.object(github_adapter.ci, "gh", fake_gh):
            github_adapter.ensure_draft_mr(conn, TASK, t)

        create_calls = [c for c in calls if c[:2] == ("pr", "create")]
        self.assertEqual(len(create_calls), 1)
        (call,) = create_calls
        self.assertIn("--repo", call)
        self.assertEqual(call[call.index("--repo") + 1],
                         f"https://example.invalid/{EXTERNAL_TARGET}")

    def test_ac7_undraft_mr_is_called_with_repo_flag_of_the_target(self):
        conn = store.db()
        store.update_task(conn, TASK, draft_mr_created=1)
        t = store.get_task(conn, TASK)
        calls, fake_gh = _gh_spy()

        with mock.patch.object(github_adapter.ci, "gh", fake_gh):
            github_adapter.undraft_mr(conn, TASK, t)

        ready_calls = [c for c in calls if c[:2] == ("pr", "ready")]
        self.assertEqual(len(ready_calls), 1)
        (call,) = ready_calls
        self.assertIn("--repo", call)
        self.assertEqual(call[call.index("--repo") + 1],
                         f"https://example.invalid/{EXTERNAL_TARGET}")

    def test_ac6_ensure_head_in_origin_publishes_to_the_target_origin(self):
        """`ensure_head_in_origin` — тот же путь push, что и Draft MR
        (SPEC AC-6 явно называет обе точки одним пунктом)."""
        conn = store.db()

        ok, detail = github_adapter.ensure_head_in_origin(
            conn, TASK, self.branch)

        self.assertTrue(ok, detail)
        ref = self.origin_git("show-ref", "--verify", "--quiet",
                              f"refs/heads/{self.branch}")
        self.assertEqual(ref.returncode, 0)


class DraftMrSelfTargetUnchangedTest(ExternalTargetGitSandbox):
    """Self: push — в origin `config.ROOT` (`pult_origin`), без `--repo`
    (SPEC AC-6/AC-7: «для self поведение прежнее»)."""

    TASK2 = "01AC6SELFDRAFTMRTASK01"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK2.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK2}: код фичи")
        conn = store.db()
        store.insert_task(conn, self.TASK2, "Задача self", "in_dev",
                          self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def test_ac6_ac7_self_target_pushes_to_the_pult_origin_without_repo_flag(self):
        conn = store.db()
        t = store.get_task(conn, self.TASK2)
        calls, fake_gh = _gh_spy()

        with mock.patch.object(github_adapter.ci, "gh", fake_gh):
            github_adapter.ensure_draft_mr(conn, self.TASK2, t)

        ref = self.pult_origin_git("show-ref", "--verify", "--quiet",
                                   f"refs/heads/{self.branch}")
        self.assertEqual(ref.returncode, 0,
                         "self-таргет больше не публикует ветку в origin "
                         "пульта")
        (create_call,) = [c for c in calls if c[:2] == ("pr", "create")]
        self.assertNotIn("--repo", create_call)


if __name__ == "__main__":
    import unittest
    unittest.main()
