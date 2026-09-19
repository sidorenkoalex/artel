"""Приёмочные тесты 01M2XFSJ1Z7BS6HR69SAT1D81Y — AC-1, AC-2: эскалация,
поднятая СОДЕРЖИМЫМ артефакта роли, оставляет в журнале задачи отдельную
запись-маркер «ответ Оператора должен дойти до роли» — непосредственно
после записи `state -> escalated` этой эскалации и до любой записи
возврата Оператора; у обеих точек эскалации (`tests_writing` по пометке
`AC-n: escalate`, `spec_writing` по батчу `QUESTIONS.md`) это ОДНА и та
же запись.

Красен до реализации: ни `fsm_advance.tests_writing`, ни
`fsm_advance.spec_writing` сегодня не журналируют после своего
`store.set_state(..., "escalated", ...)` ничего вовсе — следующей записью
журнала оказывается уже возврат Оператора (`state -> tests_writing`/
`state -> spec_writing` из `fsm._approve_escalated`), и
`_sandbox.escalation_marker_index` честно возвращает `None`: оба теста
падают на `assertIsNotNone` внутри `marker_index()`.

Текст `action` маркера здесь не зашит литералом: его значение выбирает
реализация (SPEC «Оценка объёма и деление» — место общей константы решает
разработчик, `orchestrator/pull.py::PULL_CONFLICT_ROLE_STEP_MARKER` не
переносится и не переиспользуется как значение). Проверяется то, что
описывают критерии: запись есть, стоит на названной позиции и одинакова
для обеих точек эскалации.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import EscalationByArtifactSandbox  # noqa: E402


class TestsWritingEscalationLeavesTheMarkerTest(EscalationByArtifactSandbox):
    """AC-1: эскалация `tests_writing` по пометке `AC-n: escalate`."""

    def test_ac1_tests_writing_escalation_marks_the_journal_before_the_return(self):
        """Планка с пометкой `escalate` уводит задачу в `escalated`; сразу
        за записью `state -> escalated` в журнале стоит отдельная запись
        маркера, и она появляется РАНЬШЕ записи возврата Оператора,
        сделанной последующим `approve`.

        Ловит мутацию: маркер журналируется не в точке эскалации, а в
        точке возврата (`fsm._approve_escalated`) — тогда сразу за
        `state -> escalated` идёт уже сама запись возврата, `marker_row()`
        отсеет её по префиксу `state -> ` и вернёт `None`, а `assertLess`
        порядка не выполнится даже при появившейся позже записи.
        """
        self.escalate_tests_writing()
        self.assertEqual(
            self.state(), "escalated",
            "пометка escalate в планке обязана эскалировать задачу — "
            "сценарий не воспроизведён")

        marker_index = self.marker_index()
        escalated_index = self.index_of_last("state -> escalated")
        self.assertEqual(
            marker_index, escalated_index + 1,
            "запись маркера стоит не непосредственно после "
            "state -> escalated")

        self.answer_and_approve()
        self.assertEqual(
            self.state(), "tests_writing",
            "approve не вернул задачу в tests_writing — сценарий не "
            "воспроизведён")

        return_index = self.index_of_last("state -> tests_writing")
        self.assertLess(
            marker_index, return_index,
            "запись маркера оказалась не раньше записи возврата Оператора")


class SpecWritingEscalationLeavesTheSameMarkerTest(EscalationByArtifactSandbox):
    """AC-2: эскалация `spec_writing` по наличию `QUESTIONS.md` — та же
    запись маркера, тот же порядок."""

    def test_ac2_spec_writing_escalation_marks_the_journal_the_same_way(self):
        """Батч вопросов уводит задачу в `escalated`, маркер стоит сразу за
        `state -> escalated` и до возврата; затем та же задача проходит
        эскалацию `tests_writing` по пометке — текст `action` маркера у
        обеих точек эскалации совпадает.

        Ловит мутацию: маркер заведён только в обработчике
        `fsm_advance.tests_writing` (требование 1), а ветка батча
        `QUESTIONS.md` в `fsm_advance.spec_writing` осталась нетронутой —
        `marker_action()` первой половины теста упадёт на `None`; вариант
        мутации «в spec_writing журналируется СВОЙ, другой текст» ловит
        `assertEqual` двух значений в конце.
        """
        self.escalate_spec_writing()
        self.assertEqual(
            self.state(), "escalated",
            "батч QUESTIONS.md обязан эскалировать задачу — сценарий не "
            "воспроизведён")

        spec_marker = self.marker_action()
        spec_marker_index = self.marker_index()
        self.assertEqual(
            spec_marker_index, self.index_of_last("state -> escalated") + 1,
            "запись маркера стоит не непосредственно после "
            "state -> escalated")

        self.answer_and_approve()
        self.assertEqual(
            self.state(), "spec_writing",
            "approve не вернул задачу в spec_writing — сценарий не "
            "воспроизведён")
        self.assertLess(
            spec_marker_index, self.index_of_last("state -> spec_writing"),
            "запись маркера оказалась не раньше записи возврата Оператора")

        # Вторая точка эскалации той же задачи: батч снят ролью, планка
        # несёт пометку escalate — сверяем текст маркера между двумя
        # точками, не с литералом.
        self.remove_questions()
        self.escalate_tests_writing()
        self.assertEqual(self.state(), "escalated")

        self.assertEqual(
            self.marker_action(), spec_marker,
            "эскалация spec_writing метит задачу не тем же маркером, что "
            "эскалация tests_writing")


if __name__ == "__main__":
    unittest.main()
