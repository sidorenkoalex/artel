"""Приёмочный тест 01M1SC40NT8T1WFKKKJ67CK96Z — AC-4: `tests/
test_auto_cycle.py` проходит без изменения ни одного существующего
утверждения.

Зелёный с рождения: `tests/test_auto_cycle.py` уже сегодня зелёный (это
единственный источник истины поведения цикла `auto` ДО рефакторинга) —
тест ниже не проверяет новую функциональность, а замыкает наблюдаемое
следствие требования 5 SPEC («существующие тесты зелёные без правки
утверждений»): раз ассерты этого файла буквально сверяют журнал/print
цикла (см. `AutoStopsWhereTheOperatorIsNeededTest` и соседние классы),
сохранение его зелёности «без правки утверждений» механически влечёт и
буквальную неизменность текстов (AC-3) для ВСЕГО, что этот файл
покрывает — более широкий прогон, чем три сценария AC-6.

Настоящий `unittest discover`, не разбор исходников: прогон внешним
`subprocess` — тот же приём, что и `tasks/T085/acceptance_tests/
test_ac6_t066_composition_updated.py` (общий узел «дискавер зелёный»),
единственный способ доказать «утверждения не потребовали правки» без
самого дифа под рукой на момент написания теста (диф появится только
после рефакторинга — сверку буквы правки видит ревьювер).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class ExistingAutoCycleSuiteStaysGreenTest(unittest.TestCase):

    def test_ac4_test_auto_cycle_suite_is_fully_green(self):
        """`python3 -m unittest tests/test_auto_cycle.py` завершается
        нулевым кодом и без FAILED/ERROR в выводе.

        Ловит мутацию: рефакторинг случайно поменял поведение (не только
        структуру) — любой из ~90 существующих тестов этого файла,
        сверяющих конкретные переходы/подсказки/стоп-краны буквально,
        покраснеет, и вывод внешнего прогона это отразит кодом возврата.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_auto_cycle", "-v"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)

        self.assertEqual(
            0, result.returncode,
            f"AC-4: tests/test_auto_cycle.py обязан остаться зелёным без "
            f"правки утверждений.\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}")
        self.assertNotIn("FAILED", result.stderr)
        self.assertNotIn("FAILED", result.stdout)


if __name__ == "__main__":
    unittest.main()
