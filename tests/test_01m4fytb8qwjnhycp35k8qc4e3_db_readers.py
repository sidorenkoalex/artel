"""Читатели БД пульта на непригодном и отсутствующем файле `config.DB`.

Группа: долгоживущий
Красен до реализации: читатели проверяют только `config.DB.exists()` и открывают `store.db()` — пустой, чужой или бестабличный файл даёт `no such table`/`file is not a database` наружу и переписывается режимом WAL, а семь тестов `tests/` без подмены пути БД падают на пустом `state.db`.

Перечень читателей — требование 1 SPEC задачи: репозиторий ссылки
документов задачи и ветка задачи помощника планки (публичный вход —
`acceptance.materialize_files`, строка `DOCS_REPO` выложенного помощника),
`workspace.task_target`, `acceptance.journal_suite_metrics`, target и
признак записи `acceptance.full_suite`, `models.live_task_set_providers`,
проверка приостановки пары (публичный вход — `models.resolve_task_role`).
Клоны проектов песочницы — каталоги с `.git` в области проектов, контекст
проекта отдаёт подменённый `repo_context.resolve`.
"""

import json
import random
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, config, models, repo_context, store,
                          workspace)
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_OTHER_MODEL,
                           TmpRootTest)

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
GREEN = "========== 3 passed in 0.10s ==========\n"
UNUSABLE_KINDS = ("пустой файл", "SQLite без таблицы tasks", "не SQLite")
COMPANIONS = ("", "-wal", "-shm", "-journal")
PAIR_ROLE = "developer"
ADMITTED_PAIR = (
    "sets:\npairs:\n  developer:\n"
    f"    {FIXTURE_OTHER_MODEL}:\n      date: 2026-10-01\n"
    "      basis: тест\n      state: допущена\n"
    "canary_templates:\n")


def write_unusable(path: Path, kind: str, rng: random.Random) -> None:
    """Непригодный файл БД вида `kind` на месте `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "пустой файл":
        path.write_bytes(b"")
    elif kind == "SQLite без таблицы tasks":
        conn = sqlite3.connect(path)
        name = "t_" + "".join(rng.choice(LETTERS) for _ in range(8))
        conn.execute(f"CREATE TABLE {name} (x TEXT)")
        conn.execute(f"PRAGMA user_version = {rng.randrange(1, 1000)}")
        conn.commit()
        conn.close()
    else:
        body = rng.randbytes(rng.randrange(1, 9000))
        # Префикс не совпадает с заголовком SQLite — файл точно чужой.
        path.write_bytes(b"not a database: " + body)


def drop_db_files() -> None:
    for suffix in COMPANIONS:
        Path(f"{config.DB}{suffix}").unlink(missing_ok=True)


class DbReadersTest(TmpRootTest):
    """Песочница с путями `config` во временном каталоге; каждый читатель
    перечня зовётся через публичный вход."""

    def setUp(self):
        super().setUp()
        self.use_catalog_fixture()
        models.model_sets_path().write_text(ADMITTED_PAIR, encoding="utf-8")
        self.seed = random.randrange(2**32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.task = "01M" + "".join(self.rng.choice(ALPHABET)
                                    for _ in range(23))
        self.other = "p" + "".join(self.rng.choice(LETTERS) for _ in range(8))
        self.code_dir = self.root / "code"
        self.code_dir.mkdir()
        self.run_root = self.root / "run"
        self.run_root.mkdir()
        self.task_row = self.memory_task_row()
        for target in (config.DEFAULT_TARGET, self.other):
            (repo_context.clone_path(target) / ".git").mkdir(parents=True,
                                                           exist_ok=True)
        patcher = mock.patch.object(
            repo_context, "resolve",
            side_effect=lambda name: repo_context.RepoContext(
                path=repo_context.clone_path(name), remote="origin",
                base=config.MAIN_BRANCH, target=name))
        patcher.start()
        self.addCleanup(patcher.stop)
        drop_db_files()

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def memory_task_row(self):
        """Строка задачи на наборе (developer → модель допущенной пары) из
        БД в памяти: `resolve_task_role` получает строку, а проверку
        приостановки пары делает по `config.DB`."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        store.create_schema(conn)
        store.insert_task(conn, self.task, "Задача", "in_dev",
                          f"task/{self.task.lower()}-x", self.other, 25.0)
        store.update_task(conn, self.task, model_set="nabor",
                          model_set_members=json.dumps(
                              {PAIR_ROLE: FIXTURE_OTHER_MODEL}))
        return store.get_task(conn, self.task)

    def readers(self) -> dict:
        """Читатель перечня -> функция, отдающая сравнимый итог."""

        def helper_text():
            tdir = acceptance.materialize_files(self.task, {}, self.code_dir)
            return (tdir / "acceptance_tests" /
                    acceptance.PLANK_HELPER_NAME).read_text(encoding="utf-8")

        def docs_repo():
            found = re.search(r"^DOCS_REPO = (.*)$", helper_text(),
                              re.MULTILINE)
            return found.group(1) if found else None

        def full_suite():
            with mock.patch.object(acceptance, "run_full_suite",
                                   return_value=(True, GREEN)):
                run = acceptance.full_suite(self.run_root, self.task,
                                            fresh=True)
            return run.green, run.outcome

        def pair_check():
            step = models.resolve_task_role(PAIR_ROLE, self.task_row)
            return step.resolution.model, step.withdrawn

        return {
            "workspace.task_target":
                lambda: workspace.task_target(self.task),
            "репозиторий ссылки документов (DOCS_REPO помощника)": docs_repo,
            "acceptance.journal_suite_metrics":
                lambda: acceptance.journal_suite_metrics(
                    self.task, {"duration_seconds": self.rng.random()}),
            "ветка задачи помощника планки (materialize_files)": helper_text,
            "acceptance.full_suite": full_suite,
            "models.live_task_set_providers":
                lambda: models.live_task_set_providers(),
            "приостановка пары (resolve_task_role)": pair_check,
        }

    def shuffled_readers(self) -> list:
        items = list(self.readers().items())
        self.rng.shuffle(items)
        return items

    def test_ac1_unusable_db_reads_as_absent(self):
        """Пустой, бестабличный и чужой файл на месте БД читаются как её отсутствие.

        Сценарий: итог каждого читателя перечня снимается без файла
        `config.DB`; затем для каждого вида непригодного файла (0 байт,
        SQLite без таблицы `tasks` со случайной чужой таблицей, случайные
        байты без заголовка SQLite) каждый читатель зовётся снова — итог тот
        же, исключения нет.

        Ловит мутацию: один из читателей перечня оставлен на
        `config.DB.exists()` (например `workspace.task_target`) — на пустом
        файле вызов падает `sqlite3.OperationalError: no such table: tasks`
        вместо проекта по умолчанию.
        """
        absent = {name: read() for name, read in self.shuffled_readers()}
        self.assertEqual(absent["workspace.task_target"],
                         config.DEFAULT_TARGET, self.note("без файла БД"))
        self.assertEqual(absent["models.live_task_set_providers"], set(),
                         self.note("без файла БД"))
        for kind in UNUSABLE_KINDS:
            for name, read in self.shuffled_readers():
                with self.subTest(kind=kind, reader=name, seed=self.seed):
                    drop_db_files()
                    write_unusable(config.DB, kind, self.rng)
                    try:
                        got = read()
                    except Exception as exc:  # noqa: BLE001 — итог теста
                        self.fail(self.note(
                            f"{name} на файле «{kind}» поднял "
                            f"{type(exc).__name__}: {exc}"))
                    self.assertEqual(got, absent[name], self.note(
                        f"{name} на файле «{kind}» дал не тот итог, что "
                        f"без файла"))
        drop_db_files()

    def test_ac1_usable_db_values_come_from_db(self):
        """При пригодной БД с задачей другого проекта читатели берут значения из неё.

        Сценарий: схема БД заведена, задача — в проекте со случайным
        именем и на наборе с моделью провайдера codex, пара developer →
        модель набора приостановлена пультом. `workspace.task_target` даёт
        этот проект, `DOCS_REPO` выложенного помощника планки — клон этого
        проекта, `live_task_set_providers` несёт codex, проверка пары —
        отказ приостановки, `journal_suite_metrics` пишет запись в журнал
        задачи.

        Ловит мутацию: проверка пригодности ошибочно отвергает и пригодную
        БД (например ищет таблицу не `tasks`) — `task_target` отдаёт проект
        по умолчанию, `live_task_set_providers` — пустое множество.
        """
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, self.task, "Задача", "in_dev",
                          f"task/{self.task.lower()}-x", self.other, 25.0)
        store.update_task(conn, self.task, model_set="nabor",
                          model_set_members=json.dumps(
                              {PAIR_ROLE: FIXTURE_CODEX_MODEL}))
        store.insert_pair_suspension(conn, PAIR_ROLE, FIXTURE_OTHER_MODEL,
                                     "nabor", self.task, "серия вердиктов")
        readers = self.readers()
        own_repo = repo_context.clone_path(self.other)

        self.assertEqual(readers["workspace.task_target"](), self.other,
                         self.note("task_target"))
        self.assertEqual(
            readers["репозиторий ссылки документов (DOCS_REPO помощника)"](),
            repr(str(own_repo)), self.note("репозиторий ссылки документов"))
        self.assertIn("codex", readers["models.live_task_set_providers"](),
                      self.note("live_task_set_providers"))
        model, withdrawn = readers["приостановка пары (resolve_task_role)"]()
        self.assertIsNotNone(withdrawn, self.note("приостановка пары"))
        readers["acceptance.journal_suite_metrics"]()
        actions = [row["action"] for row in store.task_steps(conn, self.task)]
        self.assertIn(acceptance.SUITE_DURATION_ACTION, actions,
                      self.note("journal_suite_metrics"))
        helper = readers["ветка задачи помощника планки (materialize_files)"]()
        self.assertIn(f"TASK_ID = {self.task!r}", helper,
                      self.note("помощник планки"))

    def test_ac2_readers_do_not_create_or_change_db(self):
        """Чтение не заводит отсутствующий файл БД и не меняет непригодный.

        Сценарий: без файла `config.DB` каждый читатель перечня (в том числе
        target задачи в `full_suite` и ветка задачи помощника планки)
        зовётся по очереди — файла после каждого вызова нет. Затем на месте
        БД лежит непригодный файл каждого вида — после каждого читателя он
        байт в байт прежний.

        Ловит мутацию: проверка пригодности открывает файл через
        `sqlite3.connect` без режима только чтения (или зовёт `store.db()`)
        — отсутствующий файл появляется, а пустой получает заголовок SQLite
        и режим WAL.
        """
        for name, read in self.shuffled_readers():
            with self.subTest(state="нет файла", reader=name, seed=self.seed):
                drop_db_files()
                try:
                    read()
                except Exception:  # noqa: BLE001 — предмет здесь файл
                    pass
                self.assertFalse(config.DB.exists(), self.note(
                    f"{name} завёл файл БД при чтении"))
        for kind in UNUSABLE_KINDS:
            for name, read in self.shuffled_readers():
                with self.subTest(kind=kind, reader=name, seed=self.seed):
                    drop_db_files()
                    write_unusable(config.DB, kind, self.rng)
                    before = config.DB.read_bytes()
                    try:
                        read()
                    except Exception:  # noqa: BLE001 — предмет здесь файл
                        pass
                    self.assertTrue(config.DB.exists(), self.note(
                        f"{name} убрал файл «{kind}»"))
                    self.assertEqual(config.DB.read_bytes(), before,
                                     self.note(f"{name} изменил файл «{kind}»"))
        drop_db_files()


# Тесты требования 3 SPEC: обращались к `store.db()` без подмены пути БД и
# краснели на пустом `.artel/state.db` в корне дерева прогона (09.10).
NAMED_TESTS = (
    "tests.test_acceptance.MaterializeFromBranchGitFailureTest",
    "tests.test_fsm_autogate.SourceNoteOnPassTest",
    "tests.test_fsm_autogate.DiskAccTdirIgnoredForConditionATest",
    "tests.test_fsm_autogate.CiMarkerConditionTest",
    "tests.test_fsm_autogate.ChecklistNamesRealChecksTest",
)


class NamedTestsWithEmptyDbTest(unittest.TestCase):
    """Названные тесты прогоняются в этом же процессе, пока `config.DB`
    указывает на пустой файл `.artel/state.db` во временном корне — так же,
    как в рабочей копии, где файл завёлся."""

    def test_ac3_named_tests_green_with_empty_state_db(self):
        """Семь тестов требования 3 зелёные при пустом state.db в корне дерева.

        Сценарий: `.artel/state.db` — файл 0 байт либо SQLite без таблиц
        (форма инцидента 09.10, 4096 байт); `config.DB` указывает на него;
        классы `MaterializeFromBranchGitFailureTest`, `SourceNoteOnPassTest`,
        `DiskAccTdirIgnoredForConditionATest`, `CiMarkerConditionTest`,
        `ChecklistNamesRealChecksTest` исполняются загрузчиком unittest —
        ни падений, ни ошибок.

        Ловит мутацию: изоляция БД не добавлена в подготовку этих классов, а
        читатель ссылки документов по-прежнему принимает наличие файла за
        схему — вложенный прогон падает `no such table: tasks`.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for kind in ("пустой файл", "SQLite без таблиц"):
            with self.subTest(kind=kind, seed=seed):
                with tempfile.TemporaryDirectory() as holder:
                    db = Path(holder) / ".artel" / "state.db"
                    db.parent.mkdir()
                    if kind == "пустой файл":
                        db.write_bytes(b"")
                    else:
                        conn = sqlite3.connect(db)
                        conn.execute(f"PRAGMA user_version = "
                                     f"{rng.randrange(1, 1000)}")
                        conn.commit()
                        conn.close()
                    suite = unittest.defaultTestLoader.loadTestsFromNames(
                        NAMED_TESTS)
                    result = unittest.TestResult()
                    with mock.patch.object(config, "DB", db):
                        suite.run(result)
                problems = "\n\n".join(
                    f"{test.id()}:\n{trace}"
                    for test, trace in result.failures + result.errors)
                self.assertGreater(result.testsRun, 0, f"зерно: {seed}")
                self.assertTrue(result.wasSuccessful(),
                                f"зерно: {seed}; файл «{kind}»:\n{problems}")


if __name__ == "__main__":
    unittest.main()
