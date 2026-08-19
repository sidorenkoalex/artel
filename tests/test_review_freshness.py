"""Тесты свежести вердикта ревью (см. tasks/T004/SPEC.md).

Сценарии гоняются на временной БД: artel.DB и artel.TASKS подменяются
на tmpdir, команды FSM вызываются напрямую.
"""
import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel  # noqa: E402

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
---

# REVIEW: проверка
"""

PLAN_READY_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
---

# PLAN: проверка
"""


class FreshVerdictIterationTest(unittest.TestCase):
    def test_next_iteration_is_fresh(self):
        self.assertEqual(artel.fresh_verdict_iteration({"iteration": "2"}, 1), 2)

    def test_first_verdict_is_fresh(self):
        self.assertEqual(artel.fresh_verdict_iteration({"iteration": "1"}, 0), 1)

    def test_already_counted_iteration_is_stale(self):
        self.assertIsNone(artel.fresh_verdict_iteration({"iteration": "1"}, 1))

    def test_older_iteration_is_stale(self):
        self.assertIsNone(artel.fresh_verdict_iteration({"iteration": "1"}, 2))

    def test_missing_iteration_is_stale(self):
        self.assertIsNone(artel.fresh_verdict_iteration({}, 0))

    def test_unparsable_iteration_is_stale(self):
        self.assertIsNone(artel.fresh_verdict_iteration({"iteration": "две"}, 0))

    def test_iteration_with_trailing_spaces(self):
        self.assertEqual(artel.fresh_verdict_iteration({"iteration": " 3 "}, 2), 3)


class ReviewFreshnessScenarioTest(unittest.TestCase):
    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks")):
            patcher = mock.patch.object(artel, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.tdir = artel.TASKS / self.TASK
        self.capture(artel.cmd_init)
        self.capture(artel.cmd_new, "Проверка вердикта")
        self.set_state("review")
        self.write_plan_ready()

    # ------------------------------------------------------------ утилиты

    def capture(self, fn, *args) -> str:
        """Вызывает команду FSM и возвращает её stdout."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def task_row(self) -> sqlite3.Row:
        return artel.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def set_state(self, state: str) -> None:
        conn = artel.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write_review(self, status: str, iteration: int) -> None:
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_MD.format(task=self.TASK, status=status, iteration=iteration),
            encoding="utf-8")

    def write_plan_ready(self) -> None:
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY_MD.format(task=self.TASK), encoding="utf-8")

    def journal_actions(self) -> list[tuple[str, str]]:
        return [(r["action"], r["detail"]) for r in artel.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def back_to_review_after_acceptance_reject(self) -> None:
        """review(approved #1) → acceptance → reject → in_dev → review."""
        self.write_review("approved", 1)
        self.capture(artel.cmd_advance, self.TASK)
        self.assertEqual(self.task_row()["state"], "acceptance")
        self.capture(artel.cmd_reject, self.TASK, "критерий 2 не выполнен")
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.capture(artel.cmd_advance, self.TASK)
        self.assertEqual(self.task_row()["state"], "review")

    # ----------------------------------------------------------- сценарии

    def test_stale_approved_does_not_pass_after_acceptance_reject(self):
        self.back_to_review_after_acceptance_reject()

        out = self.capture(artel.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "review")
        self.assertIn("уже учтён", out)
        self.assertIn("iteration: 2", out)

    def test_stale_verdict_is_journaled(self):
        self.back_to_review_after_acceptance_reject()

        self.capture(artel.cmd_advance, self.TASK)

        rejected = [d for a, d in self.journal_actions() if a == "переход отклонён"]
        self.assertEqual(len(rejected), 1)
        self.assertIn("уже учтён", rejected[0])

    def test_fresh_verdict_passes_to_acceptance(self):
        self.back_to_review_after_acceptance_reject()
        self.capture(artel.cmd_advance, self.TASK)  # старый вердикт не провозит

        self.write_review("approved", 2)
        self.capture(artel.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "acceptance")

    def test_changes_requested_counted_once(self):
        self.write_review("changes_requested", 1)
        self.capture(artel.cmd_advance, self.TASK)
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertEqual(self.task_row()["review_iters"], 1)

        self.capture(artel.cmd_advance, self.TASK)  # in_dev -> review, PLAN ready
        out = self.capture(artel.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "review")
        self.assertIn("уже учтён", out)
        # лимит итераций тот же вердикт второй раз не съедает
        self.assertEqual(self.task_row()["review_iters"], 1)

    def test_first_verdict_passes_as_before(self):
        self.write_review("approved", 1)

        self.capture(artel.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "acceptance")
        self.assertEqual(self.task_row()["reviewed_iter"], 1)

    def test_draft_review_still_waits_for_verdict(self):
        self.write_review("draft", 1)

        out = self.capture(artel.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "review")
        self.assertIn("жду вердикта", out)

    def test_reviewer_prompt_asks_for_next_iteration(self):
        self.back_to_review_after_acceptance_reject()

        with mock.patch("orchestrator.artel.subprocess.run") as run_mock:
            run_mock.return_value = mock.Mock(returncode=0)
            self.capture(artel.cmd_run, self.TASK)

        prompt = run_mock.call_args.args[0][2]
        self.assertIn("iteration: 2", prompt)


class MigrationTest(unittest.TestCase):
    def test_old_db_gets_reviewed_iter_column(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / ".artel" / "state.db"
        db_path.parent.mkdir()

        old = sqlite3.connect(db_path)
        old.executescript(
            """
            CREATE TABLE tasks (
              id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
              review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
              budget_usd REAL, spent_usd REAL DEFAULT 0,
              created_at TEXT, updated_at TEXT
            );
            INSERT INTO tasks (id, state) VALUES ('T001', 'review');
            """
        )
        old.commit()
        old.close()

        with mock.patch.object(artel, "DB", db_path):
            row = artel.db().execute("SELECT * FROM tasks WHERE id='T001'").fetchone()

        self.assertEqual(row["reviewed_iter"], 0)


if __name__ == "__main__":
    unittest.main()
