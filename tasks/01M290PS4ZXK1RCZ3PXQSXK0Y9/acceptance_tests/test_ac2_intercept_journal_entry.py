"""AC-2 (tasks/01M290PS4ZXK1RCZ3PXQSXK0Y9/SPEC.md): перехват из AC-1
пишет запись журнала «lease перехвачен» тем же текстом/форматом, что и
существующий перехват по протуханию, с причиной «pid держателя мёртв
(pid <pid>)» и указанием прежнего session_id и pid держателя.

Красен до реализации: сегодня `lease.acquire` даже не доходит до ветки
записи журнала для этого сценария — heartbeat моложе порога отказывает
раньше (`orchestrator/lease.py:84`), так что `store.task_steps` не
получает новую запись вовсе, и `assertEqual(len(new_steps), 1)` ниже
падает на пустом списке.
"""
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402

TASK = "T001"


class InterceptJournalEntryTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        self.dead_pid = _dead_pid()
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (TASK, "sess-dead-holder", self.dead_pid, socket.gethostname(),
             _ts_ago(5)))
        conn.commit()
        self.steps_before = len(store.task_steps(store.db(), TASK))

    def test_ac2_intercept_journals_the_same_event_with_pid_dead_cause(self):
        """Один новый шаг журнала «lease перехвачен» с причиной «pid
        держателя мёртв (pid <pid>)», прежним session_id и прежним pid.

        Ловит мутацию: если перехват из AC-1 реализовать БЕЗ вызова
        `store.journal` (например, молча переписать строку `leases`
        и вернуть `(None, False)`), новых записей не появится и
        `assertEqual(len(new), 1)` упадёт на нуле; если причину перепутать
        с текстом протухания («heartbeat протух»), `assertIn` на
        «pid держателя мёртв» и на число `self.dead_pid` упадут.
        """
        refusal, _fresh = lease.acquire(store.db(), TASK, "sess-caller")
        self.assertIsNone(refusal, refusal)

        new = store.task_steps(store.db(), TASK)[self.steps_before:]
        self.assertEqual(len(new), 1, new)
        step = new[0]
        self.assertEqual(step["action"], "lease перехвачен")
        self.assertIn("pid держателя мёртв", step["detail"])
        self.assertIn(str(self.dead_pid), step["detail"])
        self.assertIn("sess-dead-holder", step["detail"])
        self.assertEqual(step["session_id"], "sess-caller")


if __name__ == "__main__":
    unittest.main()
