"""AC-14 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md, требование 6): строки
вывода `artel.py version`, существовавшие до этой задачи, остаются
байт-в-байт; существующие `tests/test_version.py` проходят без правок.

Зелёный с рождения: сегодняшний `orchestrator/version.py::cmd_version`
уже печатает эти три строки, а `tests/test_version.py` уже зелён —
тест фиксирует БАЗОВУЮ ЛИНИЮ регрессии до всякой правки кода задачи;
после неё разработчик обязан не тронуть ни одну из проверенных здесь строк.
"""
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import version  # noqa: E402


class VersionOutputExistingLinesTest(unittest.TestCase):

    def test_ac14_existing_output_lines_and_existing_tests_are_untouched(self):
        """Требование 6/AC-14: три существующие строки вывода `version`
        не изменены, `tests/test_version.py` (существующий набор)
        проходит без правок.

        Ловит мутацию: разработчик переписал/убрал одну из трёх
        существующих строк вместо того, чтобы только ДОБАВИТЬ новые
        (`assertIn` по каждому префиксу откажет), либо изменение сломало
        существующие юниты `tests/test_version.py` (ненулевой код
        возврата подпроцесса).
        """
        buf = StringIO()
        with redirect_stdout(buf):
            version.cmd_version()
        out = buf.getvalue()

        for prefix in ("CLI (пин из конфига):", "CLI (установлена):",
                      "Схема артефактов:"):
            self.assertIn(
                prefix, out,
                f"строка вывода version, существовавшая до этой задачи, "
                f"пропала или изменилась: {prefix!r}")

        result = subprocess.run(
            ["python3", "-m", "unittest", "tests.test_version", "-v"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(
            0, result.returncode,
            f"tests/test_version.py красный:\n{result.stdout[-2000:]}\n"
            f"{result.stderr[-2000:]}")


if __name__ == "__main__":
    unittest.main()
