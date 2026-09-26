"""AC-1 (tasks/01M3EM7EFQ4X4CAYMNG35P9D7Y/SPEC.md): `approve` на
`spec_gate` для SPEC с секцией «## Деление» — после перехода подзадачи
заведены, родитель в `killed` с пометкой «поделена на: …», worktree
родителя не зарегистрирован и его каталога нет, кодовой ветки родителя
нет среди локальных веток.

Сценарий: `DivisionApproveSandbox.enter_spec_gate` заводит родителя с
валидной секцией «## Деление», кодовой веткой и worktree (ветка без
собственных коммитов — ровно топология двух висящих родителей из
«Контекста» SPEC), затем `approve` подтверждает гейт зафиксированным
sha.

Красен до реализации: `orchestrator/fsm.py::_spawn_division_subtasks`
сегодня заводит подзадачи и переводит родителя в `killed`, но уборки не
зовёт вовсе (orchestrator/fsm.py:686-692 — тело функции целиком:
`catalog.spawn_subtask` в цикле и один `store.set_state`), поэтому
worktree остаётся зарегистрированным, его каталог на месте, а ветка — в
списке локальных: три ассерта уборки покраснеют, пока разработчик не
добавит вызов `cleanup.cleanup_killed_task` (требование 1).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import DivisionApproveSandbox  # noqa: E402
from orchestrator import workspace  # noqa: E402


class DivisionRemovesParentTailsTest(DivisionApproveSandbox):

    def test_ac1_approve_spawns_subtasks_and_clears_parent_tails(self):
        """Деление на гейте SPEC доводит родителя до `killed` «поделена
        на: …» и одновременно снимает его worktree и кодовую ветку.

        Ловит мутацию: уборка вызвана ДО `git worktree remove` (или
        worktree не убирается вовсе) — `git branch -d` откажет, пока
        ветку держит worktree, и ветка останется в списке локальных;
        тот же ассерт ловит и полное отсутствие вызова уборки
        (сегодняшнее поведение).
        """
        sha = self.enter_spec_gate()
        wt_path = workspace.path(self.TASK)
        self.assertTrue(self.worktree_registered(),
                        "предусловие AC-1: worktree родителя заведён")
        self.assertIn(self.BRANCH, self.branches(),
                      "предусловие AC-1: кодовая ветка родителя заведена")

        self.approve(sha)

        subtasks = self.subtask_ids()
        self.assertEqual(
            2, len(subtasks),
            f"деление не завело по подзадаче на каждый подраздел «## "
            f"Деление» (AC-1): заведено {subtasks}")
        row = self.task_row()
        self.assertEqual("killed", row["state"],
                         f"родитель не в killed после деления (AC-1): {row}")
        self.assertIn("поделена на:", self.journal_text(),
                      "журнал родителя не несёт пометки «поделена на: …» "
                      "(AC-1)")

        self.assertFalse(
            self.worktree_registered(),
            f"worktree родителя остался зарегистрированным в git worktree "
            f"list после деления (AC-1): {wt_path}")
        self.assertFalse(
            wt_path.exists(),
            f"каталог worktree родителя остался на диске после деления "
            f"(AC-1): {wt_path}")
        self.assertNotIn(
            self.BRANCH, self.branches(),
            f"кодовая ветка родителя осталась среди локальных веток после "
            f"деления (AC-1): {self.branches()}")


if __name__ == "__main__":
    unittest.main()
