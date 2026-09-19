"""Приёмочные тесты 01M2XFSJ1Z7BS6HR69SAT1D81Y — AC-3, AC-4: сценарий
инцидента 13.09 сквозь цикл `auto`, обе точки эскалации по содержимому
артефакта роли. Эскалация → ответ Оператора → `approve` → `auto`: роль
состояния (`test_author` для `tests_writing`, `analyst` для
`spec_writing`) получает шаг, предварительный advance не повторяет ту же
самую, уже отвеченную эскалацию до него, и следующий `approve` не требует
второго ANSWER.

Красен до реализации: `auto._pre_advance_step` зовёт `fsm.cmd_advance`
первым же действием итерации, а гейт переделки `auto._rework_gate_blocks`
на этом возврате не держит — запись возврата несёт общий текст
`fsm._approve_escalated` («эскалация разрешена, продолжаем»), входящий в
`auto._ESCALATED_RETURN_DETAILS` и пропускаемый при поиске анкера (а для
первого захода в `spec_writing` записи `state -> spec_writing` нет вовсе).
Рубеж вырождается в «сверять нечем», `fsm_advance.tests_writing`/
`fsm_advance.spec_writing` перечитывают ту же пометку/тот же батч и уводят
задачу в `escalated` за 0 секунд: `cmd_run` не вызывается ни разу, роль в
журнале не появляется, а поднятый второй раз `answer_baseline` заставляет
следующий `approve` требовать ANSWER-2 — ровно то, что оба теста ниже
запрещают.

Канал «ANSWER в брифе» (AC-3) отдельно не проверяется: бриф роли этой
задачей не меняется (SPEC «Не входит» — механика T075 уже существует),
предметом критерия остаётся сам факт запуска роли до повторной эскалации.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (EscalationByArtifactSandbox,  # noqa: E402
                      agent_run_finished_actors)
from orchestrator import fsm, store  # noqa: E402

# Текст, которым `auto._pre_advance_step` отмечает «переход выполнен без
# шага роли» — буквальная формулировка AC-3/AC-4.
PRE_ADVANCE_NOTE = "шаг {role} не нужен: переход выполнен по готовым артефактам"


class _ReturnFromEscalationTest(EscalationByArtifactSandbox):
    """Общая проверка окна «между возвратом и первым шагом роли»: там не
    должно быть ни заметки пред-advance, ни новой записи
    `state -> escalated`."""

    def assert_no_repeat_escalation_before_the_role_step(
            self, return_index: int, role: str) -> None:
        window = self.rows()[return_index + 1:
                             self.index_of_first_role_step(role)]
        note = PRE_ADVANCE_NOTE.format(role=role)
        self.assertNotIn(
            note, [r["action"] for r in window],
            f"между возвратом Оператора и шагом роли {role} цикл auto "
            f"успел продвинуть задачу предварительным advance")
        self.assertNotIn(
            "state -> escalated", [r["action"] for r in window],
            f"между возвратом Оператора и шагом роли {role} задача снова "
            f"ушла в escalated — та же эскалация повторилась до роли")

    def assert_approve_does_not_demand_a_second_answer(self) -> None:
        """`approve` после возврата не требует ещё одного ANSWER: ни в
        выводе, ни в журнале нет отказа «не хватает ANSWER-<n+1>»."""
        expected_next = f"ANSWER-{self.answer_count() + 1}"
        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertNotIn(
            expected_next, out,
            f"approve после возврата потребовал {expected_next} — значит "
            f"answer_baseline подняла повторная эскалация")
        self.assertNotIn(
            "approve отклонён: нет ANSWER",
            [r["action"] for r in self.rows()],
            "в журнале есть отказ approve по отсутствию ANSWER — возврат "
            "из эскалации обошёлся Оператору вторым ответом")


class IncidentScenarioForTestsWritingTest(_ReturnFromEscalationTest):
    """AC-3: инцидент 13.09 дословно — эскалация `tests_writing` по
    пометке `AC-n: escalate`."""

    def test_ac3_auto_runs_test_author_instead_of_repeating_the_escalation(self):
        """Планка с пометкой `escalate` эскалирует задачу, Оператор
        отвечает и возвращает её через `approve`, затем зовёт `auto`: шаг
        test_author обязан состояться (роль снимает пометку, получив
        ответ), повторной эскалации по той же пометке до его шага быть не
        должно, а следующий `approve` не должен требовать второго ANSWER.

        Ловит мутацию: маркер эскалации журналируется, но
        `auto._role_step_since_state_entry` его не читает (запись возврата
        по-прежнему пропускается как `_ESCALATED_RETURN_DETAILS`) — рубеж
        не держит, `_pre_advance_step` перечитывает ту же пометку и
        эскалирует задачу раньше единственного вызова `cmd_run`:
        `index_of_first_role_step("test_author")` не найдёт записи вовсе.
        """
        self.escalate_tests_writing()
        self.assertEqual(self.state(), "escalated",
                         "сценарий не воспроизведён: пометка не эскалировала")

        self.answer_and_approve()
        self.assertEqual(
            self.state(), "tests_writing",
            "approve не вернул задачу в tests_writing — сценарий не "
            "воспроизведён")
        return_index = self.index_of_last("state -> tests_writing")

        # Шаг роли: получив ANSWER, test_author переписывает планку без
        # пометки escalate — так эскалация и разрешается по существу.
        self.agent.script = [lambda: self.write_plank(escalate=False)]
        self.auto()

        actors = agent_run_finished_actors(store.db(), self.TASK)
        self.assertEqual(
            actors[:1], ["test_author"],
            "первым после возврата отработал не test_author (или роль не "
            "отработала вовсе) — предварительный advance забрал ход себе")
        self.assert_no_repeat_escalation_before_the_role_step(
            return_index, "test_author")
        self.assert_approve_does_not_demand_a_second_answer()


class IncidentScenarioForSpecWritingTest(_ReturnFromEscalationTest):
    """AC-4: тот же сценарий для `spec_writing`, эскалированного батчем
    `QUESTIONS.md`."""

    def test_ac4_auto_runs_analyst_instead_of_repeating_the_stale_batch(self):
        """Батч вопросов эскалирует задачу, Оператор отвечает и возвращает
        её через `approve`, затем зовёт `auto`: шаг analyst обязан
        состояться (роль снимает отвеченный батч своим шагом), повторной
        эскалации по тому же файлу до его шага быть не должно, а следующий
        `approve` не должен требовать второго ANSWER.

        Ловит мутацию: маркер заведён и читается только для
        `tests_writing` (требование 1 сделано, требование 2 забыто) —
        `fsm_advance.spec_writing` снова эскалирует по тому же
        `QUESTIONS.md` первым же действием цикла, и `analyst` не получает
        ни одного вызова: `index_of_first_role_step("analyst")` не найдёт
        записи вовсе.
        """
        self.escalate_spec_writing()
        self.assertEqual(self.state(), "escalated",
                         "сценарий не воспроизведён: батч не эскалировал")

        self.answer_and_approve()
        self.assertEqual(
            self.state(), "spec_writing",
            "approve не вернул задачу в spec_writing — сценарий не "
            "воспроизведён")
        return_index = self.index_of_last("state -> spec_writing")

        self.agent.script = [lambda: self.remove_questions()]
        self.auto()

        actors = agent_run_finished_actors(store.db(), self.TASK)
        self.assertEqual(
            actors[:1], ["analyst"],
            "первым после возврата отработал не analyst (или роль не "
            "отработала вовсе) — предварительный advance забрал ход себе")
        self.assert_no_repeat_escalation_before_the_role_step(
            return_index, "analyst")
        self.assert_approve_does_not_demand_a_second_answer()


if __name__ == "__main__":
    unittest.main()
