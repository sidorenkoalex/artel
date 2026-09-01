"""Юнит-тесты чистых функций `orchestrator/report.py` (tasks/T092/SPEC.md).

Сквозной путь (запись файла по фиксированному пути, печать пути, read-only
относительно `state.db`) уже покрыт приёмочными тестами
`tasks/T092/acceptance_tests/` — здесь только функции метрик и рендера,
тем же приёмом, что `tests/test_retro.py` держит для `orchestrator/retro.py`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, report, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


def _row(**fields):
    """Строка `steps`/`tasks`, доступная по имени колонки — как sqlite3.Row."""
    return fields


class RatioTest(unittest.TestCase):

    def test_empty_entries_return_none(self):
        self.assertIsNone(report._ratio([]))

    def test_counts_and_rounds_percentages(self):
        entries = ([_row(actor="autogate")] * 9
                  + [_row(actor="operator")] * 11)

        result = report._ratio(entries)

        self.assertEqual(result["total"], 20)
        self.assertEqual(result["autogate"], 9)
        self.assertEqual(result["operator"], 11)
        self.assertEqual(result["autogate_pct"], 45)
        self.assertEqual(result["operator_pct"], 55)


class GateRatioTest(unittest.TestCase):

    def test_ignores_other_actions_and_actors(self):
        steps = [
            _row(id=1, action="state -> merge_gate", actor="autogate"),
            _row(id=2, action="state -> in_dev", actor="autogate"),
            _row(id=3, action="state -> merge_gate", actor="fsm"),
        ]

        result = report._gate_ratio(steps)

        self.assertEqual(result["history"]["total"], 1)
        self.assertEqual(result["history"]["autogate"], 1)

    def test_last_window_uses_only_the_tail_of_qualifying_entries(self):
        history = [_row(id=i, action="state -> merge_gate", actor="operator")
                  for i in range(15)]
        history += [_row(id=15 + i, action="state -> merge_gate",
                         actor="autogate") for i in range(10)]

        result = report._gate_ratio(history)

        self.assertEqual(result["history"]["operator"], 15)
        self.assertEqual(result["history"]["autogate"], 10)
        # Последние 10 записей — все autogate: окно не совпадает с историей.
        self.assertEqual(result["last_window"]["autogate"], 10)
        self.assertEqual(result["last_window"]["operator"], 0)

    def test_no_qualifying_entries_gives_none_ratios(self):
        result = report._gate_ratio([_row(id=1, action="state -> in_dev",
                                          actor="operator")])

        self.assertIsNone(result["history"])
        self.assertIsNone(result["last_window"])


class OperatorJournalByDayTest(unittest.TestCase):

    def test_groups_operator_entries_by_day(self):
        steps = [
            _row(actor="operator", ts="2026-08-30 10:00:00Z"),
            _row(actor="operator", ts="2026-08-30 11:00:00Z"),
            _row(actor="operator", ts="2026-08-31 09:00:00Z"),
        ]

        with _frozen_today("2026-09-01"):
            result = report._operator_journal_by_day(steps)

        self.assertEqual(result, [("2026-08-30", 2), ("2026-08-31", 1)])

    def test_excludes_non_operator_actors(self):
        steps = [
            _row(actor="operator", ts="2026-08-31 09:00:00Z"),
            _row(actor="autogate", ts="2026-08-31 09:05:00Z"),
        ]

        with _frozen_today("2026-09-01"):
            result = report._operator_journal_by_day(steps)

        self.assertEqual(result, [("2026-08-31", 1)])

    def test_excludes_entries_older_than_the_window(self):
        steps = [
            _row(actor="operator", ts="2026-01-01 00:00:00Z"),
            _row(actor="operator", ts="2026-08-31 00:00:00Z"),
        ]

        with _frozen_today("2026-09-01"):
            result = report._operator_journal_by_day(steps)

        self.assertEqual(result, [("2026-08-31", 1)])

    def test_malformed_timestamp_is_skipped_not_raised(self):
        steps = [_row(actor="operator", ts="")]

        result = report._operator_journal_by_day(steps)

        self.assertEqual(result, [])


class CostPerDoneTaskTest(unittest.TestCase):

    def test_none_without_done_tasks(self):
        tasks = [_row(state="in_dev", spent_usd=5.0)]

        self.assertIsNone(report._cost_per_done_task(tasks))

    def test_averages_only_done_tasks(self):
        tasks = [
            _row(state="done", spent_usd=50.0),
            _row(state="done", spent_usd=250.0),
            _row(state="done", spent_usd=300.0),
            _row(state="in_dev", spent_usd=999.0),
        ]

        self.assertEqual(report._cost_per_done_task(tasks), 200.0)


class TileHtmlTest(unittest.TestCase):

    def test_non_escalated_task_has_no_escalation_marker(self):
        row = _row(id="T001", title="Задача", state="in_dev",
                   escalated_from=None, budget_usd=10.0, spent_usd=1.0,
                   review_iters=0)

        self.assertNotIn("Эскалация", report._tile_html(row))

    def test_escalated_task_names_the_source_step(self):
        row = _row(id="T002", title="Задача", state="escalated",
                   escalated_from="review", budget_usd=10.0, spent_usd=1.0,
                   review_iters=1)

        html = report._tile_html(row)

        self.assertIn("Эскалация", html)
        self.assertIn("review", html)

    def test_title_is_html_escaped(self):
        row = _row(id="T003", title="<script>alert(1)</script>",
                   state="in_dev", escalated_from=None, budget_usd=1.0,
                   spent_usd=0.0, review_iters=0)

        html = report._tile_html(row)

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class BoardHtmlTest(unittest.TestCase):

    def test_known_states_follow_canonical_fsm_order(self):
        tasks = [
            _row(id="T001", title="A", state="done", escalated_from=None,
                budget_usd=1.0, spent_usd=0.0, review_iters=0),
            _row(id="T002", title="B", state="in_dev", escalated_from=None,
                budget_usd=1.0, spent_usd=0.0, review_iters=0),
        ]

        html = report._board_html(tasks)

        self.assertLess(html.index("in_dev"), html.index("done"))

    def test_unknown_state_is_appended_sorted_not_dropped(self):
        tasks = [_row(id="T001", title="A", state="zzz_unknown",
                     escalated_from=None, budget_usd=1.0, spent_usd=0.0,
                     review_iters=0)]

        html = report._board_html(tasks)

        self.assertIn("zzz_unknown", html)
        self.assertIn("T001", html)

    def test_no_tasks_reports_empty_board(self):
        self.assertIn("Задач нет", report._board_html([]))


class StyleBoardColumnWidthTest(unittest.TestCase):
    """Ширина колонки борда следует норме `docs/design-system.md`
    (tasks/T096/SPEC.md, требование 4 и AC-2/AC-7 — расхождение с
    `tasks/T080/mockup.html` устранено значением, не структурой)."""

    def test_col_width_matches_mockup_norm(self):
        self.assertIn("min-width: 168px; flex: 0 0 168px;", report._STYLE)
        self.assertNotIn("200px", report._STYLE)


class EscUsdTest(unittest.TestCase):

    def test_esc_escapes_html_special_characters(self):
        self.assertEqual(report._esc("<a>&"), "&lt;a&gt;&amp;")

    def test_usd_formats_none_as_zero(self):
        self.assertEqual(report._usd(None), "$0.00")

    def test_usd_formats_value(self):
        self.assertEqual(report._usd(12.5), "$12.50")


class CmdReportIntegrationTest(TmpRootTest):
    """Один сквозной прогон поверх настоящей БД — склейка store.py-чтений
    и рендера в файл; детальные критерии приёмки — в
    tasks/T092/acceptance_tests/, не дублируются здесь построчно."""

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T001", "Интеграционная задача-фикстура",
                          "in_dev", branch="task/t001-x",
                          target=config.DEFAULT_TARGET, budget_usd=10.0)

    def test_writes_report_html_under_artel_dir_and_prints_its_path(self):
        out = self.capture(report.cmd_report)

        path = config.ROOT / ".artel" / "report.html"
        self.assertTrue(path.is_file())
        self.assertIn(str(path), out)
        self.assertIn("T001", path.read_text(encoding="utf-8"))


class _frozen_today:
    """Подмена «сегодня» для `report._operator_journal_by_day` (окно 14
    дней считается от `datetime.now`) — без неё тест был бы завязан на
    реальную дату запуска и требовал бы пересчёта смещений руками."""

    def __init__(self, iso_date: str):
        self.iso_date = iso_date
        self._patcher = None

    def __enter__(self):
        from datetime import datetime, timezone
        from unittest import mock

        fixed = datetime.fromisoformat(self.iso_date).replace(tzinfo=timezone.utc)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed if tz is None else fixed.astimezone(tz)

        self._patcher = mock.patch.object(report, "datetime", _FrozenDatetime)
        self._patcher.start()
        return self

    def __exit__(self, *exc_info):
        self._patcher.stop()


if __name__ == "__main__":
    unittest.main()
