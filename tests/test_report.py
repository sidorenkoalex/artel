"""Юнит-тесты чистых функций `orchestrator/report.py` (tasks/T092/SPEC.md).

Сквозной путь (запись файла по фиксированному пути, печать пути, read-only
относительно `state.db`) уже покрыт приёмочными тестами
`tasks/T092/acceptance_tests/` — здесь только функции метрик и рендера,
тем же приёмом, что `tests/test_retro.py` держит для `orchestrator/retro.py`.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import agent_log, config, report, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


def _row(**fields):
    """Строка `steps`/`tasks`, доступная по имени колонки — как sqlite3.Row."""
    return fields


def _event(**fields) -> str:
    """Строка потока `--output-format stream-json` (tasks/T095/SPEC.md)."""
    return json.dumps(fields, ensure_ascii=False) + "\n"


def _read_call(call_id: str, file_path: str) -> str:
    return _event(type="assistant", message={"role": "assistant", "content": [
        {"type": "tool_use", "id": call_id, "name": "Read",
         "input": {"file_path": file_path}}]})


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


class MetricsHtmlTest(unittest.TestCase):
    """`report._metrics_html` — верхняя оценка отдельной строкой от
    точного расхода (SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, требование 6)."""

    def test_estimate_and_exact_spend_are_distinct_figures(self):
        html = report._metrics_html([], [], 3.0, 7.0)

        self.assertIn("$3.00", html)
        self.assertIn("$7.00", html)
        self.assertNotIn("$10.00", html, "суммы не должны складываться")

    def test_zero_estimate_still_shows_its_own_zeroed_line(self):
        """В отличие от RETRO (условная строка, требование 7), report —
        всегда видимая метрика: нулевая оценка означает «пока нет
        неучтённых шагов», а не «строка скрыта»."""
        html = report._metrics_html([], [], 3.0, 0.0)

        self.assertIn("Суммарная верхняя оценка", html)
        self.assertIn("$0.00", html)


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

    def test_report_sums_the_upper_estimate_across_tasks(self):
        store.update_task(store.db(), "T001", spent_estimate_usd=7.0)

        self.capture(report.cmd_report)

        path = config.ROOT / ".artel" / "report.html"
        self.assertIn("$7.00", path.read_text(encoding="utf-8"))


class TaskStepLogsTest(TmpRootTest):
    """tasks/T095/SPEC.md — файлы логов задачи, доступные на диске."""

    def test_missing_logs_dir_is_an_empty_list(self):
        self.assertEqual(report._task_step_logs("T001"), [])

    def test_finds_only_logs_of_the_given_task(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T001-developer-1.log").write_text("", encoding="utf-8")
        (config.LOGS / "T001-developer-2.log").write_text("", encoding="utf-8")
        (config.LOGS / "T002-developer-1.log").write_text("", encoding="utf-8")

        found = [p.name for p in report._task_step_logs("T001")]

        self.assertEqual(sorted(found),
                         ["T001-developer-1.log", "T001-developer-2.log"])


class TaskJournalFrictionTest(unittest.TestCase):
    """tasks/T095/SPEC.md, вариант 4б — трение, записанное `runner.py`
    в журнал `steps` (`agent_log.FRICTION_JOURNAL_ACTION`)."""

    def test_no_matching_rows_gives_empty_list(self):
        steps = [_row(task_id="T001", action="agent run finished", detail="rc=0")]

        self.assertEqual(report._task_journal_friction("T001", steps), [])

    def test_collects_only_this_tasks_friction_rows(self):
        steps = [
            _row(task_id="T001", action=agent_log.FRICTION_JOURNAL_ACTION,
                detail="0.5000"),
            _row(task_id="T002", action=agent_log.FRICTION_JOURNAL_ACTION,
                detail="0.9000"),
            _row(task_id="T001", action="agent run finished", detail="rc=0"),
        ]

        self.assertEqual(report._task_journal_friction("T001", steps), [0.5])

    def test_unparsable_detail_is_skipped_not_raised(self):
        steps = [_row(task_id="T001", action=agent_log.FRICTION_JOURNAL_ACTION,
                     detail="перекачка не завершилась")]

        self.assertEqual(report._task_journal_friction("T001", steps), [])


class TaskFrictionTest(TmpRootTest):
    """tasks/T095/SPEC.md, AC-2/AC-5 — среднее по шагам задачи: журнал
    (вариант 4б) в приоритете, файлы `.artel/logs/` — запасной путь,
    честный пропуск отсутствующих/нечитаемых."""

    def test_no_logs_and_no_journal_gives_no_average(self):
        self.assertEqual(report._task_friction("T001", []), (None, 0))

    def test_averages_over_every_available_log_when_journal_is_empty(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T001-developer-1.log").write_text(
            _read_call("t1", "a.py") + _read_call("t2", "b.py"), encoding="utf-8")
        (config.LOGS / "T001-developer-2.log").write_text(
            _read_call("t1", "a.py") + _read_call("t2", "a.py"), encoding="utf-8")

        avg, n = report._task_friction("T001", [])

        self.assertEqual(n, 2)
        self.assertEqual(avg, 0.25)  # (0.0 + 0.5) / 2

    def test_a_log_that_disappears_before_reading_is_skipped_not_raised(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T001-developer-1.log").write_text(
            _read_call("t1", "a.py"), encoding="utf-8")

        with mock.patch.object(agent_log, "step_friction",
                               side_effect=OSError("вычищено prune")):
            self.assertEqual(report._task_friction("T001", []), (None, 0))

    def test_journal_rows_take_priority_over_stale_log_files(self):
        """Реальный шаг: и журнальная запись, и рендер-лог существуют —
        лог несёт 0.0 (рендер, не сырой поток), журнал несёт настоящее
        число; должно победить журнальное значение, а не их смесь."""
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T001-developer-1.log").write_text(
            "· Read a.py\n· Read a.py\n", encoding="utf-8")
        steps = [_row(task_id="T001", action=agent_log.FRICTION_JOURNAL_ACTION,
                     detail="0.7500")]

        avg, n = report._task_friction("T001", steps)

        self.assertEqual((avg, n), (0.75, 1))


class FrictionByTaskTest(unittest.TestCase):
    """tasks/T095/SPEC.md, требование 3 — только последние задачи."""

    def test_limits_to_the_most_recent_tasks(self):
        tasks = [_row(id=f"T{i:03d}") for i in range(1, 15)]

        with mock.patch.object(report, "_task_friction", return_value=(0.0, 1)):
            by_task = report._friction_by_task(tasks, [])

        self.assertEqual(len(by_task), report.FRICTION_RECENT_TASKS)
        self.assertEqual(by_task[0][0], "T005")
        self.assertEqual(by_task[-1][0], "T014")


class FrictionTrendTest(unittest.TestCase):
    """tasks/T095/SPEC.md, требование 3 — направление, без median/порогов
    (AC-9/AC-10)."""

    def test_fewer_than_two_known_values_is_insufficient_data(self):
        self.assertEqual(report._friction_trend([]), "недостаточно данных")
        self.assertEqual(report._friction_trend([("T001", 0.1, 1)]),
                         "недостаточно данных")

    def test_rising_average_is_growth(self):
        by_task = [("T001", 0.0, 1), ("T002", 0.5, 1)]

        self.assertEqual(report._friction_trend(by_task), "рост")

    def test_falling_average_is_decline(self):
        by_task = [("T001", 0.5, 1), ("T002", 0.0, 1)]

        self.assertEqual(report._friction_trend(by_task), "снижение")

    def test_unchanged_average_is_stable(self):
        by_task = [("T001", 0.2, 1), ("T002", 0.2, 1)]

        self.assertEqual(report._friction_trend(by_task), "стабильно")

    def test_tasks_without_data_are_excluded_from_the_comparison(self):
        by_task = [("T001", None, 0), ("T002", 0.0, 1), ("T003", 0.5, 1)]

        self.assertEqual(report._friction_trend(by_task), "рост")


class FrictionHtmlTest(unittest.TestCase):
    """tasks/T095/SPEC.md, требование 3 — форма блока трения в report."""

    def test_no_tasks_says_so(self):
        self.assertIn("Задач нет", report._friction_html([], []))

    def test_mentions_the_trend(self):
        self.assertIn("Тренд", report._friction_html([], []))

    def test_task_without_data_is_named_not_a_number(self):
        with mock.patch.object(report, "_task_friction", return_value=(None, 0)):
            html = report._friction_html([_row(id="T001")], [])

        self.assertIn("T001", html)
        self.assertIn("трение не посчитано", html)

    def test_task_with_data_shows_its_percentage(self):
        with mock.patch.object(report, "_task_friction", return_value=(0.25, 2)):
            html = report._friction_html([_row(id="T001")], [])

        self.assertIn("25%", html)
        self.assertIn("шагов: 2", html)


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
