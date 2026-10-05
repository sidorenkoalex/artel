"""Юнит-тесты помощника планки `_pult.py` (SPEC 01M44EP4Q927DJXVX9YMMZ0B7V):
исходный текст `orchestrator/plank_helper.py`, его выкладка
`orchestrator/acceptance.py`, зарезервированное имя (`scripts/guard.py`,
`orchestrator/advance_gates/tests_writing.py`) и рецепт отказа чтения
артефактов с диска.

Настоящий git (`tests.sandbox.SyncedOriginConnSandbox`): предмет — ответы git
на вопросы помощника, заглушкой их не изобразить.
"""
import ast
import importlib.util
import itertools
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, artifact_branch, checkpoint,  # noqa: E402
                          config, gitcmd, store, workspace)
from orchestrator.advance_gates import tests_writing as gates  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import SyncedOriginConnSandbox  # noqa: E402

TASK = "01UTPLANKHELPERTASK0000000"
BRANCH = f"task/{TASK.lower()}-helper"
HELPER = "_pult.py"
PLANK_TEST = "import unittest\n\n\nclass T(unittest.TestCase):\n    pass\n"
_loaded = itertools.count()


def load_helper(path: Path):
    spec = importlib.util.spec_from_file_location(
        f"ut_pult_helper_{next(_loaded)}", path)
    module = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


class PlankHelperSourceTest(unittest.TestCase):

    def test_source_imports_only_stdlib(self):
        """Исходный текст помощника импортирует только стандартную библиотеку.

        Ловит мутацию: помощник берёт `from orchestrator import gitcmd` или
        относительный импорт пакета ради готовых примитивов — разбор
        называет этот импорт, а планка в рабочей копии со сломанным
        `orchestrator` упала бы на импорте помощника."""
        source = (Path(acceptance.__file__).with_name("plank_helper.py")
                  .read_text(encoding="utf-8"))
        foreign = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                foreign += [a.name for a in node.names
                            if a.name.split(".")[0] not in sys.stdlib_module_names]
            elif isinstance(node, ast.ImportFrom):
                if node.level or (node.module or "").split(".")[0] \
                        not in sys.stdlib_module_names:
                    foreign.append(f"{'.' * node.level}{node.module}")

        self.assertEqual(foreign, [])


class ReservedNameGuardTest(unittest.TestCase):

    def test_reserved_name_is_extraneous_other_underscore_modules_are_not(self):
        """`_pult.py` планки — посторонний файл; прочие `_*.py` — законны.

        Ловит мутацию: резервирование снято (имя снова проходит `_*.py`) —
        копия помощника, оставленная в рабочей копии кода, доехала бы
        автокоммитом до ссылки документов; либо резервирование задело все
        `_*.py` — `_plank.py`/`_sandbox.py` стали бы посторонними."""
        self.assertTrue(guard.is_extraneous_acceptance_test_file(HELPER))
        for name in ("_plank.py", "_sandbox.py", "_pult_util.py", "test_x.py"):
            self.assertFalse(guard.is_extraneous_acceptance_test_file(name), name)

    def test_disk_read_recipe_names_helper_function(self):
        """Рецепт отказа «чтение артефакта с диска» называет `artifact_text`.

        Ловит мутацию: рецепт снова советует `gitcmd.show(…)` — планка в
        рабочей копии без `.artel/` не нашла бы им клон ссылки."""
        errors = guard.artifact_disk_read_errors_from_files(
            [("acceptance_tests/test_x.py",
              "from pathlib import Path\n"
              "p = Path(__file__).parent / 'REVIEW.md'\n")])

        self.assertEqual(len(errors), 1, errors)
        self.assertIn('artifact_text("REVIEW.md")', errors[0])
        self.assertNotIn("gitcmd.show(", errors[0])


class _HelperSandbox(SyncedOriginConnSandbox):
    """Задача `TASK` в `tests_writing`, рабочая копия на `BRANCH`, ссылка
    документов с SPEC.md."""

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "помощник", "tests_writing",
                          BRANCH, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(TASK, BRANCH)
        self.assertIsNone(error)
        self.wt = wt
        self.commit_to_ref({"SPEC.md": "# SPEC\n"})
        self.helper_path = self.wt / "tasks" / TASK / "acceptance_tests" / HELPER

    def commit_to_ref(self, files: dict) -> None:
        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/{rel}": text for rel, text in files.items()},
            "документы")
        self.assertTrue(sha)
        store.record_fixation(self.conn, TASK)

    def wt_git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.wt, capture_output=True,
                             text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def commit_code(self, rel: str, text: str) -> None:
        (self.wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.wt / rel).write_text(text, encoding="utf-8")
        self.wt_git("add", rel)
        self.wt_git("commit", "-q", "-m", "код")

    def materialize(self):
        acceptance.materialize_from_branch(
            TASK, artifact_branch.branch_name(TASK), self.wt)
        return load_helper(self.helper_path)


class MaterializationTest(_HelperSandbox):

    def test_values_are_substituted_from_layout_moment(self):
        """Выложенный помощник несёт значения выкладки, а не заглушки шаблона.

        Ловит мутацию: строка значения не подставлена (регулярное
        выражение блока разошлось с именем константы) или база посчитана
        своим `merge-base` от локальной ветки — значение расходится с
        `gitcmd.diff_base`/`ref_head`."""
        helper = self.materialize()

        self.assertEqual(helper.TASK_ID, TASK)
        self.assertEqual(Path(helper.CODE_ROOT), self.wt.resolve())
        self.assertEqual(Path(helper.DOCS_REPO).resolve(),
                         workspace.task_repo(TASK).resolve())
        self.assertEqual(helper.DOCS_REVISION, artifact_branch.ref_head(TASK))
        self.assertEqual(helper.DIFF_BASE,
                         gitcmd.diff_base(BRANCH, repo=workspace.task_repo(TASK)))
        self.assertEqual(helper.DIFF_BASE_SOURCE,
                         gitcmd.diff_base_source(BRANCH,
                                                 repo=workspace.task_repo(TASK)))

    def test_pult_file_wins_over_plank_file_and_drop_removes_it(self):
        """Свой `_pult.py` планки и черновика перетирается помощником; уборка
        выкладки убирает помощник вместе с планкой.

        Ловит мутацию: помощник кладётся до файлов планки (`{helper,
        **wanted}`) — на диске файл планки без `TASK_ID`."""
        self.commit_to_ref({"acceptance_tests/test_ac1.py": PLANK_TEST,
                            f"acceptance_tests/{HELPER}": "OWN = 1\n"})
        self.assertEqual(self.materialize().TASK_ID, TASK)

        acceptance.materialize_files(TASK, {"test_ac1.py": PLANK_TEST,
                                            HELPER: b"OWN = 1\n"}, self.wt)
        self.assertFalse(hasattr(load_helper(self.helper_path), "OWN"))

        acceptance.drop_from_code_copy(TASK, self.wt)
        self.assertFalse(self.helper_path.exists())

    def test_helper_alone_is_not_a_plank(self):
        """Каталог, где лежит только помощник, — «тесты не заведены».

        Сценарий: в ссылке нет `acceptance_tests/`; выкладка всё равно
        кладёт `_pult.py`. `acceptance.run`, `collect` и `summary` отвечают
        так же, как без каталога: зелёно, pytest не запускается.

        Ловит мутацию: `_run_targets`/`summary` снова проверяют только
        наличие каталога — pytest получает каталог без тестов, код выхода
        5, задача без планки краснеет на приёмке."""
        tdir = acceptance.materialize_from_branch(
            TASK, artifact_branch.branch_name(TASK), self.wt)
        self.assertTrue(self.helper_path.is_file())

        self.assertEqual(acceptance.run(tdir, cwd=self.wt)[0], True)
        self.assertEqual(acceptance.collect(tdir, cwd=self.wt)[0], True)
        self.assertIn("не заведены", acceptance.summary(tdir))


class HelperFunctionsTest(_HelperSandbox):

    def test_artifact_text_reads_layout_revision(self):
        """`artifact_text` — ревизия выкладки; файла нет — `None`.

        Ловит мутацию: чтение по имени ссылки, а не по sha выкладки, —
        после нового коммита помощник отдаёт новый текст."""
        self.commit_to_ref({"PLAN.md": "v1\n"})
        helper = self.materialize()
        self.commit_to_ref({"PLAN.md": "v2\n", "REVIEW.md": "r\n"})

        self.assertEqual(helper.artifact_text("PLAN.md"), "v1\n")
        self.assertIsNone(helper.artifact_text("REVIEW.md"))
        self.assertIsNone(helper.artifact_text("acceptance_tests"))

    def test_artifact_text_git_failure_is_named_error_not_none(self):
        """Ревизии нет в репозитории ссылки — `ArtifactReadError`, не `None`.

        Ловит мутацию: ненулевой код `git ls-tree` трактуется как «файла
        нет» — сбой git молча становится отсутствием артефакта."""
        helper = self.materialize()
        helper.DOCS_REVISION = "0" * 40

        with self.assertRaises(helper.ArtifactReadError):
            helper.artifact_text("SPEC.md")

    def test_changed_paths_skips_uncommitted_tracked_edits(self):
        """`changed_paths()`: закоммиченное + неотслеживаемое вне `tasks/<id>/`.

        Сценарий: закоммичен `feature.py`, неотслеживаемый `notes/a.txt`,
        отслеживаемый `marker.txt` правлен без коммита, рядом выложена
        планка. Список — `feature.py`, `notes/a.txt`; `branch_diff()` несёт
        `feature.py`, но не правку `marker.txt`.

        Ловит мутацию: неотслеживаемые читаются `git status --porcelain`
        (как довесок гейта зон) — в списке появляется `marker.txt`; либо
        каталог задачи не исключён — в списке `_pult.py`."""
        self.commit_code("feature.py", "X = 1\n")
        (self.wt / "notes").mkdir()
        (self.wt / "notes" / "a.txt").write_text("a\n", encoding="utf-8")
        (self.wt / "marker.txt").write_text("грязно\n", encoding="utf-8")
        helper = self.materialize()

        self.assertEqual(sorted(helper.changed_paths()),
                         ["feature.py", "notes/a.txt"])
        diff = helper.branch_diff()
        self.assertIn("+X = 1", diff)
        self.assertNotIn("marker.txt", diff)

    def test_apply_check_against_head_tree_leaves_copy_intact(self):
        """`apply_check` — дерево HEAD во временном индексе; копия не меняется.

        Сценарий: `marker.txt` грязный; дифф к HEAD-версии применим, уже
        наложенный коммит применим обратно, но не прямо; статус и индекс до
        и после совпадают.

        Ловит мутацию: `--cached` без временного индекса (`GIT_INDEX_FILE`)
        — проверка шла бы по общему индексу рабочей копии; без `--cached` —
        по грязному рабочему дереву, применимый к HEAD дифф получил бы
        отказ."""
        self.commit_code("feature.py", "X = 1\n")
        applied = self.wt_git("diff", "HEAD~1", "HEAD")
        (self.wt / "marker.txt").write_text("грязно\n", encoding="utf-8")
        self.wt_git("add", "marker.txt")
        helper = self.materialize()
        to_head = ("diff --git a/marker.txt b/marker.txt\n--- a/marker.txt\n"
                   "+++ b/marker.txt\n@@ -1 +1 @@\n-main\n+правка\n")
        before = (self.wt_git("status", "--porcelain=v1"),
                  self.wt_git("ls-files", "-s"))

        self.assertEqual(helper.apply_check(to_head), "")
        self.assertEqual(helper.apply_check(applied, reverse=True), "")
        self.assertNotEqual(helper.apply_check(applied), "")

        self.assertEqual((self.wt_git("status", "--porcelain=v1"),
                          self.wt_git("ls-files", "-s")), before)


class ReservedNameGateTest(_HelperSandbox):

    def test_reserved_name_in_docs_ref_refuses_with_hint(self):
        """`_pult.py` в планке ссылки — отказ классом «посторонние файлы».

        Ловит мутацию: проверка ссылки снята или сравнивает путь не того
        уровня (`acceptance_tests/x/_pult.py`) — отказа нет."""
        self.assertIsNone(gates._tests_writing_stray_plank_files_gate(
            self.conn, TASK))
        self.commit_to_ref({f"acceptance_tests/{HELPER}": "OWN = 1\n"})

        refusal = gates._tests_writing_stray_plank_files_gate(self.conn, TASK)

        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.action, gates.STRAY_PLANK_FILES_ACTION)
        self.assertIn(guard.RESERVED_PLANK_HELPER_HINT, refusal.hint)

    def test_stray_journal_names_reserved_name_only_when_dropped(self):
        """Отброшенный автокоммитом `_pult.py` — подсказка про занятое имя;
        прочие отброшенные файлы — прежняя подсказка.

        Ловит мутацию: подсказка про имя помощника печатается на любой
        записи посторонних файлов (или не печатается вовсе) — роль ищет не
        ту причину."""
        prefix = checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX
        store.journal(self.conn, TASK, "orchestrator",
                      checkpoint.STRAY_ACCEPTANCE_FILES_ACTION,
                      f"{prefix}acceptance_tests/shared.py")
        other = gates._tests_writing_stray_plank_files_gate(self.conn, TASK)
        store.journal(self.conn, TASK, "orchestrator",
                      checkpoint.STRAY_ACCEPTANCE_FILES_ACTION,
                      f"{prefix}acceptance_tests/{HELPER}, acceptance_tests/x.py")
        reserved = gates._tests_writing_stray_plank_files_gate(self.conn, TASK)

        self.assertNotIn(guard.RESERVED_PLANK_HELPER_HINT, other.hint)
        self.assertIn(guard.RESERVED_PLANK_HELPER_HINT, reserved.hint)


if __name__ == "__main__":
    unittest.main()
