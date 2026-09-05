"""Приёмочный тест AC-4 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-4: `fsm._pull_main_or_escalate` для target ≠ self сравнивает
(`commits_behind`) и выполняет merge подтяжки в клоне/worktree контекста
target'а, а не в worktree `config.ROOT`; для self — поведение прежнее.

Настоящий git с двух сторон (пульт + внешний target с bare-origin) —
единственный надёжный способ отличить «подтяжка произошла в клоне
целевого» от «подтяжка произошла в worktree пульта, а внешний target
просто не заметил» (обе ветки кода сегодня возвращают один и тот же
исход `"pulled"`, различие — только в ТОМ, ГДЕ появился merge-коммит).

Красен до реализации: сегодня `_pull_main_or_escalate` для ЛЮБОГО target
сравнивает/мержит в `workspace.ensure(...)` — worktree `config.ROOT`;
для внешнего target ветки задачи там нет вовсе, `gitcmd.commits_behind`
возвращает `None`, и функция всегда отвечает `"fresh"`, даже когда
`target_origin` реально ушёл вперёд — тест ниже ждёт `"pulled"` и найдёт
merge-коммит в `target_workspace`, чего сегодняшний код не даёт.
"""
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, fsm, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402

TASK = "01AC4PULLMAINTASK00001"


class ExternalTargetPullMainTest(ExternalTargetGitSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{TASK}: код фичи")

        # main целевого уходит вперёд ПОСЛЕ того, как ветка задачи от
        # него ответвилась — реальное отставание, не гипотетическое.
        self.wgit("checkout", "-q", config.MAIN_BRANCH)
        (self.target_workspace / "unrelated.txt").write_text(
            "не относится к задаче\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", "правка main целевого")
        self.wgit("push", "-q", "origin", config.MAIN_BRANCH)
        self.advanced_main_sha = self.wgit("rev-parse",
                                           config.MAIN_BRANCH).strip()
        # Роль стоит на ветке задачи — так застаёт её оркестратор.
        self.wgit("checkout", "-q", self.branch)

        self.insert_external_task(TASK, self.branch, state="in_dev")

    def test_ac4_external_target_branch_gets_merged_in_the_target_clone(self):
        """`_pull_main_or_escalate` для внешнего target подтягивает main
        ИМЕННО в `target_workspace`, возвращает `"pulled"`, и главная
        копия целевого (`main` в `target_workspace`) не сдвигается сама
        (merge только в ветку задачи).

        Ловит мутацию: подтяжка продолжает идти в `workspace.ensure`
        пульта (`config.WORKTREES` в `self.root`) — `target_workspace`
        не получил бы нового коммита на `self.branch`, и `assertIn`
        на предка `advanced_main_sha` внутри `target_workspace` не
        прошёл бы.
        """
        conn = store.db()
        t = store.get_task(conn, TASK)

        outcome = fsm._pull_main_or_escalate(conn, TASK, t, "in_dev")

        self.assertEqual(outcome, "pulled")
        merged_ancestors = self.wgit(
            "log", "--format=%H", self.branch).split()
        self.assertIn(
            self.advanced_main_sha, merged_ancestors,
            f"подтянутый main целевого ({self.advanced_main_sha}) не "
            f"найден в истории {self.branch} внутри target_workspace — "
            f"похоже, merge случился не в клоне целевого")
        # config.ROOT (пульт) не несёт такой ветки вовсе — если бы merge
        # случился в worktree пульта, эта команда либо создала бы
        # артефакт там, либо упала на несуществующей ветке.
        root_branches = self.git("branch", "--list", self.branch)
        self.assertEqual(root_branches.strip(), "",
                         "ветка задачи внешнего target материализовалась "
                         "в репозитории пульта — подтяжка ушла не туда")

    def test_ac4_external_target_does_not_touch_the_pult_worktree_area(self):
        """`config.WORKTREES` пульта не получает нового каталога ради
        подтяжки внешнего target — `workspace.ensure` (self-специфичный
        механизм) для target ≠ self не должен вызываться вовсе."""
        conn = store.db()
        t = store.get_task(conn, TASK)

        fsm._pull_main_or_escalate(conn, TASK, t, "in_dev")

        wt_path = config.WORKTREES / TASK
        self.assertFalse(
            wt_path.exists(),
            f"{wt_path} создан ради подтяжки внешнего target — "
            f"AC-4 требует клон/worktree КОНТЕКСТА target'а, не пульта")


class SelfTargetPullMainUnchangedTest(ExternalTargetGitSandbox):
    """Self (`config.DEFAULT_TARGET`): поведение прежнее — worktree
    `config.ROOT` (SPEC требование 3 — «для self не меняется»)."""

    TASK = "01AC4SELFPULLMAIN00001"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: код фичи")

        self.git("checkout", "-q", config.MAIN_BRANCH)
        (self.root / "unrelated.txt").write_text("x\n", encoding="utf-8")
        self.git("add", "unrelated.txt")
        self.git("commit", "-q", "-m", "правка main пульта")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        # Главная копия (`self.root`) остаётся на `main` — ветку
        # задачи роль ведёт в СВОЁМ worktree (`workspace.ensure`,
        # SPEC T045), а не в главной копии: если оставить `self.root`
        # на `self.branch`, `git worktree add` дальше откажет
        # («already used by worktree»), потому что git не даёт
        # checkout ОДНОЙ ветки сразу в двух рабочих копиях.

        conn = store.db()
        store.insert_task(conn, self.TASK, "Задача self", "in_dev",
                          self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def test_ac4_self_target_still_merges_in_the_pult_worktree(self):
        """Self-target: `config.WORKTREES/<id>` заводится и получает
        merge-коммит — байт-в-байт прежний путь через `workspace.ensure`.
        """
        conn = store.db()
        t = store.get_task(conn, self.TASK)

        outcome = fsm._pull_main_or_escalate(conn, self.TASK, t, "in_dev")

        self.assertEqual(outcome, "pulled")
        wt_path = config.WORKTREES / self.TASK
        self.assertTrue(wt_path.exists(),
                        f"{wt_path} не создан — self-target больше не "
                        f"пользуется worktree пульта")
        log = subprocess.run(
            ["git", "-C", str(wt_path), "log", "--format=%s", "-1"],
            capture_output=True, text=True, check=True).stdout
        self.assertIn("подтяжка", log)


if __name__ == "__main__":
    import unittest
    unittest.main()
