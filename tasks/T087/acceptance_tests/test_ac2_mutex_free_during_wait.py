"""AC-2 (tasks/T087/SPEC.md): мьютекс merge-окна освобождается сразу
после пуша нового head и НЕ удерживается ни на одной итерации цикла
ожидания CI (пауза, чтение статуса, авто-ре-ран).

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-2.

Наблюдаемая точка — `store.merge_lock_row` (строка мьютекса в БД,
`orchestrator/merge_lock.py`): проверяется НЕПОСРЕДСТВЕННО из моков
трёх операций, которые требование 2 перечисляет буквально — чтение
статуса (`ci.branch_status`), авто-ре-ран (`ci.trigger_rerun`) и пауза
(`time.sleep`, через `FakeClock` песочницы) — в момент, когда каждая из
них исполняется, мьютекс обязан быть свободен.

Красен до реализации: сегодня цикла ожидания нет вовсе — `_pull_main_or_
escalate` возвращающий "pulled" внутри `merge_gate` останавливает
`approve` немедленно после ЕДИНСТВЕННОГО сообщения, ни разу не читая
`ci.branch_status` в этом вызове (`orchestrator/fsm.py`) — до вызова
проверяющих моков дело не доходит вовсе, `checked["n"] == 0` ловит это
как отдельный явный отказ теста, не тихий пропуск.
"""
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import GREEN, RED, RUNNING  # noqa: E402
from _sandbox import MergeGateCiWaitTest


class Ac2MutexFreeDuringWaitTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()

    def test_ac2_mutex_row_absent_at_every_wait_operation(self):
        self.add_main_commit()

        checked = {"status": 0, "rerun": 0, "sleep": 0}
        # RUNNING (пауза после) -> RED (ре-ран) -> GREEN (ре-ран зелёный,
        # флейк) -> approve обязан довести задачу до done в ЭТОМ ЖЕ
        # вызове (AC-5), проходя через все три операции цикла ожидания.
        responses = [RUNNING, RED, GREEN]

        def branch_status_checks_mutex_free(branch):
            checked["status"] += 1
            self.assertTrue(
                self.merge_lock_free(),
                f"AC-2: мьютекс merge-окна обязан быть свободен во время "
                f"чтения статуса CI (итерация {checked['status']})")
            return responses[min(checked["status"] - 1, len(responses) - 1)]

        def trigger_rerun_checks_mutex_free(branch):
            checked["rerun"] += 1
            self.assertTrue(
                self.merge_lock_free(),
                "AC-2: мьютекс merge-окна обязан быть свободен во время "
                "авто-ре-рана красного CI")
            return "ре-ран (тест)"

        original_sleep = self.clock.sleep

        def sleep_checks_mutex_free(seconds):
            checked["sleep"] += 1
            self.assertTrue(
                self.merge_lock_free(),
                "AC-2: мьютекс merge-окна обязан быть свободен во время "
                "паузы между попытками цикла ожидания")
            return original_sleep(seconds)

        self.patch_branch_status(branch_status_checks_mutex_free)
        self.patch_trigger_rerun(trigger_rerun_checks_mutex_free)
        patcher = mock.patch.object(time, "sleep", sleep_checks_mutex_free)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.approve()

        self.assertGreaterEqual(
            checked["status"], 3,
            f"предпосылка теста: обязаны быть прочитаны все три канонных "
            f"статуса (идёт/красный/ре-ран-зелёный), фактически "
            f"{checked['status']}")
        self.assertGreaterEqual(
            checked["rerun"], 1,
            "предпосылка теста: авто-ре-ран красного статуса обязан "
            "сработать хотя бы раз")
        self.assertGreaterEqual(
            checked["sleep"], 1,
            "предпосылка теста: между итерациями обязана быть хотя бы "
            "одна пауза (после статуса «ещё идёт»)")
        self.assertEqual(
            self.state(), "done",
            "флейк (красный -> ре-ран зелёный) обязан довести задачу до "
            "done в этом же вызове approve (AC-5)")


if __name__ == "__main__":
    import unittest
    unittest.main()
