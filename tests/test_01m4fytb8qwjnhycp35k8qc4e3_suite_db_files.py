"""Файлы БД пульта в дереве полного прогона: отказ, ключ кэша, след прогона.

Группа: долгоживущий
Красен до реализации: `acceptance.full_suite` не смотрит на `.artel/state.db*` в дереве прогона и гоняет набор, ключ `suite_tree_hash`/`suite_result_key` не видит игнорируемый `.artel/`, текст повторного итога не называет `--fresh-suite`, а файл БД, заведённый прогоном, журналом не замечается.

Дерево прогона — отдельный git worktree репозитория песочницы
(`RealGitSandbox`, `.artel/` в нём игнорируется git, как в репозитории
пульта); БД пульта `config.DB` лежит вне этого дерева. Запуск pytest
подменён публичной точкой `acceptance.run_full_suite`. Гейт приёмки
(`acceptance_suite`) и гейт мержа (`fsm_merge_gate`) зовут один узел
`acceptance.full_suite` — требование 4 SPEC.
"""

import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, store
from tests.sandbox import RealGitSandbox

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DB_FILES = (".artel/state.db", ".artel/state.db-wal", ".artel/state.db-shm",
            ".artel/state.db-journal")
RED = ("========== short test summary info ==========\n"
       "FAILED tests/test_x.py::test_x - AssertionError: x\n"
       "========== 1 failed, 2 passed in 0.10s ==========\n")
GREEN = "========== 3 passed in 0.10s ==========\n"
LEAK_NOTE = "прогон набора создал файл БД — неполная изоляция тестов"


class SuiteTreeSandbox(RealGitSandbox):
    """Задача в БД пульта и дерево прогона — свежий worktree main."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2**32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.task = "01M" + "".join(self.rng.choice(ALPHABET)
                                    for _ in range(23))
        store.insert_task(store.db(), self.task, "Задача", "acceptance",
                          f"task/{self.task.lower()}-x",
                          config.DEFAULT_TARGET, 25.0)
        holder = Path(tempfile.mkdtemp(prefix="artel-suite-tree-")).resolve()
        self.addCleanup(shutil.rmtree, holder, True)
        self.tree = holder / "tree"
        self.git("worktree", "add", "-q", "--detach", str(self.tree),
                 config.MAIN_BRANCH)
        self.addCleanup(self.git, "worktree", "remove", "--force",
                        str(self.tree))

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def drop_db_files(self) -> None:
        for rel in DB_FILES:
            (self.tree / rel).unlink(missing_ok=True)

    def put(self, rel: str, data: bytes) -> Path:
        path = self.tree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def results_snapshot(self) -> dict:
        folder = acceptance.suite_results_dir()
        if not folder.is_dir():
            return {}
        return {p.relative_to(folder).as_posix(): p.read_bytes()
                for p in folder.rglob("*") if p.is_file()}

    def key(self):
        return acceptance.suite_result_key(acceptance.suite_tree_hash(self.tree))

    def journal_rows(self) -> list:
        return [f"{row['action']} {row['detail'] or ''}"
                for row in store.task_steps(store.db(), self.task)]


class DbFilesRefusalTest(SuiteTreeSandbox):

    def test_ac4_db_file_in_tree_refuses_without_run_and_cache(self):
        """Файл БД пульта в дереве — отказ «не проверен» без прогона и без записи итога.

        Сценарий: в корне дерева прогона лежит каждый из файлов
        `.artel/state.db`, `-wal`, `-shm`, `-journal` поодиночке и
        случайный набор из нескольких (содержимое случайное, бывает пустым).
        Полный прогон зовётся двумя входами гейтов — `full_suite` (гейт
        мержа) и `acceptance_suite` (автогейт и `approve`). pytest не
        запускается; исход не зелёный и не «красный прогон»; текст называет
        «не проверен», путь каждого найденного файла и
        `artel.py worktree-db-clean <id>`; каталог сохранённых итогов не
        меняется.

        Ловит мутацию: проверка ищет только `.artel/state.db` и пропускает
        спутники SQLite — при одиноком `state.db-wal` набор запускается
        (подменённый `run_full_suite` вызван) и итог пишется в кэш.
        """
        cases = [(rel,) for rel in DB_FILES]
        cases.append(tuple(self.rng.sample(DB_FILES, self.rng.randint(2, 4))))
        entries = {
            "full_suite": lambda: acceptance.full_suite(self.tree, self.task),
            "acceptance_suite": lambda: acceptance.acceptance_suite(
                store.db(), self.tree, self.task,
                f"task/{self.task.lower()}-x", self.root,
                actor="orchestrator", fresh=True),
        }
        for found in cases:
            for entry, call in entries.items():
                with self.subTest(files=found, entry=entry, seed=self.seed):
                    self.drop_db_files()
                    for rel in found:
                        self.put(rel, self.rng.randbytes(
                            self.rng.choice((0, self.rng.randrange(1, 5000)))))
                    before = self.results_snapshot()
                    with mock.patch.object(acceptance, "run_full_suite",
                                           return_value=(True, GREEN)) as run:
                        result = call()
                    context = self.note(f"{entry}, файлы {found}: {result}")
                    run.assert_not_called()
                    self.assertFalse(result.green, context)
                    self.assertNotEqual(result.outcome,
                                        acceptance.FULL_SUITE_RED, context)
                    self.assertIn("не проверен", result.detail, context)
                    for rel in found:
                        self.assertIn(rel, result.detail, context)
                    self.assertIn(f"artel.py worktree-db-clean {self.task}",
                                  result.detail, context)
                    self.assertEqual(self.results_snapshot(), before, context)
        self.drop_db_files()


class DbFilesCacheKeyTest(SuiteTreeSandbox):

    def test_ac5_db_files_change_suite_cache_key(self):
        """Появление, правка и уборка файла БД в корне дерева меняют ключ кэша.

        Сценарий: для каждого из четырёх файлов БД пульта при неизменном
        git-дереве ключ `suite_result_key(suite_tree_hash(дерево))` снят
        без файла (дважды — он стабилен), с пустым файлом, со случайным
        содержимым A, с другим содержимым B и после уборки — соседние
        состояния дают разные ключи. Итог, сохранённый под ключом
        состояния A, в состоянии B не находится, а при возврате к A —
        находится.

        Ловит мутацию: ключ учитывает только наличие файла, а не хэш его
        содержимого — ключи состояний A и B совпадают, и итог, снятый при
        одном содержимом, повторно используется при другом.
        """
        for rel in DB_FILES:
            with self.subTest(file=rel, seed=self.seed):
                self.drop_db_files()
                clean = self.key()
                self.assertIsNotNone(clean, self.note("ключ чистого дерева"))
                self.assertEqual(self.key(), clean,
                                 self.note("ключ без файлов БД нестабилен"))
                self.put(rel, b"")
                empty = self.key()
                content_a = self.rng.randbytes(self.rng.randrange(1, 4000))
                content_b = content_a + self.rng.randbytes(1)
                self.put(rel, content_a)
                key_a = self.key()
                tree_a = acceptance.suite_tree_hash(self.tree)
                self.put(rel, content_b)
                key_b = self.key()
                tree_b = acceptance.suite_tree_hash(self.tree)
                self.drop_db_files()
                removed = self.key()
                states = [("без файла", clean), ("пустой", empty),
                          ("содержимое A", key_a), ("содержимое B", key_b),
                          ("после уборки", removed)]
                for (name1, k1), (name2, k2) in zip(states, states[1:]):
                    self.assertIsNotNone(k2, self.note(f"{rel}: {name2}"))
                    self.assertNotEqual(k1, k2, self.note(
                        f"{rel}: ключ «{name1}» равен ключу «{name2}»"))

                log = Path(config.LOGS) / f"{self.task}-fullsuite-1.log"
                acceptance.save_suite_result("gate", key_a, tree_a,
                                             acceptance.FULL_SUITE_GREEN,
                                             GREEN, log)
                self.put(rel, content_b)
                self.assertIsNone(acceptance.saved_suite_result(
                    "gate", self.key(),
                    tree=acceptance.suite_tree_hash(self.tree)),
                    self.note(f"{rel}: итог A взят в состоянии B"))
                self.put(rel, content_a)
                self.assertIsNotNone(acceptance.saved_suite_result(
                    "gate", self.key(),
                    tree=acceptance.suite_tree_hash(self.tree)),
                    self.note(f"{rel}: итог A не найден в том же состоянии"))
                self.drop_db_files()


class CachedResultNamesFreshFlagTest(SuiteTreeSandbox):

    def test_ac6_reused_result_names_fresh_suite_flag(self):
        """Итог полного прогона, взятый из кэша, называет флаг --fresh-suite.

        Сценарий: на чистом дереве (содержимое отслеживаемого файла
        случайное для каждого исхода) полный прогон зовётся дважды, первый
        раз pytest (подменённый) даёт красный либо зелёный итог; второй
        вызов pytest не запускает и берёт сохранённый итог — его текст
        несёт `--fresh-suite`.

        Ловит мутацию: строка повторного использования собирается прежним
        текстом «… — использован повторно» без подсказки флага — в
        `detail` второго вызова нет `--fresh-suite`.
        """
        for index, (green, output) in enumerate([(False, RED), (True, GREEN)]):
            with self.subTest(green=green, seed=self.seed):
                (self.tree / "marker.txt").write_text(
                    f"{self.seed}:{index}:{self.rng.getrandbits(64)}\n",
                    encoding="utf-8")
                with mock.patch.object(acceptance, "run_full_suite",
                                       return_value=(green, output)) as run:
                    first = acceptance.full_suite(self.tree, self.task)
                    second = acceptance.full_suite(self.tree, self.task)
                context = self.note(f"первый: {first}\nвторой: {second}")
                self.assertEqual(run.call_count, 1, context)
                self.assertEqual(second.green, green, context)
                self.assertIn("--fresh-suite", second.detail, context)


class RunCreatedDbFileTest(SuiteTreeSandbox):

    def test_ac10_db_file_created_by_run_is_journaled(self):
        """Файл БД, появившийся за время прогона, — запись в журнале задачи; итог прежний.

        Сценарий: дерево до прогона чистое; подменённый pytest за время
        прогона заводит в корне дерева один из файлов БД пульта (каждый из
        четырёх, исход прогона — зелёный или красный от зерна). Итог
        `full_suite` — тот же исход, что выдал pytest; в журнале задачи —
        запись с путём файла и пометкой «прогон набора создал файл БД —
        неполная изоляция тестов».

        Ловит мутацию: дерево сверяется только до прогона, а после — нет;
        записи с пометкой в журнале задачи не появляется.
        """
        for rel in DB_FILES:
            green, output = self.rng.choice([(False, RED), (True, GREEN)])
            with self.subTest(file=rel, green=green, seed=self.seed):
                self.drop_db_files()
                data = self.rng.randbytes(self.rng.randrange(0, 3000))

                def leaky_run(*args, **kwargs):
                    self.put(rel, data)
                    return green, output

                with mock.patch.object(acceptance, "run_full_suite",
                                       side_effect=leaky_run) as run:
                    result = acceptance.full_suite(self.tree, self.task,
                                                   fresh=True)
                rows = self.journal_rows()
                context = self.note(f"{rel}: {result}\nжурнал:\n"
                                    + "\n".join(rows))
                self.assertEqual(run.call_count, 1, context)
                self.assertEqual(result.green, green, context)
                self.assertEqual(result.outcome,
                                 acceptance.FULL_SUITE_GREEN if green
                                 else acceptance.FULL_SUITE_RED, context)
                self.assertTrue([row for row in rows
                                 if LEAK_NOTE in row and rel in row], context)
        self.drop_db_files()


if __name__ == "__main__":
    unittest.main()
