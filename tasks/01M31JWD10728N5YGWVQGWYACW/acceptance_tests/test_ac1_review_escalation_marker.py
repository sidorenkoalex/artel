"""Приёмочный тест 01M31JWD10728N5YGWVQGWYACW — AC-1: эскалация ревьювера
(`REVIEW.md status: escalate`) оставляет в журнале задачи маркер «ответ
Оператора должен дойти до роли» отдельной записью непосредственно после
записи `state -> escalated` — тем же вызовом `_mark_artifact_escalation`,
что и эскалации `spec_writing`/`tests_writing` (то есть той же записью
`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` с `detail` самой эскалации).

Красен до реализации: `orchestrator/fsm_advance.py::_review_escalate`
после своего `store.set_state(..., "escalated", ..., detail="эскалация от
ревьювера")` не журналирует ничего вовсе — следующей записью журнала
оказывается уже возврат Оператора, `_sandbox.escalation_marker_index`
честно возвращает `None`, и тест падает на `assertIsNotNone` внутри
`marker_index()`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ReviewEscalationSandbox  # noqa: E402
from orchestrator import fsm  # noqa: E402


class ReviewEscalationLeavesTheMarkerTest(ReviewEscalationSandbox):

    def test_ac1_review_escalation_marks_the_journal_right_after_escalated(self):
        """Вердикт `escalate` уводит задачу из `review` в `escalated`; сразу
        за записью `state -> escalated` стоит отдельная запись маркера
        `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` с тем же `detail`, что у
        самой эскалации (подпись вызова `_mark_artifact_escalation`), и она
        появляется РАНЬШЕ записи возврата Оператора, сделанной последующим
        `approve`.

        Ловит мутацию: `_mark_artifact_escalation` вызван в
        `_review_escalate` ДО `store.set_state` (порядок строк перепутан) —
        маркер окажется перед записью `state -> escalated`, сразу за ней
        пойдёт уже возврат Оператора, и `marker_index()` упадёт на `None`;
        `auto._role_step_since_state_entry` такой маркер тоже не прочитал
        бы (он гасится первой же записью `state -> {state}`).
        """
        self.escalate_from_review()
        self.assertEqual(
            self.state(), "escalated",
            "вердикт escalate обязан эскалировать задачу — сценарий не "
            "воспроизведён")

        marker_index = self.marker_index()
        escalated_index = self.index_of_last("state -> escalated")
        self.assertEqual(
            marker_index, escalated_index + 1,
            "запись маркера стоит не непосредственно после "
            "state -> escalated")

        rows = self.rows()
        self.assertEqual(
            rows[marker_index]["action"],
            fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER,
            "эскалация ревьювера метит журнал не тем маркером, которым "
            "метят себя эскалации spec_writing/tests_writing — рубеж "
            "переделки (auto._ROLE_STEP_REQUIRED_MARKERS) его не прочитает")
        self.assertEqual(
            rows[marker_index]["detail"], rows[escalated_index]["detail"],
            "detail маркера не совпадает с detail самой эскалации — "
            "_mark_artifact_escalation вызвана не с текстом эскалации")

        self.answer_and_approve()
        self.assertEqual(
            self.state(), "in_dev",
            "approve не вернул задачу в in_dev — сценарий не воспроизведён")
        self.assertLess(
            marker_index, self.index_of_last("state -> in_dev"),
            "запись маркера оказалась не раньше записи возврата Оператора")


if __name__ == "__main__":
    unittest.main()
