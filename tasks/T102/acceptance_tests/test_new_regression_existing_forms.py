"""Приёмочные тесты T102 — AC-6, AC-7 (tasks/T102/SPEC.md): существующие
корректные формы `new` продолжают работать без изменений после того, как
T102 научит разбор argv отказывать на нераспознанном вводе.

Зелёный с рождения: `new "Название"` и `new "Название" --tz <файл>` уже
сегодня заводят задачу штатно (`catalog.cmd_new`, SPEC T048/T025) — эти
два теста фиксируют регресс-планку ДО правки T102, чтобы разработчик не
мог сузить разбор argv так, что заодно отвалятся и корректные формы
(SPEC.md, требование 4 / «Не входит»).

Песочница и приём (копия `templates/`, `fake_git` вместо `gitcmd.git`,
`catalog.cmd_init`) — тот же образец, что `tests/test_catalog_new_race.py`:
worktree и коммит задачи не нуждаются в настоящем git, а `task_dir.mkdir`
внутри `cmd_new` реально создаёт файлы на диске поверх заглушки.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artel, catalog, config, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402

TITLE = "Название"


class NewExistingFormsRegressionTest(TmpRootTest):

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.capture(catalog.cmd_init)

    def _cli_new(self, *rest: str) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", "new", *rest]):
            return self.capture(artel.main)

    # ------------------------------------------------------------ AC-6

    def test_ac6_title_without_tz_creates_task_as_before(self):
        self._cli_new(TITLE)

        row = store.db().execute(
            "SELECT * FROM tasks WHERE id='T001'").fetchone()
        self.assertIsNotNone(row, "`new \"Название\"` обязан завести T001")
        self.assertEqual(row["title"], TITLE)
        self.assertEqual(row["branch"],
                         f"task/t001-{catalog.slugify(TITLE)}")

        task_dir = config.WORKTREES / "T001" / "tasks" / "T001"
        self.assertTrue((task_dir / "SPEC.md").exists(),
                        "шаблонный SPEC.md обязан появиться в ветке задачи")
        self.assertFalse((task_dir / "TZ.md").exists(),
                         "без --tz TZ.md появляться не должен")

    # ------------------------------------------------------------ AC-7

    def test_ac7_title_with_tz_creates_task_with_tz_as_before(self):
        tz_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tz_dir, ignore_errors=True)
        tz_path = Path(tz_dir) / "tz.txt"
        tz_text = "Проверка регресса `--tz` при разборе argv T102.\n"
        tz_path.write_text(tz_text, encoding="utf-8")

        self._cli_new(TITLE, "--tz", str(tz_path))

        row = store.db().execute(
            "SELECT * FROM tasks WHERE id='T001'").fetchone()
        self.assertIsNotNone(
            row, "`new \"Название\" --tz <файл>` обязан завести T001")
        self.assertEqual(row["title"], TITLE)
        self.assertEqual(row["branch"],
                         f"task/t001-{catalog.slugify(TITLE)}")

        task_dir = config.WORKTREES / "T001" / "tasks" / "T001"
        self.assertTrue((task_dir / "SPEC.md").exists())
        tz_written = task_dir / "TZ.md"
        self.assertTrue(tz_written.exists(),
                        "--tz обязан завести TZ.md в ветке задачи")
        self.assertIn(tz_text, tz_written.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
