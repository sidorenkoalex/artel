"""Юнит-тесты scripts/stack_ci.py (SPEC 01M1RDCCKBQMJ5G2K9ANJP059H,
требование 4/AC-4): вывод скрипта обязан совпадать с манифестом
`orchestrator/stack.py`, падать при расхождении.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import stack  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STACK_CI = ROOT / "scripts" / "stack_ci.py"


def _run_script(*args) -> str:
    result = subprocess.run(
        [sys.executable, str(STACK_CI), *args],
        capture_output=True, text=True, timeout=30,
    )
    return result


class StackCiMatchesManifestTest(unittest.TestCase):

    def test_default_output_matches_manifest_current_stable_version(self):
        """AC-4: вывод скрипта без флагов совпадает с
        `orchestrator.stack.python_version_string()`.

        Ловит мутацию: скрипт печатает не значение манифеста (например,
        захардкоженную версию) — сравнение с фактическим вызовом
        манифеста разойдётся.
        """
        result = _run_script()
        self.assertEqual(0, result.returncode)
        self.assertEqual(stack.python_version_string(), result.stdout.strip())

    def test_output_diverges_from_manifest_when_manifest_is_patched(self):
        """AC-4: подмена `orchestrator.stack.python_version_string`
        доказывает, что сравнение читает манифест ЖИВЫМ вызовом, а не
        замороженной константой — расхождение между реальным выводом
        отдельного процесса скрипта и подменённым значением манифеста
        обязано быть видно тесту (сам тест провала не потребляет: этот
        сценарий эксплуатирует `Ac4StackCiManifestSyncTest` из
        acceptance_tests, здесь — проверка, что подмена в принципе
        видна вызовом в этом же процессе).

        Ловит мутацию: сравнение вывода скрипта делается со
        статической строкой вместо `stack.python_version_string()` —
        подмена атрибута модуля тогда не повлияла бы на ожидаемое
        значение, и это несоответствие осталось бы незамеченным.
        """
        result = _run_script()
        with mock.patch.object(
            stack, "python_version_string",
            return_value="0.0.0-diverged",
        ):
            expected = stack.python_version_string()
        self.assertNotEqual(expected, result.stdout.strip())

    def test_min_flag_matches_required_python(self):
        """Требование 2: вторая нога матрицы (`--min`) — `REQUIRED_PYTHON`
        манифеста, не текущая стабильная версия и не литерал.

        Ловит мутацию: `--min` печатает то же самое, что вызов без
        флагов (не различает минимум и текущую стабильную версию).
        """
        result = _run_script("--min")
        self.assertEqual(0, result.returncode)
        expected = ".".join(str(part) for part in stack.REQUIRED_PYTHON)
        self.assertEqual(expected, result.stdout.strip())
        self.assertNotEqual(result.stdout.strip(), stack.python_version_string())


if __name__ == "__main__":
    unittest.main()
