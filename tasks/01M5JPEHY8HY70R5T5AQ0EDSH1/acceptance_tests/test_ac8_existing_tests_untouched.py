"""Существующие тесты очереди и замка зоны задачей не правятся.

Группа: разовый
Зелёный с рождения: ветка задачи до реализации не трогает ни `tests/test_zone_lock.py`, ни тест очереди зоны — тест держит этот факт до мержа.

AC-8: `tests/test_zone_lock.py` и тест очереди зоны (файл
`test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py` в `tests/`) не
входят в пути задачи (`changed_paths()` помощника пульта: закоммиченный
дифф от базы плюс неотслеживаемые файлы).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402

EXISTING = ("tests/test_zone_lock.py",
            "tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py")


class ExistingTestsUntouchedTest(unittest.TestCase):

    def test_ac8_existing_zone_tests_not_changed(self):
        """Пути задачи от базы ветки не содержат ни одного из двух существующих файлов тестов зоны.

        Сценарий: помощник пульта считает пути задачи правилом гейта зон;
        ни `tests/test_zone_lock.py`, ни тест очереди зоны среди них нет.

        Ловит мутацию: разработчик подогнал существующий тест под новый
        текст отказа (например, поправил `DEPENDENCY_TEXT` или ассерт
        «ради зависимости» в `tests/test_zone_lock.py`) — путь попадает в
        `changed_paths()`, и тест краснеет с его именем.
        """
        changed = set(changed_paths())
        for path in EXISTING:
            with self.subTest(path=path):
                self.assertNotIn(path, changed,
                                 f"задача правит существующий тест {path}")


if __name__ == "__main__":
    unittest.main()
