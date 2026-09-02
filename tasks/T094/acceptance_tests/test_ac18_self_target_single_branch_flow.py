"""Приёмочный тест T094 — AC-18 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-18: «До исполнения A7 задачи с целевым self не заводят артефактную
ветку, паспорт живой задачи и снапшот при закрытии — проходят прежним
однобраншевым флоу без регресса существующих тестов self-таргета.»

Зелёный с рождения: сегодня артефактная ветка/паспорт/снапшот закрытия
не существуют вовсе ни для кого (AC-8/AC-9/AC-12/AC-13 этой же задачи —
красные до реализации), поэтому self-таргет тривиально им не подвержен
уже сейчас — это тест СОХРАНЕНИЯ существующего поведения (требование
16 SPEC, догфуд-оговорка переходного периода), не тест новой
функциональности: он обязан остаться зелёным и ПОСЛЕ того, как
разработчик добавит артефактную ветку/паспорт/снапшот для внешних
target — как раз тогда он и получает смысл guard'а от регресса.

`catalog.cmd_new` без `target=` — это и есть self (`config.
DEFAULT_TARGET`, требование 16 SPEC); реальный git (`RealGitSandbox`),
не заглушка, — сама механика worktree/веток и есть предмет проверки.
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, cleanup, config, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402


def _show_ref_exists(root: Path, ref: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", "--quiet", ref],
        capture_output=True, text=True)
    return res.returncode == 0


class Ac18SelfTargetSingleBranchFlowTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        capture(catalog.cmd_init)

    def test_ac18_self_target_new_does_not_create_a_separate_artifact_branch(self):
        task_id = catalog.cmd_new("Задача self-таргета")
        row = store.get_task(store.db(), task_id)
        tid, branch, target = row["id"], row["branch"], row["target"]
        self.assertEqual(target, config.DEFAULT_TARGET)

        out = subprocess.run(
            ["git", "branch", "--list"], cwd=self.root,
            capture_output=True, text=True, check=True).stdout
        # `+` — маркер «эта ветка занята другим worktree» (worktree
        # задачи, T045); `*` — текущая ветка ЭТОЙ рабочей копии.
        branches = {line.lstrip("*+ ").strip() for line in out.splitlines()}
        self.assertEqual(
            branches, {config.MAIN_BRANCH, branch},
            f"self-таргет завёл больше веток, чем {{main, ветка задачи}} "
            f"— похоже на отдельную артефактную ветку пульта (AC-18, "
            f"требование 16 запрещает её self до A7): {branches}")

        files = subprocess.run(
            ["git", "-C", str(self.root), "ls-tree", "-r", "--name-only",
             branch, "--", f"tasks/{tid}"],
            capture_output=True, text=True, check=True).stdout
        self.assertTrue(
            files.strip(),
            f"tasks/{tid}/ не найден в единственной ветке задачи {branch} "
            f"— однобраншевый флоу self должен нести артефакты прямо там")

    def test_ac18_self_target_kill_does_not_publish_a_snapshot_ref(self):
        task_id = catalog.cmd_new("Задача self-таргета")

        capture(cleanup.cmd_kill, task_id)

        self.assertFalse(
            _show_ref_exists(self.root, f"refs/artifacts/{task_id}"),
            f"self-таргет опубликовал refs/artifacts/{task_id} при "
            f"закрытии — требование 16/AC-18 исключает снапшот закрытия "
            f"для self до A7")


if __name__ == "__main__":
    import unittest
    unittest.main()
