"""AC-4 (tasks/T075/SPEC.md): для той же задачи после создания
`ANSWER-n.md` (AC-2) `approve` переводит задачу дальше по ПРЕЖНЕЙ
адресации возврата: эскалация из `spec_writing` — в `spec_writing`;
эскалация из `tests_writing` или `review` — в состояние, из которого она
пришла, либо в `in_dev`, если эскалация не зафиксировала исходное
состояние (как сейчас).

«Как сейчас» — буквально сегодняшняя адресация `orchestrator/fsm.py`
(строки 1140-1150, `back = t["escalated_from"] or "in_dev"`): AC-4 не
просит менять, КУДА возвращается каждый класс — только то, что теперь
это происходит ПОСЛЕ появления ANSWER-n.md, а не сразу («Не входит»
SPEC: «Изменение механики самих эскалаций... не входит»). Сегодня
`escalated_from` == "tests_writing" для маркера `AC-n: escalate`
(fsm.py:763), поэтому tests_writing-сценарий возвращается в
`tests_writing`; для вердикта REVIEW.md `status: escalate`
`escalated_from` НЕ выставляется (fsm.py:746-748) — review-сценарий
возвращается в `in_dev`, тот же фолбэк, что и для эскалаций-«лимитов».

Красен до реализации: с новой (ещё не написанной) проверкой ANSWER-n.md
(AC-3) approve обязан начать ОТКАЗЫВАТЬ там, где сегодня он молча
проходит без вопроса — тесты здесь чинят это состояние: как только
разработчик добавит гейт AC-3, `write_answer()` перед вызовом
`cmd_approve` обязана снять этот отказ и восстановить сегодняшний
результат перехода. Сегодня (без гейта) эти тесты уже проходят —
`AnswerGateTmpRootTest`/маркер модуля предупреждает: они станут
регрессионным барьером ПОСЛЕ AC-3, не только тестом AC-4 (тот же приём,
что `tasks/T051/acceptance_tests/test_ac4_not_behind_transition_unchanged.py`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402

from _sandbox import AnswerGateTmpRootTest  # noqa: E402


class SpecWritingQuestionsWithAnswerReturnsToSpecWritingTest(AnswerGateTmpRootTest):

    def test_ac4_approve_with_answer_returns_to_spec_writing(self):
        self.escalate_from_spec_writing_questions()
        self.write_answer(1)

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "spec_writing",
            "эскалация из spec_writing обязана вернуться в spec_writing "
            "после появления ANSWER-n.md (SPEC AC-4)")
        self.assertIsNone(
            self.row()["escalated_from"],
            "адресация возврата сброшена, как и до этой задачи")


class TestsWritingAcMarkerWithAnswerReturnsToTestsWritingTest(AnswerGateTmpRootTest):

    def test_ac4_approve_with_answer_returns_to_tests_writing(self):
        self.escalate_from_tests_writing_ac_marker()
        self.write_answer(1)

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "tests_writing",
            "эскалация из tests_writing (escalated_from == 'tests_writing', "
            "fsm.py:763) обязана вернуться в tests_writing после появления "
            "ANSWER-n.md — прежняя адресация не меняется (SPEC AC-4)")


class ReviewEscalateVerdictWithAnswerReturnsToInDevTest(AnswerGateTmpRootTest):

    def test_ac4_approve_with_answer_returns_to_in_dev(self):
        self.escalate_from_review_verdict()
        self.write_answer(1)

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "in_dev",
            "вердикт REVIEW.md status: escalate не фиксирует "
            "escalated_from (fsm.py:746-748) — прежняя адресация "
            "возврата — фолбэк in_dev, ANSWER-n.md её не меняет (SPEC "
            "AC-4, «как сейчас»)")


if __name__ == "__main__":
    unittest.main()
