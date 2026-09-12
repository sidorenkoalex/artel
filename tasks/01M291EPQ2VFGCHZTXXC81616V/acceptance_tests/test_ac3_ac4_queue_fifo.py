"""AC-3/AC-4 — ожидающие регистрируются в таблице `merge_queue` (колонки
`task_id`, `session_id`, `pid`, `hostname`, `enqueued_ts`, `heartbeat_ts`)
в порядке FIFO по времени входа; освободившееся окно берёт ТОЛЬКО голова
очереди — прочие продолжают ждать, даже если мьютекс на момент их опроса
свободен (SPEC 01M291EPQ2VFGCHZTXXC81616V).

Красен до реализации: таблицы `merge_queue` нет ни в `SCHEMA`, ни в
`migrate()` (`orchestrator/schema.py`) — прямой `SELECT ... FROM
merge_queue` из теста AC-3 упадёт `sqlite3.OperationalError: no such
table: merge_queue`, это и есть отсутствие кода задачи, не опечатка
теста (само существование таблицы с этими колонками — часть критерия).
AC-4 упадёт раньше, на `start_waiting`, тем же образом, что и AC-1 (нет
цикла ожидания вовсе, второй/третий approve сразу `sys.exit`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import merge_lock, store  # noqa: E402

from _sandbox import QueueSandbox  # noqa: E402


class QueueFifoRegistrationTest(QueueSandbox):

    def test_ac3_third_approve_registers_third_in_the_merge_queue_table(self):
        """Держатель окна (первый approve) + два ожидающих (второй и
        третий approve) — второй встаёт первым в очереди, третий вторым;
        таблица `merge_queue` несёт ровно эти две строки с непустыми
        `task_id`/`session_id`/`pid`/`hostname`/`enqueued_ts`/
        `heartbeat_ts`, в порядке входа (FIFO).

        Ловит мутацию: третий approve вставлен ПЕРЕД вторым (порядок
        FIFO нарушен — например, сортировка по task_id вместо времени
        входа) — assertEqual порядка списка упадёт; регистрация пишет не
        все требуемые колонки (например, забыт `pid`/`hostname`) —
        assertTrue на непустых значениях упадёт.
        """
        self.seed_holder(self.TASK_A, "sess-a")

        t_b = self.start_waiting(self.TASK_B)
        t_c = self.start_waiting(self.TASK_C)
        try:
            rows = store.db().execute(
                "SELECT task_id, session_id, pid, hostname, enqueued_ts, "
                "heartbeat_ts FROM merge_queue ORDER BY enqueued_ts, rowid"
            ).fetchall()

            self.assertEqual([r["task_id"] for r in rows],
                             [self.TASK_B, self.TASK_C],
                             "второй approve обязан встать первым в "
                             "очереди, третий — вторым (FIFO по времени "
                             "входа)")
            for r in rows:
                self.assertTrue(r["session_id"], dict(r))
                self.assertTrue(r["pid"], dict(r))
                self.assertTrue(r["hostname"], dict(r))
                self.assertTrue(r["enqueued_ts"], dict(r))
                self.assertTrue(r["heartbeat_ts"], dict(r))
        finally:
            merge_lock.release(store.db(), "sess-a")
            self.proceed[self.TASK_B].set()
            self.proceed[self.TASK_C].set()
            t_b.join(timeout=5)
            t_c.join(timeout=5)


class QueueHeadOnlyGetsTheWindowTest(QueueSandbox):

    def test_ac4_non_head_waiter_keeps_waiting_even_when_the_mutex_is_free(self):
        """Голова очереди (второй approve, B) и не-голова (третий, C) ждут
        одновременно; мьютекс освобождается, и опрос НЕ-головы (C)
        происходит первым — C обязан остаться ждать (не занять свободный
        мьютекс), только следующий опрос головы (B) забирает окно.

        Ловит мутацию: любой ожидающий с успешным `merge_lock.acquire`
        забирает окно вне очереди (проверка головы отсутствует) — после
        опроса C `store.merge_lock_row` перестанет быть `None`, и/или C
        окажется в `self.done` раньше B.
        """
        self.seed_holder(self.TASK_A, "sess-a")

        t_b = self.start_waiting(self.TASK_B)
        t_c = self.start_waiting(self.TASK_C)
        try:
            merge_lock.release(store.db(), "sess-a")

            # C (не голова очереди) опрашивает первым, хотя мьютекс уже
            # свободен.
            got_ready = self.advance(self.TASK_C)
            self.assertTrue(got_ready,
                            "C обязан вернуться к следующему опросу, не "
                            "зависнуть и не завершиться")
            self.assertIsNone(
                store.merge_lock_row(store.db()),
                "AC-4: не-голова очереди не имеет права занять "
                "освободившееся окно")
            self.assertNotIn(self.TASK_C, self.done)

            # Голова очереди (B) опрашивает и получает окно.
            self.proceed[self.TASK_B].set()
            t_b.join(timeout=5)
            self.assertIn(self.TASK_B, self.done,
                         "голова очереди обязана получить освободившееся "
                         "окно")

            self.proceed[self.TASK_C].set()
            t_c.join(timeout=5)
            self.assertIn(self.TASK_C, self.done,
                         "после ухода головы очередь должна дойти до "
                         "конца и для оставшегося участника")
        finally:
            t_b.join(timeout=1)
            t_c.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
