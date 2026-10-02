"""Регрессия нестабильного `tests/test_agent_failure.py::CmdRunFailureTest::
test_missing_cli_is_not_retried` (SPEC 01M3YS928033B1QF89VN2N5KC3).

Причина: предполётная сверка модели шага (`providers/claude.py::
model_verdict` -> `stack.installed_cli_version`) и fingerprint окружения
в журнале старта попытки (`agent_log.environment_fingerprint`, кэш на
процесс — платит первый шаг процесса) звали настоящий `claude --version`
машины прогона. `subprocess.run(timeout=…)` после
чтения вывода ждёт выхода процесса циклом `time.sleep`, а тест подменяет
`runner.time.sleep` — то есть `time.sleep` всего процесса — сбором пауз
бэкоффа. CLI, закрывший вывод чуть раньше выхода (живой `claude` под
нагрузкой соседних сессий), дописывал в `self.pauses` паузы чужого
ожидания, и падало `assertEqual(self.pauses, [])`.

Здесь тот же тест прогоняется с подставным `claude` первым в PATH: исход
не должен зависеть от того, какой CLI стоит на машине и как он отвечает.
Подставной CLI — shell-скрипт, поэтому файл только для POSIX (macOS,
Linux), как и весь пульт.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import agent_log  # noqa: E402
from tests import test_agent_failure  # noqa: E402

# Печатает правдоподобную версию, закрывает вывод и выходит через секунду —
# окно, в котором `subprocess.run` уже дочитал вывод и ждёт выхода.
SLOW_EXIT = ('echo "2.1.283 (Claude Code)"\n'
             "exec >&- 2>&-\n"
             "sleep 1\n")
BELOW_MINIMUM = 'echo "0.9.0 (Claude Code)"\n'
REFUSAL = "echo 'claude: отказ' >&2\nexit 1\n"
UNRECOGNIZED = "echo 'нет версии'\n"


class CliIsolationTest(unittest.TestCase):
    """`test_missing_cli_is_not_retried` при разных `claude` в PATH."""

    def path_with_claude(self, script: str | None) -> str:
        """PATH прогона: каталог с подставным `claude` первым; `None` —
        `claude` нет нигде (каталоги, где он есть, из PATH убраны)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dirs = os.environ.get("PATH", "").split(os.pathsep)
        if script is None:
            # `shutil.which` подменён песочницей тестов — проверка руками.
            return os.pathsep.join(
                d for d in dirs
                if not os.access(os.path.join(d, "claude"), os.X_OK))
        fake = Path(tmp.name) / "claude"
        fake.write_text("#!/bin/sh\n" + script, encoding="utf-8")
        fake.chmod(0o755)
        return os.pathsep.join([tmp.name, *dirs])

    def run_flaky_test(self, script: str | None) -> unittest.TestResult:
        case = test_agent_failure.CmdRunFailureTest(
            "test_missing_cli_is_not_retried")
        result = unittest.TestResult()
        # Кэш fingerprint сброшен: иначе от порядка набора зависело бы,
        # дойдёт ли этот прогон до `claude --version` в нём вообще.
        with mock.patch.dict(os.environ,
                             {"PATH": self.path_with_claude(script)}), \
                mock.patch.object(agent_log, "_environment_fingerprint_cache",
                                  None):
            case.run(result)
        return result

    def assert_passes(self, result: unittest.TestResult) -> None:
        problems = [text for _, text in result.failures + result.errors]
        self.assertEqual(problems, [])
        self.assertEqual(result.testsRun, 1)

    def test_cli_exit_lag_does_not_leak_into_backoff_pauses(self):
        """CLI, который закрыл вывод раньше выхода, не дописывает паузы
        ожидания своего выхода в паузы бэкоффа шага.

        Ловит мутацию: убрать из `CmdRunFailureTest.setUp` любую из двух
        подмен — `stack.installed_cli_version` или `agent_log.
        environment_fingerprint` — `claude --version` снова пойдёт в
        подставной CLI, его ожидание наполнит `self.pauses`, и тест
        покраснеет на `assertEqual(self.pauses, [])`.
        """
        self.assert_passes(self.run_flaky_test(SLOW_EXIT))

    def test_outcome_does_not_depend_on_cli_in_path(self):
        """Исход одинаков, когда `claude` в PATH нет, когда он отказывает,
        когда версия не распознаётся и когда она ниже минимума модели.

        Ловит мутацию: убрать подмену `stack.installed_cli_version` из
        `CmdRunFailureTest.setUp` — вариант «версия ниже минимума» уведёт
        шаг в отказ предполётной сверки до `spawn_agent`, и подтест
        покраснеет.
        """
        variants = {"нет в PATH": None, "отказ": REFUSAL,
                    "версия не распознана": UNRECOGNIZED,
                    "версия ниже минимума": BELOW_MINIMUM}
        for name, script in variants.items():
            with self.subTest(claude=name):
                self.assert_passes(self.run_flaky_test(script))


if __name__ == "__main__":
    unittest.main()
