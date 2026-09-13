"""Юнит-тесты orchestrator/release.py (SPEC T062).

Приёмочные тесты (tasks/T062/acceptance_tests) кроют AC-1..AC-5 сквозным
путём через `release.cmd_release`; здесь — сам модуль в изоляции: точная
форма журнальной записи, поведение при отсутствии lease (журнал не
пишется — решение разработчика, AC-3) и защита от гонки между чтением
строки и её удалением, тем же приёмом, что `tests/test_lease.py`/
`tests/test_merge_lock.py` уже применили к своим модулям.
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, release, store  # noqa: E402
from tests.sandbox import BudgetSeededTmpRootTest, _ts_ago, capture  # noqa: E402

HOLDER_SESSION = "session-holder"
HOLDER_PID = 424242
HOLDER_HOST = "holder-host"


class ReleaseTest(BudgetSeededTmpRootTest):

    def insert_lease(self, task_id: str, session_id: str, pid: int,
                     hostname: str, heartbeat_ts: str) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def row(self, task_id: str = None):
        return store.lease_row(store.db(), task_id or self.TASK)

    def journal(self):
        return store.task_steps(store.db(), self.TASK)

    def test_deletes_the_lease_row(self):
        self.insert_lease(self.TASK, HOLDER_SESSION, HOLDER_PID,
                          HOLDER_HOST, store.now())

        capture(release.cmd_release, self.TASK)

        self.assertIsNone(self.row())

    def test_journals_former_holder_with_numeric_heartbeat_age(self):
        """HOLDER_HOST — чужой host с ещё свежим (123 сек) heartbeat:
        после исправления R1-F1 `warn_foreign_live` тоже журналирует
        отдельной записью ДО снятия — здесь проверяется именно запись
        самого снятия (`action == "lease снят Оператором"`), а не первая
        запись журнала."""
        stale_ts = _ts_ago(123)
        self.insert_lease(self.TASK, HOLDER_SESSION, HOLDER_PID,
                          HOLDER_HOST, stale_ts)

        capture(release.cmd_release, self.TASK)

        steps = self.journal()
        release_steps = [s for s in steps if s["action"] == "lease снят Оператором"]
        self.assertEqual(len(release_steps), 1, steps)
        entry = release_steps[0]
        self.assertEqual(entry["actor"], "operator")
        self.assertIn(HOLDER_SESSION, entry["detail"])
        self.assertIn(str(HOLDER_PID), entry["detail"])
        self.assertIn(HOLDER_HOST, entry["detail"])
        # heartbeat_ts зафиксирован 123 сек назад — журнал обязан назвать
        # возраст, а не сырой timestamp.
        self.assertRegex(entry["detail"], r"12[0-9] сек")

    def test_removes_fresh_lease_without_checking_staleness(self):
        self.insert_lease(self.TASK, HOLDER_SESSION, HOLDER_PID,
                          HOLDER_HOST, store.now())

        capture(release.cmd_release, self.TASK)

        self.assertIsNone(self.row())

    def test_removes_stale_lease(self):
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 100)
        self.insert_lease(self.TASK, HOLDER_SESSION, HOLDER_PID,
                          HOLDER_HOST, stale_ts)

        capture(release.cmd_release, self.TASK)

        self.assertIsNone(self.row())

    def test_no_lease_prints_friendly_message_and_does_not_journal(self):
        self.assertIsNone(self.row())

        output = capture(release.cmd_release, self.TASK)

        self.assertTrue(output.strip())
        self.assertEqual(self.journal(), [],
                         "release без lease не должен писать журнал "
                         "(решение разработчика, AC-3)")

    def test_no_lease_does_not_raise_or_exit(self):
        result = release.cmd_release(self.TASK)

        self.assertIsNone(result)

    def test_does_not_touch_lease_of_another_task(self):
        store.insert_task(store.db(), "T002", "Другая задача", "in_dev",
                          "task/t002-drugaya", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.insert_lease("T002", "session-other", 1, "other-host",
                          store.now())

        capture(release.cmd_release, self.TASK)

        self.assertIsNotNone(self.row("T002"),
                             "release чужой задачи снял lease T002")

    # ------------------------------------- предупреждение о чужом lease
    # (SPEC 01M1NEEYSP0QWPMXHG0BK591M7) — сквозной путь AC-1..AC-7 уже
    # покрыт приёмочными тестами задачи; здесь — что вызов действительно
    # подключён к `lease.warn_foreign_live` (не дублирует его логику).
    # Своего host (не HOLDER_HOST выше) лизинг-строка нужна здесь только
    # затем, чтобы pid реально был проверяем этим тестом через
    # `liveness._pid_alive(os.getpid())` — `foreign_live_lease` после
    # исправления R1-F1 сочла бы живой и лизинг-строку HOLDER_HOST'а
    # (чужой host уже не требует проверки pid), но `os.getpid()` работает
    # без риска флуктуаций между прогонами.

    def test_release_warns_on_foreign_live_lease(self):
        """Ловит мутацию: если `cmd_release` перестанет звать
        `lease.warn_foreign_live` (или начнёт звать его ПОСЛЕ снятия
        lease), вывод перестанет называть держателя чужого живого
        lease — сквозной путь к уже протестированной в изоляции логике
        `lease.py`."""
        self.insert_lease(self.TASK, "sess-live-holder", os.getpid(),
                          socket.gethostname(), _ts_ago(5))

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-current"}):
            output = capture(release.cmd_release, self.TASK)

        self.assertIn("sess-live-holder", output)

    def test_release_journals_the_warning_as_an_extra_entry(self):
        """Ловит мутацию: если вызов `lease.warn_foreign_live` уберут из
        `cmd_release`, журнал понесёт только запись самого снятия lease
        вместо двух записей — предупреждение перестанет дублироваться
        событием журнала (требование 3)."""
        self.insert_lease(self.TASK, "sess-live-holder", os.getpid(),
                          socket.gethostname(), _ts_ago(5))

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-current"}):
            capture(release.cmd_release, self.TASK)

        steps = self.journal()
        self.assertEqual(len(steps), 2, steps)
        self.assertTrue(any("sess-live-holder" in s["detail"] for s in steps
                            if s["detail"]))

    def test_row_replaced_between_read_and_delete_is_not_removed(self):
        """Гонка: строка сменила держателя между `lease_row` и удалением
        (перехват `lease.acquire` другой сессией) — `release_lease`
        удаляет по паре (task_id, session_id), поэтому устаревшая
        картина, прочитанная `cmd_release`, не сносит уже новую строку.

        REVIEW T062, итерация 1, Замечание 1: no-op под гонкой не должен
        выглядеть как успех — ни в журнале, ни в печатном сообщении.
        `store.lease_row` замокан на весь вызов `cmd_release`, поэтому
        `warn_foreign_live` тоже видит устаревшую строку (HOLDER_HOST —
        чужой host, heartbeat свежий) и после исправления R1-F1 честно
        журналирует своё предупреждение — здесь проверяется отсутствие
        именно записи о СНЯТИИ (`action == "lease снят Оператором"`), не
        пустота журнала целиком."""
        self.insert_lease(self.TASK, HOLDER_SESSION, HOLDER_PID,
                          HOLDER_HOST, store.now())
        stale_row = store.lease_row(store.db(), self.TASK)

        with mock.patch.object(store, "lease_row", return_value=stale_row):
            # Строку успели перехватить уже после чтения, которое увидел
            # cmd_release (замоканного выше) — session_id сменился.
            conn = store.db()
            conn.execute(
                "UPDATE leases SET session_id=? WHERE task_id=?",
                ("session-new-holder", self.TASK))
            conn.commit()

            output = capture(release.cmd_release, self.TASK)

        row = self.row()
        self.assertIsNotNone(row, "release снял строку нового держателя")
        self.assertEqual(row["session_id"], "session-new-holder")
        release_steps = [s for s in self.journal()
                        if s["action"] == "lease снят Оператором"]
        self.assertEqual(release_steps, [],
                         "no-op под гонкой не должен журналироваться "
                         "как свершившееся снятие")
        self.assertNotIn("lease снят Оператором", output,
                         "печать не должна заявлять успех при no-op")
        self.assertIn(HOLDER_SESSION, output,
                      "сообщение о гонке должно называть устаревшего "
                      "держателя, который читал release")


if __name__ == "__main__":
    unittest.main()
