"""AC-5 — записи `merge_queue` двух процессов одной сессии независимы:
продление heartbeat и снятие записи адресуются процессом (задача
01M2XFSE8G3MBRHHQR38H53J1M).

Красен до реализации: `store.touch_merge_queue_heartbeat` и
`store.dequeue_merge_wait` адресуют записи одним `session_id`
(`orchestrator/store.py:720`, `:728` — `WHERE session_id=?`), поэтому один
процесс продлевает heartbeat ЧУЖОЙ записи своей сессии, а его `finally`
снимает её из очереди целиком: второй записи той же сессии в очереди не
остаётся.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import merge_queue, store  # noqa: E402

from _sandbox import MergeOwnerSandbox, _alive_foreign_pid, _ts_ago  # noqa: E402


class QueueRowsPerProcessTest(MergeOwnerSandbox):

    def setUp(self):
        super().setUp()
        self.other_pid = _alive_foreign_pid(self)
        self.host = socket.gethostname()

    def other_row(self):
        return next((r for r in self.queue_rows()
                     if r["task_id"] == self.TASK_B), None)

    def test_ac5_non_head_process_waits_without_touching_the_other_row(self):
        """В очереди уже стоит запись другого живого процесса той же сессии
        `sess-a` (задача B, вошла раньше — голова очереди). Наш процесс
        встаёт в `wait_for_window` по задаче A: головой он не является,
        окно не берёт (мьютекс остаётся свободным до самого потолка), а
        чужую запись не продлевает и в своём `finally` не снимает.

        Ловит мутацию: `touch_merge_queue_heartbeat`/`dequeue_merge_wait`
        оставлены по одному `session_id` — heartbeat записи B окажется
        продлён нашим опросом (сверка `heartbeat_ts` покраснеет), а сама
        запись B исчезнет вместе с нашей (сверка списка задач очереди
        покраснеет).
        """
        # Запись B вошла на 30 секунд РАНЬШЕ нашей (`enqueue` кладёт одну и
        # ту же метку в `enqueued_ts` и `heartbeat_ts`) — по FIFO она голова
        # очереди, наша задача A головой стать не может.
        seeded_heartbeat = _ts_ago(30)
        self.enqueue(self.TASK_B, "sess-a", self.other_pid, self.host,
                     seeded_heartbeat)
        self.fake_clock()

        with self.assertRaises(SystemExit):
            merge_queue.wait_for_window(store.db(), self.TASK_A, "sess-a")

        self.assertEqual([r["task_id"] for r in self.queue_rows()],
                         [self.TASK_B],
                         "своя запись обязана сняться, чужая — остаться")
        self.assertEqual(self.other_row()["heartbeat_ts"], seeded_heartbeat,
                         "опрос одного процесса не имеет права продлевать "
                         "heartbeat записи другого")
        self.assertIsNone(store.merge_lock_row(store.db()),
                          "процесс, не являющийся головой очереди, окно "
                          "не берёт")

    def test_ac5_head_process_takes_the_window_and_leaves_the_row_behind_it(self):
        """Запись другого процесса той же сессии вошла в очередь ПОЗЖЕ
        (задача B), значит голова — наша задача A: мьютекс свободен, и наш
        процесс обязан взять окно, сняв только свою запись; запись B
        остаётся ждать своей очереди с неизменным heartbeat.

        Ловит мутацию: снятие записи по одному `session_id` — запись B
        уйдёт из очереди вместе с нашей, хотя её процесс жив и окна не
        получал; FIFO-порядок для следующего опроса будет потерян.
        """
        # Зеркально предыдущему тесту: метка записи B на 30 секунд ВПЕРЁД,
        # значит по FIFO голова очереди — наша задача A.
        seeded_heartbeat = _ts_ago(-30)
        self.enqueue(self.TASK_B, "sess-a", self.other_pid, self.host,
                     seeded_heartbeat)
        clock = self.fake_clock()

        merge_queue.wait_for_window(store.db(), self.TASK_A, "sess-a")

        row = store.merge_lock_row(store.db())
        self.assertEqual(row["task_id"], self.TASK_A)
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(clock.sleep_calls, [],
                         "голова очереди при свободном окне не ждёт")
        self.assertEqual([r["task_id"] for r in self.queue_rows()],
                         [self.TASK_B])
        self.assertEqual(self.other_row()["heartbeat_ts"], seeded_heartbeat)


if __name__ == "__main__":
    unittest.main()
