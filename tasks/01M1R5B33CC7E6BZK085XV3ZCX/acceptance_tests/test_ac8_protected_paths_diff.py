"""Приёмочный тест AC-8 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-8: подсветка защищённых путей в MR (`_touched_protected_paths`)
считает diff в клоне контекста target'а, не в `config.ROOT`, когда
target ≠ self.

Наблюдаемый эффект — единственный внешний след этой приватной функции:
комментарий `gh pr comment`, который `ensure_draft_mr` отправляет,
только когда diff реально задевает `config.PROTECTED_PATHS`.

Красен до реализации: `_touched_protected_paths` сегодня считает diff
безусловно в `config.ROOT` (`gitcmd.git("diff", ...)`), где ветки
внешнего target нет вовсе — `git diff` там либо падает, либо (что тише)
просто не видит правку `gates.yaml`, сделанную в `target_workspace`:
комментарий о защищённых путях не появится никогда для внешнего target.
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, github_adapter, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402

TASK = "01AC8PROTECTEDPATHTASK1"


def _gh_spy():
    calls = []

    def fake_gh(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("pr", "create"):
            return subprocess.CompletedProcess(
                args, 0, "https://example.invalid/extproj/pull/1\n", "")
        return subprocess.CompletedProcess(args, 0, "ok\n", "")
    return calls, fake_gh


class ProtectedPathCommentTest(ExternalTargetGitSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "gates.yaml").write_text(
            "policy: auto\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{TASK}: правка gates.yaml")
        self.insert_external_task(TASK, self.branch, state="in_dev")

    def test_ac8_touching_gates_yaml_in_the_target_clone_triggers_a_comment(self):
        """Правка `gates.yaml` целиком внутри `target_workspace` (не в
        `config.ROOT`, где такого файла в этом дереве и не было) —
        `ensure_draft_mr` шлёт `pr comment` с именем пути.

        Ловит мутацию: diff считается в `config.ROOT` — там нет ни
        ветки, ни файла с таким изменением, `protected` осталось бы
        пустым, и `pr comment` не позвался бы вовсе.
        """
        conn = store.db()
        t = store.get_task(conn, TASK)
        calls, fake_gh = _gh_spy()

        with mock.patch.object(github_adapter.ci, "gh", fake_gh):
            github_adapter.ensure_draft_mr(conn, TASK, t)

        comment_calls = [c for c in calls if c[:2] == ("pr", "comment")]
        self.assertEqual(
            len(comment_calls), 1,
            f"нет ровно одного pr comment о защищённых путях: {calls}")
        self.assertTrue(
            any("gates.yaml" in str(part) for part in comment_calls[0]),
            f"комментарий не называет gates.yaml: {comment_calls[0]}")

    def test_ac8_no_protected_paths_touched_means_no_comment(self):
        """Симметрия: правка НЕ защищённого пути — комментария нет
        вовсе (не любой diff считается тревожным)."""
        task2 = "01AC8NOPROTECTEDPATH002"
        branch2 = f"task/{task2.lower()}-x"
        # От `main`, НЕ от текущего HEAD (`self.branch` уже несёт
        # правку `gates.yaml` из setUp — ветвление от него унаследовало
        # бы её и в diff `branch2`, ложно превращая эту проверку в
        # копию предыдущей).
        self.wgit("checkout", "-q", config.MAIN_BRANCH)
        self.wgit("checkout", "-q", "-b", branch2)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{task2}: код фичи")
        self.insert_external_task(task2, branch2, state="in_dev")
        conn = store.db()
        t = store.get_task(conn, task2)
        calls, fake_gh = _gh_spy()

        with mock.patch.object(github_adapter.ci, "gh", fake_gh):
            github_adapter.ensure_draft_mr(conn, task2, t)

        comment_calls = [c for c in calls if c[:2] == ("pr", "comment")]
        self.assertEqual(comment_calls, [])


if __name__ == "__main__":
    import unittest
    unittest.main()
