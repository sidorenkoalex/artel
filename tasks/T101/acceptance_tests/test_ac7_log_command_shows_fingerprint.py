"""AC-7 (SPEC T101) — fingerprint виден Оператору штатным просмотром
журнала (`artel.py log <id>`) без дополнительных флагов.

`artel.py log <id>` резолвится в `orchestrator/catalog.cmd_log`
(`orchestrator/artel.py`: `"log": lambda: catalog.cmd_log(rest[0])`) без
единого дополнительного аргумента — вызов `catalog.cmd_log` напрямую
здесь и есть та самая команда, без обёртки CLI-парсера.

Красен до реализации: без сборщика fingerprint печатаемая строка
`cmd_log` для события "приёмочные тесты пройдены" не несёт версии git.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config  # noqa: E402
from _sandbox import AC_TEST_PASS, ReviewAdvanceSandbox, version_stub_run  # noqa: E402


class LogCommandShowsFingerprintTest(ReviewAdvanceSandbox):

    def test_ac7_fingerprint_visible_via_log_command_without_flags(self):
        self.write_acceptance_tests(AC_TEST_PASS)
        with mock.patch("subprocess.run", side_effect=version_stub_run()):
            self.advance()
        self.assertEqual(self.state(), "verifying")

        out = self.capture(catalog.cmd_log, self.TASK)

        self.assertIn("приёмочные тесты пройдены", out)
        self.assertIn("2.43.0", out,
                      f"версия git не видна в выводе `artel.py log` без "
                      f"доп. флагов (AC-7):\n{out}")
        self.assertIn(config.CLI_VERSION_PIN, out,
                      f"версия claude CLI не видна в выводе `artel.py log` "
                      f"без доп. флагов (AC-7):\n{out}")


if __name__ == "__main__":
    unittest.main()
