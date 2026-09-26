"""AC-2 (tasks/01M3EM7EFQ4X4CAYMNG35P9D7Y/SPEC.md): после перехода
деления в журнале родителя есть запись действия «уборка», перечисляющая
сделанное (worktree, каталог, ветка).

Сценарий тот же, что у AC-1 (`DivisionApproveSandbox`), предмет другой:
не состояние диска и git, а запись журнала — по ней Оператор узнаёт, что
именно убрано, не пересматривая репозиторий руками.

Красен до реализации: уборка при делении не вызывается вовсе
(`orchestrator/fsm.py::_spawn_division_subtasks`, строки 686-692 —
`catalog.spawn_subtask` в цикле и один `store.set_state`), а единственный
сегодняшний автор записи «уборка» — `cleanup.cleanup_killed_task`
(orchestrator/cleanup.py:136), которого на пути деления нет: записей с
действием «уборка» в журнале родителя ноль, и первый же ассерт
покраснеет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CLEANUP_ACTION, DivisionApproveSandbox  # noqa: E402
from orchestrator import workspace  # noqa: E402


class DivisionJournalsCleanupTest(DivisionApproveSandbox):

    def test_ac2_journal_of_the_parent_lists_what_was_cleaned(self):
        """Единственная запись «уборка» в журнале поделённого родителя
        называет все три хвоста: снятый worktree, каталог артефактов и
        кодовую ветку.

        Ловит мутацию: уборка при делении сделана «тихо» — прямыми
        вызовами `workspace.remove`/`drop_task_branch` без общего узла
        `cleanup_killed_task`, который и пишет запись журнала: диск и
        git приходят в порядок (AC-1 зелен), а следов в журнале нет.
        """
        sha = self.enter_spec_gate()
        wt_path = workspace.path(self.TASK)

        self.approve(sha)

        notes = self.cleanup_notes()
        self.assertTrue(
            notes,
            f"в журнале родителя нет ни одной записи действия "
            f"«{CLEANUP_ACTION}» после деления (AC-2): "
            f"{self.journal_text()}")
        note = notes[-1]
        self.assertIn(
            f"worktree {wt_path}", note,
            f"запись «{CLEANUP_ACTION}» не называет снятый worktree "
            f"(AC-2): {note!r}")
        self.assertIn(
            f"tasks/{self.TASK}/", note,
            f"запись «{CLEANUP_ACTION}» не называет каталог артефактов "
            f"родителя (AC-2): {note!r}")
        self.assertIn(
            self.BRANCH, note,
            f"запись «{CLEANUP_ACTION}» не называет кодовую ветку "
            f"родителя (AC-2): {note!r}")


if __name__ == "__main__":
    unittest.main()
