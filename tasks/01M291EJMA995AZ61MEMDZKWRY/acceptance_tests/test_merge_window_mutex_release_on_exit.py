"""Приёмочные тесты SPEC 01M291EJMA995AZ61MEMDZKWRY (AC-5): мьютекс
merge-окна снимается безусловно по завершении внешнего цикла
`_cmd_approve_merge_gate_cycle` в любом исходе — merge в `done`, отказ
(`sys.exit`), истечение потолка ожидания CI.

Зелёный с рождения: каждый сценарий ниже завершает цикл на ПЕРВОМ же
заходе в тело (`("done",)`, `sys.exit` тела, либо истечение потолка
ожидания CI внутри одного захода) — сегодняшний код
(`orchestrator/fsm_merge_gate.py:696-704`) берёт и безусловно
освобождает мьютекс вокруг КАЖДОГО отдельного захода в тело своим
собственным `try/finally`, так что на любом из этих трёх путей, где
тело вызывается ровно один раз, освобождение уже происходит корректно
сегодня — по счастливому совпадению тесной область видимости, а не
потому что требование 4 (единая точка освобождения ВНЕШНЕГО цикла) уже
реализовано. Перенос `acquire`/`release` за пределы `while True`
(AC-1/AC-7, `tasks/01M291EJMA995AZ61MEMDZKWRY/acceptance_tests/
test_merge_window_mutex_cycle.py`) обязан сохранить это же поведение
безусловного освобождения на КАЖДОМ из трёх путей — тест фиксирует его
как регрессионную планку, не как факт ещё не написанного кода.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import catalog, ci, config, fsm_merge_gate, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

RUNNING = (False, "CI коммита abc12345 ещё идёт: python")


class FakeClock:
    """`sleep(s)` продвигает `monotonic()` на `s` вместо настоящего
    ожидания — тот же приём, что `tests/test_merge_gate_ci_wait.py`."""

    def __init__(self, start: float = 0.0):
        self.value = start

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class MutexReleasedOnCycleExitTest(TmpRootTest):
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

    def test_ac5_lock_released_after_successful_cycle_completion(self):
        """Тело гейта сразу возвращает `("done",)` — цикл завершается
        успехом на первом же заходе; после возврата строки `merge_locks`
        быть не должно.

        Ловит мутацию: если снятие мьютекса выпадает из точки
        освобождения (перенесено куда-то, откуда исход `"done"` не
        проходит), строка `merge_locks` останется занятой сессией
        `"sess-1"` после возврата из `_cmd_approve_merge_gate_cycle`.
        """
        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            return ("done",)

        def fake_wait(conn, task_id, branch, start, deadline):
            self.fail("тело гейта не должно было уйти в ожидание CI")

        with mock.patch.object(fsm_merge_gate, "_cmd_approve_merge_gate",
                               fake_body), \
             mock.patch.object(fsm_merge_gate, "_wait_for_branch_ci_green",
                               fake_wait):
            fsm_merge_gate._cmd_approve_merge_gate_cycle(
                store.db(), self.TASK, "sess-1", {"branch": self.BRANCH},
                "merge_gate")

        self.assertIsNone(
            store.merge_lock_row(store.db()),
            "мьютекс обязан быть снят по завершении цикла успешным "
            "merge (AC-5)")

    def test_ac5_lock_released_when_body_call_raises_sys_exit(self):
        """Тело гейта завершается `sys.exit` (типичный именованный
        отказ гейта) — мьютекс всё равно обязан быть снят безусловно.

        Ловит мутацию: освобождение мьютекса обёрнуто только вокруг
        штатного (не исключительного) пути — тогда `sys.exit` внутри
        тела гейта оставит строку `merge_locks` висящей на `"sess-1"`
        навсегда.
        """
        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            sys.exit(f"[{task_id}] merge отклонён: тестовый отказ тела гейта")

        def fake_wait(conn, task_id, branch, start, deadline):
            self.fail("тело гейта не должно было уйти в ожидание CI")

        with mock.patch.object(fsm_merge_gate, "_cmd_approve_merge_gate",
                               fake_body), \
             mock.patch.object(fsm_merge_gate, "_wait_for_branch_ci_green",
                               fake_wait):
            with self.assertRaises(SystemExit):
                fsm_merge_gate._cmd_approve_merge_gate_cycle(
                    store.db(), self.TASK, "sess-1", {"branch": self.BRANCH},
                    "merge_gate")

        self.assertIsNone(
            store.merge_lock_row(store.db()),
            "мьютекс обязан быть снят даже когда тело завершилось "
            "sys.exit (AC-5)")

    def test_ac5_lock_released_when_ci_wait_ceiling_expires(self):
        """Настоящий (не замоканный) `_wait_for_branch_ci_green` истекает
        по потолку `MERGE_GATE_CI_WAIT_CEILING_SEC` (CI держится "ещё
        идёт" на всех опросах, `FakeClock` прокручивает время без
        настоящего ожидания) и завершает процесс `sys.exit` изнутри
        цикла — мьютекс обязан быть снят и в этом исходе.

        Ловит мутацию: точка освобождения мьютекса обёрнута только
        вокруг вызова тела гейта, не вокруг ожидания CI — `sys.exit` из
        истечения потолка внутри `_wait_for_branch_ci_green` тогда
        проскочит мимо освобождения мьютекса.
        """
        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            return ("wait", self.BRANCH)

        status_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: RUNNING)
        status_patcher.start()
        self.addCleanup(status_patcher.stop)

        with mock.patch.object(fsm_merge_gate, "_cmd_approve_merge_gate",
                               fake_body):
            with self.assertRaises(SystemExit):
                fsm_merge_gate._cmd_approve_merge_gate_cycle(
                    store.db(), self.TASK, "sess-1", {"branch": self.BRANCH},
                    "merge_gate")

        self.assertIsNone(
            store.merge_lock_row(store.db()),
            "мьютекс обязан быть снят даже когда цикл завершился "
            "истечением потолка ожидания CI (AC-5)")


if __name__ == "__main__":
    unittest.main()
