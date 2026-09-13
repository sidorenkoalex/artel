"""Юнит-тесты `orchestrator/prune.py` и опорных функций `store.py`
(alerts_older_than/archive_alert) — tasks/T073/SPEC.md, требование 3.

Полную таблицу истинности «90 дней И вне последних N задач» и отчёт
`prune` уже гоняют приёмочные тесты (tasks/T073/acceptance_tests/
test_ac4..test_ac7); здесь — более мелкие срезы поведения (архивная
таблица напрямую, повторный прогон, отсутствие каталога логов), не
дублирующие их построчно.
"""
import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, catalog, config, prune, store  # noqa: E402
from tests.sandbox import InitializedTmpRootTest, TmpRootTest, capture  # noqa: E402


def _ts(days_ago: int) -> str:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return when.strftime("%Y-%m-%d %H:%M:%SZ")


class PruneLogCandidatesTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        config.LOGS.mkdir(parents=True, exist_ok=True)

    def _log(self, task_id: str, age_days: int) -> Path:
        path = config.LOGS / f"{task_id}-analyst-1.log"
        path.write_text("лог\n", encoding="utf-8")
        mtime = time.time() - age_days * 86400
        os.utime(path, (mtime, mtime))
        return path

    def test_no_logs_directory_yields_no_candidates(self):
        conn = store.db()

        self.assertEqual(prune._log_candidates(conn), [])

    def test_log_of_task_missing_from_db_is_a_candidate_when_old(self):
        """Задачи с этим task_id в БД нет вовсе (осиротевший лог) — она
        не входит в «последние N» ни при каком прочтении списка задач,
        поэтому решает только возраст."""
        old = self._log("T09999", 200)
        conn = store.db()

        candidates = prune._log_candidates(conn)

        self.assertIn(old, candidates)

    def test_log_of_orphan_task_survives_while_recent(self):
        recent = self._log("T09999", 5)
        conn = store.db()

        candidates = prune._log_candidates(conn)

        self.assertNotIn(recent, candidates)

    def test_repeated_execute_on_already_pruned_state_is_a_no_op(self):
        store.insert_task(store.db(), "T00001", "Задача", "done",
                          "task/t00001-x", config.DEFAULT_TARGET, 25.0)
        self._log("T00001", 200)
        conn = store.db()
        prune.cmd_prune(True)
        self.assertEqual(prune._log_candidates(conn), [])

        out = capture(prune.cmd_prune, True)

        self.assertIn("нечего убирать", out)


class PruneCanaryDiagCandidatesTest(InitializedTmpRootTest):
    """`prune._canary_diag_candidates` (SPEC 01M1TKP269W9JN3NBJCR5Q6C3B,
    требование 4/AC-9) — тот же порог давности, что и `.artel/logs/`,
    БЕЗ второго условия «последние N задач» (canary `task_id` никогда не
    попадает в БД пульта — см. PLAN.md этой задачи, «Подход»); полную
    сквозную проверку prune --execute на реальном дереве несёт залоченная
    планка (`test_ac9_prune_retention_for_canary_dir.py`), здесь —
    сама функция-отбор в изоляции."""

    def _diag(self, run_stamp: str, task_id: str, age_days: float) -> Path:
        path = config.ROOT / ".artel" / "canary" / run_stamp / task_id / "steps.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("журнал\n", encoding="utf-8")
        mtime = time.time() - age_days * 86400
        os.utime(path, (mtime, mtime))
        return path

    def test_no_canary_dir_yields_no_candidates(self):
        """Ловит мутацию: проверка `root.is_dir()` убрана — отсутствие
        `.artel/canary/` привело бы к исключению вместо пустого списка
        кандидатов."""
        self.assertEqual(prune._canary_diag_candidates(), [])

    def test_old_diagnostics_file_is_a_candidate(self):
        """Ловит мутацию: сравнение `st_mtime < cutoff` инвертировано
        или `config.LOG_RETENTION_DAYS` не используется — файл
        диагностики старше порога давности не попал бы в кандидаты на
        удаление."""
        old = self._diag("20200101T000000Z", "T00001",
                         config.LOG_RETENTION_DAYS + 1)

        self.assertIn(old, prune._canary_diag_candidates())

    def test_fresh_diagnostics_file_is_not_a_candidate(self):
        """Ловит мутацию: отбор по давности инвертирован или выпал
        вовсе — свежий файл диагностики моложе `config.LOG_RETENTION_
        DAYS` ошибочно попал бы под удаление."""
        fresh = self._diag("20260101T000000Z", "T00002", 1)

        self.assertNotIn(fresh, prune._canary_diag_candidates())

    def test_execute_removes_old_diagnostics_and_reports_it(self):
        """Ловит мутацию: `_canary_diag_candidates` собирается, но не
        подключена к удалению/отчёту `cmd_prune --execute` — старый
        файл диагностики пережил бы `prune --execute`, либо отчёт
        молчал бы о найденной диагностике канарейки."""
        old = self._diag("20200101T000000Z", "T00003",
                         config.LOG_RETENTION_DAYS + 1)

        out = capture(prune.cmd_prune, True)

        self.assertFalse(old.exists())
        self.assertIn("диагностика канарейки", out)


class PruneAlertArchiveStoreTest(InitializedTmpRootTest):
    """store.alerts_older_than/archive_alert напрямую — опора `prune` на
    хранилище (SQL живёт только в store.py, ADR-0003 3ж)."""

    def test_alerts_older_than_excludes_recent_and_includes_old(self):
        conn = store.db()
        alerts.raise_alert(conn, None, "incident", "test", "старый")
        alerts.raise_alert(conn, None, "incident", "test", "свежий")
        conn.execute("UPDATE alerts SET ts=? WHERE message='старый'",
                     (_ts(200),))
        conn.execute("UPDATE alerts SET ts=? WHERE message='свежий'",
                     (_ts(1),))
        conn.commit()

        old_rows = store.alerts_older_than(conn, _ts(90))

        messages = {r["message"] for r in old_rows}
        self.assertIn("старый", messages)
        self.assertNotIn("свежий", messages)

    def test_archive_alert_moves_row_and_keeps_original_id(self):
        conn = store.db()
        alerts.raise_alert(conn, None, "incident", "test", "к архивации")
        row = conn.execute(
            "SELECT id FROM alerts WHERE message='к архивации'").fetchone()

        store.archive_alert(conn, row["id"])

        self.assertIsNone(store.get_alert(conn, row["id"]))
        archived = conn.execute(
            "SELECT * FROM alerts_archive WHERE id=?", (row["id"],)).fetchone()
        self.assertIsNotNone(archived)
        self.assertEqual(archived["message"], "к архивации")
        self.assertIsNotNone(archived["archived_ts"])

    def test_archive_alert_on_unknown_id_is_a_no_op(self):
        conn = store.db()

        store.archive_alert(conn, 404)

        self.assertEqual(
            conn.execute("SELECT * FROM alerts_archive").fetchall(), [])


class PruneReportEmptyStateTest(InitializedTmpRootTest):

    def test_dry_run_report_says_nothing_to_clean_up_when_nothing_qualifies(self):
        out = capture(prune.cmd_prune)

        self.assertIn("нечего убирать", out)

    def test_execute_report_says_nothing_to_clean_up_when_nothing_qualifies(self):
        out = capture(prune.cmd_prune, True)

        self.assertIn("нечего убирать", out)


if __name__ == "__main__":
    unittest.main()
