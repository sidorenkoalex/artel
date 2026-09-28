"""AC-4 — `amend-tests` проверяет строку группы у планки, зафиксированной
после мержа этой задачи, и не проверяет у зафиксированной до мержа.

«После мержа» — планка прошла новый выход из `tests_writing` в песочнице
(код этой задачи уже на месте). «До мержа» — `_amend_sandbox.
enter_in_dev_legacy`: лок записан без нового выхода, файлы без строк
группы, задача заведена задолго до этой. Песочница — настоящий git
(`tests/sandbox.py::RealGitSandbox`), рецепт `tests/test_amend.py::
AmendThenReviewGateTest`.

Группа: разовый
Красен до реализации: `amend-tests` строку группы не проверяет — правка файла без неё проходит и сдвигает `tests_locked_sha`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _amend_sandbox  # noqa: E402


class AmendTestsGroupLineTest(_amend_sandbox.AmendSandbox):

    def test_ac4_post_merge_plank_amend_without_group_line_refuses(self):
        """Планка прошла новый выход из `tests_writing`; правка файла
        `test_ac.py`, убирающая строку группы, — `amend-tests` отказывает
        с именем файла, `tests_locked_sha` прежний. Та же правка со
        строкой группы — проходит, лок сдвигается (контроль, что
        песочница `amend-tests` вообще пропускает правку).

        Ловит мутацию: проверку строки группы подключили к выходу из
        `tests_writing`, но не к `_cmd_amend_tests` — правка без строки
        проходит и сдвигает лок.
        """
        self.enter_in_dev_through_gate()
        locked = self.row()["tests_locked_sha"]

        self.write_worktree_plank(
            _amend_sandbox.plank_file(None, variant="правка без группы"))
        refused, text = self.amend()
        self.assertTrue(refused, f"amend-tests без строки группы прошёл: {text}")
        self.assertIn("test_ac.py", text)
        self.assertEqual(self.row()["tests_locked_sha"], locked)

        self.write_worktree_plank(
            _amend_sandbox.plank_file("Группа: долгоживущий",
                                      variant="правка с группой"))
        refused, text = self.amend()
        self.assertFalse(refused, f"правка со строкой группы отклонена: {text}")
        self.assertNotEqual(self.row()["tests_locked_sha"], locked)

    def test_ac4_pre_merge_plank_is_not_checked_for_group_line(self):
        """Планка без строк группы, зафиксированная до мержа этой задачи;
        правка её файла (строки группы по-прежнему нет) — `amend-tests`
        проходит, лок сдвигается на новый коммит артефактной ветки.

        Ловит мутацию: `amend-tests` требует строку группы у ЛЮБОЙ
        планки, без различения момента фиксации — правка старой задачи
        отклонена, её `amend-tests` становится невозможным без переписи
        всех файлов планки.
        """
        self.enter_in_dev_legacy()
        locked = self.row()["tests_locked_sha"]

        self.write_worktree_plank(
            _amend_sandbox.plank_file(None, variant="правка старой планки"))
        refused, text = self.amend()
        self.assertFalse(refused, f"правка старой планки отклонена: {text}")
        self.assertNotEqual(self.row()["tests_locked_sha"], locked)


if __name__ == "__main__":
    unittest.main()
