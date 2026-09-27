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


class CliVersionPinTest(unittest.TestCase):
    """Пин CLI поднят до установленной версии
    (01M3FTQ16M3VVXPPFCC0BGA39V, требование 7; CR-2026-09-26-7):
    расхождение пина с фактом давало warn «cli-version» на каждом шаге."""

    def test_pin_value_and_operator_decision_mark(self):
        """Значение пина — `2.1.267`, а строка константы несёт дату и
        находку, по которой Оператор его сдвинул: подъём пина — решение
        Оператора, а не автоматика, и по строке это обязано читаться.

        Ловит мутацию: значение поднято без пометки (или пометка
        осталась от прошлого решения 03.09) — по строке нельзя понять,
        чьим решением сдвинут пин, и `assertIn` покраснеет."""
        self.assertEqual("2.1.267", config.CLI_VERSION_PIN)
        source = Path(config.__file__).read_text(encoding="utf-8")
        line, = [text for text in source.splitlines()
                 if text.startswith("CLI_VERSION_PIN")]
        self.assertIn("26.09", line)
        self.assertIn("CR-2026-09-26-7", line)

    def test_doctor_reports_ok_for_the_pinned_version(self):
        """`doctor.check_cli_version` на установленной 2.1.267 — `ok`,
        а не warn о расхождении.

        Ловит мутацию: пин поднят с опечаткой в цифре или лишним
        пробелом внутри строки — сверка `version != CLI_VERSION_PIN`
        снова даст warn, и предупреждение вернулось бы на каждый шаг."""
        with mock.patch.object(doctor, "cli_version",
                               return_value="2.1.267"):
            check = doctor.check_cli_version()

        self.assertEqual("cli-version", check.name)
        self.assertEqual("ok", check.status, check.detail)


if __name__ == "__main__":
    unittest.main()
