"""Юнит-тесты `orchestrator/canary.py` v2 (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ;
v1 — tasks/T065/SPEC.md).

Сквозной сценарий (заведение задач в эфемерном клоне, прогон auto-циклом
до гейтов, эскалация синтетическим ANSWER, kill на merge_gate, ноль
следов в main) уже покрыт приёмочными тестами `tasks/
01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/` (AC-1..AC-9, реальный
git) — здесь только то, что они не изолируют: чистая арифметика
отклонения от бейзлайна, парсинг маркера «ожидается эскалация»,
выборка `k` из `N`, сборка метрик из журнала, пересчёт путей `config`
под эфемерный клон (без реального git) и факт пометки/учёта canary в
`store`/`catalog`/`retro` без полного прогона конвейера.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifact_branch, canary, catalog, config,  # noqa: E402
                          retro, store)
from tests.sandbox import RealGitSandbox, capture  # noqa: E402


class DeviationTest(unittest.TestCase):
    """`canary._deviation_exceeds` — чистая арифметика (SPEC, требование 12)."""

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


class DevRetriesConfigConstantTest(unittest.TestCase):
    """`config.CANARY_MAX_DEV_RETRIES` (01M2ARQD7C472KZACB3SZXGF1N,
    требование 1) — потолок повторов developer на красной планке."""

    def test_value_is_two(self):
        """Ловит мутацию: константа переименована/удалена либо несёт
        другое значение (0, 1, 3) — потолок повторов developer разошёлся
        бы с решением Оператора 12.09 (вариант а)."""
        self.assertEqual(config.CANARY_MAX_DEV_RETRIES, 2)


class TaskDeviationWarningsTest(unittest.TestCase):
    """`canary._task_deviation_warnings` — отклонение ОДНОЙ задачи от ЕЁ
    per-task бейзлайна (требование 9, 12), не суммы по набору (v1-регресс,
    который и заменяет v2)."""

    def test_no_warning_when_both_metrics_within_threshold(self):
        metrics = {"steps": 12, "cost_usd": 10.0}
        baseline = {"steps": 10, "cost_usd": 9.0}
        self.assertEqual(canary._task_deviation_warnings(metrics, baseline, 0.5), [])

    def test_warns_on_steps_deviation_only(self):
        metrics = {"steps": 20, "cost_usd": 10.0}
        baseline = {"steps": 10, "cost_usd": 10.0}
        warnings = canary._task_deviation_warnings(metrics, baseline, 0.5)
        self.assertEqual(len(warnings), 1)
        self.assertIn("шагам", warnings[0])

    def test_warns_on_both_metrics(self):
        metrics = {"steps": 20, "cost_usd": 30.0}
        baseline = {"steps": 10, "cost_usd": 10.0}
        warnings = canary._task_deviation_warnings(metrics, baseline, 0.5)
        self.assertEqual(len(warnings), 2)


class ExpectedEscalationMarkerTest(unittest.TestCase):
    """`canary._expected_escalation` — разбор HTML-комментария маркера
    (требование 8, AC-8)."""

    def test_yes_marker_is_true(self):
        self.assertTrue(canary._expected_escalation(
            f"{canary.MARK_EXPECT_ESCALATION_YES}\nтекст шаблона"))

    def test_no_marker_is_false(self):
        self.assertFalse(canary._expected_escalation(
            f"{canary.MARK_EXPECT_ESCALATION_NO}\nтекст шаблона"))

    def test_missing_marker_is_none(self):
        self.assertIsNone(canary._expected_escalation("просто текст без маркера"))


class SamplePoolTemplatesTest(unittest.TestCase):
    """`canary._sample_pool_templates` — выборка `k` из `N` (требование 1,
    AC-1), без прогона FSM."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pool_dir = Path(tmp.name)
        for i in range(1, 6):
            (self.pool_dir / f"shablon-{i}.md").write_text("x", encoding="utf-8")
        (self.pool_dir / "не-шаблон.txt").write_text("x", encoding="utf-8")

    def test_samples_exactly_k_of_n_md_files(self):
        chosen = canary._sample_pool_templates(self.pool_dir, 2)
        self.assertEqual(len(chosen), 2)
        self.assertTrue(all(p.suffix == ".md" for p in chosen))
        self.assertEqual(len(set(chosen)), 2)

    def test_ignores_non_md_files_when_counting_n(self):
        chosen = canary._sample_pool_templates(self.pool_dir, 5)
        self.assertEqual(len(chosen), 5)

    def test_k_greater_than_n_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            canary._sample_pool_templates(self.pool_dir, 6)
        self.assertIn("больше числа доступных шаблонов", str(ctx.exception))

    def test_empty_pool_exits(self):
        empty = self.pool_dir / "empty"
        empty.mkdir()
        with self.assertRaises(SystemExit) as ctx:
            canary._sample_pool_templates(empty, 1)
        self.assertIn("нет файлов", str(ctx.exception))


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

    def test_test_author_visited_true_when_tests_writing_in_journal(self):
        """Ловит мутацию: `_test_author_visited` возвращает `False`
        безусловно (или сравнение строки действия подменено на другой
        переход, например `state -> in_dev`) — задача реально прошла
        `tests_writing`, а признак АС-5 ошибочно остался бы «нет»."""
        store.journal(self.conn, self.TASK, "fsm", "state -> spec_gate", "")
        store.journal(self.conn, self.TASK, "operator",
                      "state -> tests_writing", "")

        steps = store.task_steps(self.conn, self.TASK)

        self.assertTrue(canary._test_author_visited(steps))
        self.assertTrue(canary._task_metrics(
            self.conn, self.TASK)["test_author_visited"])

    def test_task_metrics_includes_dev_retries_count(self):
        """Ловит мутацию: `_task_metrics` не прокидывает `_dev_retry_count`
        в возвращаемый словарь (поле `dev_retries` отсутствует или всегда
        0) — отчёт `_run_one_task` не смог бы напечатать реальное число
        повторов developer (01M2ARQD7C472KZACB3SZXGF1N, требование 5)."""
        store.journal(self.conn, self.TASK, "canary",
                      canary._DEV_RETRY_ACTION, "попытка 1/2")
        store.journal(self.conn, self.TASK, "canary",
                      canary._DEV_RETRY_ACTION, "попытка 2/2")

        metrics = canary._task_metrics(self.conn, self.TASK)

        self.assertEqual(metrics["dev_retries"], 2)

    def test_test_author_visited_false_when_tests_writing_skipped(self):
        """Ловит мутацию: `_test_author_visited` возвращает `True`
        безусловно (или `any(...)` подменён на проверку непустоты
        `steps`) — журнал без перехода `state -> tests_writing` (SPEC
        без AC-разметки ушёл `spec_gate -> in_dev` напрямую) ошибочно
        дал бы «test_author=да»."""
        store.journal(self.conn, self.TASK, "fsm", "state -> spec_gate", "")
        store.journal(self.conn, self.TASK, "canary", "state -> in_dev", "")

        steps = store.task_steps(self.conn, self.TASK)

        self.assertFalse(canary._test_author_visited(steps))
        self.assertFalse(canary._task_metrics(
            self.conn, self.TASK)["test_author_visited"])


class NeedsDiagnosticsTest(unittest.TestCase):
    """`canary._needs_diagnostics` — ANSWER-1.md, правило 1 (требование 1,
    AC-1/AC-4): диагностика сохраняется во всех случаях, кроме «штатно
    И без расхождения» одновременно."""

    def test_normal_without_mismatch_does_not_need_diagnostics(self):
        """Ловит мутацию: `_needs_diagnostics` возвращает `True`
        безусловно (или роняет проверку `not mismatch`) — единственная
        комбинация, где диагностика НЕ нужна (штатный исход без
        расхождения, ANSWER-1.md правило 1), ошибочно попала бы под
        сохранение."""
        self.assertFalse(canary._needs_diagnostics(True, False))

    def test_not_normal_without_mismatch_needs_diagnostics(self):
        """Ловит мутацию: `and` в выражении подменён на `or` (или
        проверка `normal_outcome` инвертирована) — нештатный исход без
        расхождения маркера ошибочно классифицировался бы как
        «диагностика не нужна», теряя ту самую диагностику, ради
        которой SPEC затевался (AC-1)."""
        self.assertTrue(canary._needs_diagnostics(False, False))

    def test_normal_with_mismatch_needs_diagnostics(self):
        """Ловит мутацию: проверка `mismatch` выпала из выражения
        (например, `not normal_outcome` вместо `not (normal_outcome
        and not mismatch)`) — штатный исход С расхождением маркера
        ошибочно посчитался бы «диагностика не нужна», хотя расхождение
        — как раз то, что требуется расследовать."""
        self.assertTrue(canary._needs_diagnostics(True, True))

    def test_not_normal_with_mismatch_needs_diagnostics(self):
        """Ловит мутацию: функция всегда возвращает `False` (или обе
        проверки инвертированы одновременно, компенсируя друг друга) —
        худший случай (и не штатно, и расхождение) остался бы без
        диагностики."""
        self.assertTrue(canary._needs_diagnostics(False, True))


class JournalExcerptLinesTest(unittest.TestCase):
    """`canary._journal_excerpt_lines` (требование 2, AC-6) — переходы
    состояний и записи «переход отклонён»/«auto остановлен», не
    произвольные записи журнала, с потолком по числу строк."""

    TASK = "T901"

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
                          "killed", "task/t901-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

    def _steps(self):
        return store.task_steps(self.conn, self.TASK)

    def test_keeps_state_transitions_refusals_and_auto_stopped(self):
        """Ловит мутацию: фильтр по префиксам `state -> `/`store.
        REFUSAL_ACTION_PREFIX`/`_AUTO_STOPPED_ACTION` сужен или порядок
        строк перепутан — любая из трёх целевых записей журнала выпала
        бы из выдержки или оказалась не на своём месте, срывая
        требование 2 (переходы состояний и «эскалация»/«переход
        отклонён»/«auto остановлен» обязаны попасть в вывод)."""
        store.journal(self.conn, self.TASK, "canary", "state -> in_dev", "")
        store.journal(self.conn, self.TASK, "fsm",
                      "переход отклонён: замечания ревью не отработаны", "")
        store.journal(self.conn, self.TASK, "operator", "auto остановлен",
                      "лимит шагов")

        lines = canary._journal_excerpt_lines(self._steps())

        self.assertEqual(len(lines), 3)
        self.assertIn("state -> in_dev", lines[0])
        self.assertIn("переход отклонён", lines[1])
        self.assertIn("auto остановлен", lines[2])

    def test_drops_unrelated_journal_rows(self):
        """Ловит мутацию: условие `continue` для нецелевых действий
        убрано или инвертировано — служебные записи runner (`agent run
        started`/`finished`) просочились бы в выдержку журнала, раздувая
        вывод сверх требования 2."""
        store.journal(self.conn, self.TASK, "runner", "agent run started", "")
        store.journal(self.conn, self.TASK, "runner", "agent run finished", "")

        self.assertEqual(canary._journal_excerpt_lines(self._steps()), [])

    def test_caps_at_the_given_limit_keeping_the_most_recent(self):
        """Ловит мутацию: срез `lines[-limit:]` заменён на `lines[:limit]`
        (или лимит не применяется вовсе) — вместо самых СВЕЖИХ записей
        (причина финального исхода) в выдержке остались бы самые
        старые, либо потолок в 20 строк на задачу (требование 2) был
        бы сорван."""
        for i in range(5):
            store.journal(self.conn, self.TASK, "canary", f"state -> s{i}", "")

        lines = canary._journal_excerpt_lines(self._steps(), limit=2)

        self.assertEqual(len(lines), 2)
        self.assertIn("state -> s3", lines[0])
        self.assertIn("state -> s4", lines[1])


class DiagnosticsDirTest(unittest.TestCase):
    """`canary._diagnostics_dir` — путь диагностики строится от каталога
    СНАРУЖИ клона (`outer_root`), не от текущего (возможно, патченного
    на клон) `config.ROOT` (требование 1, AC-1)."""

    def test_path_shape(self):
        """Ловит мутацию: путь строится от текущего (возможно,
        патченного на клон) `config.ROOT` вместо переданного
        `outer_root`, либо сегменты `.artel/canary/<run_stamp>/
        <task_id>` переставлены/пропущены — диагностика писалась бы
        ВНУТРЬ эфемерного клона и была бы уничтожена `shutil.rmtree`
        вместе с ним (требование 1, AC-1)."""
        outer_root = Path("/tmp/artel-outer")

        result = canary._diagnostics_dir(outer_root, "20260906T000000Z", "T902")

        self.assertEqual(
            result,
            outer_root / ".artel" / "canary" / "20260906T000000Z" / "T902")


class CanaryBaselineStoreRoundtripTest(unittest.TestCase):
    """`store.canary_baseline`/`set_canary_baseline` — бейзлайн per-task,
    ключ `title`, не `task_id` (требование 9)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()

    def test_missing_baseline_is_none(self):
        self.assertIsNone(store.canary_baseline(self.conn, "prostaya-pravka"))

    def test_write_then_read_roundtrips(self):
        store.set_canary_baseline(self.conn, "prostaya-pravka", steps=5,
                                  cost_usd=1.5, review_iterations=0)
        row = store.canary_baseline(self.conn, "prostaya-pravka")
        self.assertEqual(row["steps"], 5)
        self.assertEqual(row["cost_usd"], 1.5)
        self.assertEqual(row["review_iterations"], 0)

    def test_second_write_overwrites_the_same_title(self):
        store.set_canary_baseline(self.conn, "t", steps=5, cost_usd=1.0,
                                  review_iterations=0)
        store.set_canary_baseline(self.conn, "t", steps=9, cost_usd=2.0,
                                  review_iterations=1)
        row = store.canary_baseline(self.conn, "t")
        self.assertEqual(row["steps"], 9)

    def test_insert_canary_run_is_a_separate_table_from_tasks_and_steps(self):
        store.insert_canary_run(
            self.conn, "20260101T000000Z", "prostaya-pravka", "01AAA",
            steps=3, cost_usd=0.5, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False)
        rows = self.conn.execute("SELECT * FROM canary_runs").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "prostaya-pravka")
        self.assertEqual(store.all_tasks(self.conn), [])

    def test_insert_canary_run_without_main_sha_or_verdict_defaults_to_none(self):
        """Вызыватели кода до этой задачи (tasks/
        01M1NGFK3N6MRMYGCC09H975V3, ANSWER-1 п.2) не передают
        `main_sha`/`verdict` — сигнатура обязана остаться совместимой."""
        store.insert_canary_run(
            self.conn, "20260101T000000Z", "prostaya-pravka", "01AAA",
            steps=3, cost_usd=0.5, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False)
        row = self.conn.execute("SELECT * FROM canary_runs").fetchone()
        self.assertIsNone(row["main_sha"])
        self.assertIsNone(row["verdict"])


class GreenCanaryRunsTest(unittest.TestCase):
    """`store.green_canary_runs`/`latest_green_canary_run` (tasks/
    01M1NGFK3N6MRMYGCC09H975V3, ANSWER-1 п.2/п.5) — источник guard'а
    привязки пина и цели отката по умолчанию `pin --to`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()

    def _insert(self, run_stamp, verdict, created_at, main_sha="sha"):
        store.insert_canary_run(
            self.conn, run_stamp, "t", f"01{run_stamp}", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=main_sha, verdict=verdict)
        self.conn.execute(
            "UPDATE canary_runs SET created_at=? WHERE run_stamp=?",
            (created_at, run_stamp))
        self.conn.commit()

    def test_empty_journal_has_no_green_runs(self):
        """Ловит мутацию: `_ensure_canary_tables` не вызван до `SELECT`
        (падение `sqlite3.OperationalError: no such table` на первом
        обращении к пустой БД, до единственной строки журнала)."""
        self.assertEqual(store.green_canary_runs(self.conn), [])
        self.assertIsNone(store.latest_green_canary_run(self.conn))

    def test_red_runs_are_excluded(self):
        """Ловит мутацию: фильтр `WHERE verdict='green'` пропущен или
        перепутан на `verdict != 'red'` (совпадает и с `NULL`, который
        обязан оставаться исключённым — вызыватели кода до этой задачи не
        знают о `verdict` вовсе, AC-8)."""
        self._insert("r1", "red", "2026-01-01 00:00:00Z")

        self.assertEqual(store.green_canary_runs(self.conn), [])
        self.assertIsNone(store.latest_green_canary_run(self.conn))

    def test_latest_green_run_is_the_most_recent_by_created_at(self):
        """Ловит мутацию: сортировка `ORDER BY created_at` без `DESC`
        (или без учёта промежуточной красной строки `r2`) — вернула бы
        самый старый зелёный прогон `r1` вместо самого свежего `r3`."""
        self._insert("r1", "green", "2026-01-01 00:00:00Z", main_sha="old")
        self._insert("r2", "red", "2026-01-02 00:00:00Z", main_sha="mid")
        self._insert("r3", "green", "2026-01-03 00:00:00Z", main_sha="new")

        latest = store.latest_green_canary_run(self.conn)

        self.assertEqual(latest["main_sha"], "new")
        self.assertEqual([r["run_stamp"] for r in store.green_canary_runs(self.conn)],
                         ["r3", "r1"])


class CmdCanaryBadInputTest(unittest.TestCase):
    """CLI-отказы `canary.cmd_canary` на плохом вводе (требование 1) —
    `Path.home()` подменена на пустой временный каталог, реальный
    `~/.artel-canary` Оператора этот тест не трогает."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.fake_home = Path(tmp.name)
        patcher = mock.patch.object(Path, "home", return_value=self.fake_home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_pool_dir_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            canary.cmd_canary(k=1)
        self.assertIn("каталог пула не найден", str(ctx.exception))

    def test_nonpositive_k_exits(self):
        (self.fake_home / config.CANARY_POOL_DIRNAME).mkdir()
        with self.assertRaises(SystemExit) as ctx:
            canary.cmd_canary(k=0)
        self.assertIn("--k", str(ctx.exception))


class ResolveTargetShaTest(unittest.TestCase):
    """`canary._resolve_target_sha` (SPEC 01M2B6K02YVJBWE1JDWP85EJH0,
    требование 1, AC-1/AC-2) — чистая маршрутизация без реального git."""

    def test_explicit_sha_is_returned_verbatim_without_touching_origin(self):
        """Ловит мутацию: явный `--sha` всё равно уходит в `gitcmd.
        fetch_ref_sha` — AC-2 запрещает обращение к `origin`, когда sha
        уже известен явно; с этой мутацией `fetch_ref_sha` был бы вызван
        независимо от переданного `explicit_sha`."""
        with mock.patch.object(canary.gitcmd, "fetch_ref_sha") as fetch_mock:
            sha, origin_sha = canary._resolve_target_sha("deadbeef")
        self.assertEqual(sha, "deadbeef")
        self.assertIsNone(origin_sha)
        fetch_mock.assert_not_called()

    def test_missing_sha_resolves_via_fetch_ref_sha_of_origin_main(self):
        """Ловит мутацию: источник sha по умолчанию — `gitcmd.head_sha()`
        главной копии (старое поведение) вместо `gitcmd.fetch_ref_sha(
        "origin", config.MAIN_BRANCH)` — вызов ушёл бы в другую функцию
        или с другими аргументами."""
        with mock.patch.object(canary.gitcmd, "fetch_ref_sha",
                               return_value=("cafefeed", "")) as fetch_mock:
            sha, origin_sha = canary._resolve_target_sha(None)
        fetch_mock.assert_called_once_with("origin", config.MAIN_BRANCH)
        self.assertEqual(sha, "cafefeed")
        self.assertEqual(origin_sha, "cafefeed")

    def test_fetch_failure_falls_back_to_local_head_sha(self):
        """`origin` недоступен (нет remote вовсе, сеть недоступна) —
        деградация на `gitcmd.head_sha()` главной копии, тем же приёмом,
        что `doctor.check_root_pin`/`check_pin_unpushed` (SPEC
        01M2B6K02YVJBWE1JDWP85EJH0, требование 1) — стенды без единого
        `origin` (например, `tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/
        acceptance_tests/`, локальная планка ДРУГОЙ, уже смерженной
        задачи, гоняющая `canary` без единого `origin`) не должны
        получить безусловный отказ прогона целиком.

        Ловит мутацию: отказ `fetch_ref_sha` завершает прогон `SystemExit`
        вместо деградации — стенд без `origin` терял бы возможность
        прогнать канарейку вовсе, хотя раньше (до этой задачи) прогонял
        её без единого `origin`."""
        with mock.patch.object(canary.gitcmd, "fetch_ref_sha",
                               return_value=("", "нет такого remote")), \
             mock.patch.object(canary.gitcmd, "head_sha",
                               return_value="localhead"):
            sha, origin_sha = canary._resolve_target_sha(None)
        self.assertEqual(sha, "localhead")
        self.assertIsNone(origin_sha)


class ShaLabelTest(unittest.TestCase):
    """`canary._sha_label` (требование 4, AC-8)."""

    def test_matches_local_head_is_pin_code_even_if_origin_matches_too(self):
        """Ловит мутацию: приоритет отдан «код origin/main» вместо «код
        пина», когда оба совпадения истинны одновременно (стенд
        синхронен) — AC-8 перечисляет «код пина» первым."""
        with mock.patch.object(canary.gitcmd, "head_sha", return_value="same"):
            label = canary._sha_label("same", "same")
        self.assertEqual(label, "код пина")

    def test_matches_origin_head_only_is_origin_main_code(self):
        """Ловит мутацию: сравнение с `origin_sha` не выполняется вовсе —
        sha, совпавший с головой origin, но не с пином, получил бы «код
        <sha>» вместо «код origin/main»."""
        with mock.patch.object(canary.gitcmd, "head_sha", return_value="pin"):
            label = canary._sha_label("upstream", "upstream")
        self.assertEqual(label, "код origin/main")

    def test_matches_neither_is_bare_sha_code(self):
        """Ловит мутацию: третья ветка (`else`) не реализована — sha, не
        совпавший ни с пином, ни с origin (или origin неизвестен, явный
        `--sha`), получил бы одну из первых двух пометок вместо «код
        <sha>» с буквальным значением."""
        with mock.patch.object(canary.gitcmd, "head_sha", return_value="pin"):
            label = canary._sha_label("other", None)
        self.assertEqual(label, "код other")


class EphemeralCloneConfigRemapTest(unittest.TestCase):
    """`canary._ephemeral_clone` — пересчёт путей `config` под клон и их
    восстановление по выходу, БЕЗ реального git (реальный git — приём
    `_sandbox.py::_EphemeralDirTracker` в приёмочных тестах): каждый
    патчнутый атрибут — буквально `ROOT / <подпуть>`, значит пересчёт
    `dest / saved[attr].relative_to(outer_root)` обязан давать тот же
    подпуть под новым корнем."""

    def setUp(self):
        self.real_root = config.ROOT
        self.suffixes = {
            attr: getattr(config, attr).relative_to(self.real_root)
            for attr in canary._CLONE_CONFIG_ATTRS}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.outer_root = Path(tmp.name) / "outer"
        self.outer_root.mkdir()
        for attr in canary._CLONE_CONFIG_ATTRS:
            patcher = mock.patch.object(
                config, attr, self.outer_root / self.suffixes[attr])
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_attrs_point_under_clone_inside_block_and_restore_after(self):
        saved_before = {attr: getattr(config, attr)
                        for attr in canary._CLONE_CONFIG_ATTRS}
        fake_clone_dir = self.outer_root.parent / "clone"

        def fake_run(cmd, **kw):
            if cmd[:2] == ["git", "clone"]:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(canary.tempfile, "mkdtemp",
                               return_value=str(fake_clone_dir)), \
             mock.patch.object(canary.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(canary.catalog, "cmd_init", lambda: None):
            with canary._ephemeral_clone("f" * 40) as dest:
                self.assertEqual(dest, fake_clone_dir)
                for attr in canary._CLONE_CONFIG_ATTRS:
                    self.assertEqual(getattr(config, attr),
                                     dest / self.suffixes[attr])

        for attr in canary._CLONE_CONFIG_ATTRS:
            self.assertEqual(getattr(config, attr), saved_before[attr])
        self.assertFalse(fake_clone_dir.exists())

    def test_config_restored_even_when_block_raises(self):
        saved_before = {attr: getattr(config, attr)
                        for attr in canary._CLONE_CONFIG_ATTRS}
        fake_clone_dir = self.outer_root.parent / "clone2"

        def fake_run(cmd, **kw):
            if cmd[:2] == ["git", "clone"]:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(canary.tempfile, "mkdtemp",
                               return_value=str(fake_clone_dir)), \
             mock.patch.object(canary.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(canary.catalog, "cmd_init", lambda: None):
            with self.assertRaises(ValueError):
                with canary._ephemeral_clone("f" * 40):
                    raise ValueError("boom")

        for attr in canary._CLONE_CONFIG_ATTRS:
            self.assertEqual(getattr(config, attr), saved_before[attr])
        self.assertFalse(fake_clone_dir.exists())

    def test_checkout_uses_target_sha(self):
        """`_ephemeral_clone` делает checkout ИМЕННО переданного
        `target_sha` (SPEC 01M2B6K02YVJBWE1JDWP85EJH0, требование 1/AC-3).

        Ловит мутацию: клон не делает `git checkout <target_sha>` вовсе
        (или делает его с другим значением, например HEAD `outer_root`
        по умолчанию) — это ровно мутация «клон остаётся на HEAD главной
        копии вместо целевого sha», прямо названная в AC-4."""
        fake_clone_dir = self.outer_root.parent / "clone3"
        calls = []

        def fake_run(cmd, **kw):
            calls.append((list(cmd), kw.get("cwd")))
            if cmd[:2] == ["git", "clone"]:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        target_sha = "deadbeef" * 5
        with mock.patch.object(canary.tempfile, "mkdtemp",
                               return_value=str(fake_clone_dir)), \
             mock.patch.object(canary.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(canary.catalog, "cmd_init", lambda: None):
            with canary._ephemeral_clone(target_sha):
                pass

        checkout_calls = [c for c, _cwd in calls if c[:2] == ["git", "checkout"]]
        self.assertEqual(len(checkout_calls), 1, calls)
        self.assertEqual(checkout_calls[0][-1], target_sha)
        self.assertIn(config.MAIN_BRANCH, checkout_calls[0])


class DriveTaskEscalationCapTest(unittest.TestCase):
    """`canary._drive_task` — потолок повторных `escalated`-циклов
    (REVIEW.md итерации 1, R1-F1, blocker): `review_iters` не
    сбрасывается при возврате из `escalated` (общее свойство FSM) —
    задача, чей лимит ревью уже исчерпан, эскалируется заново на первом
    же следующем `changes_requested`. Без потолка `_drive_task` гонял
    бы её по кругу бесконечно."""

    TASK = "T910"

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
                          "escalated", "task/t910-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)
        store.update_task(self.conn, self.TASK, escalated_from="in_dev")

        # Эмулирует реальный сценарий R1-F1: developer доработал,
        # ревьювер снова дал changes_requested, лимит ревью уже
        # исчерпан -> мгновенная повторная эскалация, без реального
        # прогона агентов.
        def fake_auto(task_id):
            t = store.get_task(self.conn, task_id)
            if t["state"] == "in_dev":
                store.set_state(self.conn, task_id, "escalated", "test",
                                expected_state="in_dev")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        # Синтетический ANSWER настоящий коммитит в git (answer.cmd_answer)
        # — здесь заменён тем же эффектом перехода без git, сам переход
        # `_drive_task` — предмет теста, не устройство ANSWER.
        def fake_pass_escalated(conn, task_id):
            store.update_task(conn, task_id, escalated_from=None,
                              answer_baseline=None)
            store.set_state(conn, task_id, "in_dev", "test",
                            expected_state="escalated")

        patcher = mock.patch.object(
            canary, "_pass_escalated_with_synthetic_answer",
            side_effect=fake_pass_escalated)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_repeated_escalation_is_capped_and_task_is_killed(self):
        """Ловит мутацию: потолок `config.CANARY_MAX_ESCALATION_CYCLES`
        не проверяется вовсе (или проверяется со сдвигом) — `_drive_task`
        зациклился бы на бесконечном `escalated` <-> `in_dev` вместо
        `cleanup.cmd_kill` через ограниченное число циклов."""
        canary._drive_task(self.conn, self.TASK)

        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)
        rows = store.open_alerts(self.conn, "threshold")
        self.assertTrue(any(r["target"] == self.TASK for r in rows))

    def test_does_not_escalate_more_times_than_the_cap_allows(self):
        canary._drive_task(self.conn, self.TASK)

        journaled = store.task_steps(self.conn, self.TASK)
        escalations = sum(1 for r in journaled if r["action"] == "state -> escalated")
        # Первая эскалация уже стояла до входа в `_drive_task` (не
        # журналирована этим тестом) — считаем только те, что случились
        # внутри цикла: не больше потолка.
        self.assertLessEqual(escalations, config.CANARY_MAX_ESCALATION_CYCLES)


class DriveTaskStallCapTest(unittest.TestCase):
    """`canary._drive_task` — потолок проходов без прогресса (REVIEW.md
    итерации 1, R1-F1, blocker, второй сценарий): бюджет задачи
    исчерпан, `runner.cmd_run` отказывает `SystemExit`'ом ДО смены
    состояния на каждом вызове — `auto.cmd_auto` эту причину не
    отличает от «шаг ещё не готов» и просто возвращается, не меняя
    состояние. Без потолка `_drive_task` крутился бы здесь бесконечно."""

    TASK = "T911"

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
                          "in_dev", "task/t911-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        # `auto.cmd_auto` при исчерпанном бюджете ничего не двигает —
        # ровно как реальный вызов, поймавший `SystemExit` изнутри и
        # молча вернувшийся (см. `auto._cmd_auto`).
        patcher = mock.patch.object(canary.auto, "cmd_auto", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_progress_is_capped_and_task_is_killed(self):
        """Ловит мутацию: потолок проходов без прогресса не проверяется
        (или сверяется с чужим счётчиком) — `_drive_task` крутился бы
        здесь бесконечно вместо `cleanup.cmd_kill` через ограниченное
        число проходов `auto.cmd_auto`, вернувших состояние без изменений."""
        canary._drive_task(self.conn, self.TASK)

        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)
        rows = store.open_alerts(self.conn, "threshold")
        self.assertTrue(any(r["target"] == self.TASK for r in rows))

    def test_state_is_untouched_while_stalled(self):
        canary._drive_task(self.conn, self.TASK)

        # `_drive_task` сам состояние не меняет в стагнирующем случае —
        # только звонит `cleanup.cmd_kill` (замокан здесь), реальный
        # переход в `killed` — его работа, не предмет этого теста.
        self.assertEqual(store.get_task(self.conn, self.TASK)["state"], "in_dev")


class DriveTaskDevRetryOnAcceptanceRefusalTest(unittest.TestCase):
    """`canary._drive_task` — повтор developer на красной приёмочной
    планке (01M2ARQD7C472KZACB3SZXGF1N, требование 2, AC-7): решение
    Оператора 12.09 (вариант а) — воспроизвести ручной возврат `run <id>`
    ВНУТРИ цикла канарейки на отказе «переход отклонён: приёмочные
    тесты», не дожидаясь стагнации."""

    TASK = "T920"

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
                          "in_dev", "task/t920-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        self.auto_calls = 0

        def fake_auto(task_id):
            self.auto_calls += 1
            if self.auto_calls == 1:
                store.journal(self.conn, task_id, "fsm",
                             "переход отклонён: приёмочные тесты",
                             "acceptance_tests красные:\n...")
                return
            # Второй проход — задача сдвинулась дальше `in_dev` (планка
            # исправлена повтором): цикл продолжает работу очередным
            # `auto.cmd_auto`, а не застревает на этом отказе навсегда.
            store.set_state(self.conn, task_id, "merge_gate", "test",
                            expected_state="in_dev")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.runner, "cmd_run")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_single_refusal_retries_developer_once_and_continues(self):
        """Ловит мутацию: ветка повтора developer не добавлена в
        `_drive_task` (или добавлена ПОСЛЕ generic-ветки `runner.
        step_role`) — отказ приёмочной планки по-прежнему копил бы
        `stall_streak` вместо вызова `runner.cmd_run`, и `_drive_task`
        никогда не дошёл бы до `merge_gate` этим же прогоном."""
        canary._drive_task(self.conn, self.TASK)

        canary.runner.cmd_run.assert_called_once_with(self.TASK)
        self.assertEqual(self.auto_calls, 2)
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)

    def test_refusal_wrapped_by_auto_stopped_is_detected_too(self):
        """Тот же отказ, видимый ТОЛЬКО как причина остановки `auto`
        стоп-краном T038 («auto остановлен: in_dev: переход отклонён:
        приёмочные тесты — ...»), не прямой записью `fsm`.

        Ловит мутацию: детектор ищет отказ ТОЛЬКО буквальным `action ==
        "переход отклонён: приёмочные тесты"`, не заглядывая в `detail`
        записи «auto остановлен» — этот сценарий (T038 срабатывает раньше
        отдельной проверки цикла) остался бы нераспознанным, и `runner.
        cmd_run` не был бы вызван ни разу."""
        self.auto_calls = 0

        def fake_auto_wrapped(task_id):
            self.auto_calls += 1
            if self.auto_calls == 1:
                store.journal(
                    self.conn, task_id, "operator", "auto остановлен",
                    f"in_dev: переход отклонён: приёмочные тесты — "
                    f"почини причину и повтори artel.py advance {task_id}")
                return
            store.set_state(self.conn, task_id, "merge_gate", "test",
                            expected_state="in_dev")

        canary.auto.cmd_auto.side_effect = fake_auto_wrapped

        canary._drive_task(self.conn, self.TASK)

        canary.runner.cmd_run.assert_called_once_with(self.TASK)
        self.assertEqual(self.auto_calls, 2)


class DriveTaskDevRetryCapExceededTest(unittest.TestCase):
    """`canary._drive_task` — потолок `config.CANARY_MAX_DEV_RETRIES`
    повторов developer подряд одного визита `in_dev` (требование 3,
    AC-4, тест AC-8): без потолка цикл гонял бы developer по кругу на
    реально не сходящейся планке бесконечно."""

    TASK = "T921"

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
                          "in_dev", "task/t921-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        # Тот же отказ на КАЖДОМ проходе — планка реально не сходится.
        def fake_auto(task_id):
            store.journal(self.conn, task_id, "fsm",
                         "переход отклонён: приёмочные тесты",
                         "acceptance_tests красные: одна и та же причина")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.runner, "cmd_run")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exceeding_cap_kills_inconclusive_and_bounds_retries(self):
        """Ловит мутацию: потолок `config.CANARY_MAX_DEV_RETRIES` не
        проверяется (или сверяется со сдвигом) — цикл звал бы `runner.
        cmd_run` без ограничения на каждом проходе; тест либо завис бы,
        либо число вызовов `runner.cmd_run` превысило бы потолок вместо
        `cleanup.cmd_kill` через ограниченное число повторов."""
        canary._drive_task(self.conn, self.TASK)

        cap = config.CANARY_MAX_DEV_RETRIES
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)
        self.assertEqual(canary.runner.cmd_run.call_count, cap)
        rows = store.open_alerts(self.conn, "threshold")
        matching = [r for r in rows if r["target"] == self.TASK]
        expected_text = (f"canary: {cap} повторов developer на красной "
                         "планке — задача не сходится")
        self.assertTrue(any(r["message"] == expected_text for r in matching),
                        [r["message"] for r in matching])


class DriveTaskOtherClassRefusalDoesNotRetryDeveloperTest(unittest.TestCase):
    """`canary._drive_task` — отказ ДРУГОГО класса (не «приёмочные
    тесты») в `in_dev` не лечится повтором developer (требование 4,
    тест AC-9): планка не найдена в источнике/зоны/гейт заявки
    мутации/лок планки — прежняя стагнация (`config.
    CANARY_MAX_STALL_ITERS`) сохраняется байт-в-байт."""

    TASK = "T922"

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
                          "in_dev", "task/t922-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        def fake_auto(task_id):
            store.journal(self.conn, task_id, "fsm",
                         "переход отклонён: гейт заявки мутации",
                         "мутация не заявлена")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.runner, "cmd_run")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_other_class_refusal_never_calls_runner_cmd_run(self):
        """Ловит мутацию: детектор `_acceptance_refusal_blocks_in_dev`
        сравнивает по префиксу `"переход отклонён"` вместо точного текста
        `"переход отклонён: приёмочные тесты"` — отказ другого класса
        (гейт заявки мутации) ошибочно запустил бы повтор developer,
        хотя требование 4 предписывает не трогать это поведение."""
        canary._drive_task(self.conn, self.TASK)

        canary.runner.cmd_run.assert_not_called()
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)
        rows = store.open_alerts(self.conn, "threshold")
        matching = [r for r in rows if r["target"] == self.TASK]
        self.assertTrue(
            any("проходов подряд без прогресса" in r["message"]
               for r in matching),
            [r["message"] for r in matching])
        self.assertEqual(
            store.get_task(self.conn, self.TASK)["state"], "in_dev")


class PassVerifyingTest(unittest.TestCase):
    """`canary._pass_verifying` (ANSWER-3.md 06.09, задача
    01M1TKP269W9JN3NBJCR5Q6C3B): ADR-0015 переставил `verifying` перед
    ревьювером — приравнивание к финальному kill (старое `_kill_at_
    verifying`) убивало канареечную задачу раньше, чем прогон успевал
    дойти до сценариев «не сошлась»/эскалации (6 из 18 приёмочных тестов
    планки покраснели после подтяжки main по этой причине)."""

    TASK = "T912"

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
                          "verifying", "task/t912-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)
        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_transitions_to_review_instead_of_killing(self):
        """Ловит мутацию: `_pass_verifying` зовёт `cleanup.cmd_kill`
        вместо `store.set_state(..., "review", ...)` (старое поведение
        `_kill_at_verifying`) — задача осталась бы убитой на `verifying`,
        не дойдя до ревьювера, ровно дефект ANSWER-3.md."""
        canary._pass_verifying(self.conn, self.TASK)

        self.assertEqual(
            store.get_task(self.conn, self.TASK)["state"], "review")
        canary.cleanup.cmd_kill.assert_not_called()

    def test_journals_synthetic_pass_with_canary_actor(self):
        """Ловит мутацию: журнальная запись зовётся другим actor'ом или
        без своего текста вовсе — `_kill_outcome_note`/диагностика
        теряют след того, что переход был синтетическим, не реальным
        зелёным CI ветки."""
        canary._pass_verifying(self.conn, self.TASK)

        steps = store.task_steps(self.conn, self.TASK)
        self.assertTrue(any(
            r["actor"] == canary.CANARY_MARK_ACTOR
            and "verifying пройден синтетически" in r["action"]
            for r in steps))


class DriveTaskPassesVerifyingSyntheticallyTest(unittest.TestCase):
    """`canary._drive_task` — `verifying` больше не завершает вождение
    задачи (ANSWER-3.md 06.09): проходится синтетически, и цикл продолжает
    вести задачу дальше вместо того, чтобы считать её законченной здесь."""

    TASK = "T913"

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
                          "verifying", "task/t913-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        # `auto.cmd_auto` реально не входит в опрос `verifying` для
        # канареечных задач (auto.py, условие цикла с `is_canary`) — здесь
        # то же самое: no-op, всё решение — за `_drive_task` самим.
        patcher = mock.patch.object(canary.auto, "cmd_auto", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

        # После синтетического прохода в `review` у состояния нет
        # агентской роли в этом тесте (реального ревьювера не заводим) —
        # `_drive_task` обязан остановиться сам, не убивая задачу.
        patcher = mock.patch.object(canary.runner, "step_role", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_moves_past_verifying_into_review_without_killing(self):
        """Ловит мутацию: `_drive_task` при `state == "verifying"` снова
        зовёт `cleanup.cmd_kill`/`return` вместо `_pass_verifying`/
        `continue` (старое `_kill_at_verifying`) — задача осталась бы
        `killed` на `verifying`, тот же дефект, из-за которого 6 из 18
        тестов планки покраснели после подтяжки main (ADR-0015)."""
        canary._drive_task(self.conn, self.TASK)

        self.assertEqual(
            store.get_task(self.conn, self.TASK)["state"], "review")
        canary.cleanup.cmd_kill.assert_not_called()


class KillAtVerifyingCompatTest(unittest.TestCase):
    """`canary._kill_at_verifying` — `_drive_task` её больше не зовёт
    (см. `PassVerifyingTest`/`DriveTaskPassesVerifyingSyntheticallyTest`
    выше), но функция и признание её литерала «штатным» в
    `_kill_outcome_note` остаются нетронутыми: `tasks/
    01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
    test_canary_report_kill_reason.py::
    test_ac4_verifying_kill_is_also_reported_as_normal` (залоченная
    планка ДРУГОЙ, уже смерженной задачи) зовёт её напрямую и сверяет
    вывод — REVIEW.md 01M1TKP269W9JN3NBJCR5Q6C3B итерации 2, R2-F1."""

    TASK = "T914"

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
                          "verifying", "task/t914-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)
        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_journals_verifying_kill_action(self):
        """Ловит мутацию: `_kill_at_verifying` перестаёт журналировать
        `_VERIFYING_KILL_ACTION` (переименован/убран литерал) — чужая
        планка теряет след, по которому `_kill_outcome_note` узнаёт
        «штатно»."""
        canary._kill_at_verifying(self.conn, self.TASK)

        steps = store.task_steps(self.conn, self.TASK)
        self.assertTrue(any(
            r["actor"] == canary.CANARY_MARK_ACTOR
            and r["action"] == canary._VERIFYING_KILL_ACTION
            for r in steps))
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)

    def test_kill_outcome_note_still_classifies_it_as_normal(self):
        """Ловит мутацию: `_kill_outcome_note` перестаёт узнавать
        `_VERIFYING_KILL_ACTION` (например, если признание сузили обратно
        до одного лишь `_MERGE_GATE_KILL_ACTION`) — чужая планка красна."""
        canary._kill_at_verifying(self.conn, self.TASK)

        steps = store.task_steps(self.conn, self.TASK)
        self.assertEqual(
            canary._kill_outcome_note(self.conn, self.TASK, steps), "штатно")


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


class RunOneTaskVerdictUsesNormalOutcomeTest(unittest.TestCase):
    """Возврат из merge_gate (06.09, п.2): verdict привязки пина
    (`canary._run_one_task` -> `store.insert_canary_run(verdict=...)`)
    обязан читать «смерженное» понятие штатного исхода прогона
    (`normal_outcome`/`_needs_diagnostics`, ANSWER-1.md правило 1), не
    маркер «дошла до состояния merge_gate/verifying» — `verifying` с
    ADR-0015 не конечная точка реального вождения вовсе (проходится
    синтетически, `_pass_verifying`), поэтому только `_needs_diagnostics`
    может корректно отличить зелёный исход от красного."""

    def test_verdict_formula_matches_needs_diagnostics_inverse(self):
        """Ловит мутацию: `verdict` вычисляется любым другим способом,
        кроме `not _needs_diagnostics(normal_outcome, mismatch)` —
        таблица истинности та же, что уже покрыта `NeedsDiagnosticsTest`."""
        for normal_outcome, mismatch, expected in (
            (True, False, "green"),
            (False, False, "red"),
            (True, True, "red"),
            (False, True, "red"),
        ):
            with self.subTest(normal_outcome=normal_outcome, mismatch=mismatch):
                verdict = ("green"
                          if not canary._needs_diagnostics(normal_outcome, mismatch)
                          else "red")
                self.assertEqual(verdict, expected)


class MergesSinceLastGreenRunTest(RealGitSandbox):
    """`canary.merges_since_last_green_run` (tasks/
    01M1NGFK3N6MRMYGCC09H975V3, ANSWER-1 п.3) — общая арифметика
    возраста guard'а AC-1/AC-3/AC-4. Реальный git: сама история мержей —
    предмет проверки, заглушкой не изобразить (тот же приём, что
    `CommitsBehindTest` в tests/test_gitcmd_branch_reads.py)."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def _merge(self, name: str) -> str:
        self.checkout(name, create=True)
        (self.root / f"{name}.txt").write_text("x\n", encoding="utf-8")
        self.git("add", f"{name}.txt")
        self.git("commit", "-q", "-m", f"работа {name}")
        self.checkout(config.MAIN_BRANCH)
        self.git("merge", "--no-ff", "-q", "-m", f"merge {name}", name)
        return self.git("rev-parse", "HEAD").strip()

    def _insert_green(self, run_stamp: str, main_sha: str) -> None:
        store.insert_canary_run(
            self.conn, run_stamp, "t", f"01{run_stamp}", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=main_sha, verdict="green")

    def test_empty_journal_is_none(self):
        """Ловит мутацию: пустой журнал трактуется как «возраст 0»
        вместо `None` — вырожденный случай AC-3 («сравнивать не с чем» ⇔
        «порог всегда достигнут») слился бы с «только что прогнали»."""
        head = self.git("rev-parse", "HEAD").strip()

        self.assertIsNone(canary.merges_since_last_green_run(self.conn, head))

    def test_picks_the_minimum_age_among_several_valid_green_runs(self):
        """Ловит мутацию: берётся ПЕРВЫЙ подходящий прогон (порядок
        `store.green_canary_runs`, свежие первыми) вместо МИНИМАЛЬНОГО
        возраста среди всех валидных — здесь оба прогона валидны, но
        `r2` (mid_sha) младше `r1` (old_sha); взятие не-минимума дало бы
        2 вместо 1."""
        old_sha = self.git("rev-parse", "HEAD").strip()
        mid_sha = self._merge("m1")
        target = self._merge("m2")
        self._insert_green("r1", old_sha)
        self._insert_green("r2", mid_sha)

        self.assertEqual(
            canary.merges_since_last_green_run(self.conn, target), 1)

    def test_red_verdict_is_ignored(self):
        """Ловит мутацию: `store.green_canary_runs` не фильтрует по
        `verdict`, либо `merges_since_last_green_run` сам не проверяет
        его — красный прогон посчитался бы валидным источником возраста."""
        red_sha = self.git("rev-parse", "HEAD").strip()
        target = self._merge("m1")
        store.insert_canary_run(
            self.conn, "r1", "t", "01AAA", steps=1, cost_usd=0.1,
            review_iterations=0, escalations=0, outcome="killed",
            expected_escalation=None, actual_escalation=False,
            marker_mismatch=False, main_sha=red_sha, verdict="red")

        self.assertIsNone(
            canary.merges_since_last_green_run(self.conn, target))

    def test_run_on_an_unrelated_branch_is_not_considered(self):
        """Ловит мутацию: фильтр `gitcmd.is_ancestor(main_sha, target_sha)`
        пропущен — прогон с чужой, несвязанной историей (тупиковая ветка)
        посчитался бы валидным источником возраста вместо того, чтобы
        быть отброшенным целиком (ANSWER-1 п.3)."""
        self.checkout("abandoned", create=True)
        (self.root / "x.txt").write_text("x\n", encoding="utf-8")
        self.git("add", "x.txt")
        self.git("commit", "-q", "-m", "тупиковая ветка")
        abandoned_sha = self.git("rev-parse", "HEAD").strip()
        self.checkout(config.MAIN_BRANCH)
        target = self._merge("m1")
        self._insert_green("r1", abandoned_sha)

        self.assertIsNone(
            canary.merges_since_last_green_run(self.conn, target))


class SpecGateArtifactSourceTest(RealGitSandbox):
    """`canary._spec_gate_next_state`/`_pass_spec_gate` (SPEC
    01M2A22CG2P0E69H00RDHFF3K4): после ADR-0016 `tasks/<id>/` живёт
    ТОЛЬКО в артефактной ветке пульта (`artifact/<id>`) — ни на кодовой
    ветке задачи (которая на стадии `spec_gate` зачастую ещё не заведена
    в git вовсе), ни на диске `config.TASKS/<id>/SPEC.md`. Реальный git —
    сам предмет проверки (расхождение чтения с кодовой и с артефактной
    ветки), заглушкой `fake_git` не изобразить."""

    TASK = "T950"
    CODE_BRANCH = "task/t950-marker"

    SPEC_WITH_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: маркер артефактной ветки

## Критерии приёмки
AC-1. Критерий.
"""

    SPEC_SKIP_TESTS = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
skip_tests: причина пропуска
---

# SPEC: маркер артефактной ветки

## Критерии приёмки
AC-1. Критерий.
"""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача",
                          "spec_gate", self.CODE_BRANCH, config.DEFAULT_TARGET,
                          50.0, is_canary=True)
        self.artifact_branch = artifact_branch.branch_name(self.TASK)

    def _commit_spec_on_artifact_branch(self, template: str) -> None:
        self.checkout(self.artifact_branch, create=True)
        d = self.root / "tasks" / self.TASK
        d.mkdir(parents=True, exist_ok=True)
        (d / "SPEC.md").write_text(template.format(task=self.TASK),
                                   encoding="utf-8")
        self.git("add", f"tasks/{self.TASK}")
        self.git("commit", "-q", "-m", "SPEC задачи")
        self.checkout(config.MAIN_BRANCH)

    def test_ac1_spec_only_on_artifact_branch_goes_to_tests_writing(self):
        """Ловит мутацию (AC-6): `_spec_gate_next_state` определяет
        источник SPEC обратно через `gitcmd.on_foreign_branch(t
        ["branch"])` (кодовая ветка), не через `artifact_source.
        resolve` — кодовая ветка задачи не существует в git вовсе на
        этой стадии, `on_foreign_branch` даёт `False`, мутировавший код
        падает на пустой disk-read (`config.TASKS/<id>/SPEC.md` тоже не
        существует) и вернул бы `in_dev` вместо `tests_writing`, минуя
        test_author."""
        self._commit_spec_on_artifact_branch(self.SPEC_WITH_AC)
        t = store.get_task(self.conn, self.TASK)

        with mock.patch.object(canary.gitcmd, "on_foreign_branch") as spy:
            result = canary._spec_gate_next_state(self.conn, self.TASK, t)

        self.assertEqual(result, "tests_writing")
        spy.assert_not_called()  # AC-4

    def test_ac2_skip_tests_on_artifact_branch_goes_to_in_dev(self):
        """Ловит мутацию: `_spec_gate_next_state` игнорирует `skip_tests`
        из frontmatter артефактной ветки (например, читает только
        раздел «Критерии приёмки» и не смотрит на поле `meta`) —
        SPEC с `skip_tests: <причина>` ошибочно ушёл бы `tests_writing`
        вместо штатного `in_dev`."""
        self._commit_spec_on_artifact_branch(self.SPEC_SKIP_TESTS)
        t = store.get_task(self.conn, self.TASK)

        result = canary._spec_gate_next_state(self.conn, self.TASK, t)

        self.assertEqual(result, "in_dev")

    def test_ac3_spec_not_found_anywhere_kills_inconclusive_not_in_dev(self):
        """Ловит мутацию: `_spec_gate_next_state` возвращает `"in_dev"`
        вместо `None`, когда SPEC не прочитан ни с одной ветки (ни
        артефактная ветка не заведена, ни SPEC на диске) — `_pass_spec_
        gate` истолковал бы отсутствие SPEC как «без AC-разметки» и
        перевёл бы задачу в `in_dev`, вместо вызова `_kill_inconclusive`
        с именованной причиной (требование 2)."""
        with mock.patch.object(canary.cleanup, "cmd_kill") as kill:
            canary._pass_spec_gate(self.conn, self.TASK)

        kill.assert_called_once_with(self.TASK)
        self.assertEqual(
            store.get_task(self.conn, self.TASK)["state"], "spec_gate")
        steps = store.task_steps(self.conn, self.TASK)
        self.assertTrue(any(
            "SPEC не найден в источнике артефактов" in r["action"]
            for r in steps))


class PoolSerializationRoundtripTest(unittest.TestCase):
    """`canary._serialize_pool`/`_deserialize_pool` (SPEC
    01M1NSR5M5THYRC0RFWPMVE2DW) — байт-в-байт round trip самой
    сериализации в изоляции от шифрования/диска: юникод, пустой файл,
    пустой пул. Полный цикл seal -> restore уже покрыт приёмочными
    тестами (AC-16) — здесь только эта прослойка."""

    def test_roundtrip_preserves_names_and_bytes(self):
        """Ловит мутацию: длина-префикс имени/содержимого перепутана
        местами либо формат `struct` сужен (например, `>I` вместо `>Q`
        для длины содержимого) — юникод-имя или байты содержимого
        побьются на границе разбора, `restored` разойдётся с исходником
        либо `_deserialize_pool` упадёт на смещении."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "a.md").write_text(
            "тело А, юникод: üñïçødé\n", encoding="utf-8")
        (root / "b.md").write_bytes(b"")
        files = sorted(root.iterdir())

        restored = canary._deserialize_pool(canary._serialize_pool(files))

        self.assertEqual(set(restored), {"a.md", "b.md"})
        self.assertEqual(restored["a.md"], (root / "a.md").read_bytes())
        self.assertEqual(restored["b.md"], b"")

    def test_empty_pool_serializes_to_empty_payload(self):
        """Ловит мутацию: `_serialize_pool` пишет заголовок/счётчик даже
        для пустого списка файлов — `_serialize_pool([])` перестал бы
        быть пустой строкой байт, и `_deserialize_pool(b"")` либо упал
        бы, либо вернул неверную форму словаря."""
        self.assertEqual(canary._serialize_pool([]), b"")
        self.assertEqual(canary._deserialize_pool(b""), {})


class MacKeyTest(unittest.TestCase):
    """`canary._mac_key` — ключ HMAC выводится из ключа пула
    детерминированно (ANSWER-1 п.1): тот же вход -> тот же результат,
    разный вход -> разный, и сам вывод не совпадает с исходным ключом
    (иначе тег и шифрование делили бы один материал)."""

    def test_same_input_gives_same_mac_key(self):
        """Ловит мутацию: вывод подмешивает недетерминированную соль
        (`os.urandom`/временную метку) — два вызова на тот же ключ
        пула разошлись бы, и `_authorized_pool_payload` не смог бы
        воспроизвести тег при восстановлении, посчитанный при seal."""
        self.assertEqual(canary._mac_key("key-A"), canary._mac_key("key-A"))

    def test_different_input_gives_different_mac_key(self):
        """Ловит мутацию: `_mac_key` игнорирует аргумент и возвращает
        константу (заглушка вместо реального вывода) — разные ключи
        пула дали бы один и тот же MAC-ключ."""
        self.assertNotEqual(canary._mac_key("key-A"), canary._mac_key("key-B"))

    def test_mac_key_is_not_the_pool_key_itself(self):
        """Ловит мутацию: `_mac_key` возвращает ключ пула без вывода
        (забытый `hashlib.sha256(...)`) — тег и шифрование делили бы
        один материал вопреки разделению ключей ANSWER-1 п.1."""
        self.assertNotEqual(canary._mac_key("key-A"), "key-A")


class AuthorizedPoolPayloadRoleEnvTest(unittest.TestCase):
    """`canary._authorized_pool_payload` — рубеж role_env (требование 5,
    AC-15) срабатывает ДО любого обращения к keychain: и restore, и
    drift-warning идут через эту единую точку входа, поэтому проверяется
    здесь один раз, а не в обоих вызывающих."""

    def test_role_environment_refuses_before_touching_keychain(self):
        """Ловит мутацию: проверка `runner.in_role_environment()`
        переставлена ПОСЛЕ `keychain.token(...)` (или убрана вовсе) —
        `token_mock` был бы вызван раньше отказа, требование 5/AC-15
        («второй, независимый от permissions.deny рубеж») перестало бы
        держаться этой единой точкой входа."""
        with mock.patch.object(canary.runner, "in_role_environment",
                               return_value=True):
            with mock.patch.object(canary.keychain, "token") as token_mock:
                payload, refusal = canary._authorized_pool_payload()

        self.assertIsNone(payload)
        self.assertIn("role_env", refusal)
        token_mock.assert_not_called()


class RestorePoolIfMissingNoOpTest(unittest.TestCase):
    """`canary.restore_pool_if_missing` — каталог пула уже есть (AC-7):
    no-op молча, keychain не спрашивается вовсе (нечего расшифровывать)."""

    def test_existing_pool_dir_short_circuits_before_keychain(self):
        """Ловит мутацию: проверка `pool_dir.exists()` убрана или
        переставлена после обращения к keychain — `token_mock` был бы
        вызван даже когда `~/.artel-canary` уже есть, нарушая AC-7
        («при наличии каталога ничего не трогают»)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        existing = Path(tmp.name)
        with mock.patch.object(canary, "_pool_dir", return_value=existing):
            with mock.patch.object(canary.keychain, "token") as token_mock:
                result = canary.restore_pool_if_missing(conn=None)

        self.assertIsNone(result)
        token_mock.assert_not_called()


class OpensslSecretPassingTest(unittest.TestCase):
    """`canary._openssl_encrypt`/`_openssl_decrypt` — ключ передаётся
    `openssl enc` через файловый дескриптор (`-pass fd:N`), не
    аргументом командной строки (REVIEW.md итерации 1, R1-F1): аргумент
    виден в выводе `ps`/`ps aux` любому процессу того же пользователя
    на время жизни подпроцесса — ровно тот секрет, ради которого
    существует вся задача."""

    KEY = "unit-test-fd-key-98765"

    @staticmethod
    def _spy(calls):
        def fake_run(cmd, **kw):
            calls.append((list(cmd), kw))
            return subprocess.CompletedProcess(cmd, 0, b"stub-output", b"")
        return fake_run

    def test_encrypt_argv_never_carries_the_raw_key(self):
        """Ловит мутацию: регресс к `-pass pass:{key}` литералом в
        argv — греп по буквальному значению ключа среди ВСЕХ элементов
        вызова находит его; отсутствие `pass_fds` в kwargs тоже ловится
        (без него дескриптор не переживает `exec`)."""
        calls = []
        with mock.patch.object(canary.subprocess, "run",
                               side_effect=self._spy(calls)):
            canary._openssl_encrypt(b"payload", self.KEY)

        self.assertTrue(calls)
        cmd, kw = calls[0]
        self.assertNotIn(self.KEY, cmd, f"ключ найден буквально в argv: {cmd}")
        self.assertTrue(
            any(isinstance(a, str) and a.startswith("fd:") for a in cmd),
            f"-pass не передан через fd:N: {cmd}")
        self.assertIn("pass_fds", kw)

    def test_decrypt_argv_never_carries_the_raw_key(self):
        """Ловит мутацию: то же самое для расшифровки — регресс к
        `-pass pass:{key}` в `_openssl_decrypt`."""
        calls = []
        with mock.patch.object(canary.subprocess, "run",
                               side_effect=self._spy(calls)):
            canary._openssl_decrypt(b"ciphertext-stub", self.KEY)

        self.assertTrue(calls)
        cmd, kw = calls[0]
        self.assertNotIn(self.KEY, cmd, f"ключ найден буквально в argv: {cmd}")
        self.assertIn("pass_fds", kw)


if __name__ == "__main__":
    unittest.main()
