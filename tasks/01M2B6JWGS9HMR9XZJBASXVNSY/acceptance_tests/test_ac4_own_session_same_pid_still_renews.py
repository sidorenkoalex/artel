"""Приёмочный тест 01M2B6JWGS9HMR9XZJBASXVNSY — AC-4.

AC-4. Своя сессия, pid прежнего держателя равен pid текущего процесса
— строка lease продлевается (heartbeat обновляется), как и до этой
задачи.

Зелёный с рождения: сегодняшняя ветка «своя сессия» продлевает
безусловно, `row["pid"] == os.getpid()` — тоже частный случай этого
кода, так что продление уже происходит. Тест — регресс-щит: после
реализации требования 1 (AC-1/AC-2/AC-5 добавляют отказ/`same_host_ok`
для ЧУЖОГО, но живого pid) собственный pid обязан остаться на
прежнем пути продления, а не провалиться в новую ветку.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import lease, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTmpRootTest, insert_lease_row  # noqa: E402
from tests.sandbox import _ts_ago  # noqa: E402


class OwnSessionSamePidStillRenewsTest(LeaseTmpRootTest):

    def test_ac4_heartbeat_is_renewed_for_the_same_pid(self):
        """Строка lease уже принадлежит этому же процессу (тот же pid,
        та же сессия) — повторный `acquire` обязан продлить heartbeat,
        не отказывать и не считать это взятием «с нуля».

        Ловит мутацию: если новая ветка AC-1 забудет исключить случай
        `row["pid"] == os.getpid()` из проверки «жив и не равен
        текущему» (например, будет сравнивать только `hostname`), этот
        же самый процесс получит отказ самому себе вместо продления.
        """
        conn = store.db()
        old_heartbeat = _ts_ago(30)
        insert_lease_row(conn, self.TASK, "sess-a", os.getpid(),
                         socket.gethostname(), old_heartbeat)

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertFalse(fresh)
        row = self.row()
        self.assertEqual(row["pid"], os.getpid())
        self.assertNotEqual(row["heartbeat_ts"], old_heartbeat)


if __name__ == "__main__":
    unittest.main()
