"""AC-7 (tasks/T079/SPEC.md): `advance` из `verifying`, когда check-runs
головного коммита пусты, но `gh run list` по ветке показывает запуск для
этой ветки/коммита, трактует статус как «проверки идут» (не как «проверок
нет»); диагностика в журнале называет источник (`gh run list`); задача
остаётся в `verifying`.

Красен до реализации: состояния `verifying` в коде нет (см. докстринг
`test_ac5_verifying_green_ci_to_acceptance.py`); текущий `ci.branch_status`
тоже не различает источник «check-runs пусты, но gh run list — не пусты»
от «проверок нет вовсе» — оба сегодня читаются одинаково («у коммита
нет ни одной проверки CI»), это и есть строка роадмапа P3 (T040),
которую и закрывает requirement 5.

`gh run list` — не домысел интерфейса: SPEC называет источник дословно
(требование 5, AC-6/AC-7) — тест вправе искать литерал в журнале, тем
же приёмом, что и `_sandbox.py::set_ci_dual` ищет его в argv `gh`
(докстринг `_sandbox.py`).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import NO_RUNS, SOME_RUN_LIST, VerifyingTest  # noqa: E402


class VerifyingChecksRunningViaGhRunListTest(VerifyingTest):

    def test_ac7_empty_check_runs_but_gh_run_list_hit_stays_in_verifying(self):
        self.enter_verifying(NO_RUNS, SOME_RUN_LIST)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "«проверки идут» (по gh run list) не имеет права перевести "
            "задачу ни в acceptance, ни в escalated")

    def test_ac7_journal_names_gh_run_list_as_the_source(self):
        self.enter_verifying(NO_RUNS, SOME_RUN_LIST)
        since = self.last_step_id()

        self.capture(fsm.cmd_advance, self.TASK)

        details = " ".join(self.journal_details_since(since))
        self.assertIn(
            "gh run list", details,
            "диагностика обязана назвать источник дословно — «gh run "
            "list» (SPEC AC-7), а не только сказать «проверки идут»")

if __name__ == "__main__":
    unittest.main()
