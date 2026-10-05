"""AC-9: отказ «планка читает артефакты с диска» называет `artifact_text(`.

Текст `scripts/guard.py::ARTIFACT_DISK_READ_RECIPE_TMPL` и подсказка
`_tests_writing_artifact_source_gate` называют `artifact_text(` помощника,
а не `gitcmd.show(`; планка, которую гейт отказывал до задачи,
отказывается и после неё.

Группа: разовый
Красен до реализации: рецепт и подсказка называют `gitcmd.show(artifact_branch.branch_name(TASK_ID), …)` и «артефактную ветку» — `artifact_text(` в них нет.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator.advance_gates import tests_writing as gates  # noqa: E402
from scripts import guard  # noqa: E402

TASK_ID = "01FIXTUREDISKREADTASK00000"
NEW = "artifact_text("
OLD = "gitcmd.show("

# Планки, которые гейт отказывал до задачи (формы якоря: `__file__`,
# корневой литерал `tasks`, `config.TASKS`) — тексты фикстур, не код этой
# планки.
REFUSED_BEFORE = {
    "from __file__": '''import unittest
from pathlib import Path


class PlankTest(unittest.TestCase):
    def test_ac1_x(self):
        plan = Path(__file__).resolve().parents[1] / "PLAN.md"
        self.assertTrue(plan.read_text(encoding="utf-8"))
''',
    "literal tasks": '''import os
import unittest

TASK = "01FIXTUREDISKREADTASK00000"


class PlankTest(unittest.TestCase):
    def test_ac1_x(self):
        with open(os.path.join("tasks", TASK, "SPEC.md"), encoding="utf-8") as fh:
            self.assertTrue(fh.read())
''',
    "config.TASKS": '''import unittest

from orchestrator import config

TASK = "01FIXTUREDISKREADTASK00000"


class PlankTest(unittest.TestCase):
    def test_ac1_x(self):
        self.assertTrue((config.TASKS / TASK / "REVIEW.md").read_text())
''',
}


class RecipeTextTest(unittest.TestCase):

    def test_ac9_recipe_template_names_artifact_text(self):
        """Шаблон рецепта называет `artifact_text(`, а не `gitcmd.show(`.

        Ловит мутацию: правка задачи дошла до скила, но не до
        `ARTIFACT_DISK_READ_RECIPE_TMPL` — шаблон по-прежнему советует
        `gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`."""
        self.assertIn(NEW, guard.ARTIFACT_DISK_READ_RECIPE_TMPL)
        self.assertNotIn(OLD, guard.ARTIFACT_DISK_READ_RECIPE_TMPL)

    def test_ac9_previously_refused_planks_still_refused_with_new_recipe(self):
        """Планки, отказанные до задачи, отказываются и после — с новым рецептом.

        Сценарий: три формы чтения артефакта с диска (`Path(__file__)…/
        "PLAN.md"`, `open(os.path.join("tasks", …, "SPEC.md"))`,
        `config.TASKS / … / "REVIEW.md"`); для каждой guard даёт ошибку,
        и текст ошибки называет `artifact_text(`, но не `gitcmd.show(`.

        Ловит мутацию: вместе с рецептом ослаблено правило (снят якорь
        `config.TASKS` или корневой литерал `tasks`) — одна из форм больше
        не отказывается."""
        for form, source in REFUSED_BEFORE.items():
            errors = guard.artifact_disk_read_errors_from_files(
                [("acceptance_tests/test_ac.py", source)])
            self.assertTrue(errors, f"форма «{form}» больше не отказывается")
            for error in errors:
                self.assertIn(NEW, error, f"форма «{form}»")
                self.assertNotIn(OLD, error, f"форма «{form}»")


class GateHintTest(unittest.TestCase):

    def setUp(self):
        self.tdir = Path(tempfile.mkdtemp(prefix="plank-ac9-")) / TASK_ID
        self.addCleanup(shutil.rmtree, self.tdir.parent, ignore_errors=True)
        (self.tdir / "acceptance_tests").mkdir(parents=True)

    def test_ac9_gate_refusal_hint_names_artifact_text(self):
        """Отказ гейта источника артефактов: подсказка и detail — `artifact_text(`.

        Сценарий: каталог планки с каждой из трёх форм чтения с диска;
        `_tests_writing_artifact_source_gate` отказывает действием
        `ARTIFACT_DISK_READ_ACTION` (правило прежнее), подсказка содержит
        `artifact_text(`, ни подсказка, ни detail не содержат
        `gitcmd.show(`.

        Ловит мутацию: заменён только шаблон guard, а подсказка гейта
        осталась «перепиши чтение … на артефактную ветку» без имени
        функции помощника — `artifact_text(` в подсказке нет."""
        for form, source in REFUSED_BEFORE.items():
            (self.tdir / "acceptance_tests" / "test_ac.py").write_text(
                source, encoding="utf-8")

            refusal = gates._tests_writing_artifact_source_gate(
                self.tdir, TASK_ID)

            self.assertIsNotNone(refusal, f"форма «{form}» не отказана")
            self.assertEqual(refusal.action, gates.ARTIFACT_DISK_READ_ACTION)
            self.assertIn(NEW, refusal.hint, f"форма «{form}»")
            self.assertNotIn(OLD, refusal.hint, f"форма «{form}»")
            self.assertNotIn(OLD, refusal.detail, f"форма «{form}»")


if __name__ == "__main__":
    unittest.main()
