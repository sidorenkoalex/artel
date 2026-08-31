"""AC-10 (tasks/T079/SPEC.md): `artel.py reject <id> "<причина>"` из
`verifying` выполняет переход `verifying -> in_dev`, причина
записывается в журнал; `review_iters` и `accept_rejects` этим переходом
не изменяются.

Красен до реализации: `_cmd_reject` (orchestrator/fsm.py) сегодня
принимает только `merge_gate` (-> in_dev) и `acceptance` (-> in_dev,
считает `accept_rejects`) — любое третье состояние, в частности
`verifying` (которого к тому же ещё нет как рабочего состояния),
получает `sys.exit("reject применим только в acceptance или merge_gate
...")`. Тест ожидает УСПЕШНОГО перехода — до правки разработчика падает
именно этим `SystemExit`, не отдельной причиной теста.

Счётчики (`review_iters`, `accept_rejects`) заводятся заведомо
ненулевыми в фикстуре — совпадение с нулём по умолчанию не доказало бы
«не изменились», а «остались нулём случайно».
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402


class RejectFromVerifyingTest(FsmTest):

    def test_ac10_reject_transitions_to_in_dev_without_touching_counters(self):
        self.set_state("verifying", review_iters=1, accept_rejects=1)
        reason = "CI красный дольше потолка — возвращаю на доработку"

        self.capture(fsm.cmd_reject, self.TASK, reason)

        self.assertEqual(self.state(), "in_dev",
                         "reject из verifying обязан перевести задачу в in_dev")
        row = self.task_row()
        self.assertEqual(row["review_iters"], 1,
                         "reject из verifying не имеет права трогать review_iters")
        self.assertEqual(row["accept_rejects"], 1,
                         "reject из verifying не имеет права трогать accept_rejects")
        journal = "\n".join(r["detail"] for r in
                            store.task_steps(store.db(), self.TASK))
        self.assertIn(reason, journal,
                     "причина reject обязана попасть в журнал задачи")


if __name__ == "__main__":
    unittest.main()
