"""Приёмочный тест 01M31JWD10728N5YGWVQGWYACW — AC-7: точка возврата
эскалации ревьювера остаётся `in_dev`, а не `review`: сама эскалация
по-прежнему не выставляет `escalated_from`, и `approve` возвращает задачу
в `in_dev`.

Зелёный с рождения: так задача возвращается и сегодня (`fsm.py::
_approve_escalated`: `back = t["escalated_from"] or "in_dev"`) — критерий
фиксирует границу правки (SPEC «Не входит»: изменение точки возврата в
задачу не входит), а не новое поведение.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ReviewEscalationSandbox  # noqa: E402
from orchestrator import store  # noqa: E402


class ReviewEscalationReturnsToInDevTest(ReviewEscalationSandbox):

    def test_ac7_review_escalation_keeps_escalated_from_empty_and_returns_to_in_dev(self):
        """После эскалации ревьювера `escalated_from` задачи пуст, а
        `approve` после ответа Оператора приводит её в `in_dev`, не в
        `review`.

        Ловит мутацию: разработчик добивается обязательного шага роли не
        маркером, а точкой возврата — дописывает `escalated_from="review"`
        в `_review_escalate` (альтернатива из копилки, отвергнутая
        требованием 3 SPEC): поле перестанет быть пустым, и `approve`
        вернёт задачу в `review`, где её ждёт reviewer, а не developer с
        ANSWER в брифе.
        """
        self.escalate_from_review()
        self.assertEqual(self.state(), "escalated",
                         "сценарий не воспроизведён: вердикт не эскалировал")

        task = store.get_task(store.db(), self.TASK)
        self.assertIsNone(
            task["escalated_from"],
            "эскалация ревьювера выставила escalated_from — точка возврата "
            "изменена, чего SPEC не разрешает")

        self.answer_and_approve()

        self.assertEqual(
            self.state(), "in_dev",
            "возврат из эскалации ревьювера привёл задачу не в in_dev")


if __name__ == "__main__":
    unittest.main()
