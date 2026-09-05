"""Приёмочные тесты AC-3 задачи 01M1RDCCKBQMJ5G2K9ANJP059H.

Красен до реализации: `scripts/stack_ci.py` ещё не существует — эта
часть зависит от `orchestrator/stack.py` части 1 («манифест стека»,
SPEC, раздел «Контекст»), которая мержится в main только после этой
планки; сам `scripts/stack_ci.py` тоже пишется только после того
мержа. До тех пор запуск падает на отсутствующем пути скрипта, а не по
какой-то другой причине.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STACK_CI = ROOT / "scripts" / "stack_ci.py"

_SETUP_PYTHON_VERSION_RE = re.compile(r"^\d+(\.\d+){0,2}$")


class Ac3StackCiScriptTest(unittest.TestCase):
    """AC-3: `scripts/stack_ci.py` существует, выполняется без ошибок и
    печатает версию Python в формате, принимаемом `actions/setup-python`
    в качестве `python-version`."""

    def test_ac3_script_exits_zero_and_prints_setup_python_compatible_version(self):
        """Запускает `scripts/stack_ci.py` отдельным процессом — так же,
        как его будет запускать шаг CI-джоба, — и проверяет код возврата
        и формат вывода.

        Ловит мутацию: если скрипт печатает версию с посторонним текстом
        (например, `"Python: 3.11"` вместо `"3.11"`), несколькими
        строками, JSON-объектом или значением с суффиксом
        (`"3.11-final"`), либо завершается с ненулевым кодом —
        `actions/setup-python` не примет такое `python-version`, и этот
        тест покраснеет.
        """
        self.assertTrue(
            STACK_CI.exists(),
            f"{STACK_CI} должен существовать (AC-3)",
        )
        result = subprocess.run(
            [sys.executable, str(STACK_CI)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            "scripts/stack_ci.py должен выполняться без ошибок:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        lines = result.stdout.splitlines()
        self.assertEqual(
            len(lines), 1,
            f"вывод должен быть одной строкой с версией, получено: {result.stdout!r}",
        )
        version = lines[0].strip()
        self.assertRegex(
            version, _SETUP_PYTHON_VERSION_RE,
            "версия должна быть в формате, принимаемом actions/setup-python "
            "как python-version (например '3.11' или '3.11.2'), без "
            "постороннего текста",
        )


if __name__ == "__main__":
    unittest.main()
