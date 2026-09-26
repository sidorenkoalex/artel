"""AC-8 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: миграция сохраняет строки метрик,
заведённые до задачи, под именем набора по умолчанию.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. БД со строками `canary_baseline`/`canary_runs`, заведёнными до этой
задачи, после миграции несёт те же строки под именем набора по умолчанию,
с прежними значениями `steps`, `cost_usd`, `review_iterations`; ни одна
строка не потеряна.

«До этой задачи» воспроизводится буквально: таблицы заводятся тем же
`CREATE TABLE`, каким их заводил пульт до задачи
(`_util.RUNS_CREATE_BEFORE`/`BASELINE_CREATE_BEFORE`), затем в них
кладутся строки, и только после этого зовётся миграция. Иначе тест
проверял бы не миграцию, а сегодняшнюю схему.

Миграция зовётся двумя входами подряд (`store.migrate` и
`store._ensure_canary_tables`) — планка не фиксирует, в котором из них
живёт перенос: таблицы канарейки заводятся лениво, и оба входа штатно
идемпотентны.

Красен до реализации: в БД нет колонки имени набора вовсе, а
`_util.default_set_name` падает на отсутствующем параметре подписи
`canary.cmd_canary`.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import store  # noqa: E402

#: Строки бейзлайна «до задачи»: (title, steps, cost_usd, review_iterations).
BASELINES_BEFORE = (
    ("canary-version-json", 5, 6.54, 0),
    ("prostaya-pravka", 12, 16.97, 2),
)

#: Строки прогонов «до задачи»: (run_stamp, title, task_id, steps, cost_usd,
#: review_iterations, verdict).
RUNS_BEFORE = (
    ("20260913T090000Z", "canary-version-json", "01AAA", 5, 6.54, 0, "green"),
    ("20260926T090000Z", "canary-version-json", "01BBB", 9, 17.66, 1, "red"),
)


class MigrationKeepsOldRowsTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.conn = _util.old_schema_conn(Path(tmp.name) / "state.db")
        for title, steps, cost, iterations in BASELINES_BEFORE:
            self.conn.execute(
                "INSERT INTO canary_baseline (title, steps, cost_usd,"
                " review_iterations, updated_at) VALUES (?,?,?,?,?)",
                (title, steps, cost, iterations, "2026-09-13 09:00:00Z"))
        for stamp, title, task_id, steps, cost, iterations, verdict in RUNS_BEFORE:
            self.conn.execute(
                "INSERT INTO canary_runs (run_stamp, title, task_id, steps,"
                " cost_usd, review_iterations, escalations, outcome,"
                " expected_escalation, actual_escalation, marker_mismatch,"
                " created_at, main_sha, verdict)"
                " VALUES (?,?,?,?,?,?,0,'killed','no',0,0,?,?,?)",
                (stamp, title, task_id, steps, cost, iterations,
                 "2026-09-13 09:00:00Z", "deadbeef", verdict))
        self.conn.commit()

    def _migrate(self):
        store.migrate(self.conn)
        store._ensure_canary_tables(self.conn)

    def _rows(self, table):
        return self.conn.execute(f"SELECT * FROM {table}").fetchall()

    def _set_value(self, row, table, before):
        columns = _util.new_columns(self.conn, table, before)
        self.assertTrue(columns,
                        f"у {table} нет ни одной новой колонки — имени "
                        f"набора в строке метрик нет")
        values = {row[column] for column in columns}
        return values

    def test_ac8_baseline_rows_survive_migration_under_the_default_set(self):
        """Строки `canary_baseline`, заведённые до задачи, после миграции
        на месте — с прежними метриками и под именем набора по умолчанию.

        Ловит мутацию: миграция меняет ключ таблицы пересозданием
        (`DROP TABLE` + `CREATE TABLE` с новым PK) без переноса строк —
        бейзлайны, снятые на живых прогонах (13.09 — $6.54), исчезли бы, и
        первый же прогон после мержа завёл бы их заново, потеряв точку
        сравнения.
        """
        default_name = _util.default_set_name()

        self._migrate()

        rows = self._rows("canary_baseline")
        self.assertEqual(len(BASELINES_BEFORE), len(rows),
                         "число строк бейзлайна изменилось миграцией")
        for title, steps, cost, iterations in BASELINES_BEFORE:
            matched = [row for row in rows if row["title"] == title]
            self.assertEqual(1, len(matched), f"бейзлайн {title}")
            row = matched[0]
            self.assertEqual((steps, cost, iterations),
                             (row["steps"], row["cost_usd"],
                              row["review_iterations"]))
            self.assertIn(default_name,
                          self._set_value(row, "canary_baseline",
                                          _util.BASELINE_COLUMNS_BEFORE))

    def test_ac8_run_rows_survive_migration_under_the_default_set(self):
        """Строки `canary_runs`, заведённые до задачи, после миграции на
        месте — с прежними метриками и под именем набора по умолчанию.

        Ловит мутацию: колонка имени набора добавлена `add_column` и
        остаётся `NULL` у старых строк — журнал прогонов до мержа перестал
        бы принадлежать какому-либо набору, и `merges_since_last_green_run`
        (вход гейта пина) считал бы возраст по строкам без набора.
        """
        default_name = _util.default_set_name()

        self._migrate()

        rows = self._rows("canary_runs")
        self.assertEqual(len(RUNS_BEFORE), len(rows),
                         "число строк прогонов изменилось миграцией")
        for stamp, _title, _task, steps, cost, iterations, _verdict in RUNS_BEFORE:
            matched = [row for row in rows if row["run_stamp"] == stamp]
            self.assertEqual(1, len(matched), f"прогон {stamp}")
            row = matched[0]
            self.assertEqual((steps, cost, iterations),
                             (row["steps"], row["cost_usd"],
                              row["review_iterations"]))
            self.assertIn(default_name,
                          self._set_value(row, "canary_runs",
                                          _util.RUN_COLUMNS_BEFORE))


if __name__ == "__main__":
    unittest.main()
