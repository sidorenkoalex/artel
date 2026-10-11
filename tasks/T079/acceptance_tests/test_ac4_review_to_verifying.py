"""AC-4 (tasks/T079/SPEC.md): переход `review -> verifying`. REVIEW.md со
свежим вердиктом `approved` и зелёные `acceptance_tests` переводят задачу
в `verifying`; прямого перехода `review -> acceptance` для этого исхода
больше нет.

Красен до реализации: сегодня (до этой задачи) ровно этот же вход
(вердикт approved свежей итерации + `acceptance.run` зелёный,
`orchestrator/fsm.py`, ветка `state == "review"`, `status == "approved"`)
переводит задачу НАПРЯМУЮ в `acceptance` — тот же путь, что уже покрыт
`tests/test_review_freshness.py::ReviewFreshnessScenarioTest::
test_first_verdict_passes_as_before`. Тест ниже намеренно утверждает
НОВОЕ поведение (`verifying`, не `acceptance`) — падает до того, как
разработчик вставит состояние `verifying` между `review` и `acceptance`
(SPEC требование 4).

Песочница — `tests.test_invariants.FsmTest` (T001, git и `gh`
заглушены): переход не трогает GitHub-адаптер (Draft MR/undraft —
AC-1/AC-2, см. `test_manual_criteria.py`), только состояние FSM.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tests.test_invariants import FsmTest  # noqa: E402
from orchestrator import fsm  # noqa: E402


class ReviewToVerifyingTest(FsmTest):

    def test_ac4_approved_fresh_verdict_goes_to_verifying_not_acceptance(self):
        self.write_review("approved", 1)
        self.set_state("review")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "review -> acceptance по свежему approved+зелёным "
            "acceptance_tests больше не существует напрямую — задача "
            "обязана остановиться в verifying (SPEC требование 4)")


if __name__ == "__main__":
    unittest.main()
