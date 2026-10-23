"""Существующие тесты разбора `--yes` диспетчером `kill` задачей не правятся.

Группа: разовый
Зелёный с рождения: ветка задачи до реализации не трогает `tests/test_kill_live_cycle_refusal.py` — тест держит этот факт до мержа.

AC-16 (вторая половина): `KillDispatchYesFlagTest` в
`tests/test_kill_live_cycle_refusal.py` зелёные без правок — файл не входит
в пути задачи (`changed_paths()` помощника пульта: закоммиченный дифф от
базы плюс неотслеживаемые файлы). Зелёность самих тестов и поведение
диспетчера держит долгоживущий файл задачи в `tests/`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402

EXISTING = "tests/test_kill_live_cycle_refusal.py"


class ExistingDispatchTestsUntouchedTest(unittest.TestCase):

    def test_ac16_existing_dispatch_tests_not_changed(self):
        """Пути задачи от базы ветки не содержат файла существующих тестов диспетчера `kill`.

        Сценарий: помощник пульта считает пути задачи правилом гейта зон;
        `tests/test_kill_live_cycle_refusal.py` среди них нет.

        Ловит мутацию: разработчик передаёт `reason=None` всегда и
        подгоняет ассерты `assert_called_once_with(self.TASK, confirmed=…)`
        в `KillDispatchYesFlagTest` под новый вызов — путь попадает в
        `changed_paths()`, тест краснеет с его именем.
        """
        self.assertNotIn(EXISTING, set(changed_paths()),
                         f"задача правит существующий тест {EXISTING}")


if __name__ == "__main__":
    unittest.main()
