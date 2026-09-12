"""AC-3, AC-4, AC-5 (tasks/01M290PS4ZXK1RCZ3PXQSXK0Y9/SPEC.md): три пути,
где `config.LEASE_STALE_AFTER_SEC` остаётся ЕДИНСТВЕННЫМ основанием
перехвата и поведение НЕ меняется этой задачей:

- AC-3: свой hostname, ЖИВОЙ pid держателя, heartbeat моложе порога —
  отказ «подожди её».
- AC-4: чужой hostname, heartbeat моложе порога — отказ независимо от
  живости/мёртвости pid держателя (pid чужого host не проверяется).
- AC-5: перехват по протуханию (heartbeat старше порога) не меняется ни
  для своего, ни для чужого hostname.

Зелёный с рождения: все три сценария — уже существующее, НЕ меняемое
этой задачей поведение `lease.acquire` (ветки `orchestrator/lease.py:84`
и `orchestrator/lease.py:91-103`, дословно). Задача добавляет НОВУЮ
ветку немедленного перехвата (AC-1/AC-8) СТРОГО в дополнение к этим трём,
не переписывая их, — эти тесты фиксируют нижнюю границу: сегодняшнее
поведение обязано остаться прежним и после реализации AC-1.
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


class RefusalPathsUnchangedTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def insert_holder(self, session_id: str, pid: int, hostname: str,
                      age_seconds: float) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (TASK, session_id, pid, hostname, _ts_ago(age_seconds)))
        conn.commit()

    def test_ac3_own_host_live_pid_before_threshold_still_refuses(self):
        """Держатель на своём hostname, pid ЖИВ (текущий процесс теста),
        heartbeat 5 секунд назад — отказ, именующий session_id, hostname
        и числовой возраст heartbeat, поведение прежнее.

        Ловит мутацию: если немедленный перехват AC-1 по ошибке
        реализовать без проверки живости pid (перехватывать ЛЮБОГО
        держателя своего hostname независимо от `_pid_alive`), этот
        живой держатель тоже был бы перехвачен — `assertIsNotNone(refusal)`
        упадёт на `None`.
        """
        self.insert_holder("sess-live-holder", os.getpid(),
                           socket.gethostname(), age_seconds=5)

        refusal, fresh = lease.acquire(store.db(), TASK, "sess-caller")

        self.assertIsNotNone(refusal)
        self.assertIn("sess-live-holder", refusal)
        self.assertIn(socket.gethostname(), refusal)
        self.assertRegex(refusal, r"\d+\s*сек")
        self.assertFalse(fresh)

    def test_ac4_foreign_host_before_threshold_refuses_even_with_dead_pid(self):
        """Держатель на ДРУГОМ hostname с ЗАВЕДОМО мёртвым (на этой
        машине) pid, heartbeat 5 секунд назад — отказ независимо от
        живости/мёртвости pid: pid чужого host не проверяется.

        Ловит мутацию: если немедленный перехват AC-1 забудет сверить
        `row["hostname"] == socket.gethostname()` и станет перехватывать
        мёртвый (по локальной таблице процессов) pid ЛЮБОГО host, этот
        межхостовый держатель был бы ошибочно перехвачен —
        `assertIsNotNone(refusal)` упадёт на `None`.
        """
        self.insert_holder("sess-foreign-holder", _dead_pid(),
                           "other-host.invalid", age_seconds=5)

        refusal, fresh = lease.acquire(store.db(), TASK, "sess-caller")

        self.assertIsNotNone(refusal)
        self.assertIn("sess-foreign-holder", refusal)
        self.assertIn("other-host.invalid", refusal)
        self.assertFalse(fresh)

    def test_ac5_stale_heartbeat_still_intercepts_on_own_host(self):
        """Heartbeat СТАРШЕ порога на своём hostname — перехват по
        протуханию по-прежнему происходит (независимо от живости pid,
        сегодняшнее поведение).

        Ловит мутацию: если добавление немедленного перехвата AC-1
        случайно сузит существующее условие протухания (например, оно
        начнёт требовать ЕЩЁ и мёртвый pid для перехвата своего host),
        живой-но-протухший держатель своего host перестанет
        перехватываться — `assertIsNone(refusal)` упадёт на отказе.
        """
        stale_age = config.LEASE_STALE_AFTER_SEC + 1
        self.insert_holder("sess-stale-own-host", os.getpid(),
                           socket.gethostname(), age_seconds=stale_age)

        refusal, fresh = lease.acquire(store.db(), TASK, "sess-caller")

        self.assertIsNone(refusal, refusal)
        row = store.lease_row(store.db(), TASK)
        self.assertEqual(row["session_id"], "sess-caller")
        self.assertFalse(fresh)

    def test_ac5_stale_heartbeat_still_intercepts_on_foreign_host(self):
        """Heartbeat СТАРШЕ порога на ЧУЖОМ hostname — перехват по
        протуханию по-прежнему происходит (сегодняшнее поведение,
        требование 2а SPEC).

        Ловит мутацию: если новая ветка немедленного перехвата (AC-1)
        по ошибке перепишет условие входа в блок перехвата так, что оно
        начнёт требовать СВОЙ hostname (нужный только для проверки
        pid), протухший держатель ЧУЖОГО host перестанет перехватываться
        — `assertIsNone(refusal)` упадёт на отказе.
        """
        stale_age = config.LEASE_STALE_AFTER_SEC + 1
        self.insert_holder("sess-stale-foreign-host", 999999,
                           "other-host.invalid", age_seconds=stale_age)

        refusal, fresh = lease.acquire(store.db(), TASK, "sess-caller")

        self.assertIsNone(refusal, refusal)
        row = store.lease_row(store.db(), TASK)
        self.assertEqual(row["session_id"], "sess-caller")
        self.assertFalse(fresh)


if __name__ == "__main__":
    unittest.main()
