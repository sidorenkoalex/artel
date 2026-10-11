"""AC-6 (tasks/T073/SPEC.md): команда `prune` с явным флагом реального
исполнения переносит alerts старше 90 дней в архивную таблицу и не
удаляет их (без следа — они обязаны быть НАЙДЕНЫ где-то, не пропасть).

Имя архивной таблицы — `alerts_archive`, выбор теста (SPEC называет
только «архивная таблица», не имя): естественное имя рядом с `alerts`,
которое тест и фиксирует разработчику как контракт (test-authoring:
«написанное тобой станет неизменяемой планкой»).

Красен до реализации: `orchestrator/prune.py` не существует, таблицы
`alerts_archive` нет.
"""
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import alerts, catalog, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


def _ts(days_ago: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%SZ",
                         time.gmtime(time.time() - days_ago * 86400))


class PruneArchivesOldAlertsTest(TmpRootTest):

    OLD_MESSAGE = "инцидент старше 90 дней"
    RECENT_MESSAGE = "инцидент моложе 90 дней"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        from orchestrator import prune  # noqa: E402
        self.prune = prune

        conn = store.db()
        alerts.raise_alert(conn, None, "incident", "test.ac6", self.OLD_MESSAGE)
        alerts.raise_alert(conn, None, "incident", "test.ac6", self.RECENT_MESSAGE)
        conn.execute("UPDATE alerts SET ts=? WHERE message=?",
                     (_ts(200), self.OLD_MESSAGE))
        conn.execute("UPDATE alerts SET ts=? WHERE message=?",
                     (_ts(5), self.RECENT_MESSAGE))
        conn.commit()

    def _alerts_rows(self, message: str) -> list:
        return store.db().execute(
            "SELECT * FROM alerts WHERE message=?", (message,)).fetchall()

    def _archive_rows(self, message: str) -> list:
        conn = store.db()
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "alerts_archive" not in tables:
            return []
        return conn.execute(
            "SELECT * FROM alerts_archive WHERE message=?", (message,)).fetchall()

    def test_ac6_old_alert_moved_to_archive_table_not_deleted(self):
        capture(self.prune.cmd_prune, True)

        self.assertEqual(
            self._alerts_rows(self.OLD_MESSAGE), [],
            "alert старше 90 дней обязан покинуть таблицу alerts (перенос, "
            "не дублирование)")
        archived = self._archive_rows(self.OLD_MESSAGE)
        self.assertEqual(
            len(archived), 1,
            "alert старше 90 дней обязан оказаться в архивной таблице ровно "
            "один раз — не удалён бесследно")
        self.assertEqual(archived[0]["kind"], "incident")
        self.assertEqual(archived[0]["source"], "test.ac6")

    def test_ac6_recent_alert_stays_in_alerts_table_unarchived(self):
        capture(self.prune.cmd_prune, True)

        self.assertEqual(
            len(self._alerts_rows(self.RECENT_MESSAGE)), 1,
            "alert младше 90 дней обязан остаться в alerts")
        self.assertEqual(
            self._archive_rows(self.RECENT_MESSAGE), [],
            "alert младше 90 дней не архивируется")


if __name__ == "__main__":
    unittest.main()
