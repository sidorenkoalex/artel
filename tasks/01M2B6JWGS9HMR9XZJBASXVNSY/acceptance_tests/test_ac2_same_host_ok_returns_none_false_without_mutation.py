"""Приёмочный тест 01M2B6JWGS9HMR9XZJBASXVNSY — AC-2.

AC-2. То же условие (своя сессия, pid держателя жив, не равен
текущему), но `same_host_ok=True` — `acquire` возвращает `(None,
False)` без отказа; строка lease в БД остаётся прежней.

Красен до реализации: сегодняшняя ветка «своя сессия» не принимает во
внимание `same_host_ok` вовсе (параметр читается только в ветке «чужая
сессия») — вызов с живым чужим pid безусловно ПЕРЕПИШЕТ строку lease
pid'ом текущего процесса (как и в AC-1), хотя по AC-2 строка обязана
остаться прежней держателя.
"""
import socket
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import lease, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTmpRootTest, insert_lease_row, spawn_alive_pid  # noqa: E402


class SameHostOkOwnSessionLiveOtherPidTest(LeaseTmpRootTest):

    def test_ac2_returns_none_false_and_does_not_mutate_the_row(self):
        """`same_host_ok=True` над тем же сценарием, что и AC-1 —
        никакого отказа, но и никакой мутации строки: вызывающая
        сторона узнаёт, что задачу ведёт живой процесс её же сессии,
        не становясь новым держателем.

        Ловит мутацию: если реализация AC-1 забудет разветвить
        `same_host_ok` внутри новой ветки «своя сессия» (перенесёт
        только именованный отказ, без параллельной ветки `same_host_ok`),
        этот вызов либо получит отказ вместо `(None, False)`, либо (как
        сегодня, до реализации требования 1 вовсе) молча перепишет
        строку lease на текущий процесс.
        """
        conn = store.db()
        other_pid = spawn_alive_pid(self)
        insert_lease_row(conn, self.TASK, "sess-a", other_pid,
                         socket.gethostname(), store.now())
        before = dict(self.row())

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-a",
                                       same_host_ok=True)

        self.assertIsNone(refusal)
        self.assertFalse(fresh)
        self.assertEqual(dict(self.row()), before)


if __name__ == "__main__":
    unittest.main()
