"""Приёмочный тест 01M2B6JWGS9HMR9XZJBASXVNSY — AC-3.

AC-3. Своя сессия, pid прежнего держателя мёртв
(`liveness._pid_alive` -> `False`) — строка lease перезаписывается
pid/hostname/heartbeat текущего процесса, как и до этой задачи.

Зелёный с рождения: сегодняшняя ветка «своя сессия» переписывает
строку БЕЗУСЛОВНО (без проверки живости), поэтому мёртвый прежний
держатель уже перезаписывается — свойство сохраняется само по себе.
Тест — регресс-щит: после реализации требования 1 (AC-1/AC-2/AC-5 —
проверка живости pid) этот сценарий обязан остаться в ветке
«перезаписать», а не соскользнуть в новую ветку отказа/`same_host_ok`.
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
from tests.sandbox import _dead_pid  # noqa: E402


class OwnSessionDeadHolderStillOverwritesTest(LeaseTmpRootTest):

    def test_ac3_dead_holder_pid_is_overwritten_by_the_current_process(self):
        """Прежний держатель той же сессии физически мёртв (гарантированно
        завершившийся дочерний процесс, `_dead_pid()`) — `acquire` обязан
        перезаписать строку, не возвращая отказ.

        Ловит мутацию: если новая проверка живости из AC-1
        (`liveness._pid_alive(row["pid"])`) будет инвертирована или
        подменена сравнением возраста heartbeat, мёртвый держатель со
        свежим heartbeat ошибочно попадёт в ветку отказа AC-1 вместо
        перезаписи, и `refusal` перестанет быть `None`.
        """
        conn = store.db()
        dead_pid = _dead_pid()
        insert_lease_row(conn, self.TASK, "sess-a", dead_pid,
                         socket.gethostname(), store.now())

        refusal, fresh = lease.acquire(conn, self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertFalse(fresh)
        row = self.row()
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(row["hostname"], socket.gethostname())


if __name__ == "__main__":
    unittest.main()
