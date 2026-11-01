"""Юнит-тесты сверки MR `mr-sync` (SPEC 01M6AB4VE2R0Q2V5D4MMJGNGH7): свойства вне долгоживущих файлов задачи.

Сквозные сценарии (таблица итогов, `--confirm`, инциденты, опрос надзора)
держит `tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py`. Здесь — узлы в
изоляции: принятая голова ветки только при возврате из эскалации «чужой
коммит» (ANSWER-1 п. 6, отрицательная половина), срок опроса надзора и
показ итога в модели доски только у задачи в `awaiting_human`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import board, mr_sync, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

SERVER_HEAD = "f" * 40


class AcceptServerHeadTest(TaskSeededTmpRootTest):

    def escalate(self, detail: str) -> None:
        conn = store.db()
        store.update_task(conn, self.TASK, state="escalated")
        store.journal(conn, self.TASK, "fsm", "state -> escalated", detail)

    def accept(self) -> list:
        with mock.patch.object(mr_sync.gitcmd, "remote_branch_sha",
                               lambda branch, repo=None: SERVER_HEAD):
            mr_sync.accept_server_head(store.db(), self.TASK)
        return [r for r in store.task_steps(store.db(), self.TASK)
                if r["action"] == mr_sync.ACCEPTED_HEAD_ACTION]

    def test_foreign_commit_escalation_accepts_server_head(self):
        """Возврат из эскалации «чужой коммит» записывает голову сервера принятой.

        Ловит мутацию: голова не записывается вовсе (записи «голова ветки
        на сервере принята» нет) либо записывается не голова сервера.
        """
        self.escalate(f"{mr_sync.FOREIGN_COMMIT_DETAIL}: голова x — не своя")
        accepted = self.accept()
        self.assertEqual(len(accepted), 1)
        self.assertTrue(accepted[0]["detail"].startswith(SERVER_HEAD))
        self.assertEqual(mr_sync.expected_server_head(store.db(), self.TASK),
                         SERVER_HEAD)

    def test_other_escalation_does_not_accept_head(self):
        """Иная эскалация (например MR влит до `awaiting_human`) голову сервера не принимает.

        Ловит мутацию: голова принимается при возврате из любой эскалации —
        чужой коммит, положенный после неё, стал бы своим без решения
        Оператора по нему.
        """
        self.escalate(f"{mr_sync.MR_DONE_EARLY_DETAIL}: MR !7 merged")
        self.assertEqual(self.accept(), [])
        self.assertEqual(mr_sync.expected_server_head(store.db(), self.TASK), "")


class DueTest(unittest.TestCase):

    def test_interval_counts_minutes_since_last_sync(self):
        """Сверка надзора — не раньше `interval` минут после прошлой; первой сверки ничто не держит.

        Ловит мутацию: интервал читается в секундах (сверка через 61 с при
        N = 2 — «пора») или прошлая сверка не учитывается.
        """
        now = "2031-07-05 12:10:00Z"
        with mock.patch.object(mr_sync.store, "now", lambda: now):
            self.assertTrue(mr_sync.due({"mr_sync_at": None}, 2))
            self.assertFalse(mr_sync.due({"mr_sync_at": "2031-07-05 12:08:59Z"}, 2))
            self.assertTrue(mr_sync.due({"mr_sync_at": "2031-07-05 12:08:00Z"}, 2))


class BoardMrSyncTest(unittest.TestCase):

    @staticmethod
    def row(state: str) -> dict:
        class Row(dict):
            def keys(self):
                return list(super().keys())
        return Row(state=state, mr_sync_outcome=mr_sync.MERGED_THIS,
                   mr_sync_at="2031-07-05 12:10:00Z")

    def test_shown_only_while_awaiting_human(self):
        """Итог `mr-sync` показан у задачи в `awaiting_human` и не показан после закрытия.

        Ловит мутацию: итог показывается в любом состоянии — у закрытой
        `done` задачи доска несёт устаревшую сверку.
        """
        shown = board.mr_sync_shown(self.row("awaiting_human"))
        self.assertEqual(shown, {"outcome": mr_sync.MERGED_THIS,
                                 "at": "2031-07-05 12:10:00Z"})
        self.assertIsNone(board.mr_sync_shown(self.row("done")))


if __name__ == "__main__":
    unittest.main()
