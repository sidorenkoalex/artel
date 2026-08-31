"""AC-12 (tasks/T079/SPEC.md): ни при каком исходе `advance` из
`verifying` (AC-5..AC-9) оркестратор не создаёт коммит в ветке задачи
с единственной целью сдвинуть её голову («разбудить» CI).

Красен до реализации: `test_ac12_ceiling_escalation_creates_no_wakeup_
commit` падает уже на собственном ассерте фикстуры (см. ниже), не
дожидаясь предмета проверки. Файл смешанный, не однородно красный —
остальные четыре метода сегодня уже проходят, но по другой причине:

- четыре метода немедленных исходов (зелёный/нет проверок/идут/красный)
  проходят уже сейчас, но ВАКУУМНО: `advance` из `verifying` сегодня
  не делает вообще ничего (состояния нет — падает в `else`
  `_cmd_advance`, коммитов не создаёт никто), а не потому, что
  требование 5 выполнено. `git_spy` (`SpyRun`, `tests.test_invariants`)
  перехватывает ЛЮБОЙ `subprocess.run` процесса, поэтому эти методы
  останутся содержательными и способными покраснеть именно тогда,
  когда разработчик подключит требование 5 к реальному коду.
- `test_ac12_ceiling_escalation_creates_no_wakeup_commit` красный
  по прямой причине: сценарий, который он проверяет (эскалация по
  потолку ожидания, AC-9), сегодня недостижим вообще — задача не
  покидает `verifying` ни при каком числе повторов `advance`,
  собственный ассерт фикстуры («задача обязана дойти до escalated»)
  падает раньше проверки коммитов.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import (GREEN_RUNS, NO_RUN_LIST, NO_RUNS,  # noqa: E402
                      RED_RUNS, RUNNING_RUNS, VerifyingTest)

MAX_ADVANCE_ATTEMPTS = 200


class NoWakeupCommitsTest(VerifyingTest):

    def _assert_no_commit_created(self, check_runs_json, run_list_json,
                                  label):
        self.enter_verifying(check_runs_json, run_list_json)
        since = len(self.git_spy.calls)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertNotIn(
            "commit", self.git_subcommands_since(since),
            f"advance из verifying ({label}) создал git-коммит — "
            f"requirement 5 запрещает будить CI пустым коммитом")

    def test_ac12_green_ci_creates_no_wakeup_commit(self):
        self._assert_no_commit_created(GREEN_RUNS, NO_RUN_LIST, "зелёный CI")

    def test_ac12_no_checks_at_all_creates_no_wakeup_commit(self):
        self._assert_no_commit_created(NO_RUNS, NO_RUN_LIST, "проверок нет")

    def test_ac12_checks_running_creates_no_wakeup_commit(self):
        self._assert_no_commit_created(RUNNING_RUNS, NO_RUN_LIST,
                                       "проверки идут (check-runs)")

    def test_ac12_red_ci_creates_no_wakeup_commit(self):
        self._assert_no_commit_created(RED_RUNS, NO_RUN_LIST, "красный CI")

    def test_ac12_ceiling_escalation_creates_no_wakeup_commit(self):
        self.enter_verifying(RED_RUNS, NO_RUN_LIST)
        since = len(self.git_spy.calls)

        for _ in range(MAX_ADVANCE_ATTEMPTS):
            self.capture(fsm.cmd_advance, self.TASK)
            if self.state() == "escalated":
                break

        self.assertEqual(self.state(), "escalated",
                         "фикстура обязана довести задачу до эскалации "
                         "(см. test_ac9_verifying_wait_ceiling_escalates.py)")
        self.assertNotIn(
            "commit", self.git_subcommands_since(since),
            "истечение потолка ожидания и эскалация не имеют права "
            "создать пробуждающий коммит")


if __name__ == "__main__":
    unittest.main()
