"""Сторож главной копии пульта (SPEC 01M4G8KPP8DVNBCPGCAPSVMAKZ):
свойства вне долгоживущих тестов задачи — сбой git на сверке и окно
выборки соседних шагов. Главная копия — настоящий git песочницы."""
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import alerts, checkpoint, config, store
from tests.sandbox import RealGitSandbox


class MainCopyWatchTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        (self.root / "tracked.txt").write_text("исходное\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        self.git("commit", "-q", "-m", "посев")

    def start_step(self, task_id: str, role: str):
        store.journal(self.conn, task_id, role, "agent run started", "")
        return checkpoint.main_copy_watch_start(self.conn, task_id)

    def watch_alerts(self) -> list:
        return [row["message"] for row in alerts.open_alerts(self.conn)
                if row["source"] == checkpoint.MAIN_COPY_WATCH_SOURCE]

    def test_git_failure_after_step_is_journaled_not_silent(self):
        """git status главной копии не ответил на сверке после шага.

        Снимок на старте удался, после шага git отвечает rc=128: сверка
        возвращает False, исключения нет, алерта нет, а в журнале задачи
        есть запись «сверка главной копии не выполнена» с ролью шага.

        Ловит мутацию: сбой git на второй сверке проглатывается молча
        (нет записи журнала) или роняет шаг исключением.
        """
        watch = self.start_step("01TASKGITFAIL", "developer")
        self.assertIsNotNone(watch)
        (self.root / "tracked.txt").write_text("правка\n", encoding="utf-8")
        failed = subprocess.CompletedProcess(["git"], 128, "", "fatal")
        with mock.patch.object(checkpoint.subprocess, "run",
                               return_value=failed):
            raised = checkpoint.watch_main_copy(
                self.conn, "01TASKGITFAIL", "developer", watch)
        self.assertFalse(raised)
        self.assertEqual(self.watch_alerts(), [])
        records = [row for row in store.task_steps(self.conn, "01TASKGITFAIL")
                   if row["action"] == checkpoint.MAIN_COPY_WATCH_FAILED_ACTION]
        self.assertEqual(len(records), 1)
        self.assertIn("developer", records[0]["detail"])

    def test_orphan_start_older_than_window_is_not_a_neighbour(self):
        """Старт шага другой задачи без закрывающей записи.

        Осиротевший «agent run started» старше двух таймаутов шага до
        старта проверяемого в алерт не попадает; такой же незакрытый старт
        внутри окна попадает — алерт называет его задачу и роль.

        Ловит мутацию: окно выборки снято — осиротевший старт умершего
        процесса называется соседом в каждом алерте; либо незакрытый
        старт не считается идущим шагом — свежий сосед пропадёт.
        """
        old = (datetime.now(timezone.utc)
               - timedelta(seconds=3 * config.AGENT_TIMEOUT_SEC)
               ).strftime("%Y-%m-%d %H:%M:%SZ")
        with mock.patch.object(store, "now", return_value=old):
            store.journal(self.conn, "01TASKORPHAN", "reviewer",
                          "agent run started", "")
        store.journal(self.conn, "01TASKRUNNING", "analyst",
                      "agent run started", "")
        watch = self.start_step("01TASKCHECKED", "developer")
        (self.root / "tracked.txt").write_text("правка\n", encoding="utf-8")

        self.assertTrue(checkpoint.watch_main_copy(
            self.conn, "01TASKCHECKED", "developer", watch))
        [message] = self.watch_alerts()
        self.assertIn("tracked.txt", message)
        self.assertIn("analyst (задача 01TASKRUNNING)", message)
        self.assertNotIn("01TASKORPHAN", message)


if __name__ == "__main__":
    unittest.main()
