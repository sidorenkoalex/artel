"""AC-11 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Итоговая строка
прогона (Ran N / OK) сохраняется в журнальном событии успешной правки.»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AC_TEST_AMENDED_V1, AmendSandbox  # noqa: E402

MARKER = "правка планки"
RAN_LINE = re.compile(r"Ran \d+ tests?")


class RunSummaryInJournalTest(AmendSandbox):

    def test_ac11_journal_event_carries_ran_n_and_ok(self):
        """После успешной правки журнальная запись «правка планки» несёт
        итоговую строку прогона unittest — число прогнанных тестов
        («Ran N») и статус «OK» — не только «прошло/не прошло» одним
        словом.

        Ловит мутацию: команда прогоняет unittest, чтобы решить «OK/не
        OK» (AC-10), но не переносит сам итог прогона в журнал —
        `detail` события несёт только основание и sha, без строки
        «Ran N... OK» из вывода unittest.
        """
        self.enter_in_dev()
        self.write_acceptance_tests(AC_TEST_AMENDED_V1)

        self.run_amend(reason="исправлена опечатка теста")

        row = self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? AND action LIKE ? "
            "ORDER BY id DESC LIMIT 1",
            (self.TASK, f"%{MARKER}%")).fetchone()
        self.assertIsNotNone(row, "нет журнальной записи «правка планки»")
        detail = row["detail"] or ""
        self.assertRegex(
            detail, RAN_LINE,
            f"detail записи не содержит итоговую строку «Ran N test(s)»: "
            f"{detail!r}")
        self.assertIn(
            "OK", detail,
            f"detail записи не содержит «OK» итога прогона: {detail!r}")


if __name__ == "__main__":
    unittest.main()
