"""AC-8 (tasks/T079/SPEC.md): `advance` из `verifying`, когда check-runs
головного коммита завершены и хотя бы одна проверка не входит в
`ci.GREEN`, оставляет задачу в `verifying` (не в `in_dev`, не в
`escalated`); список незелёных проверок — в журнале.

Красен до реализации: состояния `verifying` в коде нет (см. докстринг
`test_ac5_verifying_green_ci_to_acceptance.py`). Отдельно от этого:
требование 7 (инвариант 19, симметрия SPEC T052) — красный CI сам по
себе НЕ имеет права вытолкнуть задачу из `verifying`, в частности не
в `in_dev` автоматически, — тест явно проверяет и это отрицание,
не только «не escalated».

Список незелёных проверок — по имени проверки, взятому из фикстуры
`_sandbox.RED_RUNS` (`python`, conclusion `failure`); `guard` той же
фикстуры зелёный (`success`) и не обязан быть назван — критерий
говорит именно о списке НЕЗЕЛЁНЫХ.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import NO_RUN_LIST, RED_RUNS, VerifyingTest  # noqa: E402


class VerifyingRedCiStaysTest(VerifyingTest):

    def test_ac8_red_ci_stays_in_verifying_not_in_dev_not_escalated(self):
        self.enter_verifying(RED_RUNS, NO_RUN_LIST)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "красный CI сам по себе не имеет права вытолкнуть задачу из "
            "verifying — ни в in_dev (инвариант 19), ни в escalated "
            "(до потолка ожидания, AC-9)")

    def test_ac8_journal_lists_the_non_green_check(self):
        self.enter_verifying(RED_RUNS, NO_RUN_LIST)
        since = self.last_step_id()

        self.capture(fsm.cmd_advance, self.TASK)

        details = " ".join(self.journal_details_since(since))
        self.assertIn("python", details,
                      "незелёная проверка 'python' обязана быть названа "
                      "в журнале")


if __name__ == "__main__":
    unittest.main()
