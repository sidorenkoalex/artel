"""AC-7 (tasks/01M3EM7EFQ4X4CAYMNG35P9D7Y/SPEC.md): повторный `kill`
задачи, уже находящейся в `killed`, у которой остались worktree и
кодовая ветка, убирает и worktree, и ветку, пишет «уборка» в журнал и
завершается без ошибки.

Это путь требования 6 — однократная уборка двух висящих поделённых
родителей штатной командой `artel.py kill <id>`, без ручного git.
Задача заводится в `in_dev`, получает кодовую ветку и worktree, а затем
переводится в `killed` напрямую через `store.set_state` — так
воспроизводится ровно сегодняшнее состояние тех двоих: терминальное
состояние с неубранными хвостами.

Красен до реализации: хвост здесь — ПУСТАЯ кодовая ветка (голова
совпадает с main), а `orchestrator/cleanup.py::drop_task_branch`
(строки 74-75) на такой ветке возвращает «оставлена: смержена в main» и
не удаляет её: ассерт «ветки нет среди локальных» покраснеет, хотя
worktree и снимется.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CLEANUP_ACTION, KillBranchSandbox  # noqa: E402
from orchestrator import cleanup, store, workspace  # noqa: E402
from tests.sandbox import capture  # noqa: E402


class RepeatedKillFinishesCleanupTest(KillBranchSandbox):

    def test_ac7_kill_on_already_killed_task_removes_worktree_and_branch(self):
        """`kill` уже убитой задачи не делает перехода, но доводит
        уборку хвостов до конца и не падает.

        Ловит мутацию: уборка привязана к самому переходу в `killed`
        (вызывается внутри выигранного CAS `store.set_state`, а не
        безусловно после него) — повторный `kill`, для которого перехода
        нет, печатает «уже killed — kill не требуется» и выходит, не
        тронув ни worktree, ни ветку: два висящих родителя требования 6
        так и остаются висеть.
        """
        self.ensure_code_worktree()
        store.set_state(store.db(), self.TASK, "killed", "operator",
                        expected_state="in_dev", detail="kill switch")
        wt_path = workspace.path(self.TASK)
        self.assertTrue(self.worktree_registered(),
                        "предусловие AC-7: worktree остался неубранным")
        self.assertIn(self.BRANCH, self.branches(),
                      "предусловие AC-7: кодовая ветка осталась неубранной")

        # «Завершается без ошибки» — сам факт того, что вызов вернулся:
        # `cleanup.cmd_kill` сообщает об отказах `sys.exit`, и любое
        # исключение здесь провалило бы тест раньше ассертов ниже.
        capture(cleanup.cmd_kill, self.TASK)

        self.assertFalse(
            self.worktree_registered(),
            f"повторный kill не снял worktree (AC-7): {wt_path}")
        self.assertFalse(
            wt_path.exists(),
            f"повторный kill не убрал каталог worktree (AC-7): {wt_path}")
        self.assertNotIn(
            self.BRANCH, self.branches(),
            f"повторный kill не удалил кодовую ветку (AC-7): "
            f"{self.branches()}")
        self.assertTrue(
            self.cleanup_notes(),
            f"повторный kill не записал «{CLEANUP_ACTION}» в журнал "
            f"(AC-7): {self.journal_text()}")
        self.assertEqual(
            "killed", self.task_row()["state"],
            "повторный kill увёл задачу из killed (AC-7)")


if __name__ == "__main__":
    unittest.main()
