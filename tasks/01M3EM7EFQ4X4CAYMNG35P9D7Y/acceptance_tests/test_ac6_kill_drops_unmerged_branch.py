"""AC-6 (tasks/01M3EM7EFQ4X4CAYMNG35P9D7Y/SPEC.md): `kill` задачи с
неслитой веткой удаляет её; ветки нет среди локальных веток, а вывод и
запись «уборка» в журнале говорят «удалена неслитая ветка <branch>».

Красен до реализации: сегодня `orchestrator/cleanup.py::
drop_task_branch` удаляет неслитую ветку, но возвращает строку
«удалена ветка <branch>» (строка 80) — без слова «неслитая», которым
требование 5 велит различать два исхода: ассерты на текст вывода и
журнала покраснеют, хотя сама ветка и сегодня исчезает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CLEANUP_ACTION, KillBranchSandbox  # noqa: E402
from orchestrator import cleanup, gitcmd  # noqa: E402
from tests.sandbox import capture  # noqa: E402


class KillDropsUnmergedBranchTest(KillBranchSandbox):

    def test_ac6_unmerged_branch_is_dropped_and_named_unmerged(self):
        """Ветка с собственным коммитом, не влитая в main, снимается, и
        исход назван «удалена неслитая ветка» — отдельным текстом от
        влитой.

        Ловит мутацию: требование 5 выполнено наполовину — новый текст
        заведён только для влитой ветки, а прежняя ветка кода
        (`git branch -D`) продолжает возвращать безразличное «удалена
        ветка <branch>»: по журналу уже не отличить, какая именно ветка
        была снята, ради чего различение и заводилось.
        """
        self.ensure_code_worktree()
        self.commit_in_worktree("work.txt", "работа ветки задачи\n")
        self.assertFalse(
            gitcmd.branch_merged(self.BRANCH),
            "предусловие AC-6: ветка задачи не влита в main")

        out = capture(cleanup.cmd_kill, self.TASK)

        expected = f"удалена неслитая ветка {self.BRANCH}"
        self.assertNotIn(
            self.BRANCH, self.branches(),
            f"неслитая ветка осталась среди локальных после kill "
            f"(AC-6): {self.branches()}")
        self.assertIn(
            expected, out,
            f"вывод kill не говорит «{expected}» (AC-6): {out!r}")
        notes = " | ".join(self.cleanup_notes())
        self.assertIn(
            expected, notes,
            f"запись «{CLEANUP_ACTION}» в журнале не говорит "
            f"«{expected}» (AC-6): {notes!r}")


if __name__ == "__main__":
    unittest.main()
