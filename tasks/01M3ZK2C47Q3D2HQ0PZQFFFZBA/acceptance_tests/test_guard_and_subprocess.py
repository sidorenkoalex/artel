"""Сторож и регрессия ожидания дочернего процесса.

Группа: разовый
Красен до реализации: фикстура теста runner ещё подменяет общий
time.sleep и записывает паузы ожидания дочернего процесса.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from tests import test_agent_failure  # noqa: E402


class SleepIsolationTest(unittest.TestCase):
    """Регрессия изолированной записи пауз и чувствительности сторожа."""

    def test_ac3_guard_rejects_new_global_patch_and_justifies_exception(self):
        """На временной копии тестов новый глобальный патч красит сторож.

        Сценарий сначала допускает обоснованное исключение invariants,
        затем добавляет такой же патч в обычный тест и требует отказа,
        названного именно глобальной подменой.

        Ловит мутацию: сторож перестал сканировать новые тестовые файлы —
        прогон с test_unsafe.py остался зелёным.
        """
        guard = config.ROOT / "tests" / (
            "test_01m3zk2c47q3d2hq0pzqfffzba_sleep_guard.py")
        source = guard.read_text(encoding="utf-8")
        self.assertIn("Ловит мутацию: подмена time.sleep всего процесса в тесте",
                      source)
        self.assertIn('"test_invariants.py"', source)
        with tempfile.TemporaryDirectory() as temp:
            tests = Path(temp) / "tests"
            tests.mkdir()
            (tests / guard.name).write_text(source, encoding="utf-8")
            (tests / "test_invariants.py").write_text(
                'from unittest import mock\n'
                'def test_clock():\n'
                '    with mock.patch("time.sleep"):\n'
                '        pass\n', encoding="utf-8")
            unsafe = tests / "test_unsafe.py"
            unsafe.write_text("def test_safe():\n    assert True\n", encoding="utf-8")
            command = [sys.executable, "-m", "pytest", str(tests / guard.name),
                       "-q", "-p", "no:cacheprovider", "-p", "timeout",
                       "-o", "timeout=20"]
            clean = subprocess.run(command, capture_output=True, text=True,
                                   timeout=30)
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
            unsafe.write_text('from unittest import mock\n'
                              'def test_unsafe():\n'
                              '    with mock.patch("time.sleep"):\n'
                              '        pass\n', encoding="utf-8")
            mutated = subprocess.run(command, capture_output=True, text=True,
                                     timeout=30)
            self.assertNotEqual(mutated.returncode, 0)
            self.assertIn("test_unsafe.py", mutated.stdout + mutated.stderr)
            self.assertIn("глобальная подмена time.sleep",
                          mutated.stdout + mutated.stderr)

    def test_ac4_subprocess_wait_is_not_recorded_as_runner_pause(self):
        """Ожидание живого процесса не попадает в паузы шага runner.

        Существующая фикстура шага записывает паузы runner. Внутри неё
        subprocess ждёт настоящий дочерний процесс; в записях пауз
        тестируемого шага должно остаться пусто.

        Ловит мутацию: в фикстуре вновь патчат runner.time.sleep вместо
        runner._pause — паузы опроса Popen добавляются в список пауз шага.
        """
        case = test_agent_failure.CmdRunFailureTest(
            "test_missing_cli_is_not_retried")
        try:
            case.setUp()
            subprocess.run([sys.executable, "-c",
                            "import time; time.sleep(0.08)"],
                           check=True, timeout=10)
            self.assertEqual(len(case.pauses), 0,
                             f"ожидание дочернего процесса записало "
                             f"{len(case.pauses)} чужих пауз")
        finally:
            case.doCleanups()


if __name__ == "__main__":
    unittest.main()
