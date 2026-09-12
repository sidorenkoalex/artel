"""Юнит-тесты выхода `orchestrator/fsm_advance.py::tests_writing` — сухой
сбор планки и гейт посторонних файлов (SPEC 01M2ARQRDV4YY9TVPHXN2E7136,
требования 2-3, AC-4/AC-5/AC-8/AC-12/AC-13) — постоянный набор `tests/`,
отдельный от залоченной планки задачи (`tasks/01M2ARQRDV4YY9TVPHXN2E7136/
acceptance_tests/test_ac4_ac5_tests_writing_dry_collect.py`/
`test_ac8_stray_files_last_journal_entry.py`), которая испытывает те же
сценарии, но уходит из репозитория логически вместе с задачей.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import acceptance, checkpoint, fsm, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

SPEC_ONE_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка сухого сбора (юнит)

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

    def journal_stray_files(self, names: list) -> None:
        store.journal(
            store.db(), self.TASK, "orchestrator",
            checkpoint.STRAY_ACCEPTANCE_FILES_ACTION,
            f"{checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX}"
            f"{', '.join(names)}")


class DryCollectGateTest(_DryCollectSandbox):
    """AC-4/AC-5: место сухого сбора в последовательности гейта и его
    способность отклонить переход."""

    def test_ac4_collect_runs_after_traceability_and_transition_proceeds(self):
        """Трассируемость AC пройдена, сухой сбор — зелёный: `collect`
        позван ровно один раз, переход доходит до `in_dev`.

        Ловит мутацию: сухой сбор не подключён к `tests_writing` вовсе —
        `collect_.assert_called_once()` падает, хотя переход при этом
        всё равно проходит (иллюстрирует именно пропущенную проверку, не
        поломанный прежний путь)."""
        self.enter_tests_writing()
        self.write_plank()

        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "1 test collected")) as collect_:
            self.capture(fsm.cmd_advance, self.TASK)

        collect_.assert_called_once()
        self.assertEqual(self.state(), "in_dev")

    def test_ac4_collect_is_not_called_before_traceability_passes(self):
        """Трассируемость AC не пройдена (планка вовсе не заведена) —
        сухой сбор не звался.

        Ловит мутацию: сухой сбор вызывается безусловно, раньше проверки
        трассируемости — `collect_.assert_not_called()` падает на
        несобранной, заведомо неполной планке."""
        self.enter_tests_writing()

        with mock.patch.object(acceptance, "collect") as collect_:
            out = self.capture(fsm.cmd_advance, self.TASK)

        collect_.assert_not_called()
        self.assertEqual(self.state(), "tests_writing")
        self.assertIn("AC-1", out)

    def test_ac5_failed_collect_blocks_the_transition(self):
        """Красный сухой сбор — задача остаётся в `tests_writing`, в
        журнал уходит запись «переход отклонён: планка не собирается» с
        хвостом вывода pytest, печатается подсказка.

        Ловит мутацию: отказ сухого сбора только печатается, но не
        останавливает переход — `self.state()` остался бы `in_dev`
        вместо `tests_writing`."""
        self.enter_tests_writing()
        self.write_plank()
        tail = "ModuleNotFoundError: No module named 'nope_unit'"

        with mock.patch.object(acceptance, "collect", return_value=(False, tail)):
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "tests_writing")
        self.assertIn(tail, out)
        self.assertIn(
            f"дальше: почини импорт/синтаксис планки и повтори "
            f"artel.py advance {self.TASK}", out)

    def test_ac5_failed_collect_does_not_set_the_lock(self):
        """`tests_locked_sha` не переставляется на отказе сухого сбора.

        Ловит мутацию: лок выполняется до/независимо от исхода `collect`
        — сентинельное значение было бы затёрто вычисленным."""
        self.enter_tests_writing()
        self.write_plank()
        conn = store.db()
        conn.execute("UPDATE tasks SET tests_locked_sha=? WHERE id=?",
                     ("sentinel-unit", self.TASK))
        conn.commit()

        with mock.patch.object(acceptance, "collect",
                               return_value=(False, "хвост")):
            self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["tests_locked_sha"], "sentinel-unit")


class StrayPlankFilesGateTest(_DryCollectSandbox):
    """AC-8: посторонние файлы планки как последняя запись визита."""

    def test_ac8_stray_files_as_the_last_entry_block_the_transition(self):
        """Планка полностью валидна, но последняя запись журнала визита
        `tests_writing` — «посторонние файлы в каталоге планки» —
        переход отклонён, текст называет отброшенные файлы поимённо.

        Ловит мутацию: гейт AC-8 не читает журнал вовсе (либо не
        трактует эту запись как отказ) — переход прошёл бы в `in_dev`
        несмотря на файлы, отброшенные автокоммитом этого же шага."""
        self.enter_tests_writing()
        self.write_plank()
        self.journal_stray_files(["fixtures.json", "helpers/util.py"])

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "tests_writing")
        self.assertIn("планка ссылается на отброшенные файлы", out)
        self.assertIn("fixtures.json", out)
        self.assertIn("helpers/util.py", out)

    def test_ac8_superseded_stray_entry_no_longer_blocks(self):
        """Запись «посторонние файлы...» НЕ последняя (за ней — более
        поздняя активность визита) — переход больше не блокируется ею.

        Ловит мутацию: гейт ищет «была ли КОГДА-ЛИБО такая запись с
        начала визита» вместо «остаётся ли она ПОСЛЕДНЕЙ» — устаревшая
        запись продолжала бы блокировать переход бесконечно."""
        self.enter_tests_writing()
        self.write_plank()
        self.journal_stray_files(["fixtures.json"])
        store.journal(store.db(), self.TASK, "operator", "заметка Оператора",
                      "файл поправлен, шаг test_author повторён")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")

    def test_ac9_stray_files_gate_runs_before_dry_collect(self):
        """Гейт AC-8 срабатывает ДО сухого сбора: реальный субпроцесс
        pytest не запускается, если планка уже отклонена посторонними
        файлами — диагностика точнее общей ошибки импорта.

        Ловит мутацию: порядок гейтов внутри `tests_writing` меняется
        местами — `collect` был бы позван на планке, заведомо
        отклонённой предыдущим гейтом."""
        self.enter_tests_writing()
        self.write_plank()
        self.journal_stray_files(["fixtures.json"])

        with mock.patch.object(acceptance, "collect") as collect_:
            self.capture(fsm.cmd_advance, self.TASK)

        collect_.assert_not_called()


if __name__ == "__main__":
    unittest.main()
