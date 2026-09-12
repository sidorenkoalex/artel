"""AC-8 — запись `merge_queue` с неживым pid (на своём хосте) удаляется
при следующем взятии освободившегося окна, не блокируя вечно живых
участников очереди позади себя (SPEC 01M291EPQ2VFGCHZTXXC81616V,
требование 5 — тот же признак мёртвого участника, что
`merge_lock._holder_is_dead`).

Красен до реализации: таблицы `merge_queue` нет — прямой `INSERT INTO
merge_queue` из теста упадёт `sqlite3.OperationalError: no such table:
merge_queue`, это отсутствие кода задачи (существование таблицы —
предпосылка AC-3/AC-8 одновременно), не опечатка теста.
"""
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import merge_lock, store  # noqa: E402
from tests.sandbox import _dead_pid, _ts_ago  # noqa: E402

from _sandbox import QueueSandbox  # noqa: E402


class DeadQueueEntryTest(QueueSandbox):

    def test_ac8_dead_queue_entry_is_pruned_and_does_not_block_the_live_waiter(self):
        """Мёртвая запись (неживой pid на этом host) встала в очередь
        РАНЬШЕ живого участника; окно освобождается — живой участник всё
        равно обязан его получить (мёртвая запись не наследует место
        головы очереди вечно), а сама мёртвая запись пропадает из
        `merge_queue`.

        Ловит мутацию: `_holder_is_dead`-подобная проверка для записей
        `merge_queue` не реализована (мёртвая запись считается головой
        очереди навсегда) — живой участник (`self.TASK_B`) никогда не
        попадёт в `self.done`, тест упадёт по таймауту `thread.join`
        (поток не daemon-завершится за отведённое время, останется
        висеть — `assertIn` на `self.done` не найдёт `TASK_B`); запись
        удаляется, но НЕ именно мёртвая (например, чистится вся таблица)
        — второй `assertEqual` (запись живого участника всё ещё должна
        быть видна ДО его завершения) можно расширить отдельно, здесь
        минимально проверяем, что мёртвая запись исчезла, а живой
        участник таки прошёл.
        """
        self.seed_holder(self.TASK_A, "sess-a")
        conn = store.db()
        conn.execute(
            "INSERT INTO merge_queue (task_id, session_id, pid, hostname, "
            "enqueued_ts, heartbeat_ts) VALUES (?,?,?,?,?,?)",
            (self.TASK_C, "sess-dead", _dead_pid(), socket.gethostname(),
             _ts_ago(1), _ts_ago(1)))
        conn.commit()

        thread = self.start_waiting(self.TASK_B)
        try:
            merge_lock.release(conn, "sess-a")
            self.proceed[self.TASK_B].set()
            thread.join(timeout=5)

            self.assertIn(
                self.TASK_B, self.done,
                "мёртвая запись впереди в очереди не имеет права вечно "
                "блокировать живого участника позади себя")
            remaining = conn.execute(
                "SELECT task_id FROM merge_queue WHERE task_id=?",
                (self.TASK_C,)).fetchall()
            self.assertEqual(
                remaining, [],
                "мёртвая запись обязана быть удалена при следующем "
                "взятии освободившегося окна")
        finally:
            thread.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
