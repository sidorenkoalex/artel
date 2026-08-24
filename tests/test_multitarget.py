"""Тесты мультитаргетного контура (см. tasks/T019/SPEC.md, критерии 1–8).

Классы названы по критериям приёмки: декларация целевых (targets.yaml),
каталог проекта в .artel/, колонка target в БД и миграция старых строк,
персистентная нумерация задач, режим журнала БД, консолидация SQL
в store.py, пороги суммарного расхода программы и окружение процесса
роли.

Песочница как в соседних модулях: пути config подменяются на временный
каталог, `claude` и git не запускаются.
"""
import io
import re
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (budget, catalog, config, projects,  # noqa: E402
                          runner, spend, store, targets)

REPO_ROOT = Path(__file__).resolve().parent.parent

TARGETS_YAML = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: [gates.yaml, .github/]
    project_skills: []
    merge_gate: operator
"""

# Схема tasks и steps до T019 — на ней проверяется миграция под мультитаргет.
LEGACY_SCHEMA = """
CREATE TABLE tasks (
  id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
  review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
  reviewed_iter INTEGER DEFAULT 0, escalated_from TEXT,
  budget_usd REAL, spent_usd REAL DEFAULT 0, budget_source TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, ts TEXT,
  actor TEXT, action TEXT, detail TEXT
);
"""


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class TmpRootTest(unittest.TestCase):
    """Песочница: БД, каталоги проектов и слой ролей во временном каталоге."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

        for attr, value in (("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("PROJECTS", self.root / ".artel" / "projects"),
                            ("ROLE_HOME", self.root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             self.root / ".artel" / "home" / ".claude"),
                            ("TARGETS", self.root / "targets.yaml")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_targets(self, text: str = TARGETS_YAML) -> None:
        config.TARGETS.write_text(text, encoding="utf-8")

    def legacy_db(self, rows: list) -> None:
        """БД со схемой до T019 и строками задач: (id, state, spent_usd)."""
        config.DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(config.DB)
        conn.executescript(LEGACY_SCHEMA)
        for task_id, state, spent in rows:
            conn.execute(
                "INSERT INTO tasks (id,title,state,branch,budget_usd,spent_usd)"
                " VALUES (?,?,?,?,?,?)",
                (task_id, f"задача {task_id}", state,
                 f"task/{task_id.lower()}", 25.0, spent))
            conn.execute(
                "INSERT INTO steps (task_id, ts, actor, action, detail)"
                " VALUES (?,?,?,?,?)",
                (task_id, "2026-08-01 00:00:00Z", "operator", "created", ""))
        conn.commit()
        conn.close()


class TargetsFileTest(TmpRootTest):
    """Критерий 1: запись target'а читается кодом, невалидная — отказ с полем."""

    def test_artel_record_is_read(self):
        self.write_targets()

        entry = targets.target("artel")

        self.assertEqual(entry["forge"], "github")
        self.assertEqual(entry["base"], "main")
        self.assertEqual(entry["merge_gate"], "operator")
        self.assertEqual(entry["no_paths"], ["gates.yaml", ".github/"])
        self.assertEqual(entry["project_skills"], [])

    def test_artel_is_the_first_record(self):
        """Порядок записей файла виден коду: первая запись — сам пульт."""
        self.write_targets(TARGETS_YAML + """  sled:
    forge: github
    url: https://example.invalid/sled
    base: main
    token_slot: sled-token
    no_paths: []
    project_skills: []
    merge_gate: target-human
""")

        self.assertEqual(list(targets.load()), ["artel", "sled"])

    def test_missing_field_is_named(self):
        """Критерий 1: запись без forge — отказ, и в нём названо поле."""
        broken = TARGETS_YAML.replace("    forge: github\n", "")

        self.write_targets(broken)

        with self.assertRaises(targets.TargetsError) as ctx:
            targets.target("artel")
        self.assertIn("forge", str(ctx.exception))
        self.assertIn("artel", str(ctx.exception))

    def test_unknown_forge_and_merge_gate_are_refused(self):
        for field, value in (("forge", "gitea"), ("merge_gate", "auto")):
            with self.subTest(поле=field):
                current = {"forge": "github", "merge_gate": "operator"}[field]
                self.write_targets(TARGETS_YAML.replace(
                    f"{field}: {current}", f"{field}: {value}"))

                with self.assertRaises(targets.TargetsError) as ctx:
                    targets.load()
                self.assertIn(field, str(ctx.exception))

    def test_broken_file_is_refused_by_reason_not_traceback(self):
        for text, expected in (("targets:\n  artel:\n\tforge: github\n",
                                "табуляция"),
                               ("targets: null\n", "нет раздела"),
                               ("roles:\n  developer:\n    skills: []\n",
                                "нет раздела")):
            with self.subTest(файл=text[:20]):
                self.write_targets(text)

                with self.assertRaises(targets.TargetsError):
                    targets.load()

    def test_missing_file_is_refused_by_reason(self):
        with self.assertRaises(targets.TargetsError) as ctx:
            targets.load()
        self.assertIn("не прочитан", str(ctx.exception))

    def test_undeclared_target_is_refused(self):
        self.write_targets()

        with self.assertRaises(targets.TargetsError) as ctx:
            targets.target("sled")
        self.assertIn("sled", str(ctx.exception))

    def test_repository_file_is_valid(self):
        """Файл самого репозитория читается тем же кодом, что и в песочнице."""
        with mock.patch.object(config, "TARGETS", REPO_ROOT / "targets.yaml"):
            entries = targets.load()

        self.assertEqual(list(entries)[0], config.DEFAULT_TARGET)
        self.assertEqual(entries["artel"]["forge"], "github")
        self.assertEqual(entries["artel"]["base"], config.MAIN_BRANCH)


class TargetInitTest(TmpRootTest):
    """Критерий 2: команда заводит структуру 3д и повторяется без вреда."""

    def setUp(self):
        super().setUp()
        self.write_targets()

    def dirs(self) -> list:
        return sorted(p.name for p in
                      (config.PROJECTS / "artel").iterdir())

    def test_structure_is_created(self):
        capture(projects.cmd_target_init, "artel")

        self.assertEqual(self.dirs(),
                         sorted(config.PROJECT_DIRS))
        self.assertEqual(sorted(config.PROJECT_DIRS),
                         ["knowledge", "logs", "tasks", "workspace"])

    def test_second_call_is_idempotent(self):
        capture(projects.cmd_target_init, "artel")
        (config.PROJECTS / "artel" / "tasks" / "T001").mkdir()

        out = capture(projects.cmd_target_init, "artel")

        self.assertEqual(self.dirs(), sorted(config.PROJECT_DIRS))
        self.assertIn("уже был", out)
        self.assertTrue((config.PROJECTS / "artel" / "tasks" / "T001").is_dir(),
                        "повторный вызов не трогает содержимое каталога")

    def test_missing_subdir_is_restored(self):
        capture(projects.cmd_target_init, "artel")
        (config.PROJECTS / "artel" / "knowledge").rmdir()

        capture(projects.cmd_target_init, "artel")

        self.assertEqual(self.dirs(), sorted(config.PROJECT_DIRS))

    def test_undeclared_target_creates_nothing(self):
        """Каталог без декларации был бы сиротой — команда отказывает."""
        with self.assertRaises(SystemExit) as ctx:
            capture(projects.cmd_target_init, "sled")

        self.assertIn("sled", str(ctx.exception))
        self.assertFalse((config.PROJECTS / "sled").exists())


class TargetColumnTest(TmpRootTest):
    """Критерий 3: колонка target, миграция старых строк, ничего не потеряно."""

    LEGACY = [("T001", "done", 2.40), ("T002", "done", 5.00),
              ("T017", "killed", 12.50)]

    def test_existing_rows_get_the_dogfood_target(self):
        self.legacy_db(self.LEGACY)

        conn = store.db()

        rows = {r["id"]: r for r in store.all_tasks(conn)}
        self.assertEqual(sorted(rows), ["T001", "T002", "T017"])
        for task_id, _, _ in self.LEGACY:
            self.assertEqual(rows[task_id]["target"], config.DEFAULT_TARGET)

    def test_states_and_spending_are_untouched(self):
        """Миграция добавляет колонку, а не переписывает историю задач."""
        self.legacy_db(self.LEGACY)

        conn = store.db()

        rows = {r["id"]: r for r in store.all_tasks(conn)}
        for task_id, state, spent in self.LEGACY:
            self.assertEqual(rows[task_id]["state"], state)
            self.assertAlmostEqual(rows[task_id]["spent_usd"], spent)
        self.assertAlmostEqual(store.total_spent(conn), 19.90)

    def test_journal_rows_carry_the_target_too(self):
        self.legacy_db(self.LEGACY)
        conn = store.db()

        store.journal(conn, "T001", "operator", "проверка")

        targets_seen = {r["target"] for r in store.task_steps(conn, "T001")}
        self.assertEqual(targets_seen, {config.DEFAULT_TARGET},
                         "старая запись мигрирована, новая пишется с target")

    def test_new_task_is_written_with_its_target(self):
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Мультитаргет")

        conn = store.db()
        self.assertEqual(store.get_task(conn, "T001")["target"],
                         config.DEFAULT_TARGET)
        self.assertEqual(store.task_target(conn, "T001"),
                         config.DEFAULT_TARGET)

    def test_schema_stays_portable(self):
        """Переносимость (ADR-0003 3ж): типы колонок — общий SQL."""
        capture(catalog.cmd_init)
        conn = store.db()

        for table in ("tasks", "steps", "task_counters"):
            with self.subTest(таблица=table):
                types = {r["type"].upper() for r in
                         conn.execute(f"PRAGMA table_info({table})")}
                self.assertTrue(types <= {"TEXT", "INTEGER", "REAL"},
                                f"экзотические типы в {table}: {types}")


class TaskNumberingTest(TmpRootTest):
    """Критерий 4: номера задач не переиспользуются после архивации строки."""

    def numbers(self, conn) -> list:
        return sorted(r["id"] for r in store.all_tasks(conn))

    def archive(self, conn, task_id: str) -> None:
        """Архивация строки задачи (в A1 её механики ещё нет — эмуляция)."""
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()

    def test_number_is_not_reused_after_a_row_is_archived(self):
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Первая")
        capture(catalog.cmd_new, "Вторая")
        self.archive(store.db(), "T002")

        capture(catalog.cmd_new, "Третья")

        self.assertEqual(self.numbers(store.db()), ["T001", "T003"],
                         "COUNT(*) выдал бы T002 второй раз")

    def test_counter_survives_a_reopen_of_the_database(self):
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Первая")

        self.assertEqual(store.next_task_number(store.db(), "artel"), 2)
        self.assertEqual(store.next_task_number(store.db(), "artel"), 3)

    def test_counter_is_seeded_from_the_highest_existing_number(self):
        """Счётчик догоняет БД Фазы 0: следующая задача — за максимальной."""
        self.legacy_db([("T001", "done", 1.0), ("T017", "done", 2.0)])

        capture(catalog.cmd_new, "После миграции")

        self.assertIn("T018", self.numbers(store.db()))

    def test_counters_are_per_target(self):
        conn = store.db()
        store.create_schema(conn)

        first = [store.next_task_number(conn, "artel") for _ in range(3)]
        second = [store.next_task_number(conn, "sled") for _ in range(2)]

        self.assertEqual(first, [1, 2, 3])
        self.assertEqual(second, [1, 2], "счётчик проекта свой, не общий")

    def test_task_number_reads_the_identifier(self):
        for task_id, expected in (("T001", 1), ("T019", 19), ("T1000", 1000),
                                  ("", 0), ("XYZ", 0), ("T0x1", 0)):
            with self.subTest(id=task_id):
                self.assertEqual(store.task_number(task_id), expected)


class JournalModeTest(TmpRootTest):
    """Критерий 5: журнал БД — WAL."""

    def test_database_is_opened_in_wal(self):
        capture(catalog.cmd_init)

        conn = store.db()

        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

    def test_unsupported_wal_does_not_break_the_cli(self):
        """Режим не включился (сетевая ФС) — команда всё равно работает."""
        refusing = mock.Mock()
        refusing.execute.side_effect = sqlite3.OperationalError("нет WAL")

        self.assertEqual(store.enable_wal(refusing), "unknown")


class SqlOnlyInStoreTest(unittest.TestCase):
    """Критерий 6: прямых запросов вне store.py в orchestrator/ не осталось."""

    SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|PRAGMA|ALTER|CREATE)\b")

    def test_no_sql_outside_store(self):
        offenders = []
        for path in sorted((REPO_ROOT / "orchestrator").glob("*.py")):
            if path.name == "store.py":
                continue
            for number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                if self.SQL.search(line):
                    offenders.append(f"{path.name}:{number}: {line.strip()}")

        self.assertEqual(offenders, [], "SQL живёт только в store.py "
                                        "(ADR-0003 3ж)")

    def test_store_is_the_module_that_has_it(self):
        """Обратная сторона: тест ищет то, что действительно ищется."""
        text = (REPO_ROOT / "orchestrator" / "store.py").read_text(
            encoding="utf-8")

        self.assertTrue(self.SQL.search(text))


class ProgramSpendTest(TmpRootTest):
    """Критерий 7: пороги 70% и 90% суммарного расхода — событие и алерт."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Пороги программы")

    def spend_to(self, total: float) -> None:
        """Ставит суммарный расход программы равным total."""
        store.update_task(store.db(), "T001", spent_usd=total)

    def step(self, usd: float) -> str:
        """Шаг стоимостью usd: учёт стоимости и проверка порогов после него."""
        conn = store.db()
        cost = {"usd": usd, "tokens": None}
        out = capture(spend.charge_step, conn, "T001", "developer", cost, "1/3")
        return out + capture(budget.check_program_spend, conn, "T001", cost)

    def events(self) -> list:
        return [r["detail"] for r in store.task_steps(store.db(), "T001")
                if r["action"] == "программа: порог расхода"]

    def test_crossing_seventy_percent_warns_and_journals(self):
        self.spend_to(config.PROGRAM_STOP_LOSS_USD * 0.7 - 1)

        out = self.step(2.0)

        self.assertIn("ВНИМАНИЕ", out)
        self.assertEqual(len(self.events()), 1)
        self.assertIn("70%", self.events()[0])
        self.assertIn("$1401.00", self.events()[0])

    def test_ninety_percent_is_a_second_event(self):
        self.spend_to(config.PROGRAM_STOP_LOSS_USD * 0.7 - 1)
        self.step(2.0)

        self.spend_to(config.PROGRAM_STOP_LOSS_USD * 0.9 - 1)
        out = self.step(2.0)

        self.assertIn("90%", out)
        events = self.events()
        self.assertEqual(len(events), 2, "оба порога — отдельными записями")
        self.assertIn("70%", events[0])
        self.assertIn("90%", events[1])

    def test_threshold_fires_once_not_on_every_step(self):
        self.spend_to(config.PROGRAM_STOP_LOSS_USD * 0.7 - 1)
        self.step(2.0)

        out = self.step(2.0)

        self.assertNotIn("ВНИМАНИЕ", out)
        self.assertEqual(len(self.events()), 1,
                         "порог — событие пересечения, а не состояние")

    def test_quiet_below_the_threshold(self):
        self.spend_to(10.0)

        out = self.step(5.0)

        self.assertNotIn("ВНИМАНИЕ", out)
        self.assertEqual(self.events(), [])

    def test_unknown_step_cost_is_not_a_crossing(self):
        self.spend_to(config.PROGRAM_STOP_LOSS_USD * 0.7 - 1)

        out = self.step(0.0) + capture(
            budget.check_program_spend, store.db(), "T001", None)

        self.assertNotIn("ВНИМАНИЕ", out)
        self.assertEqual(self.events(), [])

    def test_sum_covers_all_tasks_not_only_the_current_one(self):
        """Кошелёк Оператора один: сумма считается по всем задачам."""
        capture(catalog.cmd_new, "Вторая задача")
        store.update_task(store.db(), "T002",
                          spent_usd=config.PROGRAM_STOP_LOSS_USD * 0.7 - 1)

        self.step(2.0)

        self.assertEqual(len(self.events()), 1)


class RoleEnvTest(TmpRootTest):
    """Критерий 8: процесс роли несёт HOME и CLAUDE_CONFIG_DIR из .artel/."""

    def test_env_points_at_the_curated_layer(self):
        env = runner.role_env()

        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(config.ROLE_CONFIG_DIR))
        self.assertTrue(config.ROLE_CONFIG_DIR.is_dir(),
                        "каталог слоя заводит пульт, а не CLI на ходу")

    def test_layer_is_inside_artel_not_in_the_operator_home(self):
        env = runner.role_env()

        self.assertTrue(env["HOME"].startswith(str(self.root)))
        self.assertNotEqual(env["HOME"], str(Path.home()))

    def test_rest_of_the_environment_is_inherited(self):
        """Подменяются два адреса, а не всё окружение: PATH роли нужен."""
        with mock.patch.dict(runner.os.environ, {"PATH": "/usr/bin"}):
            env = runner.role_env()

        self.assertEqual(env["PATH"], "/usr/bin")

    def test_agent_process_gets_that_environment(self):
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Окружение роли")
        store.update_task(store.db(), "T001", state="in_dev")

        with mock.patch.object(runner.subprocess, "Popen") as popen:
            popen.return_value = FakeProc(["готово\n"])
            capture(runner.cmd_run, "T001")

        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(config.ROLE_CONFIG_DIR))

    def test_step_does_not_start_without_the_layer(self):
        """Каталог не создался — шаг пропущен, а не запущен с HOME Оператора."""
        capture(catalog.cmd_init)
        capture(catalog.cmd_new, "Окружение роли")
        store.update_task(store.db(), "T001", state="in_dev")

        with mock.patch.object(runner, "role_env",
                               side_effect=OSError("нет места")), \
                mock.patch.object(runner.subprocess, "Popen") as popen:
            out = capture(runner.cmd_run, "T001")

        popen.assert_not_called()
        self.assertIn("окружение роли не подготовлено", out)
        details = [r["detail"] for r in store.task_steps(store.db(), "T001")
                   if r["action"] == "agent run SKIPPED"]
        self.assertTrue(details and "нет места" in details[0])


if __name__ == "__main__":
    unittest.main()
