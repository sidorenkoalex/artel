"""AC-1 (tasks/T056/SPEC.md): запуск любой команды CLI с `config.ROOT`
внутри git-worktree завершается именованным отказом, называющим
фактический `ROOT` и путь главной копии, с подсказкой перезапустить
оттуда; каталог `.artel/` в worktree не появляется, БД не создаётся.

Требование 4 SPEC — отказ распространяется на ВСЕ команды CLI, включая
читающие — поэтому свип идёт по полной таблице команд `artel.py`
(`ALL_CLI_COMMANDS`, `_sandbox.py`), не по одной-двум показательным.

Песочница — `_sandbox.WorktreeGuardSandbox`: настоящий git-репозиторий
(«главная копия») и настоящий `git worktree add` от него — признак
worktree из требования 2 SPEC (файл-ссылка `ROOT/.git` вида
`gitdir: <main>/.git/worktrees/<id>`) даёт только реальный git, подмена
`config.ROOT` заглушкой этого не создаёт.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from _sandbox import ALL_CLI_COMMANDS, WorktreeGuardSandbox  # noqa: E402


class WorktreeRootRefusesTest(WorktreeGuardSandbox):

    def setUp(self):
        super().setUp()
        self.main_copy = self.sandbox / "main"
        self.worktree = self.sandbox / "worktree"
        self.seed_copy(self.main_copy)
        self.init_git_repo(self.main_copy)
        self.git("worktree", "add", "-q", "-b", "feature",
                 str(self.worktree), "main", cwd=self.main_copy)

    def test_ac1_worktree_root_refuses_every_cli_command_before_touching_artel_dir(self):
        for args in ALL_CLI_COMMANDS:
            with self.subTest(команда=" ".join(args)):
                result = self.run_cli(self.worktree, *args)

                self.assertNotEqual(
                    result.returncode, 0,
                    f"«{' '.join(args)}» из worktree не отказала")
                output = result.stdout + result.stderr
                self.assertIn(
                    str(self.worktree), output,
                    f"«{' '.join(args)}»: отказ не называет фактический ROOT")
                self.assertIn(
                    str(self.main_copy), output,
                    f"«{' '.join(args)}»: отказ не называет путь главной "
                    f"копии")
                self.assertIn(
                    "перезапуст", output.lower(),
                    f"«{' '.join(args)}»: отказ не подсказывает "
                    f"перезапустить из главной копии")
                self.assertFalse(
                    (self.worktree / ".artel").exists(),
                    f"«{' '.join(args)}»: паразитная .artel/ появилась в "
                    f"worktree")


if __name__ == "__main__":
    unittest.main()
