"""AC-7 (tasks/T073/SPEC.md): и dry-run, и реальное исполнение `prune`
выводят отчёт с перечнем того, что будет удалено/заархивировано
(dry-run) или было удалено/заархивировано (исполнение).

Не проверяет конкретную формулировку («будет удалено» и т.п. — выбор
разработчика): только то, что отчёт называет КОНКРЕТНЫЕ, узнаваемые
предметы уборки (имя лог-файла, текст alert-сообщения), а не абстрактный
«готово». Оба режима гоняются на ОДИНАКОВОЙ фикстуре (перед dry-run
кандидаты ещё существуют, перед execute — свежая фикстура, из другого
setUp) — план и факт называют один и тот же материал.

Лог-кандидат — не единственная задача с логом в фикстуре: при N=1
задаче он тривиально попал бы в «последние N» (AC-5) и никогда не стал
бы кандидатом на удаление независимо от возраста. N задач-заполнителей
с заведомо большими номерами (тот же приём, что и test_ac5_prune_
execute_logs_retention.py) выталкивают кандидата за пределы «последних
N» — только тогда 200-дневный возраст делает его кандидатом.

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

LOG_NAME = "T00001-analyst-1.log"
ALERT_MESSAGE = "инцидент, подлежащий архивации в отчёте prune"


class PruneReportContentsTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        from orchestrator import prune  # noqa: E402
        self.prune = prune

        config.LOGS.mkdir(parents=True, exist_ok=True)
        conn = store.db()
        store.insert_task(conn, "T00001", "Задача-кандидат отчёта prune",
                          "done", "task/t00001-x", config.DEFAULT_TARGET, 25.0)
        self.log_path = config.LOGS / LOG_NAME
        self.log_path.write_text("лог прогона\n", encoding="utf-8")
        old_mtime = time.time() - 200 * 86400
        os.utime(self.log_path, (old_mtime, old_mtime))

        n = config.LOG_RETENTION_KEEP_TASKS
        for i in range(n):
            fid = f"T{90000 + i}"
            store.insert_task(conn, fid, f"Заполнитель {fid}", "done",
                              f"task/{fid.lower()}-x", config.DEFAULT_TARGET, 25.0)
            fpath = config.LOGS / f"{fid}-analyst-1.log"
            fpath.write_text("лог прогона\n", encoding="utf-8")
            os.utime(fpath, (old_mtime, old_mtime))

        alerts.raise_alert(conn, None, "incident", "test.ac7", ALERT_MESSAGE)
        old_ts = time.strftime("%Y-%m-%d %H:%M:%SZ",
                               time.gmtime(time.time() - 200 * 86400))
        conn.execute("UPDATE alerts SET ts=? WHERE message=?",
                     (old_ts, ALERT_MESSAGE))
        conn.commit()

    def test_ac7_dry_run_report_names_the_planned_log_and_alert(self):
        out = capture(self.prune.cmd_prune)

        self.assertIn(LOG_NAME, out,
                     f"отчёт dry-run обязан назвать лог-файл кандидата:\n{out}")
        self.assertIn(ALERT_MESSAGE, out,
                     f"отчёт dry-run обязан назвать alert-кандидата:\n{out}")

    def test_ac7_execute_report_names_the_removed_log_and_archived_alert(self):
        out = capture(self.prune.cmd_prune, True)

        self.assertIn(LOG_NAME, out,
                     f"отчёт исполнения обязан назвать удалённый лог-файл:\n{out}")
        self.assertIn(ALERT_MESSAGE, out,
                     f"отчёт исполнения обязан назвать заархивированный alert:\n{out}")
        # И факт исполнения — не просто повтор dry-run плана.
        self.assertFalse(self.log_path.exists())


if __name__ == "__main__":
    unittest.main()
