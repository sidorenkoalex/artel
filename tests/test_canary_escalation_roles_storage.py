"""Хранение ролей эскалаций в `canary_runs`: пустой перечень и `None` различимы.

SPEC 01M4VC31NFCS6JZ0VE8HNJ7FYM, требование 1: пустая строка — эскалаций
не было, `NULL` — данных о ролях нет. Свойства самого перечня и критерия
чистоты держит долгоживущий файл задачи
`tests/test_01m4vc31nfcs6jz0ve8hnj7fym_escalation_roles.py`.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import canary, config, fsm, store


class EscalationRolesStorageTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(config, "DB", Path(tmp.name) / "state.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conn = store.db()
        self.addCleanup(self.conn.close)

    def insert(self, task_id: str, **kwargs) -> None:
        store.insert_canary_run(
            self.conn, "20261014T000000Z", "canary-status-sort", task_id, 7,
            1.0, 0, 0, "merge_gate", "no", False, False, verdict="green",
            **kwargs)

    def test_empty_list_is_empty_string_and_default_is_null(self):
        """`[]` пишется пустой строкой, без параметра — `NULL`.

        Ловит мутацию: пустой перечень сводится к `NULL` (`roles or None`)
        — прогон без эскалаций читается как строка без данных о ролях; или
        значение по умолчанию пишет пустую строку — прогоны без результата
        клона выглядят прогонами «без эскалаций».
        """
        self.insert("01EMPTY", escalation_roles=[])
        self.insert("01NULL")
        self.insert("01TWO", escalation_roles=["analyst", "spec_auditor"])
        rows = {r["task_id"]: r["escalation_roles"]
                for r in store.all_canary_runs(self.conn)}
        self.assertEqual(rows, {"01EMPTY": "", "01NULL": None,
                                "01TWO": "analyst,spec_auditor"})


def _step(action: str) -> dict:
    return {"ts": "t", "actor": "fsm", "action": action, "detail": ""}


class RunOneTaskRecordsEscalationRolesTest(unittest.TestCase):
    """Связка «результат клона → строка `canary_runs`» (требование 1):
    роли вычисляет пульт из `steps`, подменён только процесс клона."""

    def test_row_carries_roles_computed_from_clone_steps(self):
        """`_run_one_task` с результатом клона, где эскалировали analyst и
        аудитор SPEC (по маркеру роли каждая), пишет строку с
        `escalation_roles = 'analyst,spec_auditor'`.

        Ловит мутацию: `_run_one_task` не передаёт роли в
        `_record_canary_run` (`escalation_roles=None`) — колонка `NULL`, и
        строка молча читается прежним правилом `escalations > 1`.
        """
        marker = fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER
        steps = [
            _step("created"), _step("agent run finished"),
            _step("state -> escalated"), _step("sha зафиксирован"), _step(marker),
            _step("state -> spec_writing"), _step("sha зафиксирован"),
            _step("state -> spec_audit"), _step("sha зафиксирован"),
            _step("agent run finished"),
            _step("state -> escalated"), _step("sha зафиксирован"), _step(marker),
        ]
        target = "b" * 40
        metrics = {
            "steps": len(steps), "cost_usd": 0.0, "review_iterations": 0,
            "escalations": ["батч вопросов", "аудит: escalate"],
            "dev_retries": 0, "outcome": "killed", "kill_note": "штатно",
            "test_author_visited": False, "ceiling_exhausted": False,
            "ceiling_raise": None, "code_sha": target, "target_sha": target,
        }
        phase_one = ("01X", "shablon", "yes", steps, metrics, True, False,
                     True, None)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(config, "DB", Path(tmp.name) / "state.db"), \
                mock.patch.object(canary, "_run_task_in_ephemeral_clone",
                                  return_value=phase_one), \
                mock.patch("builtins.print"):
            canary._run_one_task(Path(tmp.name) / "shablon.md",
                                 "20261014T000000Z", 2.0, target_sha=target,
                                 sha_label="проверяемый")
            conn = store.db()
            self.addCleanup(conn.close)
            rows = [(r["escalation_roles"], r["escalations"])
                    for r in store.all_canary_runs(conn)]
        self.assertEqual(rows, [("analyst,spec_auditor", 2)])


if __name__ == "__main__":
    unittest.main()
