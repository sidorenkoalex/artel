"""Приёмочный тест 01M31JWD10728N5YGWVQGWYACW — AC-3: бриф developer шага,
который задача получает после возврата из эскалации ревьювера, несёт
ANSWER последней эскалации.

Зелёный с рождения: канал «ANSWER-n.md последней эскалации → бриф
developer» существует до этой задачи (SPEC T075; «Не входит»:
`orchestrator/brief.py` эта задача не правит) — критерий фиксирует
СОХРАНЕНИЕ канала для шага, который AC-2 делает обязательным, а не
появление нового поведения. Проверяется исполнением: бриф собирается для
задачи, стоящей ровно в том состоянии, в котором её оставил `approve`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ANSWER_BODY, ReviewEscalationSandbox  # noqa: E402
from orchestrator import brief, runner, store  # noqa: E402


class DeveloperBriefCarriesTheAnswerTest(ReviewEscalationSandbox):

    def test_ac3_brief_of_the_step_after_the_return_carries_the_answer(self):
        """После эскалации ревьювера, ответа Оператора и `approve` роль
        шага — developer, и собранный для него бриф несёт текст ANSWER-1
        (тело ответа, не только имя файла).

        Ловит мутацию: разработчик «чинит» доставку ответа сменой точки
        возврата — возвращает задачу в `review` вместо `in_dev` (вариант
        из копилки, отвергнутый требованием 3 SPEC) — роль шага станет
        reviewer, чей бриф собирается ревью-пакетом и ANSWER не несёт:
        `step_role` вернёт не developer, а `developer_brief` для этой
        задачи перестанет быть брифом её фактического шага.
        """
        self.write_spec()
        self.write_plan("ready")
        self.escalate_from_review()
        self.answer_and_approve()

        conn = store.db()
        task = store.get_task(conn, self.TASK)
        self.assertEqual(
            runner.step_role(task), "developer",
            "шаг после возврата достаётся не developer — ANSWER поедет в "
            "бриф другой роли")

        text = brief.developer_brief(conn, self.TASK)

        self.assertIn(
            ANSWER_BODY, text,
            "бриф developer не несёт текста ANSWER последней эскалации — "
            "ответ Оператора до роли не доходит")
        self.assertIn(
            f"tasks/{self.TASK}/ANSWER-1.md", text,
            "в описи брифа нет компонента ANSWER-1.md — роль не видит, "
            "откуда взят ответ")


if __name__ == "__main__":
    unittest.main()
