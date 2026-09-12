"""AC-1, AC-8 (tasks/01M290PS4ZXK1RCZ3PXQSXK0Y9/SPEC.md): перехват чужого
lease на СВОЁМ hostname, когда pid держателя мёртв, — немедленно, без
ожидания порога `config.LEASE_STALE_AFTER_SEC`.

Красен до реализации: `lease.acquire` сейчас отказывает ЛЮБОМУ чужому
lease того же hostname, если возраст heartbeat не превышает
`config.LEASE_STALE_AFTER_SEC` (orchestrator/lease.py:84) — проверка
`liveness._pid_alive` стоит СТРОГО ПОСЛЕ этого порога (строка 99) и
сегодня влияет только на текст причины уже состоявшегося перехвата по
протуханию, не на сам факт немедленного перехвата свежего чужого lease.
Оба теста ниже вставляют мёртвый pid при heartbeat моложе порога и
ожидают успешный перехват — сегодняшний код вернёт именованный отказ
«подожди её» вместо перехвата.
"""
import os
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402

TASK = "T001"


class DeadPidImmediateInterceptTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def insert_holder(self, age_seconds: float, pid: int) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (TASK, "sess-dead-holder", pid, socket.gethostname(),
             _ts_ago(age_seconds)))
        conn.commit()

    def test_ac1_dead_pid_on_own_host_intercepts_before_the_threshold(self):
        """Держатель на своём hostname с мёртвым pid и heartbeat 5 секунд
        назад (заведомо младше `config.LEASE_STALE_AFTER_SEC`) — перехват
        проходит немедленно, lease переходит вызывающей сессии.

        Ловит мутацию: если условие `liveness._pid_alive` выкинуть из
        немедленной ветки перехвата (оставив прежний ранний отказ по
        одному лишь возрасту heartbeat), `acquire` вернёт именованный
        отказ вместо `(None, ...)`, и тест упадёт на `assertIsNone`.
        """
        self.insert_holder(age_seconds=5, pid=_dead_pid())

        refusal, _fresh = lease.acquire(store.db(), TASK, "sess-caller")

        self.assertIsNone(refusal, refusal)
        row = store.lease_row(store.db(), TASK)
        self.assertEqual(row["session_id"], "sess-caller")
        self.assertEqual(row["pid"], os.getpid())
        self.assertEqual(row["hostname"], socket.gethostname())

    def test_ac8_dead_pid_intercepts_a_heartbeat_one_second_under_the_threshold(self):
        """Держатель на своём hostname, pid мёртв, heartbeat ровно на 1
        секунду МОЛОЖЕ `config.LEASE_STALE_AFTER_SEC` (граница «формально
        ещё не протух ни на секунду») — перехват всё равно проходит
        немедленно.

        Ловит мутацию AC-8: «проверка живости pid выполняется ПОСЛЕ
        порога, не как условие немедленного перехвата» — то есть код,
        который по-прежнему решает «перехватывать или нет» только по
        сравнению возраста heartbeat с порогом (как сейчас, строка 84
        `orchestrator/lease.py`) и лишь ПОТОМ, уже внутри ветки
        перехвата, использует `_pid_alive` для текста причины. При такой
        мутации ровно этот граничный возраст (моложе порога на 1 секунду)
        отказывает «подожди её» вместо перехвата — тест ловит именно
        разницу между «до» и «после» порога, которую AC-1 с более
        свободным возрастом (5 секунд) может не отличить от случайного
        совпадения.
        """
        self.insert_holder(age_seconds=config.LEASE_STALE_AFTER_SEC - 1,
                           pid=_dead_pid())

        refusal, _fresh = lease.acquire(store.db(), TASK, "sess-caller")

        self.assertIsNone(refusal, refusal)
        row = store.lease_row(store.db(), TASK)
        self.assertEqual(row["session_id"], "sess-caller")


if __name__ == "__main__":
    unittest.main()
