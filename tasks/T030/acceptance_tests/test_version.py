"""Приёмочные тесты T030 — команда `version` (SPEC.md, критерии AC-1..AC-7).

Точка входа под тестом — `orchestrator.artel.main()` с подменённым
`sys.argv` (тот же приём, что `tests/test_analyst_role.py`,
`ArtelCliTzFlagTest`): критерии описывают именно CLI-команду `artel.py
version`, а не внутреннюю функцию с ещё не решённым именем/местом —
реализация свободна выбрать модуль.

Фактическая версия `claude` (AC-3, AC-5) подменяется на уровне
`doctor.subprocess.run` — то же место, откуда её берёт `doctor.cli_version()`
(AC-3 требует именно этот способ определения), тем же приёмом, каким
пользуется `tests/test_doctor.py` (`claude_only_run`). Реальный `claude
--version` в тестах не зовётся: CI может не иметь установленного CLI
вовсе, а тест обязан быть детерминированным.

Песочница (`TmpRootTest`) — временный git-репозиторий с одним коммитом,
пути `config.ROOT/DB/TARGETS` подменены на него: AC-6 («не меняет ни
конфиг, ни БД, ни git») проверяется по-настоящему — снимком файлового
дерева и состоянием git до/после запуска команды, а не по имени вызванной
функции. Реальный репозиторий пульта командой не трогается ни в одном
тесте этого файла.

Пометка о расхождении версий (AC-5) — конкретный текст SPEC не называет,
это выбор разработчика, поэтому тест не подгадывает слова: пин и
«фактическая» версия в обеих ветках (совпадение/расхождение) — строки
РАВНОЙ длины, так что любая пометка, добавленная только при расхождении,
обязана дать более длинный вывод — поведение проверяется без завязки на
дословную формулировку.

AC-4 (версия схемы) вырезает из вывода уже проверенный AC-2 пин CLI перед
поиском — иначе поиск отдельной цифры схемы (`2`) тривиально совпал бы с
цифрой внутри самого пина (`2.1.227`) и прошёл бы независимо от того,
печатает ли команда версию схемы вообще.
"""
import hashlib
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artel, config, doctor  # noqa: E402
from scripts import guard  # noqa: E402


def claude_version_run(stdout: str):
    """Заглушка `subprocess.run` внутри `doctor.cli_version()`: отвечает
    заданной строкой `claude --version` независимо от переданных args —
    в песочнице другие subprocess-вызовы через `doctor.subprocess.run`
    команде `version` не нужны (в отличие от `doctor`, у неё нет живого
    смоука и recovery-сверки)."""
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout, "")
    return run


class TmpRootTest(unittest.TestCase):
    """Изолированный git-репозиторий: `version` читает config/doctor/guard,
    но не должна ничего писать (AC-6) — это проверяется по-настоящему, не
    в рабочем дереве пульта."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "targets.yaml").write_text("targets: {}\n", encoding="utf-8")
        self._git("init", "-q")
        self._git("add", "-A")
        self._git("-c", "user.email=t@t.invalid", "-c", "user.name=t",
                  "commit", "-q", "-m", "init")

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TARGETS", self.root / "targets.yaml")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        run_patcher = mock.patch.object(
            doctor.subprocess, "run",
            side_effect=claude_version_run(
                f"{config.CLI_VERSION_PIN} (Claude Code)\n"))
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

    # -------------------------------------------------------------- git

    def _git(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.root,
                              capture_output=True, text=True, check=True)

    def head_sha(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.strip()

    def porcelain_status(self) -> str:
        return self._git("status", "--porcelain").stdout

    def file_snapshot(self) -> dict:
        snap = {}
        for p in self.root.rglob("*"):
            if p.is_file() and ".git" not in p.relative_to(self.root).parts:
                snap[str(p.relative_to(self.root))] = hashlib.sha256(
                    p.read_bytes()).hexdigest()
        return snap

    # -------------------------------------------------------------- CLI

    def run_cli(self, *argv) -> str:
        """Прогон `artel.main()` через `sys.argv`; неизвестная команда
        падает `SystemExit` — ловим и запоминаем в `self.systemexit`,
        а не даём тесту рухнуть трейсбеком мимо содержательного assert."""
        buf = io.StringIO()
        self.systemexit = None
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            with redirect_stdout(buf):
                try:
                    artel.main()
                except SystemExit as exc:
                    self.systemexit = exc
        return buf.getvalue()


class VersionCommandTest(TmpRootTest):

    def test_ac1_version_is_a_valid_cli_command(self):
        out = self.run_cli("version")

        self.assertIsNone(
            self.systemexit,
            f"artel.py version отвергнута как неизвестная подкоманда: "
            f"{self.systemexit}")
        self.assertTrue(out.strip(), "artel.py version ничего не печатает")

    def test_ac2_output_includes_cli_pin_from_config(self):
        out = self.run_cli("version")

        self.assertIn(config.CLI_VERSION_PIN, out)

    def test_ac3_output_includes_actual_installed_cli_version(self):
        with mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_version_run("9.9.9 (Claude Code)\n")):
            out = self.run_cli("version")

        self.assertIn("9.9.9", out)

    def test_ac4_output_includes_artifact_schema_version(self):
        out = self.run_cli("version")
        # AC-2 уже покрывает пин отдельно — вырезаем его, чтобы поиск
        # цифры версии схемы не совпал с цифрой внутри пина.
        remainder = out.replace(config.CLI_VERSION_PIN, "")

        self.assertIn(str(guard.SUPPORTED_SCHEMA_VERSION), remainder)

    def test_ac5_mismatch_note_present_only_when_versions_diverge(self):
        pin = config.CLI_VERSION_PIN
        same_len_diff = pin[:-1] + ("1" if pin[-1] != "1" else "2")

        with mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_version_run(f"{pin} (Claude Code)\n")):
            matched = self.run_cli("version")

        with mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_version_run(
                    f"{same_len_diff} (Claude Code)\n")):
            diverged = self.run_cli("version")

        self.assertGreater(
            len(diverged), len(matched),
            "вывод при расхождении версий не длиннее вывода при "
            "совпадении — похоже, явная текстовая пометка о расхождении "
            "(AC-5) отсутствует")


class VersionNoSideEffectsTest(TmpRootTest):
    """AC-6, обе ветки из AC-5 (совпадение / расхождение версий)."""

    def assert_no_side_effects(self, installed: str):
        before_sha = self.head_sha()
        before_status = self.porcelain_status()
        before_files = self.file_snapshot()

        with mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_version_run(f"{installed} (Claude Code)\n")):
            self.run_cli("version")

        self.assertEqual(before_sha, self.head_sha(),
                         "artel.py version изменил HEAD git-репозитория")
        self.assertEqual(before_status, self.porcelain_status(),
                         "artel.py version изменил рабочее дерево git")
        self.assertEqual(before_files, self.file_snapshot(),
                         "artel.py version записал/изменил файл на диске "
                         "(конфиг или БД)")

    def test_ac6_no_side_effects_when_versions_match(self):
        self.assert_no_side_effects(config.CLI_VERSION_PIN)

    def test_ac6_no_side_effects_when_versions_diverge(self):
        pin = config.CLI_VERSION_PIN
        self.assert_no_side_effects(pin[:-1] + ("1" if pin[-1] != "1" else "2"))


class VersionHelpVisibilityTest(TmpRootTest):

    def test_ac7_version_listed_in_help_via_dash_dash_help_and_dash_h(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                out = self.run_cli(flag)
                self.assertIn(
                    "version", out,
                    f"artel.py {flag} не упоминает команду version в "
                    f"общей справке")


if __name__ == "__main__":
    unittest.main()
