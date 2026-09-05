"""Приёмочные тесты AC-4 задачи 01M1RDCCKBQMJ5G2K9ANJP059H.

Красен до реализации: `tests/test_stack_ci.py` и его зависимости
(`orchestrator/stack.py` части 1, `scripts/stack_ci.py` этой части) ещё
не существуют — импорт/запуск ниже падает до их появления, а не по
какой-то другой причине.
"""
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Ac4StackCiManifestSyncTest(unittest.TestCase):
    """AC-4: `tests/test_stack_ci.py` содержит тест, сравнивающий вывод
    `scripts/stack_ci.py` с версией из `orchestrator/stack.py`, и падает
    при их расхождении."""

    def test_ac4_dedicated_test_passes_when_manifest_and_script_agree(self):
        """Запускает `tests/test_stack_ci.py` отдельным процессом — так
        же, как его будет гонять CI-джоб `python` (требование 4 SPEC).

        Ловит мутацию: если файл `tests/test_stack_ci.py` не создан
        вообще, либо создан, но при согласованном на деле манифесте и
        скрипте всё равно падает или содержит только пропущенные тесты.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_stack_ci", "-v"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(
            result.returncode, 0,
            "tests/test_stack_ci.py должен быть зелёным при согласованных "
            f"манифесте и скрипте:\nSTDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}",
        )

    def test_ac4_dedicated_test_fails_when_manifest_diverges_from_script(self):
        """Подменяет `orchestrator.stack.python_version_string` на
        заведомо другое значение и прогоняет тесты `tests/test_stack_ci.py`
        в этом же процессе — они обязаны упасть, раз манифест разошёлся с
        фактическим выводом `scripts/stack_ci.py` (отдельный процесс
        скрипта подмену не видит и печатает настоящую версию, требование
        1 SPEC прямо задаёт идиому доступа `from orchestrator import
        stack; stack.python_version_string()` — подмена атрибута модуля
        `stack` перехватывает именно её).

        Ловит мутацию: если `tests/test_stack_ci.py` на деле не сравнивает
        вывод скрипта с `orchestrator.stack.python_version_string()`
        (например, пишет `assertTrue(True)` или сравнивает скрипт сам с
        собой) — расхождение манифеста и вывода отсюда его не завалит,
        хотя AC-4 прямо требует падения «при расхождении».
        """
        import orchestrator.stack as stack
        import tests.test_stack_ci as stack_ci_test_mod

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(stack_ci_test_mod)
        with mock.patch.object(
            stack, "python_version_string",
            return_value="0.0.0-ac4-mutation-marker",
        ):
            result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertFalse(
            result.wasSuccessful(),
            "tests/test_stack_ci.py обязан упасть при расхождении "
            "манифеста orchestrator.stack с фактическим выводом "
            "scripts/stack_ci.py (AC-4)",
        )


if __name__ == "__main__":
    unittest.main()
