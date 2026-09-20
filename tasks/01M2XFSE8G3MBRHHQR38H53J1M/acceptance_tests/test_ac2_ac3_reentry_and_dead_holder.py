"""AC-2/AC-3 — повторный вход ТОГО ЖЕ процесса и перехват мёртвого
держателя ЧУЖОЙ сессии не меняются сменой ключа владения на процесс
(задача 01M2XFSE8G3MBRHHQR38H53J1M).

Зелёный с рождения: все проверки здесь — про СОХРАНЕНИЕ сегодняшнего
поведения (`orchestrator/merge_lock.py:52-71`: своя строка обновляется и
даёт `None`, мёртвый держатель перехватывается с записью «мьютекс merge
перехвачен»). Красными их делает именно регрессия реализации требования 1
— например отказ своему же процессу из цикла `wait_for_window` (вечное
ожидание самого себя) или потеря одного из двух признаков мёртвого
держателя. Третий случай AC-3 (мёртвый держатель СВОЕЙ сессии) сегодня
проходит молча, без записи перехвата, и живёт отдельным файлом
`test_ac3_dead_process_of_own_session.py` — у него обратный маркер
красноты.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, liveness, merge_lock, merge_queue, store  # noqa: E402

from _sandbox import MergeOwnerSandbox, _dead_pid, _ts_ago  # noqa: E402


class HolderProcessReentryTest(MergeOwnerSandbox):

    def test_ac2_holder_process_gets_none_and_refreshes_the_row(self):
        """Мьютекс держит ЭТОТ процесс (`os.getpid()`, сессия `sess-a`) с
        heartbeat двухминутной давности; повторный `acquire` обязан
        вернуть `None` и обновить строку — задача в ней становится текущей,
        heartbeat свежим.

        Ловит мутацию: условие «свой» ужесточено до неработоспособного
        (например сверяется `row["task_id"] == task_id` вместе с pid, или
        своя строка признаётся, но `set_merge_lock` из этой ветки убран) —
        вызов вернёт отказ либо оставит протухший heartbeat, и держатель
        подставит себя под перехват `_holder_is_dead` в следующем опросе.
        """
        self.seed_lock(self.TASK_B, "sess-a", os.getpid(),
                       socket.gethostname(), _ts_ago(120))

        refusal = merge_lock.acquire(store.db(), self.TASK_A, "sess-a")

        self.assertIsNone(refusal, "своему же процессу мьютекс обязан "
                                   "оставаться своим")
        row = self.lock_row()
        self.assertEqual(row["task_id"], self.TASK_A)
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["pid"], os.getpid())
        self.assertLess(liveness._age_seconds(row["heartbeat_ts"]), 60,
                        "повторный вход обязан продлить heartbeat строки")

    def test_ac2_wait_for_window_returns_at_once_to_its_own_holder(self):
        """`wait_for_window` из процесса, который мьютекс уже держит,
        обязана вернуться на ПЕРВОМ же опросе (её цикл зовёт `acquire`) —
        без единой паузы и с снятой за собой записью очереди.

        Ловит мутацию: `acquire` перестала признавать своим процесс,
        совпадающий по session_id И pid (например сверяет pid строки с
        pid из `enqueue`, а не с `os.getpid()`) — цикл ожидания не получит
        окно ни на одном опросе и упадёт `SystemExit` по потолку
        `MERGE_QUEUE_WAIT_CEILING_SEC`.
        """
        self.seed_lock(self.TASK_A, "sess-a", os.getpid(),
                       socket.gethostname())
        clock = self.fake_clock()

        merge_queue.wait_for_window(store.db(), self.TASK_A, "sess-a")

        row = self.lock_row()
        self.assertEqual(row["session_id"], "sess-a")
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(clock.sleep_calls, [],
                         "свой же мьютекс не имеет права заставлять "
                         "процесс ждать в очереди")
        self.assertEqual(self.queue_rows(), [],
                         "полученное окно обязано снимать свою запись "
                         "очереди")


class DeadHolderInterceptTest(MergeOwnerSandbox):

    def assert_intercepted(self) -> None:
        """Перехват состоялся: мьютекс за нашим процессом и в журнале —
        прежняя запись «мьютекс merge перехвачен»."""
        row = self.lock_row()
        self.assertEqual(row["task_id"], self.TASK_A)
        self.assertEqual(row["pid"], os.getpid())
        records = self.journal_records(self.TASK_A)
        self.assertTrue(
            any("мьютекс merge перехвачен" in r for r in records), records)

    def test_ac3_stale_heartbeat_holder_is_intercepted_with_the_old_journal(self):
        """Держатель чужой сессии на чужом host с heartbeat старше
        `LEASE_STALE_AFTER_SEC` — перехватывается, `acquire` даёт `None`,
        журнал несёт прежнюю запись.

        Ловит мутацию: признак мёртвого держателя сведён к одному неживому
        pid (ветка протухшего heartbeat выброшена вместе с переработкой
        условия «свой») — держатель на чужом host, о pid которого судить
        нечем, станет вечным, и `acquire` вернёт отказ.
        """
        self.seed_lock(self.TASK_B, "sess-holder", 999, "holder-host",
                       _ts_ago(config.LEASE_STALE_AFTER_SEC + 1))

        refusal = merge_lock.acquire(store.db(), self.TASK_A, "sess-caller")

        self.assertIsNone(refusal)
        self.assert_intercepted()

    def test_ac3_dead_pid_on_own_host_is_intercepted_despite_fresh_heartbeat(self):
        """Держатель чужой сессии на ЭТОМ host с неживым pid и свежим
        heartbeat — перехватывается (второй, независимый признак мёртвого
        держателя).

        Ловит мутацию: pid-проверка переехала из `_holder_is_dead` в
        условие «свой» и на чужой сессии больше не делается — свежий
        heartbeat мёртвого процесса даст отказ вместо перехвата.
        """
        self.seed_lock(self.TASK_B, "sess-holder", _dead_pid(),
                       socket.gethostname())

        refusal = merge_lock.acquire(store.db(), self.TASK_A, "sess-caller")

        self.assertIsNone(refusal)
        self.assert_intercepted()


if __name__ == "__main__":
    unittest.main()
