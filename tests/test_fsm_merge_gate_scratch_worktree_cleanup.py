"""Регресс-тест R1-F1 (REVIEW.md 01M1R5B33CC7E6BZK085XV3ZCX итерация 1,
замечание major) — `orchestrator/fsm_merge_gate.py::_drop_scratch_worktree`
обязан дерегистрировать scratch-worktree в репозитории-ВЛАДЕЛЬЦЕ (клоне
контекста target'а, `_scratch_worktree` заводит его ИМЕННО там), а не
безусловно в `config.ROOT` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 4,
AC-12).

Реальный git (не мок), два НАСТОЯЩИХ репозитория — тем же приёмом
эмпирической проверки, что и у самого ревьювера (REVIEW.md, «Проверено
исполнением»): до фикса `git worktree remove` голой `gitcmd.git`
(=> `cwd=config.ROOT`) из чужого репозитория падает `fatal: '<path>' is
not a working tree` (код 128) и НЕ дерегистрирует административную
запись `.git/worktrees/<name>/` в клоне target'а — `_drop_scratch_
worktree` не проверяла возврат вовсе, отказ проглатывался молча.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_merge_gate, repo_context  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    res = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
    return res


class ScratchWorktreeCleanupTest(RealGitSandbox):
    """`self.root` (via RealGitSandbox) — `config.ROOT`, репозиторий
    ПУЛЬТА. `self.target_repo` — ВТОРОЙ настоящий git-репозиторий,
    отдельный от `config.ROOT`, изображающий клон внешнего target'а — тот
    же приём двух-репозиторной песочницы, что и `ExternalTargetGitSandbox`
    (`tasks/T094/acceptance_tests/_sandbox.py`)."""

    def setUp(self):
        super().setUp()
        # Вложены В `self.root` (уникальный `TemporaryDirectory` на тест),
        # НЕ в `self.root.parent` — тот делит системный временный каталог
        # со всеми тестами процесса, коллизия имён между запусками.
        self.target_repo = self.root / ".scratch-parent" / "target-clone"
        self.target_repo.mkdir(parents=True)
        _run(self.target_repo, "init", "-q", "-b", "trunk")
        _run(self.target_repo, "config", "user.email", "artel@example.invalid")
        _run(self.target_repo, "config", "user.name", "artel tests")
        (self.target_repo / "marker.txt").write_text("trunk\n", encoding="utf-8")
        _run(self.target_repo, "add", "-A")
        _run(self.target_repo, "commit", "-q", "-m", "init")

        self.ctx = repo_context.RepoContext(
            path=self.target_repo, remote="http://localhost/sled", base="trunk")
        self.assertNotEqual(self.ctx.path, config.ROOT,
                            "sanity: контекст обязан быть внешним, не self")

        sha = _run(self.target_repo, "rev-parse", "HEAD").stdout.strip()
        self.scratch = self.root / ".scratch-parent" / "scratch-worktree"
        _run(self.target_repo, "worktree", "add", "--detach",
            str(self.scratch), sha)

    def worktree_paths(self, repo: Path) -> list[str]:
        listing = _run(repo, "worktree", "list", "--porcelain").stdout
        return [line.split(" ", 1)[1] for line in listing.splitlines()
                if line.startswith("worktree ")]

    def test_cleanup_deregisters_worktree_in_the_target_clone(self):
        """Ловит мутацию R1-F1: `_drop_scratch_worktree` бьёт голой
        `gitcmd.git` (=> `config.ROOT`, репозиторий ПУЛЬТА) вместо
        `repo_context.git(ctx, ...)` — worktree остался бы
        зарегистрирован в `self.target_repo` даже после вызова (каталог
        на диске уже исчез бы `shutil.rmtree`, но админ-запись `.git/
        worktrees/` в клоне target'а — нет)."""
        self.assertIn(str(self.scratch), self.worktree_paths(self.target_repo))

        fsm_merge_gate._drop_scratch_worktree(self.ctx, self.scratch)

        self.assertFalse(self.scratch.exists())
        self.assertNotIn(str(self.scratch), self.worktree_paths(self.target_repo))

    def test_cleanup_does_not_touch_the_pult_repository(self):
        """Ловит мутацию: фикс перепутал направление и теперь ВСЕГДА
        бьёт в клон `ctx.path`, включая self — `config.ROOT` (репозиторий
        пульта) не должен видеть никаких worktree-записей от уборки
        scratch-дерева внешнего target'а."""
        fsm_merge_gate._drop_scratch_worktree(self.ctx, self.scratch)

        self.assertEqual(self.worktree_paths(config.ROOT),
                         [str(config.ROOT)])

    def test_self_context_still_cleans_up_in_the_pult_repository(self):
        """Ловит мутацию: self-путь (`ctx.path == config.ROOT`) сломан
        фиксом R1-F1 — scratch-worktree self всегда заводится и убирается
        в `config.ROOT` (byte-identical поведение до этой задачи, PLAN.md
        «Подход»)."""
        self_ctx = repo_context.RepoContext(
            path=config.ROOT, remote="origin", base=config.MAIN_BRANCH)
        sha = _run(config.ROOT, "rev-parse", "HEAD").stdout.strip()
        self_scratch = self.root / ".scratch-parent" / "self-scratch-worktree"
        _run(config.ROOT, "worktree", "add", "--detach", str(self_scratch), sha)
        self.assertIn(str(self_scratch), self.worktree_paths(config.ROOT))

        fsm_merge_gate._drop_scratch_worktree(self_ctx, self_scratch)

        self.assertFalse(self_scratch.exists())
        self.assertNotIn(str(self_scratch), self.worktree_paths(config.ROOT))


if __name__ == "__main__":
    unittest.main()
