"""Юнит-тесты гейта источника артефактов на выходе `tests_writing`
(`orchestrator/advance_gates/tests_writing.py::
_tests_writing_artifact_source_gate`, SPEC 01M2XJKKPHM5XDAE42838AMBQH,
требование 5, AC-6/AC-7) — постоянный набор `tests/`, отдельный от
залоченной планки задачи (`tasks/01M2XJKKPHM5XDAE42838AMBQH/
acceptance_tests/`), тем же приёмом, что
`tests/test_fsm_advance_tests_writing_dry_collect.py` для соседнего
гейта сухого сбора.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import acceptance, brief, fsm, store  # noqa: E402
from orchestrator.advance_gates import tests_writing as gates  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

SPEC_ONE_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка источника артефактов (юнит)

## Критерии приёмки

AC-1. Единственный критерий, покрытый тестом.
"""

CLEAN_PLANK = '''"""Зелёный с рождения: фикстура планки-сценария этого файла, не планка
реальной задачи — проверяет только прохождение гейта tests_writing."""
import unittest
from pathlib import Path

from orchestrator import artifact_branch, gitcmd

TASK = "01FIXTURETASK"


class PlankTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        text, _reason = gitcmd.show(artifact_branch.branch_name(TASK),
                                    "tasks/01FIXTURETASK/PLAN.md")
        self.assertIsNotNone(Path(__file__))
'''

DISK_READING_PLANK = '''"""Зелёный с рождения: фикстура планки-сценария этого файла, не планка
реальной задачи — читает PLAN.md с диска, чтобы гейт отказал."""
import unittest
from pathlib import Path


class PlankTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        plan = Path(__file__).resolve().parents[1] / "PLAN.md"
        self.assertTrue(plan)
'''
DISK_READ_LINENO = 9

# Планка со вложенной песочницей (ANSWER-1, вариант B): пишет и читает
# поддельный SPEC.md фиктивной задачи во временном каталоге — путь не
# якорится на рабочую копию, правило её не касается.
TEMP_DIR_FIXTURE_PLANK = '''"""Зелёный с рождения: фикстура планки-сценария этого файла, не планка
реальной задачи — пишет поддельный SPEC.md фиктивной задачи во временный
каталог, как вложенная песочница FSM-задач."""
import tempfile
import unittest
from pathlib import Path


class PlankTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        tdir = Path(tempfile.mkdtemp()) / "tasks" / "01FIXTURETASK"
        tdir.mkdir(parents=True)
        (tdir / "SPEC.md").write_text("# SPEC", encoding="utf-8")
        self.assertTrue((tdir / "SPEC.md").read_text(encoding="utf-8"))
'''


class _ArtifactSourceSandbox(LightTransitionSandbox):

    def enter_tests_writing(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            SPEC_ONE_AC.format(task=self.TASK), encoding="utf-8")
        self.set_state("tests_writing")

    def write_plank(self, content: str, name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def refusal_rows(self) -> list:
        return [dict(r) for r in store.task_steps(store.db(), self.TASK)
                if r["action"] == gates.ARTIFACT_DISK_READ_ACTION]


class ArtifactSourceGateTest(_ArtifactSourceSandbox):
    """AC-6: отказ именованным действием, текст ошибок в detail, задача
    остаётся в `tests_writing`."""

    def test_disk_reading_plank_is_refused_with_named_action(self):
        """Планка читает `PLAN.md` с диска — состояние `tests_writing`,
        ровно одна запись «переход отклонён: планка читает артефакты с
        диска», detail несёт файл, строку и рецепт, тот же текст и
        подсказка напечатаны.

        Ловит мутацию: отказ журналируется под действием сухого сбора
        («планка не собирается») или переход продолжается в `in_dev` —
        выборка по точному действию окажется пустой либо состояние
        сменится."""
        self.enter_tests_writing()
        self.write_plank(DISK_READING_PLANK)

        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "1 test collected")):
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "tests_writing")
        rows = self.refusal_rows()
        self.assertEqual(len(rows), 1, out)
        detail = rows[0]["detail"]
        self.assertIn(f"acceptance_tests/test_ac.py:{DISK_READ_LINENO}: ", detail)
        self.assertIn("gitcmd.show(artifact_branch.branch_name(TASK_ID), "
                      '"tasks/<id>/PLAN.md")', detail)
        self.assertIn(detail, out)
        self.assertIn(f"дальше: перепиши чтение артефактов планки на "
                      f"артефактную ветку (skills/test-authoring.md) и "
                      f"повтори artel.py advance {self.TASK}", out)

    def test_refusal_precedes_dry_collect(self):
        """На планке с чтением с диска субпроцесс сухого сбора не
        запускается вовсе — статическая проверка идёт первой.

        Ловит мутацию: порядок внутри гейта переставлен (сначала
        `acceptance.collect`, потом источник) — `collect` был бы позван
        на планке, заведомо отклонённой."""
        self.enter_tests_writing()
        self.write_plank(DISK_READING_PLANK)

        with mock.patch.object(acceptance, "collect") as collect_:
            self.capture(fsm.cmd_advance, self.TASK)

        collect_.assert_not_called()

    def test_refusal_does_not_set_the_lock(self):
        """`tests_locked_sha` не переставляется на отказе источника.

        Ловит мутацию: лок выполняется до/независимо от исхода гейта —
        сентинельное значение было бы затёрто вычисленным."""
        self.enter_tests_writing()
        self.write_plank(DISK_READING_PLANK)
        conn = store.db()
        conn.execute("UPDATE tasks SET tests_locked_sha=? WHERE id=?",
                     ("sentinel-unit", self.TASK))
        conn.commit()

        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "ok")):
            self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["tests_locked_sha"], "sentinel-unit")

    def test_clean_plank_passes_to_in_dev_and_collect_runs(self):
        """Планка читает `PLAN.md` через `gitcmd.show(artifact_branch.
        branch_name(...), ...)` — гейт молчит, сухой сбор позван, переход
        доходит до `in_dev` без записи отказа.

        Ловит мутацию: проверка ищет имя артефакта в любом литерале
        файла (без разбора выражения) — законная планка получила бы
        отказ, `collect` не был бы позван."""
        self.enter_tests_writing()
        self.write_plank(CLEAN_PLANK)

        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "1 test collected")) as collect_:
            self.capture(fsm.cmd_advance, self.TASK)

        collect_.assert_called_once()
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.refusal_rows(), [])

    def test_temp_dir_fixture_plank_passes_to_in_dev(self):
        """Планка со вложенной песочницей пишет `SPEC.md` фиктивной
        задачи во временный каталог и читает его оттуда — гейт молчит,
        переход доходит до `in_dev` без записи отказа (ANSWER-1, вариант
        B: путь от временного каталога не якорится на рабочую копию).

        Ловит мутацию: якорный предикат guard снят или гейт зовёт не
        `scan_artifact_disk_reads`, а текстовый поиск имени артефакта
        рядом с признаком доступа — штатный приём планок FSM-задач получал
        бы отказ, состояние осталось бы `tests_writing`."""
        self.enter_tests_writing()
        self.write_plank(TEMP_DIR_FIXTURE_PLANK)

        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "1 test collected")):
            self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.refusal_rows(), [])


class RefusalClassTest(_ArtifactSourceSandbox):
    """AC-7: отказ того же класса, что остальные отказы `tests_writing` —
    виден в истории отказов брифа test_author."""

    def test_refusal_surfaces_in_test_author_brief_history(self):
        """После отказа гейта `brief.advance_refusal_history` для
        `test_author` в `tests_writing` несёт действие и рецепт.

        Ловит мутацию: действие внесено в `brief.
        _ROLE_NOT_FINISHED_REFUSAL_ACTIONS` или журналируется не под
        actor `fsm` — история брифа окажется пустой."""
        self.enter_tests_writing()
        self.write_plank(DISK_READING_PLANK)
        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "ok")):
            self.capture(fsm.cmd_advance, self.TASK)

        text = brief.advance_refusal_history(
            store.db(), self.TASK, "test_author", "tests_writing")

        self.assertIn(gates.ARTIFACT_DISK_READ_ACTION, text)
        self.assertIn("gitcmd.show(artifact_branch.branch_name(TASK_ID)", text)


if __name__ == "__main__":
    unittest.main()
