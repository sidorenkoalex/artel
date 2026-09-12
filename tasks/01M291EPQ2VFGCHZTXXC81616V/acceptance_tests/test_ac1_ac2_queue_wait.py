"""AC-1/AC-2 — второй `approve` на занятое merge-окно ждёт в очереди,
опрашивая освобождение, вместо немедленного отказа; вход в очередь
журналируется и виден в `artel.py status` (SPEC
01M291EPQ2VFGCHZTXXC81616V).

Красен до реализации: `merge_lock.acquire` внутри
`fsm_merge_gate._cmd_approve_merge_gate_cycle` на отказ до сих пор ведёт
к `sys.exit(refusal)` (`orchestrator/fsm_merge_gate.py:697-699`) —
никакой очереди/опроса ещё нет, поэтому `time.sleep` внутри цикла ни
разу не вызывается на занятом мьютексе и тест зависает на
`ready[...].wait(timeout=5)` в `start_waiting`, падая по
`AssertionError` (не по опечатке теста — сам факт немедленного
`sys.exit` и есть проверяемое отсутствие кода задачи); `_zone_wait_
suffix`-аналога для merge-окна в `catalog.cmd_status` тоже нет — вторая
часть теста упала бы отдельно по отсутствию подстроки в выводе `status`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, merge_lock, store  # noqa: E402
from tests.sandbox import capture  # noqa: E402

from _sandbox import QueueSandbox  # noqa: E402


class QueueWaitTest(QueueSandbox):

    def test_ac1_second_approve_polls_the_queue_instead_of_exiting_immediately(self):
        """Второй `approve` на занятый мьютекс merge-окна не завершается
        `sys.exit` сразу — входит в очередь и опрашивает освобождение с
        интервалом `MERGE_GATE_CI_WAIT_POLL_SEC`, получая окно после
        освобождения В ТОМ ЖЕ вызове, без нового ручного `approve`.

        Ловит мутацию: «второй approve отказывает вместо ожидания в
        очереди» — красная (текст критерия AC-1 буквально).
        """
        self.seed_holder(self.TASK_A, "sess-a")

        thread = self.start_waiting(self.TASK_B)
        try:
            # мьютекс всё ещё занят держателем — задача не имеет права ни
            # завершиться, ни тронуть чужой мьютекс на этом опросе.
            self.assertEqual(self.done, [], "второй approve не должен "
                             "финишировать, пока окно занято")
            self.assertEqual(store.merge_lock_row(store.db())["session_id"],
                             "sess-a")
            self.assertEqual(self.sleep_seconds[self.TASK_B],
                             [config.MERGE_GATE_CI_WAIT_POLL_SEC],
                             "опрос очереди обязан паузить именно "
                             "MERGE_GATE_CI_WAIT_POLL_SEC")

            merge_lock.release(store.db(), "sess-a")
            self.proceed[self.TASK_B].set()
            thread.join(timeout=5)

            self.assertIn(self.TASK_B, self.done,
                         "после освобождения окна второй approve обязан "
                         "довести себя до done САМ, без нового вызова "
                         "Оператора")
            self.assertEqual(self.body_calls, [self.TASK_B])
        finally:
            thread.join(timeout=1)


class QueueWaitStatusAndJournalTest(QueueSandbox):

    def test_ac2_journal_entry_and_status_suffix_name_the_holder(self):
        """Вход в очередь журналируется записью «ждёт merge-окна: держит
        <id занявшей задачи>», и `artel.py status` для ждущей задачи
        показывает добавку «[ждёт merge-окна: занято <id>, N мин]» — по
        образцу существующей добавки «ждёт зоны» (`_zone_wait_suffix`).

        Ловит мутацию: журналирование записи входа в очередь удалено или
        текст действия не содержит «держит <id>» — assertIn упадёт;
        добавка `status` для merge-очереди не реализована вовсе (есть
        только существующие `_lease_holder_suffix`/`_zone_wait_suffix`) —
        assertRegex не найдёт паттерн в строке задачи.
        """
        self.seed_holder(self.TASK_A, "sess-a")
        thread = self.start_waiting(self.TASK_B)
        try:
            status_output = capture(catalog.cmd_status)
            b_line = next(line for line in status_output.splitlines()
                         if line.startswith(self.TASK_B))
            self.assertRegex(
                b_line,
                rf"\[ждёт merge-окна: занято {self.TASK_A}, \d+ мин\]",
                b_line)

            steps = store.task_steps(store.db(), self.TASK_B)
            self.assertTrue(
                any(f"ждёт merge-окна: держит {self.TASK_A}" in
                   (s["action"] or "") for s in steps),
                [s["action"] for s in steps])
        finally:
            merge_lock.release(store.db(), "sess-a")
            self.proceed[self.TASK_B].set()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
