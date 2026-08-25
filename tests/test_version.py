"""Юнит-тесты orchestrator.version (см. tasks/T030/SPEC.md).

Приёмочные критерии CLI-уровня (`artel.py version`) покрыты
`tasks/T030/acceptance_tests/test_version.py`; здесь — прямой юнит-тест
самой функции `cmd_version()`, включая случай, когда фактическая версия
не определилась (`doctor.cli_version()` вернула `None`) — CLI-приёмка
этот случай не тестирует, а `check_cli_version()` в doctor.py трактует
его отдельно (warn, не расхождение).
"""
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, doctor, version  # noqa: E402
from scripts import guard  # noqa: E402


def claude_version_run(stdout: str):
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout, "")
    return run


def claude_version_missing(args, **kwargs):
    raise FileNotFoundError("claude не найден")


class VersionCommandTest(unittest.TestCase):
    def run_version(self) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            version.cmd_version()
        return buf.getvalue()

    def test_output_includes_pin_and_schema_version(self):
        with mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_version_run(
                    f"{config.CLI_VERSION_PIN} (Claude Code)\n")):
            out = self.run_version()

        self.assertIn(config.CLI_VERSION_PIN, out)
        self.assertIn(str(guard.SUPPORTED_SCHEMA_VERSION), out)

    def test_no_mismatch_note_when_versions_match(self):
        with mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_version_run(
                    f"{config.CLI_VERSION_PIN} (Claude Code)\n")):
            out = self.run_version()

        self.assertNotIn("РАСХОЖДЕНИЕ", out)

    def test_mismatch_note_when_versions_diverge(self):
        pin = config.CLI_VERSION_PIN
        other = pin[:-1] + ("1" if pin[-1] != "1" else "2")
        with mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_version_run(f"{other} (Claude Code)\n")):
            out = self.run_version()

        self.assertIn("РАСХОЖДЕНИЕ", out)
        self.assertIn(other, out)
        self.assertIn(pin, out)

    def test_no_mismatch_note_when_installed_version_undetermined(self):
        with mock.patch.object(doctor.subprocess, "run",
                               side_effect=claude_version_missing):
            out = self.run_version()

        self.assertNotIn("РАСХОЖДЕНИЕ", out)
        self.assertIn(config.CLI_VERSION_PIN, out)


if __name__ == "__main__":
    unittest.main()
