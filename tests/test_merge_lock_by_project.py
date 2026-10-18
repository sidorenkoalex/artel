"""Мьютекс и очередь мержа по проекту — свойства из ответа Оператора
ANSWER-2 задачи 01M57PM7NBFX34319TR0F9CB4F, не покрытые долгоживущими
файлами задачи: прежняя форма `touch_heartbeat(conn)` при строках
нескольких проектов, вход в мерж через `wait_for_window` при более ранней
записи очереди другого проекта, тексты ожидания при любом порядке строк
мьютекса трёх проектов."""
import itertools
import os
from unittest import mock

from orchestrator import catalog, config, merge_lock, merge_queue, store
from tests.sandbox import TmpRootTest, _ts_ago, capture, declare_target, patch_sleep

OTHER_HOST = "other-host.invalid"


class _Base(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.conn = store.db()
        self.counter = 0
        for name in ("extone", "exttwo"):
            declare_target(name)

    def new_task(self, target: str) -> str:
        self.counter += 1
        tid = f"T{self.counter:03d}"
        store.insert_task(self.conn, tid, "мерж", "merge_gate",
                          f"task/{tid.lower()}", target, 25.0)
        return tid

    def seed_lock(self, task_id: str, session_id: str, pid: int,
                  heartbeat_ts: str = None) -> dict:
        self.conn.execute(
            "INSERT INTO merge_locks (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, OTHER_HOST,
             heartbeat_ts or store.now()))
        self.conn.commit()
        return self.locks()[task_id]

    def locks(self) -> dict:
        return {r["task_id"]: dict(r) for r in
                self.conn.execute("SELECT * FROM merge_locks").fetchall()}

    def clear(self) -> None:
        self.conn.execute("DELETE FROM merge_locks")
        self.conn.execute("DELETE FROM merge_queue")
        self.conn.commit()


class LegacyTouchHeartbeatTest(_Base):

    def test_no_args_with_several_projects_renews_only_current_session(self):
        """Строки двух проектов, обе с heartbeat десять минут назад: строка
        текущей сессии (`ARTEL_SESSION_ID`) и строка другой сессии.
        `touch_heartbeat(conn)` делает свежей только первую — при любом
        порядке вставки.

        Ловит мутацию: прежняя форма продлевает все строки либо первую
        строку таблицы — строка чужой сессии станет свежей (или своя
        останется старой в одном из порядков вставки)."""
        old = _ts_ago(600)
        for own_first in (True, False):
            with self.subTest(own_first=own_first):
                self.clear()
                own_task, other_task = (self.new_task(config.DEFAULT_TARGET),
                                        self.new_task("extone"))
                seeds = [(own_task, "s-own", 101), (other_task, "s-other", 202)]
                for args in (seeds if own_first else seeds[::-1]):
                    self.seed_lock(*args, heartbeat_ts=old)

                with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "s-own"}):
                    merge_lock.touch_heartbeat(self.conn)

                rows = self.locks()
                self.assertEqual(rows[other_task]["heartbeat_ts"], old)
                self.assertNotEqual(rows[own_task]["heartbeat_ts"], old)


class WaitForWindowOtherProjectQueueTest(_Base):

    def test_earlier_entry_of_other_project_does_not_delay_entry(self):
        """В очереди раньше стоит живая запись задачи проекта Q, мьютекс Q
        держит живой держатель; `wait_for_window` задачи проекта P берёт
        мьютекс P без единой паузы, запись Q остаётся в очереди.

        Ловит мутацию: голова очереди в `wait_for_window` — первая запись
        всей очереди (глобальный FIFO) — P не станет головой и уйдёт в
        паузу, `fake_sleep` бросит `AssertionError`."""
        for p_target, q_target in ((config.DEFAULT_TARGET, "extone"),
                                   ("extone", config.DEFAULT_TARGET)):
            with self.subTest(p=p_target, q=q_target):
                self.clear()
                q_holder, q_waiting = (self.new_task(q_target),
                                       self.new_task(q_target))
                self.seed_lock(q_holder, "s-q", 303)
                store.enqueue_merge_wait(self.conn, q_waiting, "s-qw", 404,
                                         OTHER_HOST, _ts_ago(120))
                caller = self.new_task(p_target)

                def fake_sleep(_seconds):
                    raise AssertionError("задача P ушла в паузу очереди")

                with patch_sleep(merge_queue, fake_sleep):
                    merge_queue.wait_for_window(self.conn, caller, "s-p")

                self.assertEqual(self.locks()[caller]["session_id"], "s-p")
                self.assertEqual(
                    [r["task_id"] for r in store.merge_queue_rows(self.conn)],
                    [q_waiting])


class WaitTextsAnyOrderTest(_Base):

    def test_texts_name_own_project_holder_in_every_insertion_order(self):
        """Строки мьютекса трёх проектов — во всех шести порядках вставки;
        отказ `acquire`, запись журнала входа в очередь (`wait_for_window`
        с нулевым потолком) и добавка `status` задачи проекта P называют
        держателя P.

        Ловит мутацию: держатель берётся первой (или последней) строкой
        таблицы, а не строкой проекта ждущей задачи — в части порядков
        тексты назовут держателя другого проекта."""
        targets = (config.DEFAULT_TARGET, "extone", "exttwo")
        for order in itertools.permutations(targets):
            for p_target in targets:
                with self.subTest(order=order, p=p_target):
                    self.clear()
                    holders = {}
                    for pid, target in enumerate(order, start=500):
                        holders[target] = self.seed_lock(
                            self.new_task(target), f"s-{target}", pid)
                    hp = holders[p_target]
                    caller = self.new_task(p_target)

                    refusal = merge_lock.acquire(self.conn, caller, "s-caller")
                    with mock.patch.object(config,
                                           "MERGE_QUEUE_WAIT_CEILING_SEC", 0), \
                         self.assertRaises(SystemExit):
                        merge_queue.wait_for_window(self.conn, caller,
                                                    "s-caller")
                    entered = [s["action"] for s in
                               store.task_steps(self.conn, caller)
                               if s["action"].startswith("ждёт merge-окна")]
                    store.enqueue_merge_wait(self.conn, caller, "s-caller",
                                             909, OTHER_HOST, _ts_ago(130))
                    suffix = merge_queue.wait_suffix(
                        self.conn, store.get_task(self.conn, caller))

                    self.assertIn(f"задача {hp['task_id']})", refusal)
                    self.assertIn(f"(pid {hp['pid']}, ", refusal)
                    self.assertEqual(entered, [f"ждёт merge-окна: держит "
                                               f"{hp['task_id']} (pid {hp['pid']})"])
                    self.assertEqual(
                        suffix, f"  [ждёт merge-окна: занято {hp['task_id']} "
                                f"(pid {hp['pid']}), 2 мин]")
