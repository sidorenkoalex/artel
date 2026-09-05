"""Приёмочный тест 01M1RFQ52S0VD22J628TXX96XS — AC-17: существующие
тесты остаются зелёными.

AC-17 называет ровно четыре модуля (`tests/test_brief.py`, `tests/
test_codebase_map.py`, `tests/test_fsm_map_regen.py`, `tests/
test_fsm_map_conflict_autoresolve.py`) — не «весь набор tests/» (тот
гоняет CI, скилу test_author прогонять его при написании планки
запрещено). Тест запускает именно эти четыре модуля отдельным
процессом `python3 -m unittest` — так же, как их запустил бы
разработчик или CI-джоба, без импорта в текущий процесс (эти файлы
патчят глобальные атрибуты `orchestrator.config`/`subprocess.run`
пачками тестовых классов — совместный импорт с файлами этого каталога
в одном процессе рисковал бы утечкой одной подмены в другую).

Красен до реализации: см. по существу не должен быть красным —
AC-17 требует эти тесты зелёными УЖЕ СЕЙЧАС, до правки `orchestrator/
brief.py`/`scripts/codebase_map.py` этой задачи (регрессия проверяется
против исходного состояния кода, которое эта планка не меняет). Если
тест красный на неизменённом коде — это баг тестовой обвязки этого
файла (например, неверный `cwd`), а не ожидаемая краснота «до
реализации»; см. докстринг класса ниже.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

AC17_MODULES = (
    "tests.test_brief",
    "tests.test_codebase_map",
    "tests.test_fsm_map_regen",
    "tests.test_fsm_map_conflict_autoresolve",
)


class ExistingSuiteStaysGreenTest(unittest.TestCase):
    """Зелёный с рождения: на неизменённом коде (до правки developer)
    эти четыре модуля уже проходят сегодня — эта планка запрещает их
    сломать при подключении `project_for_brief`, а не проверяет
    отсутствующую пока реализацию задачи."""

    def test_ac17_named_existing_test_modules_pass(self):
        """Прогоняет ровно четыре модуля, названных AC-17, как один
        `unittest`-прогон в отдельном процессе, и требует нулевой код
        возврата.

        Ловит мутацию: подключение `project_for_brief` к
        `developer_brief`/`analyst_map_component` меняет форму
        компонента карты так, что существующий ассерт одного из этих
        файлов (например, `DeveloperBriefTest.
        test_assembles_three_components_and_journals_their_hashes` в
        `tests/test_brief.py`, ожидающий `MAP_FRESH` буквально в
        тексте брифа) перестаёт выполняться — прогон вернёт ненулевой
        код и печатное имя упавшего теста в stderr.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *AC17_MODULES, "-v"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)

        self.assertEqual(
            result.returncode, 0,
            "один или несколько из четырёх тестов AC-17 красные:\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
