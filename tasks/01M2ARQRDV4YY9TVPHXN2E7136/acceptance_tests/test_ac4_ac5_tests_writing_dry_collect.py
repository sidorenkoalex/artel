"""AC-4, AC-5 (tasks/01M2ARQRDV4YY9TVPHXN2E7136/SPEC.md): выход
`orchestrator.fsm_advance.tests_writing` делает сухой сбор материализованной
планки (`acceptance.collect`) ПОСЛЕ проверки трассируемости AC и ДО перевода
задачи в `in_dev`; отказ сбора отклоняет переход.

Песочница — `tests.sandbox.LightTransitionSandbox` (лёгкая, `gitcmd.git`/
`show`/`ls_tree_files` заглушены на диск `config.TASKS`), тем же приёмом, что
`tests/test_acceptance_tests_flow.py::TraceabilityTest`: сценарий здесь не
копирует её патчи, только пишет свой SPEC/планку на диск.

Красен до реализации: `fsm_advance.tests_writing` пока не зовёт
`acceptance.collect` вовсе (требования 1-2 SPEC ещё не реализованы) —
`test_ac4_...` падает на `collect_.assert_called_once()` (мок ни разу не
позван, переход уходит в `in_dev` без единого вызова сухого сбора), а
`mock.patch.object(acceptance, "collect", ...)` в `test_ac5_...` падает
`AttributeError`, потому что атрибута `collect` у модуля ещё нет.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import acceptance, fsm, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

SPEC_ONE_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка сухого сбора

## Критерии приёмки

AC-1. Единственный критерий, покрытый тестом.
"""

PASSING_TEST = '''"""Зелёный с рождения: фикстура планки-сценария этого файла, не планка
реальной задачи — проверяет только прохождение гейта tests_writing."""
import unittest


class PlankTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
'''


class _DryCollectSandbox(LightTransitionSandbox):

    def enter_tests_writing(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            SPEC_ONE_AC.format(task=self.TASK), encoding="utf-8")
        self.set_state("tests_writing")

    def write_plank(self, content: str = PASSING_TEST,
                    name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]


class DryCollectPlacementTest(_DryCollectSandbox):
    """AC-4: место сухого сбора в последовательности гейта."""

    def test_ac4_collect_runs_and_transition_proceeds_when_it_passes(self):
        """Трассируемость AC пройдена, сухой сбор — зелёный: `collect`
        позван ровно один раз, переход доходит до `in_dev` как раньше.

        Ловит мутацию: сухой сбор не подключён к `tests_writing` вовсе —
        `collect_.assert_called_once()` падает («Expected... to have been
        called once. Called 0 times»), хотя переход при этом всё равно
        проходит (иллюстрирует именно ПРОПУЩЕННУЮ проверку, не поломанный
        прежний путь)."""
        self.enter_tests_writing()
        self.write_plank()

        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "1 test collected")) as collect_:
            self.capture(fsm.cmd_advance, self.TASK)

        collect_.assert_called_once()
        self.assertEqual(self.state(), "in_dev")

    def test_ac4_collect_is_not_called_before_traceability_passes(self):
        """Трассируемость AC не пройдена (планка вовсе не заведена) — сухой
        сбор не звался: требование «ПОСЛЕ проверки трассируемости AC».

        Ловит мутацию: сухой сбор вызывается БЕЗУСЛОВНО, раньше проверки
        трассируемости (или параллельно ей) — `collect_.assert_not_called()`
        падает на несобранной, заведомо неполной планке."""
        self.enter_tests_writing()
        # acceptance_tests/ не заведена вовсе — AC-1 не покрыт ни тестом,
        # ни пометкой.

        with mock.patch.object(acceptance, "collect") as collect_:
            out = self.capture(fsm.cmd_advance, self.TASK)

        collect_.assert_not_called()
        self.assertEqual(self.state(), "tests_writing")
        self.assertIn("AC-1", out)


class DryCollectFailureTest(_DryCollectSandbox):
    """AC-5: отказ сухого сбора отклоняет переход."""

    def enter_ready_tests_writing(self) -> None:
        self.enter_tests_writing()
        self.write_plank()

    def test_ac5_failed_collect_blocks_the_transition(self):
        """Красный сухой сбор — задача остаётся в `tests_writing`; в журнал
        уходит запись «переход отклонён: планка не собирается» с хвостом
        вывода pytest в `detail`; печатается подсказка «дальше: почини
        импорт/синтаксис планки и повтори artel.py advance <id>».

        Ловит мутацию: отказ сухого сбора только печатается, но не
        останавливает переход (код продолжает к `store.set_state(...,
        "in_dev", ...)` несмотря на `collected=False`) — `self.state()`
        остался бы `in_dev` вместо `tests_writing`."""
        self.enter_ready_tests_writing()
        tail = "ModuleNotFoundError: No module named 'nope_ac5'"

        with mock.patch.object(acceptance, "collect",
                               return_value=(False, tail)):
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "tests_writing")
        self.assertIn(tail, out)
        self.assertIn(
            f"дальше: почини импорт/синтаксис планки и повтори "
            f"artel.py advance {self.TASK}", out)
        details = self.journal_details("переход отклонён: планка не собирается")
        self.assertEqual(len(details), 1, details)
        self.assertIn(tail, details[0])

    def test_ac5_failed_collect_does_not_set_the_lock(self):
        """`tests_locked_sha` не переставляется на отказе сухого сбора —
        значение, стоявшее ДО этого `advance`, обязано остаться нетронутым.

        Ловит мутацию: лок (`store.update_task(..., tests_locked_sha=...)`)
        по ошибке выполняется до/независимо от проверки исхода `collect` —
        сентинельное значение, поставленное этим тестом заранее, было бы
        затёрто вычисленным (в этой песочнице — пустым, `fake_git` не знает
        ветки) sha."""
        self.enter_ready_tests_writing()
        conn = store.db()
        conn.execute("UPDATE tasks SET tests_locked_sha=? WHERE id=?",
                     ("sentinel-untouched", self.TASK))
        conn.commit()

        with mock.patch.object(acceptance, "collect",
                               return_value=(False, "хвост")):
            self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["tests_locked_sha"],
                         "sentinel-untouched")


if __name__ == "__main__":
    unittest.main()
