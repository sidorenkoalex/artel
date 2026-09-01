"""Юнит-тесты цикла ожидания CI на гейте `merge_gate` (SPEC T087, решение
Оператора 31.08, аудит v6 Q-5).

Приёмочные тесты (`tasks/T087/acceptance_tests/`) кроют AC-1..AC-11
сквозным путём через `fsm.cmd_approve` в НАСТОЯЩЕМ git (push/подтяжка
нужно наблюдать честно, см. докстринг `_sandbox.py` этой задачи); здесь —
сами новые узлы `orchestrator/fsm.py` в изоляции, тем же приёмом, что
`tests/test_merge_lock.py`/`tests/test_ci_status_kind_gate.py` уже
применили к соседним модулям того же гейта: `time.sleep`/`time.monotonic`
заглушены `FakeClock` (не настоящее ожидание), `ci.branch_status`/
`ci.trigger_rerun` — прямыми моками (не сетевой `gh`).
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, ci, config, fsm, merge_lock, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

RUNNING = (False, "CI коммита abc12345 ещё идёт: python")
UNKNOWN = (False, "статус CI коммита abc12345 неизвестен: gh не ответил")
RED = (False, "CI коммита abc12345 не зелёный: python=failure")
GREEN = (True, "CI коммита abc12345 зелёный (1 проверок)")


class FakeClock:
    """Тот же приём, что `tasks/T087/acceptance_tests/_sandbox.py`:
    `sleep(s)` продвигает `monotonic()` на `s` вместо настоящего ожидания."""

    def __init__(self, start: float = 0.0):
        self.value = start
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.value += seconds


class MergeGateCiWaitUnitTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        self.clock = FakeClock()
        sleep_patcher = mock.patch.object(time, "sleep", self.clock.sleep)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        monotonic_patcher = mock.patch.object(time, "monotonic",
                                              self.clock.monotonic)
        monotonic_patcher.start()
        self.addCleanup(monotonic_patcher.stop)

    def journal_blob(self) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
        return "\n".join(f"{r['action']} | {r['detail']}" for r in rows).lower()

    def patch_branch_status(self, fn):
        patcher = mock.patch.object(ci, "branch_status", fn)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_trigger_rerun(self, fn=lambda branch: "ре-ран (тест)"):
        patcher = mock.patch.object(ci, "trigger_rerun", fn)
        patcher.start()
        self.addCleanup(patcher.stop)

    def wait(self, ceiling_sec: float = config.MERGE_GATE_CI_WAIT_CEILING_SEC):
        conn = store.db()
        start = time.monotonic()
        deadline = start + ceiling_sec
        return fsm._wait_for_branch_ci_green(conn, self.TASK, "task/t001-zadacha",
                                             start, deadline)


class WaitLoopContinuesOnNonFinalStatusTest(MergeGateCiWaitUnitTest):
    """AC-3: «ещё идёт»/«неизвестен» паузят и продолжают цикл, не
    останавливая его; пауза — порядка `MERGE_GATE_CI_WAIT_POLL_SEC`."""

    def test_running_then_unknown_then_green_returns_green_note(self):
        responses = [RUNNING, UNKNOWN, GREEN]
        calls = {"n": 0}

        def sequenced(branch):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        self.patch_branch_status(sequenced)

        note = self.wait()

        self.assertEqual(note, GREEN[1])
        self.assertEqual(calls["n"], 3)
        self.assertEqual(self.clock.sleep_calls,
                         [config.MERGE_GATE_CI_WAIT_POLL_SEC] * 2)

    def test_each_iteration_journals_status_and_elapsed_time(self):
        responses = [RUNNING, GREEN]
        calls = {"n": 0}

        def sequenced(branch):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        self.patch_branch_status(sequenced)

        self.wait()

        journal = self.journal_blob()
        self.assertIn(RUNNING[1].lower(), journal)
        self.assertIn(GREEN[1].lower(), journal)
        self.assertIn("сек", journal)


class WaitLoopCeilingTest(MergeGateCiWaitUnitTest):
    """AC-4/AC-8: истечение потолка (не сброшенного паузами) отказывает
    «статус CI неизвестен», не зависая и не мержа."""

    def test_ceiling_expiry_refuses_with_unknown_status_message(self):
        self.patch_branch_status(lambda branch: RUNNING)

        with self.assertRaises(SystemExit) as exit_:
            self.wait(ceiling_sec=200)

        self.assertIn("неизвестен", str(exit_.exception).lower())
        self.assertGreaterEqual(self.clock.value, 200)


class WaitLoopRedStatusTest(MergeGateCiWaitUnitTest):
    """AC-7: подтверждённо красный статус (после ре-рана T082) отказывает
    именованно; флейк (ре-ран зелёный) — цикл возвращает зелёный note."""

    def test_confirmed_red_after_rerun_exits_named_refusal(self):
        self.patch_branch_status(lambda branch: RED)
        self.patch_trigger_rerun()

        with self.assertRaises(SystemExit) as exit_:
            self.wait()

        self.assertIn("отклонён", str(exit_.exception))
        self.assertIn("flake-rate", self.journal_blob())
        self.assertIn("подтверждённый красный", self.journal_blob())

    def test_flake_red_then_rerun_green_returns_green_note(self):
        responses = [RED, GREEN]
        calls = {"n": 0}

        def sequenced(branch):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        self.patch_branch_status(sequenced)
        self.patch_trigger_rerun()

        note = self.wait()

        self.assertEqual(note, GREEN[1])
        self.assertIn("флейк", self.journal_blob())


class OuterCycleDeadlineTest(MergeGateCiWaitUnitTest):
    """`_cmd_approve_merge_gate_cycle`: мьютекс берётся/отпускается вокруг
    каждого захода в тело гейта, и потолок ожидания не пересчитывается на
    повторном исходе `("wait", ...)` (AC-4, тело гейта здесь замокано —
    сама подтяжка/push кроются приёмочными тестами на настоящем git)."""

    def test_mutex_acquired_and_released_around_each_body_call(self):
        acquire_calls = []
        release_calls = []
        bodies = [("wait", "task/t001-zadacha"), ("done",)]
        mutex_held = {"value": False}

        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            self.assertTrue(
                mutex_held["value"],
                "тело гейта обязано звать под уже взятым мьютексом")
            return bodies.pop(0)

        def fake_acquire(conn, task_id, sid):
            mutex_held["value"] = True
            acquire_calls.append(sid)
            return None

        def fake_release(conn, sid):
            mutex_held["value"] = False
            release_calls.append(sid)

        self.patch_branch_status(lambda branch: GREEN)

        with mock.patch.object(merge_lock, "acquire", fake_acquire), \
             mock.patch.object(merge_lock, "release", fake_release), \
             mock.patch.object(fsm, "_cmd_approve_merge_gate", fake_body):
            fsm._cmd_approve_merge_gate_cycle(
                store.db(), self.TASK, "sess-1", {"branch": "task/t001-zadacha"},
                "merge_gate")

        self.assertEqual(acquire_calls, ["sess-1", "sess-1"])
        self.assertEqual(release_calls, ["sess-1", "sess-1"])

    def test_ceiling_not_reset_by_a_second_wait_outcome(self):
        outcomes = [("wait", "task/t001-zadacha"),
                    ("wait", "task/t001-zadacha"),
                    ("done",)]

        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            return outcomes.pop(0)

        starts = []

        def spying_wait(conn, task_id, branch, start, deadline):
            starts.append(start)
            self.clock.value += 1
            return GREEN[1]

        with mock.patch.object(merge_lock, "acquire", lambda *a: None), \
             mock.patch.object(merge_lock, "release", lambda *a: None), \
             mock.patch.object(fsm, "_cmd_approve_merge_gate", fake_body), \
             mock.patch.object(fsm, "_wait_for_branch_ci_green", spying_wait):
            fsm._cmd_approve_merge_gate_cycle(
                store.db(), self.TASK, "sess-1", {"branch": "task/t001-zadacha"},
                "merge_gate")

        self.assertEqual(len(starts), 2)
        self.assertEqual(
            starts[0], starts[1],
            "AC-4: потолок обязан отсчитываться от ПЕРВОГО пуша — второй "
            "заход в ожидание не имеет права пересчитать `start`")


if __name__ == "__main__":
    unittest.main()
