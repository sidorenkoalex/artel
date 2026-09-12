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

from orchestrator import canary, catalog, config, retro, store  # noqa: E402
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
            with canary._ephemeral_clone() as dest:
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
                with canary._ephemeral_clone():
                    raise ValueError("boom")

        for attr in canary._CLONE_CONFIG_ATTRS:
            self.assertEqual(getattr(config, attr), saved_before[attr])
        self.assertFalse(fake_clone_dir.exists())


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
