"""Приёмочный тест T094 — AC-6 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-6: «Retention логов отбирает задачи к сохранению/удалению по дате
закрытия из журнала, а не по числовому номеру; задачи с идентификатором
Tnnn участвуют в этом же датовом отборе, не в отборе «последние N по
номеру».»

Красен до реализации: сегодня `prune._kept_task_ids` (`orchestrator/
prune.py`) сортирует задачи по `store.task_number(r["id"])` — «последние
N ПО НОМЕРУ», буквально то, что критерий запрещает. Сценарий ниже
нарочно сталкивает номер и дату закрытия лбами: `T00005` (номер БОЛЬШЕ)
закрыта 200 дней назад, `T00002` (номер МЕНЬШЕ) закрыта вчера. По
номеру «последней» была бы `T00005` — её лог сегодня survives, лог
`T00002` — кандидат на удаление; по дате закрытия (AC-6) — наоборот.
Тест утверждает исход ПО ДАТЕ, поэтому падает на сегодняшнем коде.

`config.LOG_RETENTION_KEEP_TASKS` берётся из `config`, не литералом
(урок 28.08, `skills/test-authoring.md`): патчится только чтобы держать
сценарий из двух задач компактным, само число не захардкожено в
арифметике теста.
"""
import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, prune, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


def _ts(days_ago: int) -> str:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return when.strftime("%Y-%m-%d %H:%M:%SZ")


class Ac6RetentionByCloseDateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        config.LOGS.mkdir(parents=True, exist_ok=True)
        self._patch_keep = mock.patch.object(config, "LOG_RETENTION_KEEP_TASKS", 1)
        self._patch_keep.start()
        self.addCleanup(self._patch_keep.stop)

    def _log(self, task_id: str, age_days: int) -> Path:
        path = config.LOGS / f"{task_id}-analyst-1.log"
        path.write_text("лог\n", encoding="utf-8")
        mtime = time.time() - age_days * 86400
        os.utime(path, (mtime, mtime))
        return path

    def _closed_task(self, task_id: str, closed_days_ago: int) -> None:
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {task_id}", "done",
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.journal(conn, task_id, "operator", "state -> done", "")
        conn.execute(
            "UPDATE steps SET ts=? WHERE task_id=? AND action='state -> done'",
            (_ts(closed_days_ago), task_id))
        conn.commit()

    def test_ac6_log_retention_follows_close_date_not_numeric_id(self):
        # Оба возраста mtime старше LOG_RETENTION_DAYS — критерий
        # «AND» из docs/retention.md решает только пункт «последние N».
        older_days = config.LOG_RETENTION_DAYS + 50
        higher_number_old_close = self._log("T00005", older_days)
        lower_number_recent_close = self._log("T00002", older_days)

        self._closed_task("T00005", closed_days_ago=200)
        self._closed_task("T00002", closed_days_ago=1)

        conn = store.db()
        candidates = prune._log_candidates(conn)

        self.assertNotIn(
            lower_number_recent_close, candidates,
            "T00002 закрыта вчера — её лог обязан выжить как «последняя "
            "по дате закрытия» (AC-6), а не быть кандидатом на удаление")
        self.assertIn(
            higher_number_old_close, candidates,
            "T00005 закрыта 200 дней назад и не входит в «последние N по "
            "дате закрытия» (AC-6) — её лог обязан быть кандидатом на "
            "удаление, несмотря на больший числовой номер")


if __name__ == "__main__":
    unittest.main()
