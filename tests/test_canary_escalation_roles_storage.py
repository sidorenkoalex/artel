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

from orchestrator import config, store


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


if __name__ == "__main__":
    unittest.main()
