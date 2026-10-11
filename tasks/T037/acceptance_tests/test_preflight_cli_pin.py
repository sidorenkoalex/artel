"""Приёмочные тесты T037 — сверка пина CLI возвращена в pre-flight
(SPEC.md, критерий AC-4).

Песочница — минимальный вариант приёма `tests/test_doctor.py::TmpRootTest`
(тот же список подменённых путей `config`, `shutil.which`, keychain,
ambient-токены) без копирования `skills/`/`templates/`/`docs/`: этот
тест зовёт только `doctor.preflight_checks`, который в них не заглядывает
(в отличие от прогона самого шага агента) — своя копия здесь не тянет
лишнюю обвязку и не зависит от структуры `tests/sandbox.py` (AC-1),
которую эта же задача только вводит.

Требование 3 не называет имя итоговой проверки — тест опирается на уже
существующую `doctor.cli_version()`/detail-формат `check_cli_version()`
(строки 91-114 `orchestrator/doctor.py` на момент написания), которую
задача переносит в `preflight_checks`, а не изобретает заново.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, doctor, runner  # noqa: E402


class TmpConfigSandbox(unittest.TestCase):
    """Пути `config` — во временном каталоге, CLI/keychain подменены."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("ROOT", root),
                            ("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("TARGETS", root / "targets.yaml"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        which_patcher = mock.patch.object(doctor.shutil, "which",
                                          return_value="/usr/bin/claude")
        which_patcher.start()
        self.addCleanup(which_patcher.stop)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)

        env_patcher = mock.patch.dict(
            os.environ,
            {"CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_API_KEY": ""})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)


class CliVersionPinCheckedInPreflightTest(TmpConfigSandbox):
    """AC-4: сверка пина CLI (config.CLI_VERSION_PIN) выполняется в
    `preflight_checks` (orchestrator/doctor.py), а не только в `doctor`."""

    def _preflight_with_cli_version(self, version):
        with mock.patch.object(doctor, "cli_version", return_value=version):
            return doctor.preflight_checks("developer", config.DEFAULT_TARGET)

    def test_ac4_preflight_reports_a_cli_version_pin_mismatch(self):
        checks = self._preflight_with_cli_version("0.0.1")

        blocking = [c for c in checks if c.status == "fail"]
        self.assertEqual(
            blocking, [],
            f"песочница должна проходить все блокирующие проверки, иначе "
            f"тест проверяет не сверку пина CLI: {blocking}")

        version_checks = [c for c in checks if c.name == "cli-version"]
        self.assertTrue(
            version_checks,
            "preflight_checks не содержит проверку 'cli-version' — сверка "
            "пина CLI (config.CLI_VERSION_PIN) не выполняется в pre-flight")
        detail = version_checks[0].detail
        self.assertIn(config.CLI_VERSION_PIN, detail)
        self.assertIn("0.0.1", detail)

    def test_ac4_preflight_reports_a_matching_cli_version_too(self):
        checks = self._preflight_with_cli_version(config.CLI_VERSION_PIN)

        version_checks = [c for c in checks if c.name == "cli-version"]
        self.assertTrue(
            version_checks,
            "preflight_checks не содержит проверку 'cli-version' даже "
            "когда установленная версия совпадает с пином")
        self.assertEqual(version_checks[0].status, "ok")


if __name__ == "__main__":
    unittest.main()
