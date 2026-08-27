"""AC-1, AC-2 (tasks/T045/SPEC.md): команда `workspace <id>`.

AC-1. `workspace <id>` создаёт worktree на ветке задачи в стандартном
месте (`.artel/worktrees/<id>`) и печатает путь.
AC-2. Повторный вызов `workspace <id>` возвращает тот же путь без
ошибки (идемпотентность).

Прогоняется через `artel.main()` с подменённым argv — команда `workspace`
названа в критерии буквально как команда CLI, а не как имя конкретной
функции конкретного будущего модуля (см. tasks/T045/acceptance_tests/
_sandbox.py про причины реального git).
"""
import sys
import unittest
from unittest import mock

from orchestrator import artel  # noqa: E402

from _sandbox import WorktreeRepoTest  # noqa: E402


class WorkspaceCommandTest(WorktreeRepoTest):

    def cli_workspace(self, task_id=None) -> str:
        task_id = task_id or self.TASK
        with mock.patch.object(sys, "argv", ["artel.py", "workspace", task_id]):
            return self.capture(artel.main)

    def test_ac1_creates_worktree_on_task_branch_at_standard_path(self):
        out = self.cli_workspace()

        expected = self.worktree_path()
        self.assertIn(str(expected), out,
                      "команда обязана напечатать путь к worktree")
        self.assertTrue(expected.is_dir(),
                        f"worktree не создан по стандартному пути {expected}")

        listing = self.worktree_list()
        self.assertIn(str(expected), listing,
                      "git не знает про созданный worktree")

        branch_res = self.git("-C", str(expected), "rev-parse",
                              "--abbrev-ref", "HEAD")
        self.assertEqual(branch_res.stdout.strip(), self.branch,
                         "worktree должен стоять на ветке задачи")

    def test_ac2_repeated_call_returns_same_path_without_error(self):
        first_out = self.cli_workspace()
        expected = self.worktree_path()
        self.assertIn(str(expected), first_out)

        second_out = self.cli_workspace()

        self.assertIn(str(expected), second_out,
                      "повторный вызов обязан вернуть тот же путь")
        listing = self.worktree_list()
        self.assertEqual(listing.count(str(expected)), 1,
                         "повторный вызов не должен плодить дублирующую "
                         "запись worktree")


if __name__ == "__main__":
    unittest.main()
