"""AC-2 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Команда отказывает
именованно и не меняет tests_locked_sha, если в каталоге
acceptance_tests/ нет изменений.»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AmendSandbox  # noqa: E402


class NoChangesRefusalTest(AmendSandbox):

    def test_ac2_no_worktree_changes_refuses_and_keeps_lock(self):
        """Задача доведена до in_dev, Оператор ничего не правил в
        acceptance_tests/ (worktree чист по этому пути) — вызов команды с
        непустым основанием обязан отказать именованно, не создавая
        коммита и не сдвигая tests_locked_sha.

        Ловит мутацию: команда пропускает проверку «есть ли вообще
        изменения» и коммитит пустой diff (либо повторно коммитит уже
        зафиксированное состояние), сдвигая tests_locked_sha на новый sha
        того же по содержанию дерева.
        """
        locked = self.enter_in_dev()
        head_before = self.head()

        out = self.run_amend(reason="нет реальной причины для правки")

        self.assertTrue(out.strip(), "отказ обязан называть причину, а не "
                        "проходить молча")
        self.assertEqual(
            self.row()["tests_locked_sha"], locked,
            "tests_locked_sha не должен измениться при отсутствии правок")
        self.assertEqual(
            self.head(), head_before,
            "новый коммит не должен появиться на ветке задачи")


if __name__ == "__main__":
    unittest.main()
