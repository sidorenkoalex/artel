"""AC-3 (tasks/T075/SPEC.md): для задачи в `escalated`, эскалация которой
пришла из QUESTIONS.md (`spec_writing`), маркера `AC-n: escalate`
(`tests_writing`) или вердикта `REVIEW.md status: escalate` (`review`),
`approve` без нового `ANSWER-n.md` на ветке задачи отказывает, печатает,
какого файла не хватает, и не меняет состояние задачи.

Красен до реализации: сегодня (HEAD этой задачи) `orchestrator/fsm.py`
(ветка `elif state == "escalated":`, строки 1140-1150) возвращает задачу
из `escalated` БЕЗ какой-либо проверки на существование ANSWER-n.md —
`back = t["escalated_from"] or "in_dev"` следует сразу за входом в ветку.
Каждый тест здесь готовит ОДИН из трёх классов эскалации «вопрос роли»
существующей механикой (SPEC T025/T023/reviewer — не проверяется
заново), затем зовёт `fsm.cmd_approve` БЕЗ ANSWER-n.md и ожидает отказ;
сегодня approve вместо отказа успешно продвигает задачу — тест падает
на `assertEqual(self.state(), "escalated", ...)`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402

from _sandbox import AnswerGateTmpRootTest  # noqa: E402


class SpecWritingQuestionsWithoutAnswerRefusesTest(AnswerGateTmpRootTest):

    def test_ac3_approve_without_answer_refuses_for_questions_escalation(self):
        self.escalate_from_spec_writing_questions()

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "escalated",
            "approve без ANSWER-n.md не имеет права продвинуть задачу, "
            "эскалированную батчем QUESTIONS.md (SPEC AC-3)")
        self.assertIn(
            "ANSWER", out,
            f"отказ обязан называть, какого файла не хватает (SPEC AC-3) "
            f"— вывод: {out!r}")


class TestsWritingAcMarkerWithoutAnswerRefusesTest(AnswerGateTmpRootTest):

    def test_ac3_approve_without_answer_refuses_for_ac_escalate_marker(self):
        self.escalate_from_tests_writing_ac_marker()

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "escalated",
            "approve без ANSWER-n.md не имеет права продвинуть задачу, "
            "эскалированную маркером `AC-n: escalate` (SPEC AC-3)")
        self.assertIn(
            "ANSWER", out,
            f"отказ обязан называть, какого файла не хватает (SPEC AC-3) "
            f"— вывод: {out!r}")


class ReviewEscalateVerdictWithoutAnswerRefusesTest(AnswerGateTmpRootTest):

    def test_ac3_approve_without_answer_refuses_for_review_escalate_verdict(self):
        self.escalate_from_review_verdict()

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "escalated",
            "approve без ANSWER-n.md не имеет права продвинуть задачу, "
            "эскалированную вердиктом REVIEW.md status: escalate (SPEC "
            "AC-3)")
        self.assertIn(
            "ANSWER", out,
            f"отказ обязан называть, какого файла не хватает (SPEC AC-3) "
            f"— вывод: {out!r}")


if __name__ == "__main__":
    unittest.main()
