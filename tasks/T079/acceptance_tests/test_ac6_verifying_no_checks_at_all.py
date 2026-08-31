"""AC-6 (tasks/T079/SPEC.md): `advance` из `verifying`, когда check-runs
головного коммита пусты и `gh run list` по ветке тоже не показывает
запусков, оставляет задачу в `verifying`; в журнал попадает запись
«проверок нет» с подсказкой Оператору; переход ни в `acceptance`, ни
в `escalated` не выполняется (пока не исчерпан потолок ожидания из
AC-9).

Красен до реализации: `_cmd_advance` не различает сегодня «проверок нет
вовсе» от любого другого статуса — состояния `verifying` в коде нет
вообще (см. докстринг `test_ac5_verifying_green_ci_to_acceptance.py`).

Журнал проверяется на факт диагностики (что-то записано, задача
осталась в verifying), а не на точный текст: SPEC приводит «проверок
нет» как иллюстрацию сути (кавычки — «запись такого смысла»), не как
литерал для grep — над словами `провер`/`нет` тест не настаивает
жёстче, чем сама формулировка требования 5.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import NO_RUN_LIST, NO_RUNS, VerifyingTest  # noqa: E402


class VerifyingNoChecksAtAllTest(VerifyingTest):

    def test_ac6_no_checks_and_no_runs_stays_in_verifying(self):
        self.enter_verifying(NO_RUNS, NO_RUN_LIST)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "«проверок нет вовсе» не имеет права перевести задачу ни "
            "в acceptance, ни в escalated (пока не исчерпан потолок "
            "ожидания)")

    def test_ac6_absence_is_journaled_with_a_hint(self):
        self.enter_verifying(NO_RUNS, NO_RUN_LIST)
        since = self.last_step_id()

        self.capture(fsm.cmd_advance, self.TASK)

        details = " ".join(self.journal_details_since(since)).lower()
        self.assertTrue(details, "advance обязан оставить след в журнале")
        self.assertIn("провер", details,
                      "диагностика обязана назвать предмет — проверки CI")
        self.assertIn("нет", details,
                      "диагностика обязана назвать факт — проверок нет")


if __name__ == "__main__":
    unittest.main()
