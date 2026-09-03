"""AC-3 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Команда отказывает
именованно и не меняет tests_locked_sha, если есть изменения за
пределами каталога acceptance_tests/.»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AC_TEST_AMENDED_V1, AmendSandbox  # noqa: E402


class OutsideChangesRefusalTest(AmendSandbox):

    def test_ac3_change_outside_acceptance_tests_refuses_even_with_valid_edit(self):
        """Оператор одновременно правит acceptance_tests/ (валидная
        правка) И произвольный файл вне этого каталога (PLAN.md той же
        задачи) — команда обязана отказать целиком, не коммитить даже
        валидную часть правки и не двигать tests_locked_sha.

        Ловит мутацию: команда стейджит и коммитит ТОЛЬКО путь
        `acceptance_tests/` (`git add -- acceptance_tests`) не проверяя
        остальной worktree на грязь — тогда лишний файл вне каталога
        остаётся незамеченным, а лок молча сдвигается на новый коммит.
        """
        locked = self.enter_in_dev()
        head_before = self.head()
        self.write_acceptance_tests(AC_TEST_AMENDED_V1)
        (self.tdir / "PLAN.md").write_text(
            "---\ntype: plan\n---\n\nправка вне acceptance_tests/\n",
            encoding="utf-8")

        out = self.run_amend(reason="одновременная правка теста и плана")

        self.assertTrue(out.strip(), "отказ обязан называть причину")
        self.assertEqual(
            self.row()["tests_locked_sha"], locked,
            "tests_locked_sha не должен измениться — есть правка вне "
            "acceptance_tests/")
        self.assertEqual(
            self.head(), head_before,
            "команда не имеет права коммитить ничего, пока в worktree "
            "есть правка за пределами acceptance_tests/")


if __name__ == "__main__":
    unittest.main()
