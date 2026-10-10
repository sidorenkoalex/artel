"""Юнит-тесты разбора журнала гейта неотработанного ANSWER на рубеже
`in_dev -> verifying` (`orchestrator/advance_gates/review.py::
_unprocessed_answer`, SPEC 01M4KAYMW2YRFB7G0442WFVSHA, требования 1, 4, 5):
свойства, которых не касаются долгоживущие тесты задачи — шаг developer,
шедший в момент ANSWER, и коммит пульта за developer как признак шага.
"""
import unittest
from unittest import mock

from orchestrator.advance_gates import refusal_classes, review

TASK = "01M0000000000000000000TEST"


def row(actor: str, action: str, detail: str = "") -> dict:
    return {"actor": actor, "action": action, "detail": detail}


def answer(n: int) -> dict:
    return row("operator", "ANSWER создан: указание Оператора",
               f"tasks/{TASK}/ANSWER-{n}.md")


STARTED = row("developer", "agent run started")
FINISHED = row("developer", "agent run finished", "rc=0")
PULT_COMMIT = row("orchestrator", "код закоммичен пультом за роль", "a.py (sha 1)")


class UnprocessedAnswerTest(unittest.TestCase):

    def gate(self, rows: list):
        with mock.patch.object(review.store, "task_steps", return_value=rows), \
                mock.patch.object(review.cycle_hint, "launch_text",
                                  return_value="подсказка"):
            return review._answer_gate(None, TASK)

    def test_step_running_when_answer_was_given_does_not_process_it(self):
        """Шаг developer, начатый до ANSWER и завершённый после, ANSWER не отрабатывает: отказ называет его.

        Ловит мутацию: гейт сравнивает ANSWER с завершением шага, а не с его
        стартом — указание, данное поверх идущего шага (без lease), считается
        отработанным, хотя бриф шага собран до него, и задача уходит в CI.
        """
        refusal = self.gate([STARTED, answer(1), FINISHED])
        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.action,
                         refusal_classes.ANSWER_UNPROCESSED_REFUSAL_ACTION)
        self.assertIn("ANSWER-1.md", refusal.detail)
        self.assertIsNone(self.gate([STARTED, answer(1), FINISHED,
                                     STARTED, FINISHED]))

    def test_pult_commit_for_developer_counts_as_finished_step(self):
        """Коммит кода пультом за developer после ANSWER — шаг developer завершён, отказа нет; тот же коммит идущего в момент ANSWER шага — отказ.

        Ловит мутацию: запись `код закоммичен пультом за роль` не
        засчитывается признаком шага — либо засчитывается и для шага, шедшего
        в момент ANSWER (отказа на `[старт, ANSWER, коммит пульта]` нет).
        """
        self.assertIsNone(self.gate([answer(1), PULT_COMMIT]))
        self.assertIsNotNone(self.gate([STARTED, answer(1), PULT_COMMIT]))

    def test_refusal_names_the_latest_unprocessed_answer(self):
        """Два ANSWER после шага — отказ называет последний; ANSWER до шага отработан.

        Ловит мутацию: гейт запоминает первый неотработанный ANSWER, а не
        последний, — текст отказа называет ANSWER-2.md вместо ANSWER-3.md.
        """
        refusal = self.gate([answer(1), STARTED, FINISHED, answer(2), answer(3)])
        self.assertIn("ANSWER-3.md", refusal.detail)
        self.assertNotIn("ANSWER-2.md", refusal.detail)
        self.assertIsNone(self.gate([answer(1), STARTED, FINISHED]))


class AnswerRefusalClassTest(unittest.TestCase):

    def test_answer_refusal_is_role_class_with_repeat_stop(self):
        """Действие отказа — «чинит роль» и вне подкласса «роль ещё не закончила».

        Ловит мутацию: действие внесено в `ROLE_NOT_FINISHED_REFUSAL_ACTIONS`
        — повтор того же отказа после шага developer не останавливает `auto`
        (требование 5).
        """
        action = refusal_classes.ANSWER_UNPROCESSED_REFUSAL_ACTION
        self.assertEqual(refusal_classes.refusal_class(action),
                         refusal_classes.ROLE_FIXES)
        self.assertNotIn(action, refusal_classes.ROLE_NOT_FINISHED_REFUSAL_ACTIONS)


if __name__ == "__main__":
    unittest.main()
