"""Приёмочный тест 01M31JWD10728N5YGWVQGWYACW — AC-2: сценарий «эскалация
ревьювера → `answer` → `approve` → `auto`» запускает шаг developer, а не
переводит задачу `in_dev -> verifying` по готовым артефактам.

PLAN.md задачи лежит `ready` ещё ДО эскалации — именно так выглядел
инцидент, и именно поэтому предварительный advance мог увести задачу
дальше, не позвав роль ни разу.

Красен до реализации: `auto._pre_advance_step` зовёт `fsm.cmd_advance`
первым же действием итерации, а гейт переделки `auto._rework_gate_blocks`
на этом возврате не держит — запись возврата несёт общий текст
`fsm._approve_escalated` («эскалация разрешена, продолжаем»), входящий в
`auto._ESCALATED_RETURN_DETAILS` и пропускаемый при поиске анкера, а
маркера эскалации ревьювера, который сделал бы её анкером, сегодня никто
не пишет. Рубеж вырождается в «сверять нечем», готовый PLAN.md уводит
задачу `in_dev -> verifying` за секунды, `cmd_run` не вызывается ни разу —
`index_of_first_role_step("developer")` не находит записи и валит тест.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (ReviewEscalationSandbox,  # noqa: E402
                      agent_run_finished_actors)
from orchestrator import store  # noqa: E402


class AutoRunsDeveloperAfterTheReviewEscalationTest(ReviewEscalationSandbox):

    def test_ac2_return_from_the_review_escalation_runs_developer(self):
        """Ревьювер эскалирует по `REVIEW.md status: escalate`, Оператор
        отвечает и возвращает задачу через `approve`, затем зовёт `auto`:
        первым отработать обязан шаг developer, а не предварительный
        advance по готовому PLAN.md — между записью возврата и шагом роли
        в журнале нет ни заметки «шаг developer не нужен», ни
        `state -> verifying`.

        Ловит мутацию: маркер эскалации ревьювера журналируется не сразу
        после `state -> escalated`, а где-то до него (или с другим
        `action`) — `auto._role_step_since_state_entry` его не прочитает,
        запись возврата снова пропустится как `_ESCALATED_RETURN_DETAILS`,
        и цикл уведёт задачу в `verifying` без единого вызова роли.
        """
        self.write_plan("ready")
        self.escalate_from_review()
        self.assertEqual(self.state(), "escalated",
                         "сценарий не воспроизведён: вердикт не эскалировал")

        self.answer_and_approve()
        self.assertEqual(
            self.state(), "in_dev",
            "approve не вернул задачу в in_dev — сценарий не воспроизведён")
        return_index = self.index_of_last("state -> in_dev")

        self.agent.script = [lambda: None]
        self.auto()

        actors = agent_run_finished_actors(store.db(), self.TASK)
        self.assertEqual(
            actors[:1], ["developer"],
            "первым после возврата отработал не developer (или роль не "
            "отработала вовсе) — предварительный advance забрал ход себе")
        self.assert_role_runs_before_any_pre_advance(return_index, "developer")


if __name__ == "__main__":
    unittest.main()
