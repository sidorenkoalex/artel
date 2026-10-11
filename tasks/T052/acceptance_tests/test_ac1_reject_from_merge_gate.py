"""AC-1 (tasks/T052/SPEC.md): `artel.py reject <id> "<причина>"` из
`merge_gate` выполняет переход `merge_gate -> in_dev` и записывает
переданную причину в журнал задачи.

Песочница — `tests.test_invariants.FsmTest` (БД и артефакты во временном
каталоге, git подменён): переход `reject` из `merge_gate` не трогает
git вовсе (в отличие от автоматического возврата по конфликту при
`approve`, AC-3/AC-4 — там нужен настоящий git, см.
`tasks/T052/acceptance_tests/_sandbox.py`).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402


class RejectFromMergeGateTest(FsmTest):

    def test_ac1_reject_from_merge_gate_transitions_to_in_dev_and_journals_reason(self):
        self.set_state("merge_gate")
        reason = "main ушёл вперёд, актуализируй ветку и повтори приёмку"

        self.capture(fsm.cmd_reject, self.TASK, reason)

        self.assertEqual(self.state(), "in_dev",
                         "reject из merge_gate обязан перевести задачу в in_dev")
        journal = "\n".join(r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)))
        self.assertIn(reason, journal,
                     "причина reject обязана попасть в журнал задачи")


if __name__ == "__main__":
    unittest.main()
