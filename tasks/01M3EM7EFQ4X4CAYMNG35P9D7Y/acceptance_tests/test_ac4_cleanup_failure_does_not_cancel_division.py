"""AC-4 (tasks/01M3EM7EFQ4X4CAYMNG35P9D7Y/SPEC.md): сбой уборки при
делении (git отказал в удалении ветки) не отменяет деление — подзадачи
заведены, родитель остаётся `killed` с пометкой «поделена на: …», в
журнале родителя есть запись «уборка» с причиной сбоя, исключение наружу
не выходит.

Сбой воспроизводится подменой `gitcmd.git`, в которой отказывает ТОЛЬКО
`git branch -d`/`-D` (`_sandbox.failing_branch_delete`) — тем же приёмом
частичного отказа git, что уже применяет
`tests/test_kill_cleanup.py::CleanupWithoutGitTest.
capture_with_failing_git`. Узко на удаление: подмена всей подкоманды
`branch` заодно подменила бы `branch --merged`, то есть предмет
требования 4, а не сбой уборки.

Красен до реализации: записи «уборка» на пути деления сегодня нет вовсе
(уборка не вызывается — `orchestrator/fsm.py::_spawn_division_subtasks`,
строки 686-692), поэтому ассерт «в журнале есть запись «уборка» с
текстом отказа git» покраснеет; остальные ассерты фиксируют уже
работающую половину критерия (деление не отменяется) и обязаны остаться
зелёными и после реализации.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (CLEANUP_ACTION, DivisionApproveSandbox,  # noqa: E402
                      failing_branch_delete)
from orchestrator import gitcmd  # noqa: E402

GIT_REFUSAL = "fatal: фикстура AC-4 — git отказал в удалении ветки"


class CleanupFailureKeepsDivisionTest(DivisionApproveSandbox):

    def test_ac4_failed_branch_removal_keeps_subtasks_and_killed_parent(self):
        """git отказывает в удалении кодовой ветки родителя ровно в
        момент уборки: деление всё равно состоялось, а причина отказа
        осела в журнале родителя.

        Ловит мутацию: уборка вызвана так, что её сбой поднимается
        наружу (`cleanup` вызван без обработки, либо заведён свой вызов
        `git branch -d` с проверкой кода возврата через исключение) —
        `approve` падает, подзадачи уже заведены, а родитель остаётся в
        `spec_gate`, то есть деление наполовину отменено. Тот же ассерт
        ловит и обратную мутацию — сбой проглочен молча, без причины в
        журнале.
        """
        sha = self.enter_spec_gate()
        real_git = gitcmd.git

        with mock.patch.object(gitcmd, "git",
                               failing_branch_delete(real_git, GIT_REFUSAL)):
            self.approve(sha)

        subtasks = self.subtask_ids()
        self.assertEqual(
            2, len(subtasks),
            f"сбой уборки отменил заведение подзадач (AC-4): {subtasks}")
        row = self.task_row()
        self.assertEqual(
            "killed", row["state"],
            f"сбой уборки вернул родителя из killed (AC-4): {row}")
        self.assertIn(
            "поделена на:", self.journal_text(),
            "сбой уборки стёр пометку «поделена на: …» у родителя (AC-4)")

        notes = self.cleanup_notes()
        self.assertTrue(
            notes,
            f"при сбое уборки в журнале родителя нет записи "
            f"«{CLEANUP_ACTION}» (AC-4): {self.journal_text()}")
        joined = " | ".join(notes)
        self.assertIn(
            GIT_REFUSAL, joined,
            f"запись «{CLEANUP_ACTION}» не называет причину, которой "
            f"отказал git (AC-4): {joined!r}")
        self.assertIn(
            self.BRANCH, joined,
            f"запись «{CLEANUP_ACTION}» не называет ветку, которую не "
            f"удалось удалить (AC-4): {joined!r}")


if __name__ == "__main__":
    unittest.main()
