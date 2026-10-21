"""Тест подсказок шаблона `long_lived` задачи 01M5AA5TS90RDJ2AFXB882WTPD не тронут веткой задачи и проходит.

Группа: разовый
Зелёный с рождения: файл `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py` на базе ветки не изменён и проходит; тест держит этот факт до мержа — правка или поломка файла веткой задачи его покраснит.

Пути задачи — `changed_paths()` помощника пульта (`_pult.py`: дифф от
базы ветки плюс неотслеживаемые файлы); прогон — тем же pytest из корня
рабочей копии кода (`CODE_ROOT`) по относительному пути файла.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

HINTS = "tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py"


class Ac2TemplateHintsTest(unittest.TestCase):

    def test_ac2_template_hints_file_untouched_and_green(self):
        """Файл тестов подсказок шаблона не входит в пути задачи и его прогон pytest зелёный.

        Сценарий: среди путей задачи (`changed_paths()`) нет
        `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`; прогон
        этого файла pytest из корня рабочей копии кода завершается кодом 0.

        Ловит мутацию: разработчик подогнал `assertIn` прежних пунктов 2а/5
        под новый текст задания — файл в пути задачи; новое задание сломало
        прежние пункты 2а/5 у проекта с шаблоном — прогон красный.
        """
        self.assertNotIn(HINTS, changed_paths())
        run = subprocess.run(
            [sys.executable, "-m", "pytest", HINTS, "-q", "-p",
             "no:cacheprovider"],
            cwd=CODE_ROOT, capture_output=True, text=True, timeout=110)
        self.assertEqual(run.returncode, 0,
                         f"{run.stdout[-3000:]}\n{run.stderr[-2000:]}")


if __name__ == "__main__":
    unittest.main()
