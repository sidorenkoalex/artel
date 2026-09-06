"""AC-5 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): `diff_base` вернула
`None` — гейт зон и гейт ёмкости отказывают переход fail-closed (журнал
+ печать причины), тем же способом, что сейчас при `None` от
`diff_names`/`git_diff_part`.

Красен до реализации: `_zones_gate_refuses` сегодня зовёт `gitcmd.
diff_names` напрямую от `config.MAIN_BRANCH` и вообще не спрашивает
`gitcmd.diff_base`, поэтому `mock.patch.object(gitcmd, "diff_base",
return_value=None)` ниже никак не повлияет на её сегодняшнее поведение
(гейт пройдёт как обычно, `diff_names` не бросит `boom`) — тест
провалится на `refused` не-True. То же для `_capacity_gate_refuses`:
она сегодня зовёт `gitcmd.git("diff", ...)` от `config.MAIN_BRANCH`
напрямую, `diff_base` не спрашивает вовсе, и `boom`, подставленный
вместо `gitcmd.git`, не сработает — переход пройдёт вместо отказа.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class ZonesGateFailsClosedOnNoneBaseTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.branch = "task/t001-x"
        self.t = {"title": "Тест", "branch": self.branch,
                 "zones": "orchestrator/store.py", "zones_extension": None}

    def journal_details(self) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]

    def test_ac5_zones_gate_refuses_when_diff_base_returns_none(self):
        """Ловит мутацию: проверка `if base is None: ... return True`
        убрана/заменена на `return False` — гейт молча пропустил бы
        переход, так и не выяснив список файлов диффа (fail-open вместо
        fail-closed, ADR-0002); отдельно ловит мутацию «гейт всё равно
        передаёт None дальше в diff_names», которая уронила бы
        `boom`."""
        def boom(*a, **k):
            raise AssertionError(
                "гейт зон не имеет права звать diff_names без базы "
                "сравнения (diff_base вернула None)")

        with mock.patch.object(gitcmd, "diff_base", return_value=None), \
             mock.patch.object(gitcmd, "diff_names", boom):
            refused = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, self.t, self.branch, "PLAN\n")

        self.assertTrue(refused)
        details = self.journal_details()
        self.assertTrue(any("гейт зон" in d for d in details), details)


class CapacityGateFailsClosedOnNoneBaseTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.branch = "task/t001-x"
        self.t = {"title": "Тест", "branch": self.branch}

    def journal_details(self) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]

    def test_ac5_capacity_gate_refuses_when_diff_base_returns_none(self):
        """Ловит мутацию: гейт ёмкости не проверяет `None` от `diff_base`
        и передаёт его дальше как базу diff'а — `boom` вместо `gitcmd.
        git` поймает сам факт такой попытки; если проверка на `None`
        всё же есть, но не отказывает (`return False`), тест провалится
        на `refused` не-True."""
        def boom(*a, **k):
            raise AssertionError(
                "гейт ёмкости не имеет права звать git diff без базы "
                "сравнения (diff_base вернула None)")

        with mock.patch.object(gitcmd, "diff_base", return_value=None), \
             mock.patch.object(gitcmd, "git", boom):
            refused = fsm_advance._capacity_gate_refuses(
                self.conn, self.task_id, self.t, "in_dev")

        self.assertTrue(refused)
        details = self.journal_details()
        self.assertTrue(any("ёмкости" in d for d in details), details)


if __name__ == "__main__":
    unittest.main()
