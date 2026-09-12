"""Приёмочный тест 01M2B6JWGS9HMR9XZJBASXVNSY — AC-5.

AC-5. Своя сессия, pid прежнего держателя жив и не равен текущему,
`force=True` — строка lease перезаписывается (отказ по AC-1
перешагивается), как перешагивается существующий отказ по чужой
сессии.

Зелёный с рождения: сегодняшняя ветка «своя сессия» не проверяет ни
живость pid, ни `force` вовсе, поэтому строка и сейчас перезаписывается
безусловно — `force=True` здесь ничего не меняет по сравнению с
`force=False`, и заявленные ассерты уже выполняются. Тест — регресс-щит
на другую сторону дефекта: он обязан остаться зелёным ПОСЛЕ того, как
AC-1 заведёт отказ для живого чужого pid — если реализация забудет
прокинуть `force` в новую ветку (скопирует только текст отказа, не
условие `if not force`), `force=True` тоже начнёт отказывать, и этот
тест покраснеет.
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
from _sandbox import LeaseTmpRootTest, insert_lease_row, spawn_alive_pid  # noqa: E402


class ForceOverridesOwnSessionRefusalTest(LeaseTmpRootTest):

    def test_ac5_force_true_overwrites_the_row_despite_a_live_other_pid(self):
        """`force=True` над тем же сценарием, что и AC-1 (живой чужой pid
        той же сессии) — перезапись строки, не отказ.

        Ловит мутацию: если новая ветка AC-1 отказывает БЕЗУСЛОВНО, не
        сверяясь с параметром `force` (скопирует только текст отказа,
        забыв условие `if not force`), `refusal` здесь останется
        именованным отказом вместо `None`, а строка — прежней.
        """
        conn = store.db()
        other_pid = spawn_alive_pid(self)
        insert_lease_row(conn, self.TASK, "sess-a", other_pid,
                         socket.gethostname(), store.now())

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-a", force=True)

        self.assertIsNone(refusal)
        self.assertFalse(fresh)
        row = self.row()
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(row["hostname"], socket.gethostname())


if __name__ == "__main__":
    unittest.main()
