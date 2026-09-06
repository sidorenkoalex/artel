"""Песочница для AC-7/AC-8 (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0): гейт
`merge_gate` на self-target — копия `ArtelSelfTargetSandbox` из
`tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests/_sandbox.py` (A7,
плотницкий merge). `self.root` — пульт (реальный git, ветка main, один
коммит, тот же приём, что `tests.sandbox.RealGitSandbox`); `self.origin`
— bare-репозиторий, играющий роль «main артели» (ANSWER-1, вариант B):
плотницкая запись merge-коммита обязана продвигать ИМЕННО его
`refs/heads/main`, не трогая локальный чекаут/HEAD `self.root`.

Self-target (не внешний) — гейт `merge_gate` мержит кодовую ветку задачи
в main ПУЛЬТА одним и тем же кодом независимо от target
(`_perform_carpentry_merge`/`_push_merged_main` работают с origin
`config.ROOT`, не с целевым репозиторием); self проще внешнего — не
нужен отдельный bare-репозиторий целевого и `_publish_closing_snapshot_
or_wait` для self/канарейки снапшот не заводит вовсе.
"""
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import RealGitSandbox, resilient_tmp_cleanup  # noqa: E402

ARTEL_TARGETS_YAML = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class ArtelSelfTargetSandbox(RealGitSandbox):
    """`self.root` — пульт с настоящим origin-remote локально на диске
    (без сети); `self.origin` — bare-репозиторий, играющий роль главной
    копии артели на GitHub."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(ARTEL_TARGETS_YAML, encoding="utf-8")

        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
             str(self.origin)], check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

    def origin_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.origin), *args],
                              capture_output=True, text=True)

    def origin_main_sha(self) -> str:
        res = self.origin_git("rev-parse", "refs/heads/" + config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_tree_files(self, ref: str) -> list:
        res = self.origin_git("ls-tree", "-r", "--name-only", ref)
        return [p for p in res.stdout.splitlines() if p] if res.returncode == 0 else []

    def make_task_branch_in_root(self, branch: str, rel: str,
                                 text: str, message: str) -> None:
        """Заводит кодовую ветку задачи ПРЯМО в `self.root` (код задачи
        артели живёт в её собственной ветке пульта). `git add <rel>` —
        ИМЕННО файл, не `-A` (та же оговорка, что в оригинале T024 —
        слепой `-A` затянул бы незакоммиченный `.artel/state.db` в
        коммит кодовой ветки, и обратный `checkout main` удалил бы файл
        БД из рабочего дерева)."""
        self.checkout(branch, create=True)
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(text, encoding="utf-8")
        self.git("add", rel)
        self.git("commit", "-q", "-m", message)
        self.checkout(config.MAIN_BRANCH)

    def insert_task(self, task_id: str, branch: str, state: str,
                    **kwargs) -> None:
        store.insert_task(store.db(), task_id, f"Задача {task_id}", state,
                          branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD, **kwargs)

    def green_ci(self):
        """Мокает `ci.branch_status` зелёным на весь тест — гейт CI не
        предмет AC-7/AC-8, только препятствие на пути к merge."""
        from orchestrator import ci
        patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        patcher.start()
        self.addCleanup(patcher.stop)
