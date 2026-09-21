"""Приёмочный тест 01M31JWD10728N5YGWVQGWYACW — AC-4: сценарий 21.09
(задача 01M31DRD81) воспроизводится журналом задачи в песочнице.

Журнал инцидента посеян дословно по порядку записей: возврат из ревью с
замечаниями (`state -> in_dev | замечания ревью, итерация 1`), отработанный
шаг developer, `state -> verifying`, `state -> review` — и уже поверх него
настоящая эскалация ревьювера, ответ Оператора, `approve` и `auto`. Именно
тот отработанный ДО эскалации шаг developer инцидент засчитывал вместо шага
после ответа: анкером рубежа оставалась запись `state -> in_dev` ДО
эскалации, а запись возврата пропускалась как `_ESCALATED_RETURN_DETAILS`.

Красен до реализации: без маркера эскалации ревьювера
`auto._role_step_since_state_entry` находит анкером именно посеянную
запись `state -> in_dev | замечания ревью, итерация 1`, видит после неё
`agent run finished` роли developer и отвечает «шаг был» — гейт переделки
пропускает предварительный advance, готовый PLAN.md уводит задачу
`in_dev -> verifying` (та самая пара записей 08:52:09/08:52:22), и роль не
зовётся: `assertIn`/`index_of_first_role_step` ниже падают.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (PRE_ADVANCE_NOTE,  # noqa: E402
                      REVIEW_RETURN_DETAIL, ReviewEscalationSandbox,
                      agent_run_finished_actors)
from orchestrator import auto, store  # noqa: E402


class Incident2109ReplayTest(ReviewEscalationSandbox):

    def test_ac4_the_counted_developer_step_before_the_escalation_no_longer_counts(self):
        """Полный журнал 21.09: шаг developer уже был ДО эскалации
        ревьювера — после ответа Оператора и `approve` рубеж переделки
        обязан держать на записи возврата, а не на более раннем анкере.
        Цикл `auto` даёт шаг developer, а `in_dev -> verifying` случается
        только после него.

        Ловит мутацию: маркер эскалации ревьювера написан, но погашен
        раньше времени — например, вызван до `state -> escalated` либо
        `_review_escalate` метит задачу своим собственным текстом, которого
        нет в `auto._ROLE_STEP_REQUIRED_MARKERS` — анкером снова станет
        посеянная запись «замечания ревью, итерация 1», шаг developer до
        эскалации снова засчитается, и цикл уведёт задачу в `verifying`
        без роли.
        """
        self.write_plan("ready")
        self.seed_developer_step_before_the_escalation()

        self.escalate_from_review()
        self.assertEqual(self.state(), "escalated",
                         "сценарий не воспроизведён: вердикт не эскалировал")

        self.answer_and_approve()
        self.assertEqual(self.state(), "in_dev",
                         "сценарий не воспроизведён: approve не вернул "
                         "задачу в in_dev")
        return_index = self.index_of_last("state -> in_dev")

        conn = store.db()
        ran, anchor_detail = auto._role_step_since_state_entry(
            conn, self.TASK, "in_dev", "developer")
        self.assertFalse(
            ran, "шаг developer, отработанный ДО эскалации ревьювера, "
            "снова засчитан за отработанный возврат")
        self.assertNotEqual(
            anchor_detail, REVIEW_RETURN_DETAIL,
            "анкером рубежа осталась запись возврата из ревью, более "
            "ранняя, чем возврат из эскалации")

        self.agent.script = [lambda: None]
        self.auto()

        actors = agent_run_finished_actors(conn, self.TASK)
        self.assertEqual(
            actors[1:2], ["developer"],
            "после возврата из эскалации developer не получил шага — "
            "цикл продвинул задачу по готовым артефактам")
        self.assert_role_runs_before_any_pre_advance(return_index, "developer")
        self.assertIn(
            PRE_ADVANCE_NOTE.format(role="developer"), self.actions(),
            "после шага developer цикл так и не прошёл рубеж "
            "in_dev -> verifying предварительным advance — сценарий "
            "воспроизведён не до конца")
        self.assertLess(
            self.index_of_first_role_step("developer", return_index),
            self.index_of_last("state -> verifying"),
            "переход in_dev -> verifying случился раньше шага developer")


if __name__ == "__main__":
    unittest.main()
