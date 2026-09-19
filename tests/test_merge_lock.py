"""Юнит-тесты orchestrator/merge_lock.py (SPEC T053).

Приёмочные тесты (tasks/T053/acceptance_tests) кроют AC-1..AC-6 сквозным
путём через `fsm.cmd_approve`/`cmd_reject`/`cleanup.cmd_kill`; здесь — сам
модуль `merge_lock.py` в изоляции: границы `acquire`/`release` (что именно
меняется в строке БД на каждой ветке), тем же приёмом, что
`tests/test_lease.py` уже применила к `lease.py`.
"""
import os
import socket
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, liveness, merge_lock, store  # noqa: E402
from tests.sandbox import (TmpRootTest, _alive_foreign_pid, _dead_pid,  # noqa: E402
                           _ts_ago, capture)


class AcquireReleaseTest(TmpRootTest):
    TASK = "T001"
    HOLDER_TASK = "T999"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача",
                          "merge_gate", "task/t001-zadacha",
                          config.DEFAULT_TARGET, 25.0)
        store.insert_task(store.db(), self.HOLDER_TASK, "Держит окно",
                          "merge_gate", "task/t999-holder",
                          config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.merge_lock_row(store.db())

    def seed(self, session_id, pid, hostname, heartbeat_ts, task_id) -> None:
        store.set_merge_lock(store.db(), task_id, session_id, pid, hostname,
                             heartbeat_ts)

    def test_fresh_acquire_on_empty_table_takes_the_lock(self):
        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        row = self.row()
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["task_id"], self.TASK)
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(row["hostname"], socket.gethostname())

    def test_own_session_re_enters_without_refusal(self):
        merge_lock.acquire(store.db(), self.TASK, "sess-a")

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertEqual(self.row()["session_id"], "sess-a")

    def test_foreign_fresh_lock_refuses_and_names_holder_and_task(self):
        self.seed("sess-holder", 999, "holder-host", store.now(),
                  self.HOLDER_TASK)
        before = dict(self.row())

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNotNone(refusal)
        self.assertIn("sess-holder", refusal)
        self.assertIn(self.HOLDER_TASK, refusal)
        self.assertEqual(dict(self.row()), before,
                         "отказанное взятие не имеет права тронуть чужой "
                         "мьютекс")

    def test_foreign_stale_heartbeat_lock_is_taken_over_and_journalled(self):
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        self.seed("sess-holder", 999, "holder-host", stale_ts,
                  self.HOLDER_TASK)
        before = len(store.task_steps(store.db(), self.TASK))

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNone(refusal)
        row = self.row()
        self.assertEqual(row["session_id"], "sess-caller")
        self.assertEqual(row["task_id"], self.TASK)
        new_steps = store.task_steps(store.db(), self.TASK)[before:]
        self.assertTrue(any("мьютекс" in s["action"] for s in new_steps),
                        new_steps)

    def test_foreign_dead_pid_on_local_host_is_taken_over_despite_fresh_heartbeat(self):
        self.seed("sess-holder", _dead_pid(), socket.gethostname(),
                  store.now(), self.HOLDER_TASK)

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNone(
            refusal, "мёртвый pid держателя обязан перешагиваться даже при "
                    "свежем heartbeat (требование 4)")
        self.assertEqual(self.row()["session_id"], "sess-caller")

    def test_foreign_dead_pid_on_a_different_host_is_not_taken_over(self):
        """Чужой host — pid чужой процессной таблицы нельзя ни
        подтвердить, ни опровергнуть; решает только heartbeat (тот же
        приём, что `doctor.check_leases`/`check_merge_lock`)."""
        self.seed("sess-holder", 999999, "other-host", store.now(),
                  self.HOLDER_TASK)

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNotNone(refusal)

    def test_release_removes_only_the_matching_session(self):
        merge_lock.acquire(store.db(), self.TASK, "sess-a")

        merge_lock.release(store.db(), "sess-b")
        self.assertIsNotNone(self.row(), "release чужой сессией снял мьютекс")

        merge_lock.release(store.db(), "sess-a")
        self.assertIsNone(self.row())


class ProcessOwnershipTest(TmpRootTest):
    """SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требования 1-4: держатель мьютекса
    — процесс (session_id И pid), не сессия. Второй живой процесс той же
    рабочей копии пульта (тот же session_id, другой pid) — чужой
    держатель: тот же отказ, что чужой сессии; мёртвый — прежний перехват;
    `release` снимает только строку своего процесса."""

    TASK = "T001"
    HOLDER_TASK = "T999"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        for tid, branch in ((self.TASK, "task/t001-zadacha"),
                            (self.HOLDER_TASK, "task/t999-holder")):
            store.insert_task(store.db(), tid, tid, "merge_gate", branch,
                              config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.merge_lock_row(store.db())

    def seed(self, session_id, pid, hostname=None, heartbeat_ts=None):
        store.set_merge_lock(store.db(), self.HOLDER_TASK, session_id, pid,
                             hostname or socket.gethostname(),
                             heartbeat_ts or store.now())

    def test_live_other_process_of_same_session_is_refused_with_holder_pid(self):
        """Мьютекс держит живой процесс той же сессии с другим pid —
        `acquire` отказывает, называет pid держателя, строку не трогает.

        Ловит мутацию: условие «свой» оставлено по одному session_id —
        вызов вернёт `None`, строка окажется переписана на `os.getpid()`,
        и `assertIsNotNone`/сверка строки «до/после» покраснеют.
        """
        holder_pid = _alive_foreign_pid(self)
        self.seed("sess-a", holder_pid)
        before = dict(self.row())

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNotNone(refusal)
        self.assertIn(str(holder_pid), refusal)
        self.assertIn(self.HOLDER_TASK, refusal)
        self.assertEqual(dict(self.row()), before)

    def test_refusal_text_for_own_session_equals_foreign_session_text(self):
        """Один живой держатель отказывает своей и чужой сессии одним и тем
        же текстом — разница только в самом session_id.

        Ловит мутацию: для процесса своей сессии заведена отдельная ветка
        с другим текстом отказа — нормализованные строки разойдутся.
        """
        holder_pid = _alive_foreign_pid(self)
        with mock.patch.object(liveness, "_age_seconds", lambda ts: 5.0):
            self.seed("sess-holder", holder_pid)
            foreign = merge_lock.acquire(store.db(), self.TASK, "sess-caller")
            self.seed("sess-caller", holder_pid)
            own = merge_lock.acquire(store.db(), self.TASK, "sess-caller")

        self.assertIsNotNone(foreign)
        self.assertIsNotNone(own)
        self.assertEqual(own.replace("sess-caller", "SID"),
                         foreign.replace("sess-holder", "SID"))

    def test_own_process_re_enters_and_refreshes_the_row(self):
        """Строка этого процесса (session_id И `os.getpid()`) с протухшим
        на две минуты heartbeat — повторный `acquire` даёт `None`, ставит
        текущую задачу и свежий heartbeat.

        Ловит мутацию: условие «свой» требует ещё и совпадения task_id
        (либо ветка «свой» не пишет строку) — `acquire` откажет своему же
        процессу или оставит старый heartbeat, обе сверки покраснеют.
        """
        self.seed("sess-a", os.getpid(), heartbeat_ts=_ts_ago(120))

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        row = self.row()
        self.assertEqual(row["task_id"], self.TASK)
        self.assertEqual(row["pid"], os.getpid())
        self.assertLess(liveness._age_seconds(row["heartbeat_ts"]), 60)

    def test_dead_process_of_own_session_is_intercepted_and_journalled(self):
        """Держатель той же сессии, но с неживым pid на этом host —
        перехват прежней записью «мьютекс merge перехвачен», не отказ.

        Ловит мутацию: отказ «другой pid той же сессии» поставлен ПЕРЕД
        проверкой живости — мёртвый держатель своей сессии перестанет
        перехватываться, `assertIsNone` покраснеет; либо перехват своей
        сессии идёт молча без записи — сверка журнала покраснеет.
        """
        self.seed("sess-a", _dead_pid())

        refusal = merge_lock.acquire(store.db(), self.TASK, "sess-a")

        self.assertIsNone(refusal)
        self.assertEqual(self.row()["pid"], os.getpid())
        actions = [s["action"] for s in store.task_steps(store.db(), self.TASK)]
        self.assertIn("мьютекс merge перехвачен", actions, actions)

    def test_release_from_non_holder_process_keeps_the_mutex(self):
        """`release` с тем же session_id из процесса, который окна не
        держит (строка за живым другим pid), мьютекс НЕ снимает.

        Ловит мутацию: `store.release_merge_lock` удаляет по одному
        `session_id` (pid не в `WHERE`) — строка живого держателя исчезнет,
        `assertIsNotNone` покраснеет.
        """
        holder_pid = _alive_foreign_pid(self)
        self.seed("sess-a", holder_pid)

        merge_lock.release(store.db(), "sess-a")

        row = self.row()
        self.assertIsNotNone(row)
        self.assertEqual(row["pid"], holder_pid)

    def test_release_from_holder_process_removes_the_mutex(self):
        """`release` из процесса-держателя (мьютекс взят через `acquire`
        этим же процессом) снимает строку.

        Ловит мутацию: pid в `release` берётся не из вызывающего процесса
        (либо сверка pid написана наоборот) — свой мьютекс перестанет
        сниматься, `assertIsNone` покраснеет.
        """
        merge_lock.acquire(store.db(), self.TASK, "sess-a")

        merge_lock.release(store.db(), "sess-a")

        self.assertIsNone(self.row())

    def test_store_release_merge_lock_requires_both_session_and_pid(self):
        """`store.release_merge_lock(conn, session_id, pid)` — опорная
        функция снимает строку только при совпадении ОБОИХ ключей.

        Ловит мутацию: в `WHERE` остался один из ключей — вызов с чужим
        pid (или чужой сессией) снимет строку, и первые две сверки
        покраснеют.
        """
        conn = store.db()
        self.seed("sess-a", 4242)

        store.release_merge_lock(conn, "sess-a", 4243)
        self.assertIsNotNone(self.row(), "pid не совпал — строка остаётся")
        store.release_merge_lock(conn, "sess-b", 4242)
        self.assertIsNotNone(self.row(), "сессия не совпала — строка остаётся")
        store.release_merge_lock(conn, "sess-a", 4242)
        self.assertIsNone(self.row())


class RunWindowTest(TmpRootTest):
    """SPEC T057, требование 2 rev. AC-3: общая точка окна merge-мьютекса —
    `acquire` -> отказ (`sys.exit`) -> `body()` -> `release` безусловно."""

    TASK = "T001"
    HOLDER_TASK = "T999"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        store.insert_task(store.db(), self.HOLDER_TASK, "Держит окно",
                          "merge_gate", "task/t999-holder",
                          config.DEFAULT_TARGET, 25.0)

    def row(self):
        return store.merge_lock_row(store.db())

    def test_success_runs_body_and_releases_the_mutex_afterwards(self):
        conn = store.db()
        seen = []

        result = merge_lock.run_window(conn, self.TASK, "sess-a",
                                       lambda: seen.append("done") or "ok")

        self.assertEqual(result, "ok")
        self.assertEqual(seen, ["done"])
        self.assertIsNone(self.row(), "мьютекс обязан быть отпущен после "
                                      "тела окна")

    def test_refusal_exits_without_running_the_body(self):
        conn = store.db()
        store.set_merge_lock(conn, self.HOLDER_TASK, "sess-holder", 999,
                             "holder-host", store.now())
        called = []

        with self.assertRaises(SystemExit) as ctx:
            merge_lock.run_window(conn, self.TASK, "sess-caller",
                                  lambda: called.append("ran"))

        self.assertIn("sess-holder", str(ctx.exception))
        self.assertEqual(called, [])
        self.assertEqual(self.row()["session_id"], "sess-holder",
                         "отказанное взятие не имеет права тронуть чужой "
                         "мьютекс")

    def test_mutex_is_released_even_when_the_body_raises(self):
        conn = store.db()

        with self.assertRaises(ValueError):
            merge_lock.run_window(
                conn, self.TASK, "sess-a",
                lambda: (_ for _ in ()).throw(ValueError))

        self.assertIsNone(self.row(), "тело упало — мьютекс всё равно "
                                      "обязан быть отпущен")


class ConcurrentAcquireTest(TmpRootTest):
    """Read-then-write в `acquire()` (`merge_lock_row` -> `set_merge_lock`)
    обязан быть атомарным под конкурентным доступом (SPEC T053, требование
    1 — `BEGIN IMMEDIATE` по образцу `lease.acquire`, ревью T044 итерация
    1 замечание 1). Каждый поток открывает своё собственное подключение
    (`store.db()`), как и делают отдельные процессы CLI, — общий только
    файл БД."""

    TASK = "T001"
    THREADS = 8

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        # Догоняет migrate()/seed_task_counters ПОСЛЕ вставки T001, пока
        # тест ещё однопоточный — тот же приём, что
        # `tests/test_lease.py::ConcurrentAcquireTest.setUp`.
        store.db()

    def test_concurrent_acquire_on_free_lock_exactly_one_wins(self):
        barrier = threading.Barrier(self.THREADS)
        results = [None] * self.THREADS
        errors = []

        def worker(i):
            try:
                conn = store.db()
                barrier.wait(timeout=5)
                results[i] = merge_lock.acquire(conn, self.TASK, f"sess-{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,))
                  for i in range(self.THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [], "acquire() не должна падать под гонкой")
        wins = [r for r in results if r is None]
        self.assertEqual(len(wins), 1, results)
        row = store.merge_lock_row(store.db())
        self.assertTrue(row["session_id"].startswith("sess-"))


if __name__ == "__main__":
    unittest.main()
