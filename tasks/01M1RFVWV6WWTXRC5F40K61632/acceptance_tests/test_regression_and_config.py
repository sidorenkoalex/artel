"""Приёмочные тесты 01M1RFVWV6WWTXRC5F40K61632 — AC-17, AC-18.

Источник — только tasks/01M1RFVWV6WWTXRC5F40K61632/SPEC.md, раздел
«Критерии приёмки».

AC-17 называет ровно два модуля (`tests/test_fsm_map_regen.py`,
`tests/test_doctor.py`) — не «весь набор tests/» (тот гоняет CI, скилу
test_author запрещено прогонять его при написании планки). Тест
запускает именно эти два модуля отдельным процессом `python3 -m
unittest`, тем же приёмом, что уже применён соседней задачей по
codebase_map.py (01M1RFQ52S0VD22J628TXX96XS,
`test_existing_suite_regression.py`) — без импорта в текущий процесс,
чтобы патчи `config`/`subprocess.run` этого каталога не утекли туда и
обратно.

Зелёный с рождения: AC-17 требует эти тесты зелёными УЖЕ СЕЙЧАС, на
неизменённом коде (до правки developer) — эта планка запрещает их
сломать подключением `map_stats`/`check_map_growth`/записи «карта:
размер», а не проверяет отсутствующую пока реализацию задачи.

Красен до реализации: AC-18 (`ConfigConstantsDeclaredTest`) — три
константы ещё не объявлены в `orchestrator/config.py`, `hasattr`
возвращает `False` в каждом тесте класса, пока разработчик их не
добавит (требование 3 SPEC).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

AC17_MODULES = (
    "tests.test_fsm_map_regen",
    "tests.test_doctor",
)


class ExistingSuiteStaysGreenTest(unittest.TestCase):

    def test_ac17_named_existing_test_modules_pass(self):
        """Прогоняет ровно два модуля, названных AC-17, одним
        `unittest`-прогоном в отдельном процессе, требует нулевой код
        возврата.

        Ловит мутацию: подключение `check_map_growth` к `all_checks`
        меняет форму/число печатаемых проверок так, что существующий
        ассерт `tests/test_doctor.py`
        (`DoctorCommandTest.test_broken_repo_output_names_the_reasons`
        и подобные, сверяющие имена/число `Check`) перестаёт
        выполняться — прогон вернёт ненулевой код и печатное имя
        упавшего теста в stderr.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *AC17_MODULES, "-v"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)

        self.assertEqual(
            result.returncode, 0,
            "один или оба теста AC-17 красные:\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}")


class ConfigConstantsDeclaredTest(unittest.TestCase):
    """AC-18: `MAP_GROWTH_CALIBRATION_MERGES`, `MAP_GROWTH_RATIO`,
    `MAP_JUMP_RATIO` объявлены в `orchestrator/config.py`."""

    def test_ac18_calibration_merges_is_a_positive_integer(self):
        """`MAP_GROWTH_CALIBRATION_MERGES` — положительное целое (число
        измерений окна калибровки, не доля/байты).

        Ловит мутацию: константа объявлена как строка/float, или
        неположительная (например, 0 — окно калибровки, требующее
        нулевых измерений, лишено смысла).
        """
        self.assertTrue(hasattr(config, "MAP_GROWTH_CALIBRATION_MERGES"),
                        "config.MAP_GROWTH_CALIBRATION_MERGES не объявлена")
        value = config.MAP_GROWTH_CALIBRATION_MERGES
        self.assertIsInstance(value, int)
        self.assertGreater(value, 0)

    def test_ac18_growth_and_jump_ratio_are_fractions_between_zero_and_one(self):
        """`MAP_GROWTH_RATIO`/`MAP_JUMP_RATIO` — доли (0, 1) — не
        проценты (25 вместо 0.25) и не нулевые/отрицательные.

        Ловит мутацию: константа задана в процентах целым числом
        (`25` вместо `0.25`) — сравнение `bytes_total > median*(1+25)`
        в реализации сделало бы алерт практически недостижимым, эта
        проверка ловит именно диапазон значения, не сам расчёт.
        """
        for name in ("MAP_GROWTH_RATIO", "MAP_JUMP_RATIO"):
            self.assertTrue(hasattr(config, name), f"config.{name} не объявлена")
            value = getattr(config, name)
            self.assertIsInstance(value, float, f"config.{name} — не float")
            self.assertGreater(value, 0.0, f"config.{name} — не положительная доля")
            self.assertLess(value, 1.0, f"config.{name} — не доля (>=1)")


if __name__ == "__main__":
    unittest.main()
