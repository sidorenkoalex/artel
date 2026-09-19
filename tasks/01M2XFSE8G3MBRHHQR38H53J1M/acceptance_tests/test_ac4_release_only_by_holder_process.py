"""AC-4 — `merge_lock.release` снимает мьютекс только своего процесса
(задача 01M2XFSE8G3MBRHHQR38H53J1M).

Красен до реализации: `merge_lock.release` -> `store.release_merge_lock`
удаляет строку по одному `session_id` (`orchestrator/store.py:691` —
`DELETE FROM merge_locks WHERE session_id=?`), поэтому вызов из любого
процесса той же сессии (в том числе из `finally` цикла, который окна
никогда не получал) снимает мьютекс живого держателя — окно освобождается
под ним.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import merge_lock, store  # noqa: E402

from _sandbox import MergeOwnerSandbox, _alive_foreign_pid  # noqa: E402


class ReleaseByHolderProcessOnlyTest(MergeOwnerSandbox):

    def test_ac4_release_from_a_non_holder_process_keeps_the_mutex(self):
        """Мьютекс держит живой процесс A той же сессии `sess-a`; `release`
        из процесса B (сам тест) не имеет права снять строку A.

        Ловит мутацию: `release`/`store.release_merge_lock` оставлены с
        удалением по одному `session_id` (либо pid передан, но в условие
        `WHERE` не попал) — строка живого держателя исчезнет, и
        `assertIsNotNone` покраснеет.
        """
        holder_pid = _alive_foreign_pid(self)
        self.seed_lock(self.TASK_B, "sess-a", holder_pid,
                       socket.gethostname())

        merge_lock.release(store.db(), "sess-a")

        row = self.lock_row()
        self.assertIsNotNone(
            row, "release из процесса, который окна не держит, снял "
                 "мьютекс живого держателя")
        self.assertEqual(row["pid"], holder_pid)
        self.assertEqual(row["task_id"], self.TASK_B)

    def test_ac4_release_from_the_holder_process_removes_the_mutex(self):
        """Мьютекс взят ЭТИМ процессом через `acquire`; `release` с тем же
        `session_id` обязан снять его — иначе окно не освободится ни для
        кого до протухания heartbeat.

        Ловит мутацию: сверка pid в `release` написана против строки-
        держателя наоборот (`row["pid"] != os.getpid()`) либо pid берётся
        не из вызывающего процесса — свой же мьютекс перестанет
        сниматься, `assertIsNone` покраснеет.
        """
        merge_lock.acquire(store.db(), self.TASK_A, "sess-a")
        self.assertEqual(self.lock_row()["pid"], os.getpid())

        merge_lock.release(store.db(), "sess-a")

        self.assertIsNone(self.lock_row())


if __name__ == "__main__":
    unittest.main()
