"""Приёмочные тесты SPEC 01M291EJMA995AZ61MEMDZKWRY (AC-1, AC-2, AC-3,
AC-4, AC-7): мьютекс merge-окна (`orchestrator/merge_lock.py`)
резервируется на ВЕСЬ цикл `_cmd_approve_merge_gate_cycle`, а не вокруг
каждого отдельного захода в тело гейта, как сегодня — включая время
ожидания CI внутри `_wait_for_branch_ci_green`. AC-5 (безусловное
освобождение мьютекса на выходе из цикла) — отдельным файлом
`test_merge_window_mutex_release_on_exit.py`: те сценарии уже проходят
на сегодняшнем коде (тело вызывается там ровно один раз), в отличие от
тестов ниже.

Красен до реализации: сегодня `_cmd_approve_merge_gate_cycle`
(orchestrator/fsm_merge_gate.py:696-704) берёт и безусловно отпускает
мьютекс ВОКРУГ КАЖДОГО отдельного захода в тело (`merge_lock.acquire`/
`merge_lock.release` внутри `while True`, до и сразу после вызова
`_cmd_approve_merge_gate`), и `_wait_for_branch_ci_green`
(orchestrator/fsm_merge_gate.py:238-277) не трогает `merge_locks`
вовсе — мьютекс всегда свободен во время ожидания CI. Каждый тест ниже
наблюдает состояние строки `merge_locks` (напрямую или через попытку
`merge_lock.acquire` другой сессией) РОВНО в момент, когда цикл ушёл в
ожидание CI, — до переноса `acquire`/`release` за пределы цикла и
heartbeat-продления внутри `_wait_for_branch_ci_green` эти наблюдения
проваливаются.

Тело гейта (`_cmd_approve_merge_gate`) и цикл ожидания CI
(`_wait_for_branch_ci_green`, где это не предмет самого теста) —
замоканы: сама подтяжка/push/плотницкий merge не входят в эту SPEC
(«Не входит», требование 7 — порядок состояний и содержимое тела гейта
не меняются) и уже покрыты `tasks/T087/acceptance_tests` /
`tests/test_merge_gate_ci_wait.py` на настоящем git.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import (catalog, ci, config, fsm_merge_gate,  # noqa: E402
                          merge_lock, store)
from tests.sandbox import TmpRootTest, _ts_ago, capture  # noqa: E402

RUNNING = (False, "CI коммита abc12345 ещё идёт: python")
GREEN = (True, "CI коммита abc12345 зелёный (1 проверок)")


class FakeClock:
    """`sleep(s)` продвигает `monotonic()` на `s` вместо настоящего
    ожидания — тот же приём, что `tests/test_merge_gate_ci_wait.py`."""

    def __init__(self, start: float = 0.0):
        self.value = start

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class MergeWindowCycleTest(TmpRootTest):
    TASK = "T001"
    OTHER_TASK = "T002"
    BRANCH = "task/t001-zadacha"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          self.BRANCH, config.DEFAULT_TARGET, 25.0)
        store.insert_task(store.db(), self.OTHER_TASK, "Другая задача",
                          "merge_gate", "task/t002-drugaya",
                          config.DEFAULT_TARGET, 25.0)
        self.clock = FakeClock()
        sleep_patcher = mock.patch.object(time, "sleep", self.clock.sleep)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        mono_patcher = mock.patch.object(time, "monotonic",
                                         self.clock.monotonic)
        mono_patcher.start()
        self.addCleanup(mono_patcher.stop)

    def run_cycle(self, fake_body, fake_wait):
        with mock.patch.object(fsm_merge_gate, "_cmd_approve_merge_gate",
                               fake_body), \
             mock.patch.object(fsm_merge_gate, "_wait_for_branch_ci_green",
                               fake_wait):
            fsm_merge_gate._cmd_approve_merge_gate_cycle(
                store.db(), self.TASK, "sess-1", {"branch": self.BRANCH},
                "merge_gate")


class LockSurvivesWaitTest(MergeWindowCycleTest):
    """AC-1: строка `merge_locks` остаётся у держателя между заходом,
    вернувшим `("wait", ...)`, и следующим заходом в тело."""

    def test_ac1_lock_row_kept_by_same_holder_during_ci_wait(self):
        """Тело гейта на первом заходе возвращает `("wait", ...)`, второй
        заход — `("done",)`; строка `merge_locks` проверяется ИЗНУТРИ
        `_wait_for_branch_ci_green` (замокан спай-функцией) — ровно в
        момент, когда реальный код ждал бы CI между двумя заходами.

        Ловит мутацию: если цикл по-прежнему зовёт `merge_lock.release`
        сразу после КАЖДОГО захода в тело (включая исход `"wait"`),
        строка `merge_locks` окажется удалена ещё до входа в ожидание —
        `observed["row"]` останется `None`.
        """
        outcomes = [("wait", self.BRANCH), ("done",)]

        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            return outcomes.pop(0)

        observed = {}

        def spying_wait(conn, task_id, branch, start, deadline):
            row = store.merge_lock_row(conn)
            observed["row"] = dict(row) if row is not None else None
            return GREEN[1]

        self.run_cycle(fake_body, spying_wait)

        self.assertIsNotNone(
            observed["row"],
            "мьютекс обязан оставаться взятым во время ожидания CI между "
            "заходами в тело гейта (AC-1)")
        self.assertEqual(observed["row"]["session_id"], "sess-1")
        self.assertEqual(observed["row"]["task_id"], self.TASK)


class ConcurrentApproveDuringWaitTest(MergeWindowCycleTest):
    """AC-3: второй `approve` другой задачи, поданный пока первая сессия
    ждёт CI внутри своего цикла, получает именованный отказ и не меняет
    состояние своей задачи."""

    def test_ac3_second_session_is_refused_while_first_waits_for_ci(self):
        """`sess-1` ведёт цикл задачи T001 и уходит в `("wait", ...)`;
        ровно в этот момент `sess-2` пытается `approve` T002 — ожидается
        именованный отказ `merge_lock.acquire`, без изменений состояния
        T002.

        Ловит мутацию: если мьютекс уже свободен на момент ожидания CI
        (сегодняшнее поведение), `merge_lock.acquire` для `sess-2`
        вернёт `None` (взял) вместо отказа — `assertIsNotNone` провалится.

        Сегодняшняя (до фикса) реализация в этом сценарии роняет ВЕСЬ
        цикл `sess-1` своим собственным `sys.exit` (второй заход в тело
        не может заново взять мьютекс — его успел перехватить `sess-2`,
        пока строка была отпущена на время ожидания) — это тоже
        проявление отсутствующей реализации, не опечатка теста, поэтому
        `SystemExit` вокруг вызова цикла подавлен: важны наблюдения,
        сделанные ДО этого краха, не то, чем цикл в итоге завершился.
        """
        outcomes = [("wait", self.BRANCH), ("done",)]

        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            return outcomes.pop(0)

        captured = {}

        def spying_wait(conn, task_id, branch, start, deadline):
            captured["refusal"] = merge_lock.acquire(
                conn, self.OTHER_TASK, "sess-2")
            return GREEN[1]

        state_before = store.get_task(store.db(), self.OTHER_TASK)["state"]

        try:
            self.run_cycle(fake_body, spying_wait)
        except SystemExit:
            pass

        self.assertIsNotNone(
            captured.get("refusal"),
            "approve другой задачи на занятое ожиданием CI окно обязан "
            "получить именованный отказ (AC-3)")
        self.assertIn("sess-1", captured["refusal"])
        self.assertIn(self.TASK, captured["refusal"])
        self.assertEqual(
            store.get_task(store.db(), self.OTHER_TASK)["state"],
            state_before,
            "отказанный approve не имеет права менять состояние своей "
            "задачи")


class DeadHolderDuringWaitTest(MergeWindowCycleTest):
    """AC-4: протухший heartbeat держателя перехватывается новой сессией
    даже когда мьютекс удерживается циклом дольше тела одного захода —
    включая протухание во время ожидания CI."""

    def test_ac4_stale_heartbeat_during_ci_wait_is_taken_over(self):
        """Внутри симулированного ожидания CI держатель `sess-1`
        искусственно "протухает" (heartbeat старше
        `config.LEASE_STALE_AFTER_SEC`, как будто сессия зависла/умерла
        во время долгого ожидания CI) — новая сессия `sess-2` обязана
        перехватить мьютекс тем же путём `merge_lock.acquire`, что и
        межзаходовый перехват сегодня.

        Ловит мутацию: если мьютекс освобождён на время ожидания
        (сегодняшнее поведение), строки `merge_locks` в момент проверки
        просто не будет — `store.merge_lock_row` вернёт `None`, и
        манипуляция стаcким heartbeat-ом (и весь сценарий перехвата
        ИМЕННО во время ожидания) станет невозможной; тест ловит это
        явным `assertIsNotNone(row, ...)` до перехвата.

        Сегодняшняя (до фикса) реализация в этом сценарии роняет ВЕСЬ
        цикл `sess-1` своим собственным `sys.exit` (второй заход в тело
        не может заново взять мьютекс — его перехватил `sess-2`, пока
        строка была отпущена на время ожидания) — проявление
        отсутствующей реализации, не опечатка теста, поэтому `SystemExit`
        вокруг вызова цикла подавлен: важны наблюдения, сделанные ДО
        этого краха.
        """
        outcomes = [("wait", self.BRANCH), ("done",)]

        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            return outcomes.pop(0)

        captured = {}

        def spying_wait(conn, task_id, branch, start, deadline):
            row = store.merge_lock_row(conn)
            captured["row_present_during_wait"] = row is not None
            if row is not None:
                stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
                store.set_merge_lock(conn, row["task_id"], row["session_id"],
                                     row["pid"], row["hostname"], stale_ts)
            captured["refusal"] = merge_lock.acquire(
                conn, self.OTHER_TASK, "sess-2")
            new_row = store.merge_lock_row(conn)
            captured["new_holder"] = (new_row["session_id"]
                                      if new_row is not None else None)
            return GREEN[1]

        try:
            self.run_cycle(fake_body, spying_wait)
        except SystemExit:
            pass

        self.assertTrue(
            captured["row_present_during_wait"],
            "мьютекс обязан оставаться взятым во время ожидания CI, "
            "иначе протухание держателя во время ожидания некому "
            "перехватывать (AC-4)")
        self.assertIsNone(
            captured["refusal"],
            "протухший heartbeat держателя обязан перехватываться новой "
            "сессией даже во время ожидания CI внутри цикла (AC-4)")
        self.assertEqual(captured["new_holder"], "sess-2")


class OneAcquireOneReleasePerCycleTest(MergeWindowCycleTest):
    """AC-7: мьютекс берётся один раз на весь цикл и освобождается один
    раз при выходе — не вокруг каждого отдельного захода в тело, как
    сегодняшний (переписываемый этой задачей) тест
    `tests/test_merge_gate_ci_wait.py::OuterCycleDeadlineTest::
    test_mutex_acquired_and_released_around_each_body_call` утверждал
    для старого поведения."""

    def test_ac7_acquire_and_release_called_exactly_once_across_two_body_calls(self):
        """Два захода в тело (`("wait", ...)`, затем `("done",)`) —
        `merge_lock.acquire`/`merge_lock.release` обязаны быть позваны
        РОВНО по одному разу за весь цикл, не по разу на каждый заход.

        Ловит мутацию: старое поведение (acquire/release вокруг каждого
        захода в тело) даст `acquire_calls == ["sess-1", "sess-1"]` и
        `release_calls == ["sess-1", "sess-1"]` — списки длины 2 вместо 1.
        """
        acquire_calls = []
        release_calls = []
        outcomes = [("wait", self.BRANCH), ("done",)]

        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            return outcomes.pop(0)

        def fake_acquire(conn, task_id, sid):
            acquire_calls.append(sid)
            return None

        def fake_release(conn, sid):
            release_calls.append(sid)

        def fake_wait(conn, task_id, branch, start, deadline):
            return GREEN[1]

        with mock.patch.object(merge_lock, "acquire", fake_acquire), \
             mock.patch.object(merge_lock, "release", fake_release):
            self.run_cycle(fake_body, fake_wait)

        self.assertEqual(acquire_calls, ["sess-1"])
        self.assertEqual(release_calls, ["sess-1"])


class HeartbeatRenewedDuringCiWaitTest(TmpRootTest):
    """AC-2: `merge_locks.heartbeat_ts` держателя обновляется на каждой
    итерации опроса CI внутри `_wait_for_branch_ci_green`, не только на
    входе/выходе из тела гейта."""

    TASK = "T001"
    BRANCH = "task/t001-zadacha"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          self.BRANCH, config.DEFAULT_TARGET, 25.0)
        self.clock = FakeClock()
        sleep_patcher = mock.patch.object(time, "sleep", self.clock.sleep)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        mono_patcher = mock.patch.object(time, "monotonic",
                                         self.clock.monotonic)
        mono_patcher.start()
        self.addCleanup(mono_patcher.stop)

    def test_ac2_heartbeat_touched_on_every_ci_poll_iteration(self):
        """Держатель `sess-1` уже взял мьютекс (как он держал бы его на
        всё время цикла по AC-1); опрос CI внутри
        `_wait_for_branch_ci_green` проходит три итерации (два раза
        "ещё идёт", затем зелёный) — на каждой итерации ожидается запись
        в `merge_locks` (продление heartbeat), не только один раз за
        всё ожидание.

        Проверка — через `sqlite3.Connection.set_trace_callback`: считаем
        SQL-запросы, пишущие в таблицу `merge_locks`, не завязываясь на
        конкретное имя функции продления heartbeat, которое выберет
        реализация.

        Ловит мутацию: если heartbeat продлевается один раз при входе в
        ожидание (или вовсе не продлевается, как сегодня), число
        записей в `merge_locks` за три опроса CI останется меньше трёх.
        """
        conn = store.db()
        merge_lock.acquire(conn, self.TASK, "sess-1")

        responses = [RUNNING, RUNNING, GREEN]
        calls = {"n": 0}

        def sequenced(branch):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        status_patcher = mock.patch.object(ci, "branch_status", sequenced)
        status_patcher.start()
        self.addCleanup(status_patcher.stop)

        touches = []

        def trace(sql) -> None:
            normalized = sql.strip().lower()
            if "merge_locks" in normalized and not normalized.startswith("select"):
                touches.append(sql)

        conn.set_trace_callback(trace)
        try:
            start = time.monotonic()
            deadline = start + config.MERGE_GATE_CI_WAIT_CEILING_SEC
            note = fsm_merge_gate._wait_for_branch_ci_green(
                conn, self.TASK, self.BRANCH, start, deadline)
        finally:
            conn.set_trace_callback(None)

        self.assertEqual(note, GREEN[1])
        self.assertEqual(calls["n"], 3)
        self.assertGreaterEqual(
            len(touches), calls["n"],
            "heartbeat держателя обязан продлеваться на КАЖДОЙ итерации "
            f"опроса CI внутри _wait_for_branch_ci_green: на {calls['n']} "
            f"опросов CI пришлось {len(touches)} записей в merge_locks")


if __name__ == "__main__":
    unittest.main()
