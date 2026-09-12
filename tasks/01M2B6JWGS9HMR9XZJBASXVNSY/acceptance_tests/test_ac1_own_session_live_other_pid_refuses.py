"""Приёмочный тест 01M2B6JWGS9HMR9XZJBASXVNSY — AC-1.

AC-1. `lease.acquire`: своя сессия, pid прежнего держателя жив, НЕ
равен pid текущего процесса, `same_host_ok=False` — возвращается
именованный отказ, содержащий `task_id`, pid держателя и слова «этой
же сессии»; строка lease в БД (session_id/pid/hostname/heartbeat)
остаётся прежней.

Красен до реализации: ветка «своя сессия» (`orchestrator/lease.py:115-
117`, `if row["session_id"] == session_id: store.update_lease(...);
return None, False`) сегодня не смотрит на pid держателя вовсе — она
безусловно переписывает строку pid'ом текущего процесса и возвращает
`(None, False)`, поэтому `refusal` здесь останется `None`, а строка
lease будет переписана вместо оставленной как есть.
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


class OwnSessionLiveOtherPidRefusesTest(LeaseTmpRootTest):

    def test_ac1_named_refusal_and_row_unchanged(self):
        """Своя сессия уже держит lease под другим (живым) pid — второй
        вызов той же сессии обязан получить именованный отказ, не
        перехват.

        Ловит мутацию: если сравнение `row["pid"] == os.getpid()` в
        новой ветке будет заменено на всегда-`True` (или проверка
        живости `liveness._pid_alive(row["pid"])` — на всегда-`False`),
        вызов ошибочно продлит/перехватит lease вместо отказа, и
        `refusal` окажется `None`.
        """
        conn = store.db()
        other_pid = spawn_alive_pid(self)
        insert_lease_row(conn, self.TASK, "sess-a", other_pid,
                         socket.gethostname(), store.now())
        before = dict(self.row())

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-a")

        self.assertIsNotNone(refusal)
        self.assertIn(self.TASK, refusal)
        self.assertIn(str(other_pid), refusal)
        self.assertIn("этой же сессии", refusal)
        self.assertFalse(fresh)
        self.assertEqual(dict(self.row()), before)


if __name__ == "__main__":
    unittest.main()
