"""AC-2 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): гейт зон
(`_zones_gate_refuses`) сравнивает ветку задачи с базой из AC-1
трёхточечно (список файлов от merge-base до головы ветки) вместо
текущего двухточечного `gitcmd.diff_names(config.MAIN_BRANCH,
t["branch"])`.

Красен до реализации: сегодняшний `_zones_gate_refuses`
(`orchestrator/fsm_advance.py`) зовёт `gitcmd.diff_names(config.
MAIN_BRANCH, t["branch"])` буквально — список файлов диффа считается от
`config.MAIN_BRANCH`, не от результата `gitcmd.diff_base(t["branch"])`,
поэтому `names_mock` ниже получит `config.MAIN_BRANCH` первым
аргументом, а не подставленный фейковый sha, и `assert_called_once_with`
провалится.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import config, fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class ZonesGateUsesDiffBaseTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.branch = "task/t001-x"
        self.t = {"title": "Тест гейта зон", "branch": self.branch,
                 "zones": "orchestrator/store.py", "zones_extension": None}

    def test_ac2_zones_gate_diffs_from_diff_base_not_config_main_branch(self):
        """Ловит мутацию: `gitcmd.diff_names(config.MAIN_BRANCH,
        t["branch"])` оставлен как есть (не заменён на `gitcmd.diff_names
        (gitcmd.diff_base(t["branch"]), t["branch"])`) — `diff_names`
        получил бы первым аргументом литеральный `config.MAIN_BRANCH`
        вместо fake_base, и `names_mock.assert_called_once_with` ниже
        провалится."""
        fake_base = "1234567890abcdef1234567890abcdef12345678"
        self.assertNotEqual(fake_base, config.MAIN_BRANCH)

        with mock.patch.object(gitcmd, "diff_base",
                               return_value=fake_base) as base_mock, \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=[]) as names_mock:
            refused = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, self.t, self.branch, "PLAN\n")

        self.assertFalse(refused)
        base_mock.assert_called_once_with(self.branch)
        names_mock.assert_called_once_with(fake_base, self.branch)


if __name__ == "__main__":
    unittest.main()
