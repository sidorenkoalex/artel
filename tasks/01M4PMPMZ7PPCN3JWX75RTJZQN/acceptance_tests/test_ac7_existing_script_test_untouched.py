"""AC-7, часть «`CiScriptRunsAsScriptTest` зелёный без правки» — факт этой
задачи: файл теста не тронут веткой, и сам тест зелен на коде ветки.
Поведенческая часть AC-7 (код 2 при пустом `BASE_SHA` в любой форме HEAD)
— в долгоживущем файле задачи в `tests/`.

Группа: разовый
Зелёный с рождения: до реализации ветка не трогает `tests/test_protected_test_settings.py`, а скрипт при пустом `BASE_SHA` уже даёт код 2 — тест держит, чтобы реализация этого не сломала.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, changed_paths  # noqa: E402

GUARDED = "tests/test_protected_test_settings.py"


class ExistingScriptTestUntouchedTest(unittest.TestCase):

    def test_ac7_ci_script_runs_as_script_test_green_without_edit(self):
        """Ветка задачи не правит `tests/test_protected_test_settings.py`, и
        его `CiScriptRunsAsScriptTest` проходит на коде ветки.

        Ловит мутацию: разработчик подгоняет ожидание старого теста под
        новый вывод скрипта (правка файла) — путь появляется в диффе
        задачи; либо новый скрипт при пустом `BASE_SHA` перестаёт давать
        код 2 или называть `BASE_SHA` — прогон теста красный.
        """
        self.assertNotIn(GUARDED, changed_paths())
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             f"{GUARDED}::CiScriptRunsAsScriptTest"],
            cwd=CODE_ROOT, capture_output=True, text=True, timeout=110)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
