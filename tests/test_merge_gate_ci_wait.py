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
import math
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (catalog, ci, config, fsm, fsm_merge_gate,  # noqa: E402
                          github_adapter, merge_lock, repo_context, store)
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
        return fsm_merge_gate._wait_for_branch_ci_green(
            conn, self.TASK, "task/t001-zadacha", start, deadline)


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
    """`_cmd_approve_merge_gate_cycle`: мьютекс резервируется ОДИН раз на
    весь цикл (SPEC 01M291EJMA995AZ61MEMDZKWRY, требования 1-2, 4, 7;
    AC-1, AC-5, AC-7), остаётся у того же держателя между заходами в
    тело, включая время ожидания CI между ними — не берётся/отпускается
    вокруг КАЖДОГО отдельного захода, как было до этой задачи. Потолок
    ожидания не пересчитывается на повторном исходе `("wait", ...)`
    (AC-4, тело гейта здесь замокано — сама подтяжка/push кроются
    приёмочными тестами на настоящем git)."""

    def test_mutex_acquired_once_and_held_across_both_body_calls(self):
        """Ловит мутацию: если `acquire`/`release` снова вызываются вокруг
        КАЖДОГО отдельного захода в тело гейта (старое поведение до этой
        задачи), `acquire_calls`/`release_calls` станут длиной 2 (по разу
        на каждый из двух `fake_body`) вместо 1 — тест это ловит через
        `assertEqual(..., ["sess-1"])`."""
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
             mock.patch.object(fsm_merge_gate, "_cmd_approve_merge_gate", fake_body):
            fsm_merge_gate._cmd_approve_merge_gate_cycle(
                store.db(), self.TASK, "sess-1", {"branch": "task/t001-zadacha"},
                "merge_gate")

        self.assertEqual(
            acquire_calls, ["sess-1"],
            "мьютекс обязан браться РОВНО один раз на весь цикл, не на "
            "каждый заход в тело (AC-7)")
        self.assertEqual(
            release_calls, ["sess-1"],
            "мьютекс обязан отпускаться РОВНО один раз при выходе из "
            "цикла, не после каждого захода в тело (AC-7)")

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
             mock.patch.object(fsm_merge_gate, "_cmd_approve_merge_gate", fake_body), \
             mock.patch.object(fsm_merge_gate, "_wait_for_branch_ci_green", spying_wait):
            fsm_merge_gate._cmd_approve_merge_gate_cycle(
                store.db(), self.TASK, "sess-1", {"branch": "task/t001-zadacha"},
                "merge_gate")

        self.assertEqual(len(starts), 2)
        self.assertEqual(
            starts[0], starts[1],
            "AC-4: потолок обязан отсчитываться от ПЕРВОГО пуша — второй "
            "заход в ожидание не имеет права пересчитать `start`")


CANNOT_LOCK_REF = (
    "To github.com:example/artel.git\n"
    " ! [remote rejected] deadbeef -> main (cannot lock ref "
    "'refs/heads/main': is at 8772115e but expected cd979106)\n"
    "error: failed to push some refs to 'github.com:example/artel.git'\n")
NON_FAST_FORWARD = (
    " ! [rejected]        deadbeef -> main (non-fast-forward)\n"
    "error: failed to push some refs\n")
FETCH_FIRST = (
    " ! [rejected]        deadbeef -> main (fetch first)\n"
    "error: failed to push some refs\n")
HOOK_DECLINED = (
    " ! [remote rejected] deadbeef -> main (pre-receive hook declined)\n"
    "error: failed to push some refs\n")
NETWORK_FAILURE = (
    "ssh: connect to host github.com port 22: Operation timed out\n"
    "fatal: Could not read from remote repository.\n")


def _push_result(stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args=["git", "push"],
                                       returncode=returncode, stdout="",
                                       stderr=stderr)


class PushMergedMainMovedMainTest(MergeGateCiWaitUnitTest):
    """`_push_merged_main` (SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требования
    8-9): отказ push класса «main сдвинулся» — именованная запись и
    `"moved"` без завершения процесса; иные отказы — прежние «merge
    FAILED» + `SystemExit`."""

    def push_with(self, result):
        ctx = repo_context.RepoContext(path=self.root, remote="origin",
                                       base="main")
        with mock.patch.object(repo_context, "git", lambda ctx, *a: result):
            return fsm_merge_gate._push_merged_main(
                store.db(), self.TASK, "deadbeef", ctx)

    def test_classifier_recognises_the_three_moved_main_markers_only(self):
        """«cannot lock ref», «non-fast-forward», «fetch first» — сдвиг
        main; «pre-receive hook declined» (голое «rejected») и сетевой
        отказ — нет.

        Ловит мутацию: классификатор сведён к одной подстроке (только
        текст инцидента) или расширен до голого «rejected» — одна из пяти
        сверок покраснеет.
        """
        self.assertTrue(fsm_merge_gate._push_rejected_by_moved_main(CANNOT_LOCK_REF))
        self.assertTrue(fsm_merge_gate._push_rejected_by_moved_main(NON_FAST_FORWARD))
        self.assertTrue(fsm_merge_gate._push_rejected_by_moved_main(FETCH_FIRST))
        self.assertFalse(fsm_merge_gate._push_rejected_by_moved_main(HOOK_DECLINED))
        self.assertFalse(fsm_merge_gate._push_rejected_by_moved_main(NETWORK_FAILURE))

    def test_moved_main_returns_moved_and_journals_without_merge_failed(self):
        """Отказ «cannot lock ref» — возврат `"moved"`, запись «main
        сдвинулся во время окна — повтор подтяжки», без «merge FAILED» и
        без `SystemExit`.

        Ловит мутацию: ветка «сдвиг main» не заведена (любой ненулевой код
        push — `sys.exit`) — вызов упадёт `SystemExit`; либо запись
        оставлена прежней «merge FAILED» — `assertNotIn` покраснеет.
        """
        outcome = self.push_with(_push_result(CANNOT_LOCK_REF, 1))

        self.assertEqual(outcome, "moved")
        journal = self.journal_blob()
        self.assertIn("main сдвинулся во время окна — повтор подтяжки", journal)
        self.assertNotIn("merge failed", journal)

    def test_other_push_failure_journals_merge_failed_and_exits(self):
        """Сетевой отказ push — прежняя запись «merge FAILED» и
        `SystemExit`.

        Ловит мутацию: реакция «повтор подтяжки» применена к любому отказу
        push — `SystemExit` не будет, `assertRaises` покраснеет.
        """
        with self.assertRaises(SystemExit):
            self.push_with(_push_result(NETWORK_FAILURE, 128))

        self.assertIn("merge failed", self.journal_blob())
        self.assertNotIn("main сдвинулся", self.journal_blob())

    def test_git_not_answering_still_exits(self):
        """`repo_context.git` вернул `None` (git не ответил) — прежний
        «merge FAILED»/«git не ответил» и `SystemExit`.

        Ловит мутацию: чтение `push.stderr` до проверки на `None` —
        `AttributeError` вместо именованного `SystemExit`.
        """
        with self.assertRaises(SystemExit):
            self.push_with(None)

        self.assertIn("git не ответил", self.journal_blob())

    def test_successful_push_returns_ok(self):
        """Успешный push — `"ok"`, журнал без записей отказа.

        Ловит мутацию: условие успеха инвертировано — вернётся `"moved"`
        или `SystemExit`.
        """
        self.assertEqual(self.push_with(_push_result()), "ok")
        self.assertNotIn("сдвинулся", self.journal_blob())


class MovedMainRetryInCycleTest(MergeGateCiWaitUnitTest):
    """Тело гейта на `"moved"` возвращает `("moved", branch)`, и внешний
    цикл повторяет заход в том же вызове `approve`, не сбрасывая потолок
    ожидания CI (SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требования 8-9), а
    потолок на этом пути РЕАЛЬНО ограничивает повтор и между заходами
    стоит пауза (REVIEW итерации 1, R1-F1: тест с настоящим
    `_wait_for_branch_ci_green`, не с его моком)."""

    BRANCH = "task/t001-zadacha"
    # Запас сверх `CEILING / POLL` (40 при текущих константах): ловит
    # бесконечный повтор, не мешая штатному конечному пути.
    PUSH_CAP = 60

    def patch(self, target, attr, replacement):
        patcher = mock.patch.object(target, attr, replacement)
        patcher.start()
        self.addCleanup(patcher.stop)

    def setUp(self):
        super().setUp()
        self.push_results: list = []
        self.push_always = None
        self.push_calls = 0
        self.sync_calls = 0
        self.sync_outcomes: list = []
        self.ci_waits: list = []
        self.ci_wait_seconds = 100.0
        self.real_ci_wait = fsm_merge_gate._wait_for_branch_ci_green
        self.patch(fsm_merge_gate, "_protected_path_diff_gate",
                   lambda *a, **k: False)
        self.patch(fsm_merge_gate, "_ensure_branch_head_published",
                   lambda *a, **k: "ok")
        self.patch(fsm_merge_gate, "_sync_main_or_wait", self.fake_sync)
        self.patch(fsm_merge_gate, "_ci_ready_or_wait", lambda *a, **k: "ok")
        self.patch(fsm_merge_gate, "_perform_carpentry_merge",
                   lambda *a, **k: ("ok", self.root / "scratch"))
        self.patch(fsm_merge_gate, "_publish_merge_artifacts",
                   lambda *a, **k: "deadbeef")
        self.patch(fsm_merge_gate, "_publish_closing_snapshot_or_wait",
                   lambda *a, **k: "ok")
        self.patch(fsm_merge_gate, "_cleanup_merged_task", lambda *a, **k: None)
        self.patch(fsm_merge_gate, "_wait_for_branch_ci_green",
                   self.fake_ci_wait)
        self.patch(repo_context, "git", self.fake_git)

    def fake_sync(self, conn, task_id, t, state, branch, ctx):
        self.sync_calls += 1
        if self.sync_outcomes:
            return self.sync_outcomes.pop(0)
        return "fresh"

    def fake_ci_wait(self, conn, task_id, branch, start, deadline):
        self.ci_waits.append((start, deadline))
        self.clock.value += self.ci_wait_seconds
        return GREEN[1]

    def fake_git(self, ctx, *args):
        if args and args[0] == "push":
            self.push_calls += 1
            if self.push_always is not None:
                self.assertLessEqual(
                    self.push_calls, self.PUSH_CAP,
                    "push вызван больше раз, чем допускает конечный "
                    "потолок — путь повтора не завершается")
                return self.push_always
            self.assertTrue(self.push_results,
                            "push вызван больше раз, чем предусмотрено")
            return self.push_results.pop(0)
        return _push_result()

    def run_cycle(self):
        conn = store.db()
        fsm_merge_gate._cmd_approve_merge_gate_cycle(
            conn, self.TASK, "sess-1", store.get_task(conn, self.TASK),
            "merge_gate")

    def test_body_returns_moved_on_moved_main(self):
        """Тело гейта при отказе push «main сдвинулся» возвращает
        `("moved", branch)` — отдельный тег для цикла, не `("wait", …)`
        и не `("done",)`, — не переводя задачу в `done`.

        Ловит мутацию: результат `_push_merged_main` не читается (как до
        задачи) — тело дойдёт до `_finalize_done_state` и вернёт
        `("done",)` при неудавшемся push; либо тело возвращает
        `("wait", branch)` — цикл не отличит сдвиг main от исхода подтяжки
        и не поставит на этом пути ни паузы, ни сверки потолка (R1-F1).
        """
        self.push_results = [_push_result(CANNOT_LOCK_REF, 1)]

        outcome = fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), self.TASK, "merge_gate",
            store.get_task(store.db(), self.TASK), GREEN[1])

        self.assertEqual(outcome, ("moved", self.BRANCH))
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "merge_gate")

    def test_moved_path_pauses_a_poll_interval_before_reentry(self):
        """Один отказ «main сдвинулся» — ровно одна пауза
        `MERGE_GATE_CI_WAIT_POLL_SEC` перед новым заходом в тело; потом
        ожидание CI и успешный второй push.

        Ловит мутацию: пауза на пути «moved» убрана (повтор идёт сразу в
        ожидание CI, которое при зелёном статусе не паузит) —
        `sleep_calls` останется пустым.
        """
        self.push_results = [_push_result(CANNOT_LOCK_REF, 1), _push_result()]

        self.run_cycle()

        self.assertEqual(self.clock.sleep_calls,
                         [config.MERGE_GATE_CI_WAIT_POLL_SEC])
        self.assertEqual(self.push_calls, 2)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "done")

    def test_wait_path_does_not_get_the_moved_pause(self):
        """Обычный исход подтяжки `("wait", branch)` паузы перед повторным
        заходом не получает — она только для пути «moved»: после зелёного
        CI тело заходит заново сразу, как и до задачи.

        Ловит мутацию: пауза/сверка потолка навешаны на ЛЮБОЙ повторный
        заход (`outcome[0] in ("wait", "moved")` без различения) — путь
        подтяжки получит лишние 90 секунд, `sleep_calls` станет непустым.
        """
        self.sync_outcomes = [("wait", self.BRANCH)]
        self.push_results = [_push_result()]

        self.run_cycle()

        self.assertEqual(self.clock.sleep_calls, [])
        self.assertEqual(len(self.ci_waits), 1)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "done")

    def test_persistently_moved_main_exits_by_ceiling_with_real_wait_loop(self):
        """R1-F1, свойство «путь повтора конечен»: РЕАЛЬНЫЙ
        `_wait_for_branch_ci_green`, `ci.branch_status` всегда зелёный
        (голова ветки не менялась), push ВСЕГДА отвергается «cannot lock
        ref». Цикл обязан завершиться `SystemExit` за конечное число
        push'ей — не больше `CEILING / POLL` заходов, каждый с паузой, — с
        записью «merge FAILED» и задачей, оставшейся на `merge_gate`.

        Ловит мутацию: сверка потолка на пути повтора убрана — цикл не
        завершится, push упрётся в `PUSH_CAP` сценария (`assertLessEqual`
        покраснеет); пауза убрана — часы не идут, `sleep_calls` пуст и тот
        же исход.
        """
        self.patch(fsm_merge_gate, "_wait_for_branch_ci_green",
                   self.real_ci_wait)
        self.patch_branch_status(lambda branch: GREEN)
        self.push_always = _push_result(CANNOT_LOCK_REF, 1)

        with self.assertRaises(SystemExit) as exit_:
            self.run_cycle()

        expected_retries = math.ceil(config.MERGE_GATE_CI_WAIT_CEILING_SEC
                                     / config.MERGE_GATE_CI_WAIT_POLL_SEC)
        self.assertEqual(self.push_calls, expected_retries)
        self.assertEqual(self.sync_calls, expected_retries)
        self.assertEqual(self.clock.sleep_calls,
                         [config.MERGE_GATE_CI_WAIT_POLL_SEC] * expected_retries)
        self.assertGreaterEqual(self.clock.value,
                                config.MERGE_GATE_CI_WAIT_CEILING_SEC)
        self.assertIn("потолок ожидания истёк", str(exit_.exception))
        journal = self.journal_blob()
        self.assertIn("merge failed", journal)
        self.assertIn(f"{expected_retries} повтор", journal)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "merge_gate")
        self.assertIsNone(store.merge_lock_row(store.db()),
                          "мьютекс обязан быть снят `finally` цикла и на "
                          "этом отказе")

    def test_moved_after_exhausted_ceiling_exits_on_first_retry(self):
        """Потолок на пути «moved» — ОБЩИЙ с ожиданием CI, не свой: первое
        ожидание CI после подтяжки съело весь потолок, следующий отказ
        «main сдвинулся» отказывает сразу, без второго захода в тело.

        Ловит мутацию: на пути «moved» заведён собственный отсчёт
        (`deadline` пересчитан от момента отказа push) — цикл сделает ещё
        ~40 заходов вместо одного, `sync_calls` не будет равен 2.
        """
        self.sync_outcomes = [("wait", self.BRANCH)]
        self.ci_wait_seconds = float(config.MERGE_GATE_CI_WAIT_CEILING_SEC)
        self.push_results = [_push_result(NON_FAST_FORWARD, 1)]

        with self.assertRaises(SystemExit):
            self.run_cycle()

        self.assertEqual(self.sync_calls, 2)
        self.assertEqual(self.push_calls, 1)
        self.assertIn("1 повтор", self.journal_blob())
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "merge_gate")

    def test_cycle_retries_the_body_and_keeps_the_ceiling(self):
        """Первый push отклонён сдвигом main, второй успешен: тело заходит
        дважды в одном вызове, между заходами — ожидание CI с тем же
        `start`/`deadline`, задача доходит до `done`.

        Ловит мутацию: повтор реализован сбросом `deadline`/`start` перед
        новым заходом — второй `ci_waits` придёт со сдвинутым `start`, и
        `assertEqual(ci_waits[0], ci_waits[1])` покраснеет; либо повтор не
        идёт через ожидание CI — `len(ci_waits)` не равен 1.
        """
        self.push_results = [_push_result(CANNOT_LOCK_REF, 1), _push_result()]

        self.run_cycle()

        self.assertEqual(self.push_calls, 2)
        self.assertEqual(self.sync_calls, 2)
        self.assertEqual(len(self.ci_waits), 1)
        start, deadline = self.ci_waits[0]
        self.assertEqual(deadline - start, config.MERGE_GATE_CI_WAIT_CEILING_SEC)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "done")
        self.assertIn("main сдвинулся", self.journal_blob())
        self.assertNotIn("merge failed", self.journal_blob())

    def test_repeated_moved_main_shares_one_ceiling_across_retries(self):
        """Два подряд отказа «main сдвинулся» — два ожидания CI с
        ОДИНАКОВЫМИ `start`/`deadline`, хотя часы между ними ушли вперёд.

        Ловит мутацию: `deadline` пересчитывается на каждом исходе
        `("wait", ...)` — второй кортеж `ci_waits` разойдётся с первым.
        """
        self.push_results = [_push_result(NON_FAST_FORWARD, 1),
                             _push_result(CANNOT_LOCK_REF, 1),
                             _push_result()]

        self.run_cycle()

        self.assertEqual(len(self.ci_waits), 2)
        self.assertEqual(self.ci_waits[0], self.ci_waits[1])
        self.assertGreater(self.clock.value, self.ci_waits[0][0])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "done")

    def test_network_failure_in_cycle_exits_without_retry(self):
        """Сетевой отказ push внутри цикла — `SystemExit`, тело не
        повторяется, задача остаётся на `merge_gate`.

        Ловит мутацию: класс отказа в цикле не различается — второй push
        упрётся в исчерпанный сценарий (`assertTrue(push_results)`), а
        `SystemExit` не будет.
        """
        self.push_results = [_push_result(NETWORK_FAILURE, 128)]

        with self.assertRaises(SystemExit):
            self.run_cycle()

        self.assertEqual(self.sync_calls, 1)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "merge_gate")
        self.assertIn("merge failed", self.journal_blob())


class FreshPathDefersToWaitLoopTest(MergeGateCiWaitUnitTest):
    """SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-7 — эквивалент в стиле этого
    файла (реальный сценарий «первый push, CI ещё не завёлся» кроют
    приёмочные тесты задачи, `_sandbox.py::MergeGateFreshCiWaitSandbox`):
    тело гейта на пути `pull_outcome == "fresh"` с `confirmed_ci_note is
    None` обязано вернуть `("wait", branch)`, не опрашивать `ci.
    branch_status` вовсе само — опрос и решение (ждать циклом или
    отказать) целиком переехали в `_wait_for_branch_ci_green` вызывающего
    цикла, как и на пути "pulled".
    """

    def test_fresh_with_no_confirmed_note_returns_wait_without_polling_ci(self):
        """Путь "fresh" без `confirmed_ci_note` возвращает `("wait",
        branch)` и не зовёт `ci.branch_status` сам ни разу.

        Ловит мутацию: возврат старого разового опроса `ci.branch_status`
        внутри тела на пути "fresh" вместо `("wait", ...)` —
        `branch_status_calls` перестанет быть пустым, и AC-7 тихо
        откатится к немедленному отказу по одному опросу.
        """
        branch_status_calls = []

        def spying_branch_status(branch):
            branch_status_calls.append(branch)
            return (False, "у коммита abc12345 нет ни одной проверки CI")

        self.patch_branch_status(spying_branch_status)

        with mock.patch.object(fsm, "_pull_main_or_escalate",
                               return_value="fresh"), \
             mock.patch.object(github_adapter, "ensure_head_in_origin",
                               return_value=(True, "")):
            outcome = fsm_merge_gate._cmd_approve_merge_gate(
                store.db(), self.TASK, "merge_gate",
                {"branch": "task/t001-zadacha"})

        self.assertEqual(outcome, ("wait", "task/t001-zadacha"))
        self.assertEqual(
            branch_status_calls, [],
            "AC-7: путь fresh не имеет права опрашивать CI сам — опрос "
            "переехал в цикл ожидания вызывающего кода")


if __name__ == "__main__":
    unittest.main()
