"""AC-5 (SPEC T101) — fingerprint в журнальном событии, фиксирующем исход
прогона приёмочных тестов задачи, в фактической точке вызова
`acceptance.run` внутри `orchestrator/fsm_advance.py::review`
(`green, tail = acceptance.run(acc_tdir)`, строка ~151).

`orchestrator/fsm_autogate.py` НЕ вызывает `acceptance.run` нигде в
текущем коде (проверено чтением исходника на момент написания теста:
единственный вызов там — `acceptance.run_full_suite`, другая функция) —
«фактические точки вызова acceptance.run» из AC-5 в этом файле пусты,
поэтому для него здесь нет отдельного сценария: требование покрывает
ровно то множество вызовов, которое есть в коде (тот же принцип, что и
требование 1 SPEC — «по фактическим точкам исполнения кода»).

Красен до реализации: без сборщика fingerprint detail событий
"приёмочные тесты пройдены"/"переход отклонён: приёмочные тесты" не
несёт ни версии git, ни версии claude CLI.

Один процесс на весь файл (в отличие от `_driver_agent_step.py`) —
оба сценария (зелёный/красный) отвечают на git/claude ОДИНАКОВО
(`_sandbox.version_stub_run`), так что унаследованный кэш AC-6 между
ними не искажает проверку: оба ожидают одни и те же значения полей.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from _sandbox import (AC_TEST_FAIL, AC_TEST_PASS, ReviewAdvanceSandbox,  # noqa: E402
                      version_stub_run)


class AcceptanceRunFingerprintTest(ReviewAdvanceSandbox):

    def test_ac5_fingerprint_recorded_when_acceptance_tests_pass(self):
        self.write_acceptance_tests(AC_TEST_PASS)

        with mock.patch("subprocess.run", side_effect=version_stub_run()):
            self.advance()

        self.assertEqual(self.state(), "verifying",
                         "зелёная приёмка должна была продвинуть задачу")
        details = self.journal_details("приёмочные тесты пройдены")
        self.assertEqual(len(details), 1, details)
        detail = details[0]
        self.assertIn("2.43.0", detail,
                      f"версия git не найдена в detail «приёмочные тесты "
                      f"пройдены» (AC-5): {detail!r}")
        self.assertIn(config.CLI_VERSION_PIN, detail,
                      f"версия claude CLI не найдена в detail «приёмочные "
                      f"тесты пройдены» (AC-5): {detail!r}")

    def test_ac5_fingerprint_recorded_when_acceptance_tests_fail(self):
        self.write_acceptance_tests(AC_TEST_FAIL)

        with mock.patch("subprocess.run", side_effect=version_stub_run()):
            self.advance()

        self.assertEqual(self.state(), "review",
                         "красная приёмка не должна продвигать задачу")
        details = self.journal_details("переход отклонён: приёмочные тесты")
        self.assertEqual(len(details), 1, details)
        detail = details[0]
        self.assertIn("2.43.0", detail,
                      f"версия git не найдена в detail «переход отклонён: "
                      f"приёмочные тесты» (AC-5): {detail!r}")
        self.assertIn(config.CLI_VERSION_PIN, detail,
                      f"версия claude CLI не найдена в detail «переход "
                      f"отклонён: приёмочные тесты» (AC-5): {detail!r}")


if __name__ == "__main__":
    unittest.main()
