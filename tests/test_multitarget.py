"""Тесты мультитаргетного контура (см. tasks/T019/SPEC.md, критерии 1–8).

Классы названы по критериям приёмки: декларация целевых (targets.yaml),
каталог проекта в .artel/, колонка target в БД и миграция старых строк,
персистентная нумерация задач, режим журнала БД, консолидация SQL
в store.py, пороги суммарного расхода программы и окружение процесса
роли.

Песочница как в соседних модулях: пути config подменяются на временный
каталог, `claude` и git не запускаются.
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (budget, catalog, config, gitcmd, projects,  # noqa: E402
                          runner, spend, store, targets)
from tests.sandbox import (FakeProc, TmpRootTest, capture,  # noqa: E402
                           capture_new_task_id, disk_backed_show, fake_git,
                           seed_developer_brief_fixtures, sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parent.parent

TARGETS_YAML = """targets:
  artel:
    forge: github
    url: file:///nonexistent/artel
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


def result_event(usd: float) -> str:
    """Финальное событие потока `--output-format stream-json`: в нём стоимость."""
    return json.dumps({"type": "result", "subtype": "success",
                       "is_error": False, "result": "готово",
                       "total_cost_usd": usd}) + "\n"


# Идентичность, которую отдаёт подменённый `git config --get`: тесты
# окружения роли не должны зависеть от того, что настроено на машине.
PROBE_NAME = "Роль Артели"
PROBE_EMAIL = "role@artel.invalid"


def fake_git_config(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git`: отвечает на `config --get user.*`, иначе молчит."""
    answers = {"user.name": PROBE_NAME, "user.email": PROBE_EMAIL}
    value = answers.get(args[-1], "") if args[:2] == ("config", "--get") else ""
    return subprocess.CompletedProcess(list(args), 0, f"{value}\n", "")


def silent_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git` для машины без заданной идентичности: отказывает
    только `config --get user.*` — настоящий git без identity по-прежнему
    отвечает на чтения (`show`/`diff`), которых тест не касается (tasks/
    01M1K7KP0D8ZKRM9KTE75DCCYR: скилы/CLAUDE.md с этой задачи читаются
    через `gitcmd.show` ещё до git-идентичности — отказ ВСЕГО git здесь
    ронял бы шаг раньше, чем тест успевает проверить предупреждение об
    identity)."""
    if args[:2] == ("config", "--get"):
        return subprocess.CompletedProcess(list(args), 1, "", "")
    return fake_git(*args)


class _MultitargetTmpRootTest(TmpRootTest):
    """Песочница: БД, каталоги проектов и слой ролей во временном каталоге.

    `ROOT` тоже уводится (SPEC T049: холодный старт сканирует его для
    посева счётчика — непропатченный ROOT читал бы реальное дерево
    пульта и его настоящие номера задач) — `templates/` копируется рядом,
    `cmd_new` продолжает читать настоящий `templates/SPEC.md`, только уже
    из песочницы.
    """

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "PROJECTS",
                     "ROLE_HOME", "ROLE_CONFIG_DIR", "TARGETS", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        seed_developer_brief_fixtures(self.root)
        # Keychain подменяется функцией, как gitcmd.git: реальный `security`
        # (и патч Popen, ловящий его subprocess.run) в тестах не участвует.
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        # Этот модуль — про окружение/бюджет/нумерацию, не про worktree-
        # механику (SPEC T045): `gitcmd.git` тестов подменяется заглушками
        # по одному аргументу (`fake_git_config`/`silent_git`), которые не
        # умеют осмысленно отвечать на `worktree add/list` — обходим
        # `workspace.ensure` напрямую, тем же приёмом, что и keychain/
        # preflight выше, чтобы `role_cwd` для догфуда не блокировала шаг
        # раньше, чем тест успевает проверить то, ради чего он написан.
        # Путь — сам `self.root` (SPEC T048): `cmd_new` пишет TZ.md/SPEC.md
        # в `<worktree>/tasks/<id>`, а тесты этого модуля читают их через
        # `config.TASKS` (= `self.root/tasks`) — подставной каталог обязан
        # с ним совпасть, иначе файлы и проверки расходятся по разным путям.
        wt_patcher = mock.patch.object(
            runner.workspace, "ensure",
            lambda task_id, branch: (self.root, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)
        # `cmd_new` сам решает, заводить ли задачу, по ответу
        # `gitcmd.branch_exists` (SPEC T048, требование 1, AC-3) и коммитит
        # ТЗ/SPEC через `gitcmd.in_repo` — оба идут через `gitcmd.git`,
        # который этот модуль иначе не трогает вовсе; лёгкая заглушка
        # общего вида (SPEC T048, `tests.sandbox.fake_git`) отвечает «нет
        # такой ветки» и успехом на остальное, не пытаясь осмысленно вести
        # состояние репозитория — этому модулю оно не нужно.
        git_patcher = mock.patch.object(runner.gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

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


TmpRootTest = _MultitargetTmpRootTest


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
    url: file:///nonexistent/sled
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
        # .git/.gitignore — артефактный git-репо каталога (tasks/T021,
        # ADR-0003 3д/п.15), не часть структуры PROJECT_DIRS этого теста.
        names = {p.name for p in (config.PROJECTS / "artel").iterdir()}
        return sorted(names - {".git", ".gitignore"})

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
        _, task_id = capture_new_task_id(catalog.cmd_new, "Мультитаргет")

        conn = store.db()
        self.assertEqual(store.get_task(conn, task_id)["target"],
                         config.DEFAULT_TARGET)
        self.assertEqual(store.task_target(conn, task_id),
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
    """Критерий 4: номера задач не переиспользуются после архивации строки.

    SPEC T094, требование 6: `cmd_new` больше не расходует этот счётчик
    (id — ULID, `orchestrator/idgen.py`) — контур `task_counters`
    остаётся легаси, замороженным, не удалённым этой задачей. Эти три
    теста больше не могут вести сценарий ЧЕРЕЗ `cmd_new` (он не выдаёт
    `Tnnn`) — ведут `store.next_task_number`/`store.insert_task` напрямую,
    тем же приёмом, что уже применяют `test_counters_are_per_target`/
    `test_two_callers_at_once_do_not_get_the_same_number` ниже; свойство
    счётчика (не переиспользует номер, переживает переоткрытие БД,
    досеивается от наблюдаемого max) не изменилось и по-прежнему
    проверяется — изменился только вызыватель."""

    def numbers(self, conn) -> list:
        return sorted(r["id"] for r in store.all_tasks(conn))

    def archive(self, conn, task_id: str) -> None:
        """Архивация строки задачи (в A1 её механики ещё нет — эмуляция)."""
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()

    def _insert_numbered(self, conn, title: str) -> str:
        """Легаси-потребитель счётчика (SPEC T094, требование 6) — то,
        что раньше делал `cmd_new` сам, до перевода на ULID."""
        task_id = f"T{store.next_task_number(conn, 'artel'):03d}"
        store.insert_task(conn, task_id, title, "spec_writing",
                          f"task/{task_id.lower()}-x", "artel",
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def test_number_is_not_reused_after_a_row_is_archived(self):
        capture(catalog.cmd_init)
        conn = store.db()
        self._insert_numbered(conn, "Первая")
        self._insert_numbered(conn, "Вторая")
        self.archive(conn, "T002")

        self._insert_numbered(store.db(), "Третья")

        self.assertEqual(self.numbers(store.db()), ["T001", "T003"],
                         "COUNT(*) выдал бы T002 второй раз")

    def test_counter_survives_a_reopen_of_the_database(self):
        capture(catalog.cmd_init)
        self._insert_numbered(store.db(), "Первая")

        self.assertEqual(store.next_task_number(store.db(), "artel"), 2)
        self.assertEqual(store.next_task_number(store.db(), "artel"), 3)

    def test_counter_is_seeded_from_the_highest_existing_number(self):
        """Счётчик догоняет БД Фазы 0: следующая задача — за максимальной."""
        self.legacy_db([("T001", "done", 1.0), ("T017", "done", 2.0)])

        number = store.next_task_number(store.db(), "artel")

        self.assertEqual(number, 18)

    def test_counters_are_per_target(self):
        conn = store.db()
        store.create_schema(conn)

        first = [store.next_task_number(conn, "artel") for _ in range(3)]
        second = [store.next_task_number(conn, "sled") for _ in range(2)]

        self.assertEqual(first, [1, 2, 3])
        self.assertEqual(second, [1, 2], "счётчик проекта свой, не общий")

    def test_two_callers_at_once_do_not_get_the_same_number(self):
        """Номер выдаётся под транзакцией: одновременные `new` не совпадают.

        WAL (требование 5) заводится ради второго процесса на той же БД,
        поэтому чтение счётчика вне транзакции — достижимая гонка, а не
        теоретическая: оба читают один номер, второй `insert_task` падает
        IntegrityError.
        """
        capture(catalog.cmd_init)
        callers = 4
        start = threading.Barrier(callers)
        taken, failed = [], []
        lock = threading.Lock()

        def take() -> None:
            conn = store.db()
            start.wait()
            try:
                number = store.next_task_number(conn, "artel")
            except sqlite3.Error as exc:  # гонку тоже надо увидеть, не скрыть
                with lock:
                    failed.append(str(exc))
                return
            with lock:
                taken.append(number)

        threads = [threading.Thread(target=take) for _ in range(callers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(failed, [])
        self.assertEqual(sorted(taken), sorted(set(taken)),
                         "один номер двум задачам — это IntegrityError в `new`")
        self.assertEqual(len(taken), callers)

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
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Пороги программы")

    def spend_to(self, total: float) -> None:
        """Ставит суммарный расход программы равным total."""
        store.update_task(store.db(), self.TASK, spent_usd=total)

    def step(self, usd: float) -> str:
        """Шаг стоимостью usd: учёт стоимости и проверка порогов после него."""
        conn = store.db()
        cost = {"usd": usd, "tokens": None}
        out = capture(spend.charge_step, conn, self.TASK, "developer", cost, "1/3")
        return out + capture(budget.check_program_spend, conn, self.TASK, cost)

    def events(self) -> list:
        return [r["detail"] for r in store.task_steps(store.db(), self.TASK)
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
            budget.check_program_spend, store.db(), self.TASK, None)

        self.assertNotIn("ВНИМАНИЕ", out)
        self.assertEqual(self.events(), [])

    def test_sum_covers_all_tasks_not_only_the_current_one(self):
        """Кошелёк Оператора один: сумма считается по всем задачам."""
        _, other_task = capture_new_task_id(catalog.cmd_new, "Вторая задача")
        store.update_task(store.db(), other_task,
                          spent_usd=config.PROGRAM_STOP_LOSS_USD * 0.7 - 1)

        self.step(2.0)

        self.assertEqual(len(self.events()), 1)

    def test_a_step_run_is_what_moves_the_program_counter(self):
        """Порог считает прогон шага, а не только прямой вызов из теста.

        Без этого теста снятая строка `check_program_spend` из `cmd_run`
        не роняет ни один тест: стоп-лосс программы молча перестал бы
        считаться. Потолок задачи снят (budget_usd=0) — проверяется
        внешний контур, а не эскалация по бюджету задачи.
        """
        store.update_task(store.db(), self.TASK, state="in_dev", budget_usd=0,
                          spent_usd=config.PROGRAM_STOP_LOSS_USD * 0.7 - 1)

        # gitcmd подменён вместе с Popen: патч Popen ловит и `subprocess.run`
        # внутри `gitcmd.git` — реального git в этом тесте быть не должно.
        with mock.patch.object(runner.gitcmd, "git", fake_git_config), \
                mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc([result_event(2.0)])
            out = capture(runner.cmd_run, self.TASK)

        self.assertIn("пересечён порог 70%", out)
        events = self.events()
        self.assertEqual(len(events), 1)
        self.assertIn("70%", events[0])


class RoleEnvTest(TmpRootTest):
    """Критерий 8: процесс роли несёт HOME и CLAUDE_CONFIG_DIR из .artel/."""

    def setUp(self):
        super().setUp()
        # Гасим ambient GIT_AUTHOR_*/GIT_COMMITTER_* среды, где гоняются
        # тесты (машина прогона может нести реальную идентичность
        # Оператора в окружении) — `role_env` ставит идентичность через
        # `setdefault`, который смотрит на ПРИСУТСТВИЕ ключа, не на
        # истинность значения, так что тут не годится пустая строка как
        # заглушка (тот же класс утечки, что `test_doctor.py` уже гасит
        # для CLAUDE_CODE_OAUTH_TOKEN, но там `.get()` и пустая строка
        # достаточна) — нужно реальное отсутствие ключа.
        for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            if name in runner.os.environ:
                old = runner.os.environ.pop(name)
                self.addCleanup(runner.os.environ.__setitem__, name, old)

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

    def test_role_path_is_built_from_declared_tools_not_copied(self):
        """PATH роли — не копия PATH Оператора (SPEC
        01M1RDCEF0JZ4AVQRE43JFH8TN, требование 1): каталог, где
        объявленных манифестом инструментов нет вовсе, не даёт
        `role_env` тихо построить окружение с ним — падает `OSError`,
        а не подставляет операторский PATH как есть (замена теста
        «остальное окружение наследуется» — AC-14 этой же SPEC, критерий
        8 T019 больше не в силе буквально).

        Ловит мутацию: откат `role_env` к `env["PATH"] =
        os.environ["PATH"]` (копия PATH Оператора целиком) — с таким
        откатом каталог `/opt/operator-only-dir` из подложенного PATH
        Оператора попал бы в PATH роли как есть, `OSError` не случился
        бы вовсе."""
        with mock.patch.dict(runner.os.environ, {"PATH": "/opt/operator-only-dir"}), \
                mock.patch.object(runner.gitcmd, "git", fake_git_config):
            with self.assertRaises(OSError):
                runner.role_env()

    def test_env_vars_outside_the_manifest_allowlist_do_not_reach_the_role(self):
        """Переменная Оператора вне белого списка манифеста
        (`orchestrator.stack.ROLE_ENV_ALLOWLIST`) не попадает в окружение
        роли (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN, требование 2).

        Ловит мутацию: откат `role_env` к `env = dict(os.environ)`
        (копия всего окружения Оператора без фильтрации белым списком) —
        с таким откатом `SOME_OPERATOR_ONLY_VAR` дошла бы до роли и
        `assertNotIn` ниже упал бы."""
        with mock.patch.dict(runner.os.environ,
                             {"SOME_OPERATOR_ONLY_VAR": "утечка"}), \
                mock.patch.object(runner.gitcmd, "git", fake_git_config):
            env = runner.role_env()

        self.assertNotIn("SOME_OPERATOR_ONLY_VAR", env)

    def test_agent_process_gets_that_environment(self):
        capture(catalog.cmd_init)
        _, task_id = capture_new_task_id(catalog.cmd_new, "Окружение роли")
        store.update_task(store.db(), task_id, state="in_dev")

        with mock.patch.object(runner.gitcmd, "git", fake_git_config), \
                mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            capture(runner.cmd_run, task_id)

        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(config.ROLE_CONFIG_DIR))

    def test_env_carries_the_git_identity(self):
        """Слой несёт то, без чего шаг не выполним: авторство коммита."""
        with mock.patch.object(runner.gitcmd, "git", fake_git_config):
            env = runner.role_env()

        self.assertEqual(env["GIT_AUTHOR_NAME"], PROBE_NAME)
        self.assertEqual(env["GIT_COMMITTER_NAME"], PROBE_NAME)
        self.assertEqual(env["GIT_AUTHOR_EMAIL"], PROBE_EMAIL)
        self.assertEqual(env["GIT_COMMITTER_EMAIL"], PROBE_EMAIL)

    def test_identity_comes_from_the_git_config_of_the_operator(self):
        """Читается конфиг, а не константа в коде: у Оператора своё имя."""
        asked = mock.Mock(side_effect=fake_git_config)
        with mock.patch.object(runner.gitcmd, "git", asked):
            runner.role_env()

        options = [call.args[-1] for call in asked.call_args_list]
        self.assertEqual(options, ["user.name", "user.email"])

    def test_identity_already_in_the_environment_is_not_overridden(self):
        """git предпочитает переменную конфигу — заданная Оператором сильнее."""
        with mock.patch.dict(runner.os.environ,
                             {"GIT_AUTHOR_EMAIL": "operator@example.invalid"}), \
                mock.patch.object(runner.gitcmd, "git", fake_git_config):
            env = runner.role_env()

        self.assertEqual(env["GIT_AUTHOR_EMAIL"], "operator@example.invalid")
        self.assertEqual(env["GIT_COMMITTER_EMAIL"], PROBE_EMAIL)

    def commit_probe(self, env: dict) -> subprocess.CompletedProcess:
        """git init + commit в песочнице с данным окружением.

        Ни глобального, ни системного конфига: идентичность может прийти
        только из окружения — иначе проба доказывала бы ~/.gitconfig
        машины, а не перенос в слой роли.
        """
        repo = self.root / "probe"
        repo.mkdir(exist_ok=True)
        absent = str(self.root / "нет-такого-конфига")
        env = dict(env, GIT_CONFIG_GLOBAL=absent, GIT_CONFIG_SYSTEM=absent)
        for args in (["init", "-q"], ["add", "step.txt"]):
            if args[0] == "add":
                (repo / "step.txt").write_text("шаг", encoding="utf-8")
            subprocess.run(["git", *args], cwd=repo, env=env, check=True,
                           capture_output=True, text=True)
        return subprocess.run(["git", "commit", "-m", "T000: шаг роли"],
                              cwd=repo, env=env, capture_output=True, text=True)

    def test_commit_of_the_step_passes_with_that_environment(self):
        """Ради этого перенос и делается: коммит шага — предписанное действие."""
        with mock.patch.object(runner.gitcmd, "git", fake_git_config):
            env = runner.role_env()

        res = self.commit_probe(env)

        self.assertEqual(res.returncode, 0, res.stderr)

    def test_the_same_commit_without_identity_fails(self):
        """Обратная сторона: проба ловит именно то, ради чего написана."""
        with mock.patch.object(runner.gitcmd, "git", fake_git_config):
            env = runner.role_env()
        stripped = {name: value for name, value in env.items()
                    if not name.startswith("GIT_") and name != "EMAIL"}

        res = self.commit_probe(stripped)

        self.assertNotEqual(res.returncode, 0)
        self.assertIn("identity", res.stderr.lower())

    def test_absent_identity_is_journalled_before_the_step(self):
        """Идентичности нет — Оператор узнаёт до шага, а не из rc=128 потом."""
        capture(catalog.cmd_init)
        _, task_id = capture_new_task_id(catalog.cmd_new, "Окружение роли")
        store.update_task(store.db(), task_id, state="in_dev")
        sync_spec_from_worktree(task_id)

        # `silent_git` роняет ЛЮБУЮ git-команду (returncode 1) — годится
        # для предмета теста (сверка git-идентичности), но брифу роли
        # (A7: SPEC.md читается с артефактной ветки, `gitcmd.show`) нечем
        # ответить тем же провалом — `gitcmd.show` патчится отдельно, на
        # чтение с диска (`disk_backed_show`, тот же приём, что и
        # `tests.test_invariants.FsmTest`), не участвует в сверке
        # идентичности этого теста.
        with mock.patch.object(runner.gitcmd, "git", silent_git), \
                mock.patch.object(gitcmd, "show", disk_backed_show), \
                mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = capture(runner.cmd_run, task_id)

        self.assertIn("git-идентичность роли не задана", out)
        actions = [r["action"] for r in store.task_steps(store.db(), task_id)]
        self.assertIn("agent env WARNING", actions)
        popen.assert_called_once()  # предупреждение, а не отказ запускать шаг

    def test_step_does_not_start_without_the_layer(self):
        """Каталог не создался — шаг пропущен, а не запущен с HOME Оператора."""
        capture(catalog.cmd_init)
        _, task_id = capture_new_task_id(catalog.cmd_new, "Окружение роли")
        store.update_task(store.db(), task_id, state="in_dev")

        # T028: сборка брифа (до `role_env`) сверяет свежесть карты через
        # `gitcmd.git` — без подмены это настоящий git-подпроцесс, а общий
        # с `Popen` модульный объект subprocess здесь замокан целиком
        # (см. `RealPultGitTest.run_faked` в test_git_fixation.py).
        with mock.patch.object(runner, "role_env",
                               side_effect=OSError("нет места")), \
                mock.patch.object(runner.gitcmd, "git", fake_git_config), \
                mock.patch.object(runner, "spawn_agent") as popen:
            out = capture(runner.cmd_run, task_id)

        popen.assert_not_called()
        self.assertIn("окружение роли не подготовлено", out)
        details = [r["detail"] for r in store.task_steps(store.db(), task_id)
                   if r["action"] == "agent run SKIPPED"]
        self.assertTrue(details and "нет места" in details[0])


def _stack_check(name: str, status: str, detail: str):
    from types import SimpleNamespace
    return SimpleNamespace(name=name, status=status, detail=detail)


class RoleEnvVenvInterpreterTest(TmpRootTest):
    """Требование 4 (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8, AC-12/AC-13):
    интерпретатор роли — `.artel/venv`, если он согласован с файлом
    закреплённых версий (та же проверка, что `stack.check_stack()`),
    иначе `role_env()` отказывает `OSError` без тихого отката на
    системный python.

    Постоянная регрессия — переживает закрытие `tasks/
    01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests/`."""

    def test_consistent_venv_puts_its_bin_first_on_path(self):
        venv_dir = self.root / ".artel" / "venv"
        ok_checks = [_stack_check("python", "ok", "Python 3.99.0"),
                    _stack_check("venv", "ok", "venv согласован")]

        with mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
                mock.patch.object(runner.stack, "check_stack",
                                  return_value=ok_checks), \
                mock.patch.object(runner.gitcmd, "git", fake_git_config):
            env = runner.role_env()

        path_entries = env["PATH"].split(":")
        self.assertEqual(str(venv_dir / "bin"), path_entries[0])

    def test_inconsistent_venv_raises_instead_of_falling_back(self):
        warn_checks = [_stack_check("python", "ok", "Python 3.99.0"),
                      _stack_check("venv-packages", "warn",
                                   "версии расходятся: pytest")]

        with mock.patch.object(runner.stack, "check_stack",
                               return_value=warn_checks), \
                mock.patch.object(runner.gitcmd, "git", fake_git_config):
            with self.assertRaises(OSError) as ctx:
                runner.role_env()

        self.assertIn("venv", str(ctx.exception).lower())

    def test_missing_venv_also_raises_rather_than_falling_back(self):
        warn_checks = [_stack_check("python", "ok", "Python 3.99.0"),
                      _stack_check("venv", "warn",
                                   "venv не создан — `python3 artel.py "
                                   "venv-sync`")]

        with mock.patch.object(runner.stack, "check_stack",
                               return_value=warn_checks), \
                mock.patch.object(runner.gitcmd, "git", fake_git_config):
            with self.assertRaises(OSError):
                runner.role_env()


if __name__ == "__main__":
    unittest.main()
