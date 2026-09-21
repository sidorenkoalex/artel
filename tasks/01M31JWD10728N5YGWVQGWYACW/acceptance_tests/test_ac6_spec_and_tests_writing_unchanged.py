"""Приёмочные тесты 01M31JWD10728N5YGWVQGWYACW — AC-6: эскалации
`spec_writing` (батч `QUESTIONS.md`) и `tests_writing` (пометка
`AC-n: escalate` в планке) после правки ведут себя как прежде — маркер
пишется там же (отдельной записью сразу после `state -> escalated`) и так
же (тот же `action`, `detail` самой эскалации).

Зелёный с рождения: обе точки эскалации уже метят себя маркером (SPEC
01M2XFSJ1Z7BS6HR69SAT1D81Y, требования 1-2) — критерий фиксирует
СОХРАНЕНИЕ этого поведения при добавлении третьей точки, а не появление
нового.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ReviewEscalationSandbox  # noqa: E402
from orchestrator import fsm  # noqa: E402


class SpecAndTestsWritingEscalationsUnchangedTest(ReviewEscalationSandbox):

    def assert_marker_stands_right_after_the_escalation(self) -> None:
        """Общая сверка обеих точек: отдельная запись маркера сразу за
        `state -> escalated`, тот же `action`, `detail` самой эскалации."""
        marker_index = self.marker_index()
        escalated_index = self.index_of_last("state -> escalated")
        rows = self.rows()

        self.assertEqual(
            marker_index, escalated_index + 1,
            "запись маркера стоит не непосредственно после "
            "state -> escalated")
        self.assertEqual(rows[marker_index]["action"],
                         fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER)
        self.assertEqual(
            rows[marker_index]["detail"], rows[escalated_index]["detail"],
            "detail маркера разошёлся с detail самой эскалации")

    def test_ac6_tests_writing_escalation_still_marks_the_journal(self):
        """Пометка `AC-n: escalate` в планке уводит задачу из
        `tests_writing` в `escalated`, и маркер стоит там же и таким же,
        каким был до правки.

        Ловит мутацию: разработчик «обобщает» три точки эскалации —
        переносит вызов `_mark_artifact_escalation` из `tests_writing`/
        `spec_writing` в одно новое место (например, только в
        `_review_escalate` или в хелпер, который зовут не все три), —
        `tests_writing` остаётся без маркера, и `marker_index()` упадёт на
        `None`.
        """
        self.escalate_tests_writing()

        self.assertEqual(self.state(), "escalated",
                         "пометка escalate обязана эскалировать задачу — "
                         "сценарий не воспроизведён")
        self.assert_marker_stands_right_after_the_escalation()

    def test_ac6_spec_writing_escalation_still_marks_the_journal(self):
        """Батч `QUESTIONS.md` уводит задачу из `spec_writing` в
        `escalated`, и маркер стоит там же и таким же, каким был до
        правки.

        Ловит мутацию: та же «общая» переделка трёх точек задевает ветку
        батча `spec_writing` (у неё два пути — с ветки-источника и с
        диска), и маркер теряется на одном из них: `marker_index()` упадёт
        на `None`.
        """
        self.escalate_spec_writing()

        self.assertEqual(self.state(), "escalated",
                         "батч QUESTIONS.md обязан эскалировать задачу — "
                         "сценарий не воспроизведён")
        self.assert_marker_stands_right_after_the_escalation()


if __name__ == "__main__":
    unittest.main()
