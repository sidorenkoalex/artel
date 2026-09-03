"""Приёмочный тест AC-4 (tasks/01M1KCJGN61QT1M0PZKGMVA86Y/SPEC.md):
полный прогон `tests/` зелёный.

Тяжёлый тест (гоняет весь `tests/` — свыше тысячи тестов — отдельным
подпроцессом, порядка двух минут): осознанно, буквальное прочтение
критерия «Полный прогон тестового набора `tests/`», тот же приём, что
`tasks/T090/acceptance_tests/test_no_unclosed_connections.py` и
`tasks/T056/acceptance_tests/test_ac3_invariant_locked_in_test_suite.py`.

Зелёный с рождения: эмпирически перепроверено перед записью этого
файла — полный прогон `tests/` уже сегодня (ДО реализации задачи)
завершается с кодом возврата 0 («OK», 1307 тестов, ~136с): 76
исключений `_AutoClosingConnection.__del__` печатаются в `__del__` при
уничтожении объекта интерпретатором (`Exception ignored in …») в
stderr, НО это не приводит unittest к падению — печать в stderr в
момент финализации объекта не считается ошибкой теста. AC-2 отдельно
и целенаправленно проверяет именно отсутствие этой печати в
контролируемом кросс-поточном сценарии; этот тест здесь — тревожный
трос по буквальной формулировке AC-4 («зелёный»), а не по шуму в
stderr: он покраснеет, если реализация AC-1/AC-2 случайно СЛОМАЕТ
какой-то другой тест (например, перехватом более широким классом
исключений, который скрывает не относящуюся к делу ошибку в другом
месте, или изменением поведения `close()`, задевающим WAL/row_factory
инварианты `tests/test_store_db_connection_close.py::
test_row_factory_and_wal_unchanged`), а не потому что сегодня он
падает.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


class FullSuiteGreenTest(unittest.TestCase):

    def test_ac4_full_test_suite_run_is_green(self):
        """Полный прогон `python3 -m unittest discover -s tests` завершается
        успешно (код возврата 0, `OK` в выводе).

        Ловит мутацию: правка `_AutoClosingConnection.__del__`
        (AC-1/AC-2), которая ломает какой-либо другой тест набора —
        например, перехват, задевающий не только сценарий закрытия
        соединения (случайно расширенный `except`, замена `close()`
        на что-то, ломающее повторный вызов при `test_explicit_close_
        then_gc_does_not_raise`) — тогда прогон вернёт ненулевой код,
        и `assertEqual` ниже упадёт.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=REPO_ROOT, timeout=280, capture_output=True, text=True,
            encoding="utf-8")

        combined = result.stdout + result.stderr

        ran_match = re.search(r"^Ran (\d+) tests?", combined, re.M)
        self.assertTrue(
            ran_match and int(ran_match.group(1)) > 0,
            "прогон `tests/` не выполнил ни одного теста (сломан вызов "
            f"discover, а не предмет AC-4):\n{combined[-4000:]}")

        self.assertEqual(
            result.returncode, 0,
            f"полный прогон `tests/` не зелёный (код возврата "
            f"{result.returncode}):\n{combined[-4000:]}")


if __name__ == "__main__":
    unittest.main()
