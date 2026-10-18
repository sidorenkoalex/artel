"""Мьютекс и очередь мержа разделены по проекту задачи: держатель и
очередь другого проекта не задерживают мерж, внутри проекта правила
прежние.

Группа: долгоживущий
Красен до реализации: мьютекс — одна строка на пульт (`store.set_merge_lock` стирает всю таблицу, `acquire`/`wait_for_window`/тексты ожидания смотрят первую строку, голова очереди — первая запись всего пульта), `touch_heartbeat` не принимает `task_id`/`session_id` — AC-1, AC-2, AC-4 б, AC-6, AC-7, AC-8, AC-9, AC-10 (два проекта), AC-11 красны; AC-3, AC-4 а, AC-5, AC-10 (один проект), AC-16, AC-17 держат прежнее поведение одного проекта и зелены до правки.

Связка: команды модулей `merge_lock`/`merge_queue`/`store` на БД песочницы
(`TmpRootTest`), без git. Проект задачи — колонка `target` строки задачи;
внешний проект объявлен в `config.TARGETS` песочницы (`declare_target`).
Вторая строка `merge_locks` сеется прямой вставкой в таблицу: схема
(`orchestrator/schema.py`) несёт несколько строк без ключа, а прежний
`store.set_merge_lock` стирает таблицу целиком. Живой держатель — чужой
host со свежим heartbeat (pid там не проверяется), мёртвый — протухший
heartbeat (`config.LEASE_STALE_AFTER_SEC`) либо неживой pid на этом host.
Ожидание очереди идёт на подменённых часах: `time.monotonic` и пауза
`merge_queue` (`patch_sleep`) — реального сна нет.

Идентификаторы задач, сессий, pid и имя внешнего проекта случайны на
каждый запуск; зерно печатается и входит в текст провала.
"""
import os
import random
import re
import socket
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

from orchestrator import catalog, config, merge_lock, merge_queue, store
from tests.sandbox import (TmpRootTest, _dead_pid, _ts_ago, capture,
                           declare_target, patch_sleep)

OTHER_HOST = "other-host.invalid"
TS_FORMAT = "%Y-%m-%d %H:%M:%SZ"
TAKEOVER_ACTION = "мьютекс merge перехвачен"
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def refusal_pattern(caller: str, holder: dict) -> str:
    """Прежний текст отказа `acquire` целиком; секунды heartbeat — любое
    целое."""
    return (rf"^\[{re.escape(caller)}\] merge-окно занято сессией "
            rf"{re.escape(holder['session_id'])} \(pid {holder['pid']}, "
            rf"задача {re.escape(holder['task_id'])}\), heartbeat \d+ сек "
            rf"назад — дождись освобождения и повтори approve$")


class _ProjectMutexBase(TmpRootTest):
    """Стенд: инициализированный пульт, пустые `merge_locks`/`merge_queue`,
    объявленный внешний проект `self.ext` рядом с артелью."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.artel = config.DEFAULT_TARGET
        self.ext = self.new_project()
        self.conn = store.db()

    # --- фикстуры сценария ---

    def token(self, n: int = 10) -> str:
        return "".join(self.rng.choice(_ALPHABET) for _ in range(n))

    def new_project(self) -> str:
        name = "ext" + self.token(6).lower()
        declare_target(name)
        return name

    def new_task(self, target) -> str:
        """Задача в `merge_gate`; `target` — имя проекта, `""` или `None`."""
        tid = "T" + self.token(12)
        conn = store.db()
        store.insert_task(conn, tid, "мерж по проекту", "merge_gate",
                          f"task/{tid.lower()}", config.DEFAULT_TARGET, 25.0)
        if target != config.DEFAULT_TARGET:
            store.update_task(conn, tid, target=target)
        return tid

    def session(self) -> str:
        return "s-" + self.token(8).lower()

    def foreign_pid(self) -> int:
        pid = self.rng.randrange(100000, 4000000)
        return pid if pid != os.getpid() else pid + 1

    def seed_lock(self, task_id: str, session_id: str, pid: int,
                  hostname: str = OTHER_HOST, heartbeat_ts: str = None) -> dict:
        self.conn.execute(
            "INSERT INTO merge_locks (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, hostname,
             heartbeat_ts or store.now()))
        self.conn.commit()
        return self.lock_by_task()[task_id]

    def live_holder(self, target) -> dict:
        return self.seed_lock(self.new_task(target), self.session(),
                              self.foreign_pid())

    def lock_by_task(self) -> dict:
        return {r["task_id"]: dict(r) for r in
                self.conn.execute("SELECT * FROM merge_locks").fetchall()}

    def queue_task_ids(self) -> list:
        return [r["task_id"] for r in store.merge_queue_rows(self.conn)]

    def clear(self) -> None:
        self.conn.execute("DELETE FROM merge_locks")
        self.conn.execute("DELETE FROM merge_queue")
        self.conn.commit()

    def enqueue(self, task_id: str, ts: str, *, session_id: str = None,
                pid: int = None, hostname: str = OTHER_HOST) -> tuple:
        sid = session_id or self.session()
        pid = pid or self.foreign_pid()
        store.enqueue_merge_wait(self.conn, task_id, sid, pid, hostname, ts)
        return sid, pid

    def run_wait(self, task_id: str, sid: str, on_sleep=None) -> tuple:
        """`wait_for_window` на подменённых часах: (паузы, текст выхода по
        потолку либо `None` — окно получено)."""
        clock = {"value": 0.0}
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            clock["value"] += seconds
            if on_sleep is not None:
                on_sleep(len(sleeps))

        exited = None
        with mock.patch.object(time, "monotonic", lambda: clock["value"]), \
             patch_sleep(merge_queue, fake_sleep):
            try:
                merge_queue.wait_for_window(self.conn, task_id, sid)
            except SystemExit as exc:
                exited = str(exc)
        return sleeps, exited

    def actions(self, task_id: str) -> list:
        return [s["action"] for s in store.task_steps(self.conn, task_id)]

    def msg(self, ctx: str) -> str:
        return f"{ctx}; зерно {self.seed}"

    def assert_fresh(self, ts: str, ctx: str) -> None:
        stamp = datetime.strptime(ts, TS_FORMAT).replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        self.assertLess(age, 60, self.msg(f"{ctx}: heartbeat {ts} не свежий"))

    def project_pairs(self) -> tuple:
        return ((self.ext, self.artel), (self.artel, self.ext))


class AcquireByProjectTest(_ProjectMutexBase):

    def test_ac1_other_project_holder_does_not_block_acquire(self):
        """Живой держатель проекта Q; `acquire` задачи проекта P другим
        процессом берёт мьютекс, обе строки в таблице, строка Q прежняя.

        Сценарий в обе стороны: Q — внешний, P — артель, и наоборот.

        Ловит мутацию: `acquire` читает одну строку на пульт (прежний
        `merge_lock_row`) — вернётся отказ «merge-окно занято …», и
        `assertIsNone` покраснеет; либо `set_merge_lock` по-прежнему делает
        `DELETE` без `WHERE` — строка держателя Q пропадёт из таблицы."""
        for holder_target, caller_target in self.project_pairs():
            with self.subTest(holder=holder_target, caller=caller_target):
                self.clear()
                holder = self.live_holder(holder_target)
                caller, sid = self.new_task(caller_target), self.session()
                ctx = self.msg(f"держит {holder}, берёт {caller}")

                refusal = merge_lock.acquire(self.conn, caller, sid)

                self.assertIsNone(refusal, ctx)
                rows = self.lock_by_task()
                self.assertEqual(rows.get(holder["task_id"]), holder, ctx)
                self.assertIn(caller, rows, ctx)
                self.assertEqual((rows[caller]["session_id"],
                                  rows[caller]["pid"]),
                                 (sid, os.getpid()), ctx)

    def test_ac3_live_holder_of_same_project_refuses_with_old_text(self):
        """Живой держатель проекта P; `acquire` второй задачи того же P
        другим процессом даёт прежний текст отказа, таблица не меняется.

        Проверяется для артели и для внешнего проекта.

        Ловит мутацию: проект сверяется не по `target` задачи держателя
        (например, держатель того же проекта считается чужим) — `acquire`
        вернёт `None` и перепишет таблицу; либо текст отказа собран
        иначе — сверка шаблона покраснеет."""
        for target in (self.artel, self.ext):
            with self.subTest(project=target):
                self.clear()
                holder = self.live_holder(target)
                caller = self.new_task(target)
                ctx = self.msg(f"проект {target}, держит {holder}")

                refusal = merge_lock.acquire(self.conn, caller, self.session())

                self.assertIsNotNone(refusal, ctx)
                self.assertRegex(refusal, refusal_pattern(caller, holder), ctx)
                self.assertEqual(self.lock_by_task(),
                                 {holder["task_id"]: holder}, ctx)

    def test_ac4_dead_holder_of_same_project_is_taken_over(self):
        """Мёртвый держатель проекта P (протухший heartbeat) перехватывается
        `acquire` задачи P; в журнал задачи — «мьютекс merge перехвачен».

        Ловит мутацию: перехват ищет мёртвую строку не своего проекта (или
        `set_merge_lock` добавляет строку, не снося прежнюю строку
        проекта) — в таблице останется строка мёртвого держателя P, сверка
        состава покраснеет; либо перехват идёт без записи журнала."""
        stale = _ts_ago(config.LEASE_STALE_AFTER_SEC + 60)
        for target in (self.artel, self.ext):
            with self.subTest(project=target):
                self.clear()
                dead = self.seed_lock(self.new_task(target), self.session(),
                                      self.foreign_pid(), heartbeat_ts=stale)
                caller, sid = self.new_task(target), self.session()
                ctx = self.msg(f"проект {target}, мёртв {dead}")

                refusal = merge_lock.acquire(self.conn, caller, sid)

                self.assertIsNone(refusal, ctx)
                rows = self.lock_by_task()
                self.assertEqual(sorted(rows), [caller], ctx)
                self.assertEqual(rows[caller]["session_id"], sid, ctx)
                self.assertIn(TAKEOVER_ACTION, self.actions(caller), ctx)

    def test_ac4_dead_holder_of_other_project_is_left_intact(self):
        """Мёртвый держатель проекта Q (протухший heartbeat); `acquire`
        задачи проекта P берёт мьютекс, строка Q остаётся без изменений.

        Ловит мутацию: `acquire` перехватывает любую мёртвую строку
        таблицы, а не строку своего проекта, либо `set_merge_lock`
        стирает строки других проектов — строка Q исчезнет или окажется
        переписанной, `assertEqual(rows.get(...), dead)` покраснеет."""
        stale = _ts_ago(config.LEASE_STALE_AFTER_SEC + 60)
        for holder_target, caller_target in self.project_pairs():
            with self.subTest(holder=holder_target, caller=caller_target):
                self.clear()
                dead = self.seed_lock(self.new_task(holder_target),
                                      self.session(), self.foreign_pid(),
                                      heartbeat_ts=stale)
                caller = self.new_task(caller_target)
                ctx = self.msg(f"мёртв {dead}, берёт {caller}")

                refusal = merge_lock.acquire(self.conn, caller, self.session())

                self.assertIsNone(refusal, ctx)
                rows = self.lock_by_task()
                self.assertEqual(rows.get(dead["task_id"]), dead, ctx)
                self.assertIn(caller, rows, ctx)
                self.assertNotIn(TAKEOVER_ACTION, self.actions(caller), ctx)

    def test_ac16_artel_holder_excludes_empty_null_and_missing_target(self):
        """Живой держатель — задача артели с явным `target`; `acquire`
        задачи с пустым `target`, с `NULL` и задачи без строки в `tasks`
        — каждый отказ «merge-окно занято …», строка держателя прежняя.

        Ловит мутацию: проект задачи берётся сырой колонкой `target`
        (без нормализации `store.task_target`) — пустая/`NULL`/отсутствующая
        задача окажется «другим проектом», `acquire` вернёт `None`."""
        holder = self.live_holder(self.artel)
        callers = {"пустой": self.new_task(""), "NULL": self.new_task(None),
                   "нет в tasks": "T" + self.token(12)}
        for kind, caller in callers.items():
            with self.subTest(caller=kind):
                ctx = self.msg(f"{kind} target {caller}, держит {holder}")

                refusal = merge_lock.acquire(self.conn, caller, self.session())

                self.assertIsNotNone(refusal, ctx)
                self.assertIn("merge-окно занято", refusal, ctx)
                self.assertEqual(self.lock_by_task(),
                                 {holder["task_id"]: holder}, ctx)

    def test_ac16_empty_or_null_target_holder_excludes_artel_task(self):
        """Живой держатель — задача с пустым либо `NULL` `target`;
        `acquire` задачи артели с явным `target` получает отказ.

        Ловит мутацию: проект держателя берётся сырой колонкой `target` —
        держатель с `""`/`NULL` окажется «другим проектом», `acquire`
        задачи артели вернёт `None` и добавит вторую строку артели."""
        for target in ("", None):
            with self.subTest(holder_target=target):
                self.clear()
                holder = self.live_holder(target)
                caller = self.new_task(self.artel)
                ctx = self.msg(f"держатель target={target!r} {holder}")

                refusal = merge_lock.acquire(self.conn, caller, self.session())

                self.assertIsNotNone(refusal, ctx)
                self.assertIn("merge-окно занято", refusal, ctx)
                self.assertEqual(self.lock_by_task(),
                                 {holder["task_id"]: holder}, ctx)


class ReleaseAndHeartbeatTest(_ProjectMutexBase):

    def test_ac5_release_removes_only_own_process_row(self):
        """Три проекта: строка этого процесса (взята `acquire`), строка
        держателя другого проекта и строка другого процесса той же
        сессии (третий проект); `release` снимает только первую.

        Ловит мутацию: `release`/`store.release_merge_lock` сносит строки
        по одному `session_id` либо всю таблицу — строка соседа той же
        сессии (или держателя другого проекта) пропадёт, сверка состава
        покраснеет."""
        targets = [self.artel, self.ext, self.new_project()]
        self.rng.shuffle(targets)
        own_target, other_target, same_sid_target = targets
        sid = self.session()
        own = self.new_task(own_target)
        ctx = self.msg(f"свой {own_target}, чужой {other_target}, "
                       f"та же сессия {same_sid_target}")
        self.assertIsNone(merge_lock.acquire(self.conn, own, sid), ctx)
        other = self.live_holder(other_target)
        same_sid = self.seed_lock(self.new_task(same_sid_target), sid,
                                  self.foreign_pid())

        merge_lock.release(self.conn, sid)

        self.assertEqual(self.lock_by_task(),
                         {other["task_id"]: other,
                          same_sid["task_id"]: same_sid}, ctx)

    def test_ac6_touch_heartbeat_renews_only_callers_project_row(self):
        """Держат проекты A и B, обе строки с heartbeat десять минут назад;
        `touch_heartbeat(conn, task_id, session_id)` держателя A делает
        свежим heartbeat строки A, строка B прежняя.

        Ловит мутацию: продление берёт «первую» строку таблицы или
        продлевает все строки — heartbeat B станет свежим либо A останется
        старым (в одном из двух порядков вставки)."""
        old = _ts_ago(600)
        for a_target, b_target in self.project_pairs():
            for a_first in (True, False):
                with self.subTest(a=a_target, b=b_target, a_first=a_first):
                    self.clear()
                    a_task, a_sid = self.new_task(a_target), self.session()
                    b_task = self.new_task(b_target)
                    seeds = [lambda: self.seed_lock(
                                 a_task, a_sid, os.getpid(),
                                 socket.gethostname(), old),
                             lambda: self.seed_lock(
                                 b_task, self.session(), self.foreign_pid(),
                                 heartbeat_ts=old)]
                    for seed in (seeds if a_first else seeds[::-1]):
                        seed()
                    before = self.lock_by_task()
                    ctx = self.msg(f"A {a_task}, B {b_task}")

                    merge_lock.touch_heartbeat(self.conn, a_task, a_sid)

                    rows = self.lock_by_task()
                    self.assertEqual(rows[b_task], before[b_task], ctx)
                    self.assert_fresh(rows[a_task]["heartbeat_ts"], ctx)
                    self.assertEqual(
                        {k: v for k, v in rows[a_task].items()
                         if k != "heartbeat_ts"},
                        {k: v for k, v in before[a_task].items()
                         if k != "heartbeat_ts"}, ctx)

    def test_ac7_touch_heartbeat_does_not_renew_intercepted_row(self):
        """Строку проекта A перехватил новый держатель — (а) другая задача
        A, (б) та же задача с другим session_id; `touch_heartbeat` с
        задачей и сессией прежнего держателя строку нового не меняет.

        Ловит мутацию: продление сверяет только проект строки (или только
        задачу) — heartbeat нового держателя станет свежим либо строка
        перепишется задачей/сессией прежнего, сверка «до/после»
        покраснеет."""
        old = _ts_ago(300)
        for target in (self.artel, self.ext):
            for variant in ("другая задача", "другая сессия"):
                with self.subTest(project=target, variant=variant):
                    self.clear()
                    old_task, old_sid = self.new_task(target), self.session()
                    new_task = (self.new_task(target)
                                if variant == "другая задача" else old_task)
                    holder = self.seed_lock(new_task, self.session(),
                                            self.foreign_pid(),
                                            heartbeat_ts=old)
                    ctx = self.msg(f"{variant}: прежний {old_task}/{old_sid}, "
                                   f"новый {holder}")

                    merge_lock.touch_heartbeat(self.conn, old_task, old_sid)

                    self.assertEqual(self.lock_by_task(),
                                     {new_task: holder}, ctx)

    def test_ac17_touch_heartbeat_without_args_keeps_old_behaviour(self):
        """Одна строка мьютекса с heartbeat десять минут назад:
        `touch_heartbeat(conn)` делает его свежим, прочие поля прежние; без
        строки вызов ничего не меняет и не падает.

        Ловит мутацию: прежняя форма вызова без `task_id`/`session_id`
        превращена в ничего не делающую (сверка «своей» строки по `None`)
        — heartbeat останется старым, `assert_fresh` покраснеет; либо
        пустая таблица роняет вызов исключением."""
        for target in (self.artel, self.ext):
            with self.subTest(project=target):
                self.clear()
                before = self.seed_lock(self.new_task(target), self.session(),
                                        self.foreign_pid(),
                                        heartbeat_ts=_ts_ago(600))
                ctx = self.msg(f"держит {before}")

                merge_lock.touch_heartbeat(self.conn)

                rows = self.lock_by_task()
                self.assertEqual(sorted(rows), [before["task_id"]], ctx)
                after = rows[before["task_id"]]
                self.assert_fresh(after["heartbeat_ts"], ctx)
                self.assertEqual({k: v for k, v in after.items()
                                  if k != "heartbeat_ts"},
                                 {k: v for k, v in before.items()
                                  if k != "heartbeat_ts"}, ctx)
        self.clear()

        merge_lock.touch_heartbeat(self.conn)

        self.assertEqual(self.lock_by_task(), {}, self.msg("пустая таблица"))


class StoreMergeLockTest(_ProjectMutexBase):

    def test_ac11_set_merge_lock_keeps_other_project_row(self):
        """Строки держателей двух проектов; прежние `set_merge_lock`,
        `merge_lock_row`, `release_merge_lock` с прежними сигнатурами:
        запись строки проекта P не трогает строку Q, снятие — тоже.

        Ловит мутацию: `set_merge_lock` оставлен с `DELETE` без `WHERE` —
        строка Q пропадёт; либо `release_merge_lock` снимает строки по
        проекту/всю таблицу — строка Q пропадёт после снятия P."""
        for p_target, q_target in self.project_pairs():
            with self.subTest(p=p_target, q=q_target):
                self.clear()
                q_row = self.live_holder(q_target)
                p_task, sid = self.new_task(p_target), self.session()
                pid, ts = self.foreign_pid(), store.now()
                ctx = self.msg(f"Q {q_row}, P {p_task}")

                store.set_merge_lock(self.conn, p_task, sid, pid, OTHER_HOST,
                                     ts)

                rows = self.lock_by_task()
                self.assertEqual(rows.get(q_row["task_id"]), q_row, ctx)
                self.assertEqual(rows.get(p_task),
                                 {"task_id": p_task, "session_id": sid,
                                  "pid": pid, "hostname": OTHER_HOST,
                                  "heartbeat_ts": ts}, ctx)
                self.assertIsNotNone(store.merge_lock_row(self.conn), ctx)

                store.release_merge_lock(self.conn, sid, pid)

                self.assertEqual(self.lock_by_task(),
                                 {q_row["task_id"]: q_row}, ctx)


class QueueByProjectTest(_ProjectMutexBase):

    def test_ac2_other_project_holder_does_not_delay_wait_for_window(self):
        """Живой держатель проекта Q, у проекта P нет ни держателя, ни
        записей очереди; `wait_for_window` задачи P возвращается без
        единой паузы, мьютекс P взят этим процессом.

        Ловит мутацию: `wait_for_window`/`acquire` ждёт освобождения
        мьютекса всего пульта — опрос пойдёт до потолка, выход
        `SystemExit` и непустой список пауз."""
        for holder_target, caller_target in self.project_pairs():
            with self.subTest(holder=holder_target, caller=caller_target):
                self.clear()
                holder = self.live_holder(holder_target)
                caller, sid = self.new_task(caller_target), self.session()
                ctx = self.msg(f"держит {holder}, ждёт {caller}")

                sleeps, exited = self.run_wait(caller, sid)

                self.assertIsNone(exited, ctx)
                self.assertEqual(sleeps, [], ctx)
                row = self.lock_by_task().get(caller)
                self.assertIsNotNone(row, ctx)
                self.assertEqual((row["session_id"], row["pid"]),
                                 (sid, os.getpid()), ctx)

    def test_ac8_head_is_earliest_entry_of_own_project(self):
        """Раньше задачи P в очереди стоит живая запись проекта Q, мьютекс
        свободен; `wait_for_window` задачи P — голова очереди своего
        проекта — берёт окно без паузы, запись Q остаётся в очереди.

        Ловит мутацию: голова очереди — первая запись всего пульта
        (прежний `_head_task_id`) — P не станет головой, опрос дойдёт до
        потолка, `assertIsNone(exited)` покраснеет."""
        for q_target, p_target in self.project_pairs():
            with self.subTest(queue_first=q_target, caller=p_target):
                self.clear()
                q_task = self.new_task(q_target)
                self.enqueue(q_task, _ts_ago(120))
                caller, sid = self.new_task(p_target), self.session()
                ctx = self.msg(f"в очереди раньше {q_task}, ждёт {caller}")

                sleeps, exited = self.run_wait(caller, sid)

                self.assertIsNone(exited, ctx)
                self.assertEqual(sleeps, [], ctx)
                self.assertIn(caller, self.lock_by_task(), ctx)
                self.assertEqual(self.queue_task_ids(), [q_task], ctx)

    def test_ac8_same_project_tasks_enter_in_fifo_order(self):
        """В очереди: запись проекта Q, затем запись задачи P1; задача P2
        того же проекта P ждёт окна. Пока P1 в очереди, P2 окна не берёт
        (мьютекс свободен); P1 уходит из очереди на первой паузе — P2
        берёт окно на следующем опросе.

        Ловит мутацию: FIFO внутри проекта снят (голова — любая запись
        своего проекта либо своя) — P2 возьмёт окно без паузы, раньше P1;
        либо голова считается по всей очереди — после ухода P1 голова
        останется запись Q, и P2 дождётся потолка."""
        for q_target, p_target in self.project_pairs():
            with self.subTest(other=q_target, project=p_target):
                self.clear()
                q_task = self.new_task(q_target)
                self.enqueue(q_task, _ts_ago(300))
                p1 = self.new_task(p_target)
                p1_sid, p1_pid = self.enqueue(p1, _ts_ago(120))
                p2, p2_sid = self.new_task(p_target), self.session()
                seen = {}

                def on_sleep(n):
                    if n == 1:
                        seen["p2_locked_before_p1_left"] = (
                            p2 in self.lock_by_task())
                        store.dequeue_merge_wait(self.conn, p1_sid, p1_pid)

                ctx = self.msg(f"Q {q_task}, P1 {p1}, P2 {p2}")

                sleeps, exited = self.run_wait(p2, p2_sid, on_sleep)

                self.assertGreaterEqual(len(sleeps), 1,
                                        f"P2 вошёл без паузы раньше P1; {ctx}")
                self.assertFalse(seen.get("p2_locked_before_p1_left"), ctx)
                self.assertIsNone(exited, ctx)
                self.assertIn(p2, self.lock_by_task(), ctx)

    def test_ac9_dead_entry_of_project_does_not_hold_its_head(self):
        """Очередь: живая запись проекта Q, затем мёртвая запись задачи P0
        (протухший heartbeat либо неживой pid на этом host); задача P1 того
        же проекта ждёт окна. Мёртвая запись убрана, P1 берёт окно без
        паузы, запись Q на месте.

        Ловит мутацию: пруна мёртвых записей не идёт до определения головы
        проекта (или убирает только записи другого проекта) — P0 останется
        головой P, P1 дождётся потолка; либо голова по всей очереди —
        голова — запись Q."""
        stale = _ts_ago(config.LEASE_STALE_AFTER_SEC + 60)
        for q_target, p_target in self.project_pairs():
            for kind in ("протухший heartbeat", "неживой pid"):
                with self.subTest(other=q_target, project=p_target, dead=kind):
                    self.clear()
                    q_task = self.new_task(q_target)
                    self.enqueue(q_task, _ts_ago(600))
                    p0 = self.new_task(p_target)
                    if kind == "протухший heartbeat":
                        self.enqueue(p0, stale)
                    else:
                        self.enqueue(p0, _ts_ago(300), pid=_dead_pid(),
                                     hostname=socket.gethostname())
                    p1, sid = self.new_task(p_target), self.session()
                    ctx = self.msg(f"Q {q_task}, мёртвая P0 {p0}, P1 {p1}")

                    sleeps, exited = self.run_wait(p1, sid)

                    self.assertIsNone(exited, ctx)
                    self.assertEqual(sleeps, [], ctx)
                    self.assertIn(p1, self.lock_by_task(), ctx)
                    self.assertEqual(self.queue_task_ids(), [q_task], ctx)


class WaitTextsByProjectTest(_ProjectMutexBase):

    def wait_texts(self, caller: str, sid: str) -> tuple:
        """(отказ `acquire`, действия журнала после `wait_for_window` до
        потолка, добавка `status` записи очереди трёхминутной давности)."""
        refusal = merge_lock.acquire(self.conn, caller, sid)
        _sleeps, exited = self.run_wait(caller, sid)
        self.assertIsNotNone(exited, self.msg(f"{caller} получил окно"))
        actions = [a for a in self.actions(caller)
                   if a.startswith("ждёт merge-окна")]
        q_sid, q_pid = self.enqueue(caller, _ts_ago(210))
        suffix = merge_queue.wait_suffix(self.conn,
                                         store.get_task(self.conn, caller))
        store.dequeue_merge_wait(self.conn, q_sid, q_pid)
        return refusal, actions, suffix

    def test_ac10_wait_texts_name_holder_of_waiting_task_project(self):
        """Держат проекты P и Q (обе строки живые, оба порядка вставки);
        отказ `acquire`, запись журнала входа в очередь и добавка `status`
        задачи P называют держателя P, не держателя Q.

        Ловит мутацию: тексты собираются по «первой» строке таблицы
        (прежние `merge_lock_row`/`_current_holder_label`) — при строке Q
        первой в таблице текст назовёт задачу и pid держателя Q."""
        for p_target, q_target in self.project_pairs():
            for p_first in (True, False):
                with self.subTest(p=p_target, q=q_target, p_first=p_first):
                    self.clear()
                    tasks = {p_target: self.new_task(p_target),
                             q_target: self.new_task(q_target)}
                    order = ((p_target, q_target) if p_first
                             else (q_target, p_target))
                    rows = {t: self.seed_lock(tasks[t], self.session(),
                                              self.foreign_pid())
                            for t in order}
                    hp, hq = rows[p_target], rows[q_target]
                    caller = self.new_task(p_target)
                    ctx = self.msg(f"P {hp}, Q {hq}, ждёт {caller}")

                    refusal, actions, suffix = self.wait_texts(
                        caller, self.session())

                    self.assertIsNotNone(refusal, ctx)
                    self.assertRegex(refusal, refusal_pattern(caller, hp), ctx)
                    self.assertEqual(
                        actions,
                        [f"ждёт merge-окна: держит {hp['task_id']} "
                         f"(pid {hp['pid']})"], ctx)
                    self.assertEqual(
                        suffix,
                        f"  [ждёт merge-окна: занято {hp['task_id']} "
                        f"(pid {hp['pid']}), 3 мин]", ctx)
                    for text in (refusal, suffix, *actions):
                        self.assertNotIn(hq["task_id"], text, ctx)

    def test_ac10_single_project_texts_are_unchanged(self):
        """Один проект (артель), живой держатель: три текста ожидания
        совпадают с прежними побайтно (секунды heartbeat — любое целое).

        Ловит мутацию: тексты получили метку проекта или иной формат
        (например «держит <id> (pid <pid>, проект artel)») — точные сверки
        покраснеют."""
        holder = self.live_holder(self.artel)
        caller = self.new_task(self.artel)
        ctx = self.msg(f"держит {holder}, ждёт {caller}")

        refusal, actions, suffix = self.wait_texts(caller, self.session())

        self.assertIsNotNone(refusal, ctx)
        self.assertRegex(refusal, refusal_pattern(caller, holder), ctx)
        self.assertEqual(actions,
                         [f"ждёт merge-окна: держит {holder['task_id']} "
                          f"(pid {holder['pid']})"], ctx)
        self.assertEqual(suffix,
                         f"  [ждёт merge-окна: занято {holder['task_id']} "
                         f"(pid {holder['pid']}), 3 мин]", ctx)


if __name__ == "__main__":
    unittest.main()
