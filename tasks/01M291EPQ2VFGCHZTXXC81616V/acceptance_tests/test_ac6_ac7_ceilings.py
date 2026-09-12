"""AC-6/AC-7 — потолок ожидания в очереди (`MERGE_QUEUE_WAIT_CEILING_SEC`,
дефолт 7200 сек): по истечении `approve` выходит без merge с именованным
сообщением, задача остаётся на `merge_gate`; отдельно — потолок ожидания
CI (`MERGE_GATE_CI_WAIT_CEILING_SEC`) отсчитывается от момента выхода из
очереди, не от момента входа в неё (время очереди не засчитывается в
потолок CI) (SPEC 01M291EPQ2VFGCHZTXXC81616V).

Красен до реализации: `config.MERGE_QUEUE_WAIT_CEILING_SEC` не существует
вовсе — `AttributeError` на первой строке AC-6 (не опечатка теста, само
отсутствие именованной константы — часть критерия требования 3).
AC-7 красен по той же причине, что AC-1/AC-5: второй approve сейчас не
входит в очередь вовсе.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (catalog, ci, config, fsm, fsm_merge_gate,  # noqa: E402
                          github_adapter, store)
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class FakeClock:
    """Тот же приём, что `tests/test_merge_gate_ci_wait.py::FakeClock`:
    `sleep(s)` продвигает `monotonic()` на `s` вместо настоящего ожидания."""

    def __init__(self, start: float = 0.0):
        self.value = start

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class _CeilingTestBase(TmpRootTest):
    TASK = "T001"
    HOLDER = "T999"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        store.insert_task(store.db(), self.HOLDER, "Держит окно",
                          "merge_gate", "task/t999-holder",
                          config.DEFAULT_TARGET, 25.0)
        # Держатель на ЧУЖОМ host (тот же приём, что сценарии отказа
        # tests/test_merge_lock.py) — `_holder_is_dead` не проверяет pid
        # чужого host вовсе, держатель гарантированно живой независимо от
        # того, существует ли pid 111 реально на машине теста.
        store.set_merge_lock(store.db(), self.HOLDER, "sess-holder", 111,
                             "holder-host", store.now())
        self.clock = FakeClock()


class QueueWaitCeilingTest(_CeilingTestBase):

    def test_ac6_default_is_7200_and_expiry_refuses_without_advancing_state(self):
        """Дефолт константы — буквально 7200 секунд (SPEC AC-6); держатель
        никогда не отпускает окно — по истечении потолка `approve` обязан
        выйти `sys.exit`'ом без merge, задача остаётся на `merge_gate`
        (переход состояния не выполняется).

        Ловит мутацию: `MERGE_QUEUE_WAIT_CEILING_SEC` заведена с другим
        значением по умолчанию (например, скопирован `ZONE_WAIT_MAX_SEC`
        = 6*3600) — первый assertEqual упадёт; потолок не проверяется
        вовсе (бесконечный цикл) — тест не завершится за разумное время
        (таймаут прогона); `store.set_state` всё-таки вызван по истечении
        потолка — assertEqual состояния упадёт.
        """
        self.assertEqual(config.MERGE_QUEUE_WAIT_CEILING_SEC, 7200)

        with mock.patch.object(time, "sleep", self.clock.sleep), \
             mock.patch.object(time, "monotonic", self.clock.monotonic):
            with self.assertRaises(SystemExit) as exit_:
                fsm_merge_gate._cmd_approve_merge_gate_cycle(
                    store.db(), self.TASK, "sess-caller",
                    {"branch": "task/t001-zadacha"}, "merge_gate")

        self.assertIn(self.TASK, str(exit_.exception))
        self.assertGreaterEqual(self.clock.value,
                                config.MERGE_QUEUE_WAIT_CEILING_SEC)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "merge_gate")


class QueueTimeNotCountedTowardsCiCeilingTest(_CeilingTestBase):

    def test_ac7_ci_ceiling_start_is_the_moment_of_leaving_the_queue(self):
        """Окно занято 5 опросов подряд (успевает пройти 5 *
        `MERGE_GATE_CI_WAIT_POLL_SEC` виртуального времени в очереди),
        затем освобождается — момент `start`, переданный циклу ожидания
        CI, обязан совпадать с моментом ВЫХОДА из очереди (виртуальное
        время на этот момент), не с моментом ВХОДА в неё; потолок CI от
        этого `start` — полный `MERGE_GATE_CI_WAIT_CEILING_SEC`, не
        урезанный временем, проведённым в очереди.

        Ловит мутацию: `start` вычислен от момента ВХОДА в очередь
        (условно 0) вместо момента получения окна — `assertAlmostEqual`
        по значению `start` упадёт; потолок CI уменьшен на время очереди
        (`deadline = start + CEILING - время_в_очереди`) — второй
        `assertEqual` (разница `deadline - start`) упадёт.
        """
        release_after = {"n": 0}

        def sleep_and_release_on_fifth_poll(seconds):
            self.clock.value += seconds
            release_after["n"] += 1
            if release_after["n"] == 5:
                store.release_merge_lock(store.db(), "sess-holder")

        starts_deadlines = []

        class _StopAfterFirstWait(Exception):
            pass

        def spying_wait(conn, task_id, branch, start, deadline):
            # Дальше в теле гейта — настоящий git (push/merge), не нужный
            # этому тесту: он проверяет только `start`/`deadline`,
            # переданные циклу ожидания CI, останавливаемся здесь же.
            starts_deadlines.append((start, deadline))
            raise _StopAfterFirstWait()

        with mock.patch.object(time, "sleep", sleep_and_release_on_fifth_poll), \
             mock.patch.object(time, "monotonic", self.clock.monotonic), \
             mock.patch.object(fsm_merge_gate, "_wait_for_branch_ci_green",
                               spying_wait), \
             mock.patch.object(fsm, "_pull_main_or_escalate",
                               return_value="fresh"), \
             mock.patch.object(github_adapter, "ensure_head_in_origin",
                               return_value=(True, "")), \
             mock.patch.object(ci, "branch_status",
                               return_value=(False, "нет проверок")):
            with self.assertRaises(_StopAfterFirstWait):
                fsm_merge_gate._cmd_approve_merge_gate_cycle(
                    store.db(), self.TASK, "sess-caller",
                    {"branch": "task/t001-zadacha"}, "merge_gate")

        self.assertEqual(len(starts_deadlines), 1)
        start, deadline = starts_deadlines[0]
        self.assertAlmostEqual(
            start, 5 * config.MERGE_GATE_CI_WAIT_POLL_SEC, delta=1,
            msg="start обязан совпадать с моментом выхода из очереди "
               "(5 опросов), не с моментом входа в неё")
        self.assertEqual(
            deadline - start, config.MERGE_GATE_CI_WAIT_CEILING_SEC,
            "потолок ожидания CI от start обязан быть полным "
            "MERGE_GATE_CI_WAIT_CEILING_SEC, не урезанным временем "
            "очереди")


if __name__ == "__main__":
    unittest.main()
