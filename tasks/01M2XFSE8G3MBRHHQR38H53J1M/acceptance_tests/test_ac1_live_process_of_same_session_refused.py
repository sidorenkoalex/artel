"""AC-1 — мьютекс merge принадлежит ПРОЦЕССУ: другой живой процесс той же
сессии получает именованный отказ с pid держателя и уходит в очередь
(задача 01M2XFSE8G3MBRHHQR38H53J1M).

Красен до реализации: `merge_lock.acquire` считает мьютекс своим по одному
`session_id` (`orchestrator/merge_lock.py:52` — `row["session_id"] ==
session_id`), поэтому второй живой процесс той же сессии получает `None`
вместо отказа, переписывает чужую строку мьютекса на себя и цикл
`merge_gate` идёт готовить merge, минуя `merge_queue.wait_for_window`.
"""
import re
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import (fsm_merge_gate, liveness, merge_lock,  # noqa: E402
                          merge_queue, store)

from _sandbox import MergeOwnerSandbox, _alive_foreign_pid  # noqa: E402


class LiveProcessOfSameSessionRefusedTest(MergeOwnerSandbox):

    def test_ac1_acquire_refuses_naming_the_holder_pid_and_keeps_the_row(self):
        """Мьютекс взят процессом A (живой pid на этом host, сессия
        `sess-a`); `acquire` из процесса B (сам тест, та же сессия
        `sess-a`) обязан вернуть непустой отказ, назвать в нём pid
        держателя A и не тронуть строку мьютекса.

        Ловит мутацию: условие «свой» в `acquire` оставлено по одному
        `session_id` (или pid добавлен в текст отказа, но не в условие) —
        вызов вернёт `None`, а строка мьютекса окажется переписана на
        `os.getpid()`: `assertIsNotNone` и сверка строки «до/после»
        покраснеют обе.
        """
        holder_pid = _alive_foreign_pid(self)
        self.seed_lock(self.TASK_B, "sess-a", holder_pid,
                       socket.gethostname())
        before = dict(self.lock_row())

        refusal = merge_lock.acquire(store.db(), self.TASK_A, "sess-a")

        self.assertIsNotNone(
            refusal, "живой ДРУГОЙ процесс той же сессии обязан получить "
                     "отказ: держатель мьютекса — процесс, не сессия")
        self.assertIn(str(holder_pid), refusal,
                      f"отказ обязан называть pid держателя: {refusal}")
        self.assertEqual(dict(self.lock_row()), before,
                         "отказанное взятие не имеет права тронуть строку "
                         "живого держателя")

    def test_ac1_refusal_text_is_the_same_as_for_a_foreign_session(self):
        """Один и тот же живой держатель (тот же pid, host и задача)
        отказывает двум вызывающим одинаково: разница только в его
        `session_id` — чужая сессия `sess-holder` против своей же
        `sess-caller`. Тексты сравниваются после нормализации всех
        идентификаторов сессии, `_age_seconds` зафиксирован, чтобы «N сек
        назад» не зависел от границы секунды.

        Ловит мутацию: для процесса своей сессии заведён ОТДЕЛЬНЫЙ текст
        отказа («мьютекс держит другой процесс этой сессии …») вместо
        того же самого, что для чужой сессии — нормализованные строки
        разойдутся, `assertEqual` покраснеет.
        """
        holder_pid = _alive_foreign_pid(self)
        host = socket.gethostname()

        with mock.patch.object(liveness, "_age_seconds", lambda ts: 7.0):
            self.seed_lock(self.TASK_B, "sess-holder", holder_pid, host)
            foreign = merge_lock.acquire(store.db(), self.TASK_A,
                                         "sess-caller")
            self.seed_lock(self.TASK_B, "sess-caller", holder_pid, host)
            same_session = merge_lock.acquire(store.db(), self.TASK_A,
                                             "sess-caller")

        self.assertIsNotNone(foreign, "чужая живая сессия обязана "
                                      "отказывать и после задачи")
        self.assertIsNotNone(same_session)
        normalize = lambda text: re.sub(r"sess-[a-z]+", "SID", text)  # noqa: E731
        self.assertEqual(normalize(same_session), normalize(foreign))

    def test_ac1_gate_cycle_enters_the_queue_before_the_merge_body(self):
        """Цикл `approve` гейта merge при живом держателе-процессе той же
        сессии обязан сначала встать в `merge_queue.wait_for_window` (с
        своим task_id и sid), и только потом идти в тело гейта — сегодня
        он идёт в тело сразу.

        Ловит мутацию: отказ `acquire` для процесса своей сессии не
        доведён до цикла гейта (например, `acquire` отказывает, а
        `_cmd_approve_merge_gate_cycle` продолжает трактовать свою сессию
        как «мьютекс мой» отдельной проверкой) — `order` окажется
        `["тело"]` вместо `["очередь", "тело"]`.
        """
        holder_pid = _alive_foreign_pid(self)
        self.seed_lock(self.TASK_B, "sess-a", holder_pid,
                       socket.gethostname())
        order: list[str] = []
        waits: list[tuple] = []

        def fake_wait_for_window(conn, task_id, sid):
            order.append("очередь")
            waits.append((task_id, sid))

        def fake_body(conn, task_id, state, t, confirmed_ci_note=None):
            order.append("тело")
            return ("done",)

        with mock.patch.object(merge_queue, "wait_for_window",
                               fake_wait_for_window), \
             mock.patch.object(fsm_merge_gate, "_cmd_approve_merge_gate",
                               fake_body):
            fsm_merge_gate._cmd_approve_merge_gate_cycle(
                store.db(), self.TASK_A, "sess-a",
                {"branch": self.BRANCH[self.TASK_A]}, "merge_gate")

        self.assertEqual(order, ["очередь", "тело"])
        self.assertEqual(waits, [(self.TASK_A, "sess-a")])


if __name__ == "__main__":
    unittest.main()
