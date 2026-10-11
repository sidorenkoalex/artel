"""AC-4 (tasks/T073/SPEC.md): команда `prune`, вызванная без флага
реального исполнения (dry-run по умолчанию), не удаляет и не
архивирует ничего и выводит план предстоящих действий.

Интерфейс — см. tasks/T073/acceptance_tests/test_ac5_prune_execute_logs_
retention.py (докстринг): `orchestrator.prune.cmd_prune(execute: bool =
False)`. Здесь — минимальная фикстура (один заведомо просроченный лог,
один заведомо просроченный alert), проверяющая режим по умолчанию
именно ПО ЕГО ПОВЕДЕНИЮ (ничего не удалено/не заархивировано), план
печатается отдельно AC-7.

Красен до реализации: `orchestrator/prune.py` не существует.
"""
import os
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import alerts, catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class PruneDryRunDefaultTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        from orchestrator import prune  # noqa: E402
        self.prune = prune

        config.LOGS.mkdir(parents=True, exist_ok=True)
        self.old_log = config.LOGS / "T0001-analyst-1.log"
        self.old_log.write_text("лог прогона\n", encoding="utf-8")
        old_mtime = time.time() - 200 * 86400
        os.utime(self.old_log, (old_mtime, old_mtime))

        conn = store.db()
        alerts.raise_alert(conn, None, "incident", "test.ac4", "старый алерт")
        row = conn.execute(
            "SELECT id FROM alerts WHERE message='старый алерт'").fetchone()
        old_ts = time.strftime("%Y-%m-%d %H:%M:%SZ",
                               time.gmtime(time.time() - 200 * 86400))
        conn.execute("UPDATE alerts SET ts=? WHERE id=?", (old_ts, row["id"]))
        conn.commit()
        self.alert_id = row["id"]

    def test_ac4_dry_run_by_default_deletes_no_logs(self):
        capture(self.prune.cmd_prune)

        self.assertTrue(self.old_log.exists(),
                        "prune без флага не обязан удалять логи")

    def test_ac4_dry_run_by_default_archives_no_alerts(self):
        capture(self.prune.cmd_prune)

        conn = store.db()
        row = conn.execute("SELECT * FROM alerts WHERE id=?",
                          (self.alert_id,)).fetchone()
        self.assertIsNotNone(
            row, "prune без флага не обязан выносить alert из alerts")

    def test_ac4_default_call_has_no_execute_effect_positional_or_keyword(self):
        """Дефолт — именно `execute=False`/без аргумента, а не «включён
        по умолчанию» с отдельным флагом отключения: оба вызова без
        явного включения обязаны быть безопасны."""
        capture(self.prune.cmd_prune, False)

        self.assertTrue(self.old_log.exists())


if __name__ == "__main__":
    unittest.main()
