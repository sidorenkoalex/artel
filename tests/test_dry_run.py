"""Юнит-тесты orchestrator/dry_run.py (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md).

Сквозной путь по критериям приёмки (AC-1..AC-9) уже кроют приёмочные
тесты задачи (`tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/acceptance_tests/`,
залочены — тем же реальным git-приёмом, `RealGitSandbox`). Здесь —
модуль в изоляции: чистый фильтр `_is_test_file` и прямой вызов
`cmd_acceptance_dry_run` (минуя диспетчер `artel.py`) на меньшем наборе
сценариев, тем же приёмом, что `tests/test_release.py` держит для
своего модуля рядом с приёмочными тестами T062.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, dry_run, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK = "T900"
BRANCH = "task/t900-dry-run-fixture"

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: фикстура

## Критерии приёмки

{ac_section}
"""


class IsTestFileTest(unittest.TestCase):

    def test_matches_test_prefixed_py_files(self):
        self.assertTrue(dry_run._is_test_file(
            "tasks/T1/acceptance_tests/test_ac1_thing.py"))

    def test_matches_nested_test_files(self):
        self.assertTrue(dry_run._is_test_file(
            "tasks/T1/acceptance_tests/sub/test_nested.py"))

    def test_rejects_non_py_files(self):
        self.assertFalse(dry_run._is_test_file(
            "tasks/T1/acceptance_tests/test_data.txt"))

    def test_rejects_files_not_starting_with_test_prefix(self):
        self.assertFalse(dry_run._is_test_file(
            "tasks/T1/acceptance_tests/_sandbox.py"))
        self.assertFalse(dry_run._is_test_file(
            "tasks/T1/acceptance_tests/__init__.py"))
        self.assertFalse(dry_run._is_test_file(
            "tasks/T1/acceptance_tests/conftest.py"))


class DryRunSandboxTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def seed_task(self, branch: str = BRANCH, task_id: str = TASK) -> None:
        store.insert_task(self.conn, task_id, "Фикстура", "in_dev", branch,
                          config.DEFAULT_TARGET, 25.0)

    def commit_fixture(self, ac_section: str, test_files: dict,
                       branch: str = BRANCH, task_id: str = TASK) -> None:
        self.checkout(branch, create=True)
        d = self.root / "tasks" / task_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "SPEC.md").write_text(
            SPEC_TEMPLATE.format(task=task_id, ac_section=ac_section),
            encoding="utf-8")
        tests_dir = d / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        for name, content in test_files.items():
            (tests_dir / name).write_text(content, encoding="utf-8")
        self.git("add", f"tasks/{task_id}")
        self.git("commit", "-q", "-m", "фикстура")
        self.checkout(config.MAIN_BRANCH)

    def run_dry_run(self, task_id: str = TASK) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            dry_run.cmd_acceptance_dry_run(task_id)
        return buf.getvalue()


TEST_FILE = '''"""Фикстура unit-теста dry_run.

Зелёный с рождения: файл-фикстура, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest

# AC-2: manual — причина manual


class FixtureTest(unittest.TestCase):

    def test_ac1_covered(self):
        """Фикстура."""
        pass

    def test_plain_method(self):
        """Фикстура — не AC-размечен, но должен быть в списке файлов."""
        pass
'''

AC_SECTION = ("AC-1. Покрыт тестом.\n"
              "AC-2. Покрыт пометкой.\n"
              "AC-3. Ничем не покрыт.\n")


class MissingBranchTest(DryRunSandboxTest):

    def test_refuses_naming_the_missing_branch(self):
        self.seed_task(branch="task/does-not-exist-at-all")

        with self.assertRaises(SystemExit) as ctx:
            self.run_dry_run()

        self.assertIn("task/does-not-exist-at-all", str(ctx.exception))

    def test_no_journal_or_state_write_on_refusal(self):
        self.seed_task(branch="task/does-not-exist-at-all")
        steps_before = store.task_steps(store.db(), TASK)
        state_before = dict(store.get_task(store.db(), TASK))["state"]

        with self.assertRaises(SystemExit):
            self.run_dry_run()

        self.assertEqual(len(store.task_steps(store.db(), TASK)),
                         len(steps_before))
        self.assertEqual(dict(store.get_task(store.db(), TASK))["state"],
                         state_before)


class MissingDirectoryTest(DryRunSandboxTest):

    def test_refuses_naming_the_missing_directory_not_the_branch(self):
        self.checkout(BRANCH, create=True)
        d = self.root / "tasks" / TASK
        d.mkdir(parents=True, exist_ok=True)
        (d / "SPEC.md").write_text(
            SPEC_TEMPLATE.format(task=TASK, ac_section="AC-1. Крит.\n"),
            encoding="utf-8")
        self.git("add", f"tasks/{TASK}")
        self.git("commit", "-q", "-m", "SPEC без acceptance_tests")
        self.checkout(config.MAIN_BRANCH)
        self.seed_task()

        with self.assertRaises(SystemExit) as ctx:
            self.run_dry_run()

        message = str(ctx.exception)
        self.assertIn("acceptance_tests", message)
        self.assertNotIn("не существует", message,
                         "отказ по каталогу перепутан с отказом по ветке")


class HappyPathTest(DryRunSandboxTest):

    def test_output_carries_files_methods_markers_traceability_and_marker(self):
        self.commit_fixture(AC_SECTION, {"test_fixture.py": TEST_FILE})
        self.seed_task()

        out = self.run_dry_run()

        self.assertIn("test_fixture.py", out)
        self.assertIn("test_ac1_covered", out)
        self.assertIn("test_plain_method", out)
        self.assertIn("AC-2: manual", out)
        self.assertIn("причина manual", out)
        self.assertIn("AC-1: покрыт тестом", out)
        self.assertIn("AC-3: не покрыт", out)
        self.assertIn("непокрытые AC: AC-3", out)
        self.assertIn(dry_run.DRY_RUN_MARKER, out)

    def test_read_only_no_journal_state_or_lease_write(self):
        self.commit_fixture(AC_SECTION, {"test_fixture.py": TEST_FILE})
        self.seed_task()
        steps_before = store.task_steps(store.db(), TASK)
        state_before = dict(store.get_task(store.db(), TASK))["state"]

        self.run_dry_run()

        self.assertEqual(len(store.task_steps(store.db(), TASK)),
                         len(steps_before))
        self.assertEqual(dict(store.get_task(store.db(), TASK))["state"],
                         state_before)
        self.assertIsNone(store.lease_row(store.db(), TASK))


if __name__ == "__main__":
    unittest.main()
