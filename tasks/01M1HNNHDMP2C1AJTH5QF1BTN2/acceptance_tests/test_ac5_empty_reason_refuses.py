"""AC-5 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Команда отказывает
именованно и не меняет tests_locked_sha, если основание (--reason)
пустое.»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AC_TEST_AMENDED_V1, AmendSandbox  # noqa: E402


class EmptyReasonRefusalTest(AmendSandbox):

    def test_ac5_empty_reason_refuses_despite_otherwise_valid_amend(self):
        """Задача в in_dev, правка в acceptance_tests/ валидна и прогон
        был бы «OK» — единственная проблема: `--reason` передан пустой
        строкой. Команда обязана отказать именованно, не коммитить
        правку и не двигать tests_locked_sha, несмотря на то, что все
        остальные условия успешной правки выполнены.

        Ловит мутацию: проверка непустого `--reason` пропущена или
        проверяет только `is None` (не различает «флаг не передан» и
        «флаг передан пустой строкой») — пустая строка проходит как
        «основание есть».
        """
        locked = self.enter_in_dev()
        head_before = self.head()
        self.write_acceptance_tests(AC_TEST_AMENDED_V1)

        out = self.run_amend(reason="")

        self.assertTrue(out.strip(), "отказ обязан называть причину")
        self.assertEqual(
            self.row()["tests_locked_sha"], locked,
            "tests_locked_sha не должен измениться при пустом --reason")
        self.assertEqual(
            self.head(), head_before,
            "команда не имеет права коммитить правку без основания")


if __name__ == "__main__":
    unittest.main()
