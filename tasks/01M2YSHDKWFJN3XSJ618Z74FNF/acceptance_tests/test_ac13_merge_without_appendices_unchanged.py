"""AC-13 (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF): PLAN без приложений — мерж
идёт прежним путём (ни коммита приложений, ни полного прогона, ни записи
журнала о приложениях), а четыре названных существующих набора тестов
остаются зелёными без правок.

Зелёный с рождения: оба теста этого файла фиксируют СЕГОДНЯШНЕЕ поведение — мерж без приложений и четыре названных набора; красным их делает регрессия реализации (безусловный коммит приложений, безусловный полный прогон, сломанный соседний узел гейта мержа), а не отсутствие кода задачи.

Провалидировано стабом (решение Оператора 03.09): со временным
применением приложений в теле гейта мержа оба теста файла остаются
зелёными — то есть «прежний путь» и правда не задет механикой
приложений, а не просто ещё не написан; стаб удалён, репозиторий не
тронут.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

from tests import (test_fsm_merge_gate_done_snapshot,  # noqa: E402
                   test_fsm_merge_gate_scratch_worktree_cleanup,
                   test_merge_gate_ci_wait, test_protected_paths_gate)


class MergeWithoutAppendicesTest(_sandbox.MergeAppendixSandbox):

    def test_ac13_merge_without_appendices_leaves_no_appendix_trace(self):
        """PLAN без разделов «## Приложение»: мерж доходит до `done`, в
        main origin нет коммита приложений, `acceptance.run_full_suite` не
        звался ни разу, в журнале задачи нет записи о применённых
        приложениях.

        Ловит мутацию: применение приложений встроено в тело гейта
        безусловно (пустой список приложений всё равно даёт коммит
        `git commit --allow-empty` либо запись журнала) или полный
        прогон запускается для любой задачи — тогда КАЖДЫЙ мерж артели
        платил бы за механику, которой не пользовался: `full_suite_calls`
        окажется непустым, а перечень сообщений коммитов main — с лишним
        коммитом.
        """
        self.commit_plan()

        outcome = self.approve()

        self.assertEqual(outcome, ("done",))
        self.assertEqual(self.state(), "done")
        subjects = self.origin_main_subjects()
        self.assertTrue(subjects, "main origin не продвинулся вовсе")
        self.assertEqual(
            [s for s in subjects if _sandbox.APPLIED_COMMIT_MARK in s], [],
            f"в main origin есть коммит приложений там, где приложений "
            f"не было: {subjects}")
        self.assertEqual(
            self.full_suite_calls, [],
            "полный прогон запущен для задачи без приложений")
        self.assertNotIn(_sandbox.APPLIED_JOURNAL_MARK, self.journal_blob())


class NamedExistingSuitesStayGreenTest(unittest.TestCase):

    def test_ac13_four_named_suites_pass_as_whole_modules(self):
        """Четыре названных в AC-13 набора (`tests/
        test_protected_paths_gate.py`, `tests/test_merge_gate_ci_wait.py`,
        `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/
        test_fsm_merge_gate_scratch_worktree_cleanup.py`) собираются в
        один `unittest.TestSuite` и прогоняются целиком.

        Ловит мутацию: применение приложений вставлено в тело гейта так,
        что ломает соседние существующие свойства — например
        `_publish_merge_artifacts` теряет возврат `final_sha` (тогда
        `test_fsm_merge_gate_done_snapshot` не доводит задачу до `done`)
        либо scratch-дерево перестаёт убираться на пути отказа
        (`test_fsm_merge_gate_scratch_worktree_cleanup`). Любой такой
        случай делает `wasSuccessful()` ложным, и тест покраснеет с
        перечнем упавших имён.
        """
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for module in (test_protected_paths_gate, test_merge_gate_ci_wait,
                       test_fsm_merge_gate_done_snapshot,
                       test_fsm_merge_gate_scratch_worktree_cleanup):
            suite.addTests(loader.loadTestsFromModule(module))

        result = unittest.TextTestRunner(verbosity=0,
                                         stream=io.StringIO()).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            f"{len(result.failures)} провалов, {len(result.errors)} ошибок "
            f"в названных AC-13 наборах: "
            f"{[str(case) for case, _ in result.failures + result.errors]}")


if __name__ == "__main__":
    unittest.main()
