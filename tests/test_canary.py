"""Юнит-тесты `orchestrator/canary.py` (tasks/T065/SPEC.md).

Сквозной сценарий (заведение задач, прогон auto-циклом до гейтов,
kill на merge_gate, sha main до/после) уже покрыт приёмочными тестами
`tasks/T065/acceptance_tests/` (AC-1..AC-5, реальный git) — здесь только
то, что они не изолируют: чистая арифметика отклонения от бейзлайна,
сборка отчёта/метрик из журнала, поведение CLI на плохом вводе и факт
пометки/учёта canary в `store`/`catalog`/`retro` без полного прогона
конвейера.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import canary, catalog, config, retro, store  # noqa: E402
from tests.sandbox import capture  # noqa: E402


class DeviationTest(unittest.TestCase):
    """`canary._deviation_exceeds` — чистая арифметика (SPEC, требование 5)."""

    def test_within_threshold_is_not_a_deviation(self):
        self.assertFalse(canary._deviation_exceeds(140, 100, 0.5))

    def test_over_threshold_is_a_deviation(self):
        self.assertTrue(canary._deviation_exceeds(160, 100, 0.5))

    def test_exactly_at_threshold_is_not_a_deviation(self):
        # |отклонение| > ratio, не >=: ровно на пороге — не превышение.
        self.assertFalse(canary._deviation_exceeds(150, 100, 0.5))

    def test_deviation_is_symmetric_below_baseline(self):
        self.assertTrue(canary._deviation_exceeds(40, 100, 0.5))

    def test_zero_baseline_and_zero_current_is_no_deviation(self):
        self.assertFalse(canary._deviation_exceeds(0, 0, 0.5))

    def test_zero_baseline_and_nonzero_current_is_full_deviation(self):
        self.assertTrue(canary._deviation_exceeds(1, 0, 0.5))


class BaselineWarningsTest(unittest.TestCase):
    """`canary._baseline_warnings` — предупреждение печатается по каждому
    измерению независимо и молчит, когда оба в пределах порога."""

    def test_no_warning_when_both_metrics_within_threshold(self):
        warnings = canary._baseline_warnings(
            {"cost_usd": 10.0, "steps": 12}, {"cost_usd": 9.0, "steps": 10})
        self.assertEqual(warnings, [])

    def test_warns_on_steps_deviation_only(self):
        warnings = canary._baseline_warnings(
            {"cost_usd": 10.0, "steps": 20}, {"cost_usd": 10.0, "steps": 10})
        self.assertEqual(len(warnings), 1)
        self.assertIn("шагам", warnings[0])

    def test_warns_on_both_metrics(self):
        warnings = canary._baseline_warnings(
            {"cost_usd": 30.0, "steps": 20}, {"cost_usd": 10.0, "steps": 10})
        self.assertEqual(len(warnings), 2)


class MetricsFromJournalTest(unittest.TestCase):
    """`canary._task_metrics`/`_step_count`/`_escalation_notes` — сборка из
    журнала БД, без git и без FSM."""

    TASK = "T900"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача",
                          "killed", "task/t900-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

    def test_steps_counts_only_state_transitions(self):
        store.journal(self.conn, self.TASK, "runner", "agent run started", "")
        store.journal(self.conn, self.TASK, "fsm", "state -> spec_gate", "")
        store.journal(self.conn, self.TASK, "canary", "state -> in_dev", "")
        store.journal(self.conn, self.TASK, "operator", "auto старт", "")

        self.assertEqual(canary._step_count(store.task_steps(self.conn, self.TASK)), 2)

    def test_escalation_notes_collect_every_episode_in_order(self):
        store.journal(self.conn, self.TASK, "fsm", "state -> escalated", "первая")
        store.journal(self.conn, self.TASK, "operator", "state -> in_dev", "")
        store.journal(self.conn, self.TASK, "fsm", "state -> escalated", "вторая")

        notes = canary._escalation_notes(store.task_steps(self.conn, self.TASK))

        self.assertEqual(notes, ["первая", "вторая"])

    def test_task_metrics_shape_and_values(self):
        store.update_task(self.conn, self.TASK, spent_usd=3.25, review_iters=2)
        store.journal(self.conn, self.TASK, "fsm", "state -> spec_gate", "")
        store.journal(self.conn, self.TASK, "canary",
                      "state -> killed", "kill switch")

        metrics = canary._task_metrics(self.conn, self.TASK)

        self.assertEqual(metrics["steps"], 2)
        self.assertEqual(metrics["cost_usd"], 3.25)
        self.assertEqual(metrics["review_iterations"], 2)
        self.assertEqual(metrics["escalations"], [])
        self.assertEqual(metrics["outcome"], "killed")

    def test_summary_sums_across_tasks(self):
        metrics = {
            "T900": {"steps": 3, "cost_usd": 1.5},
            "T901": {"steps": 5, "cost_usd": 2.5},
        }
        self.assertEqual(canary._summary(metrics), {"cost_usd": 4.0, "steps": 8})


class ReportAndBaselineIOTest(unittest.TestCase):
    """`canary._write_report`/`_write_baseline`/`_read_baseline` — I/O в
    `.artel/canary/`, без git."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = mock.patch.object(config, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_read_baseline_missing_file_is_none(self):
        self.assertIsNone(canary._read_baseline())

    def test_write_then_read_baseline_roundtrips(self):
        canary._write_baseline({"cost_usd": 1.0, "steps": 2})
        self.assertEqual(canary._read_baseline(), {"cost_usd": 1.0, "steps": 2})

    def test_write_report_contains_tasks_and_summary(self):
        metrics = {"T900": {"steps": 1, "cost_usd": 0.0,
                            "review_iterations": 0, "escalations": [],
                            "outcome": "killed"}}
        summary = {"cost_usd": 0.0, "steps": 1}

        path = canary._write_report("20260101T000000Z", metrics, summary)

        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["tasks"], metrics)
        self.assertEqual(data["summary"], summary)
        self.assertEqual(path, self.root / ".artel" / "canary" / "20260101T000000Z.json")


class CmdCanaryBadInputTest(unittest.TestCase):
    """CLI-отказы `canary.cmd_canary` на плохом вводе (SPEC, требование 1:
    команда обязана работать с любым переданным каталогом `*.md`, а
    значит и явно отказывать на непригодном)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_missing_directory_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            canary.cmd_canary(str(self.root / "нет-такого"))
        self.assertIn("каталог не найден", str(ctx.exception))

    def test_directory_without_md_files_exits(self):
        empty = self.root / "empty"
        empty.mkdir()
        (empty / "не-тз.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            canary.cmd_canary(str(empty))
        self.assertIn("нет файлов *.md", str(ctx.exception))


class StoreAndCatalogMarkingTest(unittest.TestCase):
    """`tasks.is_canary` — колонка БД, не `title` (требование 6): заведение,
    `total_spent`, пометка в `status`, пометка/её отсутствие в RETRO."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, "T900", "фича X", "spec_gate",
                          "task/t900-x", config.DEFAULT_TARGET, 50.0,
                          is_canary=True)
        store.insert_task(self.conn, "T901", "фича Y", "spec_gate",
                          "task/t901-y", config.DEFAULT_TARGET, 50.0)

    def test_is_canary_defaults_to_false(self):
        self.assertFalse(bool(store.get_task(self.conn, "T901")["is_canary"]))

    def test_title_never_carries_the_mark(self):
        self.assertNotIn("canary", store.get_task(self.conn, "T900")["title"].lower())

    def test_total_spent_counts_canary_task_alongside_product(self):
        self.conn.execute("UPDATE tasks SET spent_usd=? WHERE id=?", (5.0, "T900"))
        self.conn.execute("UPDATE tasks SET spent_usd=? WHERE id=?", (2.0, "T901"))
        self.conn.commit()
        self.assertEqual(store.total_spent(self.conn), 7.0)

    def test_status_marks_only_the_canary_row(self):
        out = capture(catalog.cmd_status)
        canary_line = next(l for l in out.splitlines() if l.startswith("T900"))
        product_line = next(l for l in out.splitlines() if l.startswith("T901"))
        self.assertIn("canary", canary_line.lower())
        self.assertNotIn("canary", product_line.lower())

    def test_retro_marks_only_the_canary_task(self):
        store.set_state(self.conn, "T900", "killed", "operator",
                        expected_state="spec_gate", detail="kill switch")
        store.set_state(self.conn, "T901", "killed", "operator",
                        expected_state="spec_gate", detail="kill switch")

        canary_retro = retro.build_killed(self.conn, "T900")
        product_retro = retro.build_killed(self.conn, "T901")

        self.assertIn("канареечная", canary_retro.lower())
        self.assertNotIn("канаре", product_retro.lower())
        self.assertNotIn("canary", product_retro.lower())


if __name__ == "__main__":
    unittest.main()
