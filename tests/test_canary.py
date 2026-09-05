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
from tests.sandbox import capture  # noqa: E402


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


class PoolSerializationRoundtripTest(unittest.TestCase):
    """`canary._serialize_pool`/`_deserialize_pool` (SPEC
    01M1NSR5M5THYRC0RFWPMVE2DW) — байт-в-байт round trip самой
    сериализации в изоляции от шифрования/диска: юникод, пустой файл,
    пустой пул. Полный цикл seal -> restore уже покрыт приёмочными
    тестами (AC-16) — здесь только эта прослойка."""

    def test_roundtrip_preserves_names_and_bytes(self):
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
        self.assertEqual(canary._serialize_pool([]), b"")
        self.assertEqual(canary._deserialize_pool(b""), {})


class MacKeyTest(unittest.TestCase):
    """`canary._mac_key` — ключ HMAC выводится из ключа пула
    детерминированно (ANSWER-1 п.1): тот же вход -> тот же результат,
    разный вход -> разный, и сам вывод не совпадает с исходным ключом
    (иначе тег и шифрование делили бы один материал)."""

    def test_same_input_gives_same_mac_key(self):
        self.assertEqual(canary._mac_key("key-A"), canary._mac_key("key-A"))

    def test_different_input_gives_different_mac_key(self):
        self.assertNotEqual(canary._mac_key("key-A"), canary._mac_key("key-B"))

    def test_mac_key_is_not_the_pool_key_itself(self):
        self.assertNotEqual(canary._mac_key("key-A"), "key-A")


class AuthorizedPoolPayloadRoleEnvTest(unittest.TestCase):
    """`canary._authorized_pool_payload` — рубеж role_env (требование 5,
    AC-15) срабатывает ДО любого обращения к keychain: и restore, и
    drift-warning идут через эту единую точку входа, поэтому проверяется
    здесь один раз, а не в обоих вызывающих."""

    def test_role_environment_refuses_before_touching_keychain(self):
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
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        existing = Path(tmp.name)
        with mock.patch.object(canary, "_pool_dir", return_value=existing):
            with mock.patch.object(canary.keychain, "token") as token_mock:
                result = canary.restore_pool_if_missing(conn=None)

        self.assertIsNone(result)
        token_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
